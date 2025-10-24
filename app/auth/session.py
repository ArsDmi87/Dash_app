from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Request, request
from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession, sessionmaker

from app.core.settings import Settings, get_settings
from app.db.models import UserSession
from app.db.session import get_auth_session_factory


_MISSING = object()


class DatabaseSession(CallbackDict[str, Any], SessionMixin):
    """Session object that tracks modifications for server-side storage."""

    def __init__(self, initial: Dict[str, Any] | None = None, sid: str | None = None, new: bool = True) -> None:
        def on_update(_: CallbackDict) -> None:
            self.modified = True

        super().__init__(initial or {}, on_update)
        self.sid = sid or self._generate_sid()
        self.new = new
        self.permanent = True
        self.modified = False

    @staticmethod
    def _generate_sid() -> str:
        return uuid.uuid4().hex

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        return super().get(key, default)

    def pop(self, key: str, default: Any = _MISSING) -> Any:  # type: ignore[override]
        if default is _MISSING:
            return super().pop(key)
        return super().pop(key, default)


class DatabaseSessionInterface(SessionInterface):
    """Session interface that persists session state in PostgreSQL."""

    session_class = DatabaseSession

    def __init__(
        self,
        session_factory: sessionmaker[SASession] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or get_auth_session_factory(self.settings)
        self.cookie_name = self.settings.session_cookie_name
        self.lifetime = self.settings.session_lifetime

    def _create_session(self, initial: Dict[str, Any] | None = None, sid: str | None = None, new: bool = True) -> DatabaseSession:
        return self.session_class(initial=initial, sid=sid, new=new)

    def open_session(self, app, request: Request) -> DatabaseSession:
        sid = request.cookies.get(self.cookie_name)
        if not sid:
            return self._create_session(new=True)

        db: SASession = self.session_factory()
        try:
            stmt = select(UserSession).where(UserSession.session_token == sid)
            record = db.execute(stmt).scalar_one_or_none()
            now = datetime.now(timezone.utc)

            if not record or not record.is_active or record.expires_at <= now:
                if record:
                    record.is_active = False
                    record.expires_at = now
                    db.add(record)
                    db.commit()
                return self._create_session(new=True)

            session_obj = self._create_session(initial=record.session_data or {}, sid=sid, new=False)
            session_obj.permanent = True
            session_obj.modified = False
            return session_obj
        finally:
            db.close()

    def save_session(self, app, session: SessionMixin, response) -> None:
        if not isinstance(session, DatabaseSession):
            raise TypeError("DatabaseSessionInterface expects DatabaseSession instances")

        db_session = session
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        secure = self.get_cookie_secure(app)
        httponly = self.get_cookie_httponly(app)
        samesite = self.get_cookie_samesite(app)

        if not db_session:
            if db_session.sid:
                self._deactivate_session(db_session.sid)
            response.delete_cookie(self.cookie_name, path=path, domain=domain, samesite=samesite)
            return

        if db_session.sid is None:
            db_session.sid = self.session_class._generate_sid()  # type: ignore[attr-defined]
            db_session.new = True

        expires = self.get_expiration_time(app, db_session)
        now = datetime.now(timezone.utc)
        if expires is None:
            expires = now + self.lifetime
        elif expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        else:
            expires = expires.astimezone(timezone.utc)
        session_data = dict(db_session)
        user_id = session_data.get("user_id")
        client_ip = request.remote_addr if request else None
        user_agent = request.headers.get("User-Agent") if request else None

        db: SASession = self.session_factory()
        try:
            stmt = select(UserSession).where(UserSession.session_token == db_session.sid)
            record = db.execute(stmt).scalar_one_or_none()
            if user_id is None:
                if record is not None:
                    record.is_active = False
                    record.expires_at = now
                    record.session_data = session_data
                    record.ip_address = client_ip
                    record.user_agent = user_agent
                    db.add(record)
                    db.commit()
            else:
                if record is None:
                    record = UserSession(
                        session_token=db_session.sid,
                        user_id=user_id,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        expires_at=expires,
                        is_active=True,
                        session_data=session_data,
                    )
                    db.add(record)
                else:
                    record.session_data = session_data
                    record.expires_at = expires
                    record.is_active = True
                    record.ip_address = client_ip
                    record.user_agent = user_agent
                    record.user_id = user_id
                db.commit()
        finally:
            db.close()

        response.set_cookie(
            self.cookie_name,
            db_session.sid,
            expires=expires,
            httponly=httponly,
            secure=secure,
            samesite=samesite,
            domain=domain,
            path=path,
        )
        db_session.modified = False
        db_session.new = False

    def _deactivate_session(self, sid: str) -> None:
        db: SASession = self.session_factory()
        try:
            stmt = select(UserSession).where(UserSession.session_token == sid)
            record = db.execute(stmt).scalar_one_or_none()
            if record:
                record.is_active = False
                record.expires_at = datetime.now(timezone.utc)
                db.add(record)
                db.commit()
        finally:
            db.close()
