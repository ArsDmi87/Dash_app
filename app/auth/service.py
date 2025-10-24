from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import bcrypt
from flask import Request
from sqlalchemy import select, inspect
from sqlalchemy.orm import Session as SASession, joinedload

from app.core.settings import Settings, get_settings
from app.db.models import AuthLog, Group, Report, Role, RoleReport, User, UserSession
from app.db.session import auth_session


@dataclass(slots=True)
class AuthProfile:
    user_id: int
    username: str
    email: str
    full_name: str | None
    roles: list[str]
    groups: list[str]
    permissions: dict[str, list[str]]
    reports: list[dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "roles": self.roles,
            "groups": self.groups,
            "permissions": self.permissions,
            "reports": self.reports,
        }


class AuthService:
    """Handles user authentication, password verification, and session lifecycle."""

    MAX_PASSWORD_BYTES = 72

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        if not password_hash:
            return False
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False

    def hash_password(self, plain_password: str) -> str:
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > self.MAX_PASSWORD_BYTES:
            raise ValueError("Password exceeds bcrypt 72-byte limit")
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password_bytes, salt).decode("utf-8")

    def authenticate(self, username: str, password: str, request: Request | None = None) -> Optional[AuthProfile]:
        """Validate credentials and update audit tables, returning session profile."""
        with auth_session(self.settings) as session:
            stmt = (
                select(User)
                .options(
                    joinedload(User.roles)
                    .joinedload(Role.report_assignments)
                    .joinedload(RoleReport.report),
                    joinedload(User.roles).joinedload(Role.reports),
                    joinedload(User.groups)
                    .joinedload(Group.roles)
                    .joinedload(Role.report_assignments)
                    .joinedload(RoleReport.report),
                    joinedload(User.groups).joinedload(Group.roles).joinedload(Role.reports),
                )
                .where(User.username == username)
            )
            # unique() is required when joinedload() pulls back collection relationships
            user = session.execute(stmt).unique().scalar_one_or_none()
            if not user or not user.is_active:
                self._log_auth(session, username=username, user=user, success=False, action="login", request=request, error="inactive or missing user")
                return None

            if not self.verify_password(password, user.password_hash):
                user.failed_login_attempts += 1
                session.add(user)
                self._log_auth(session, username=username, user=user, success=False, action="login", request=request, error="invalid password")
                return None

            user.failed_login_attempts = 0
            user.last_login = datetime.now(timezone.utc)
            session.add(user)
            self._log_auth(session, username=username, user=user, success=True, action="login", request=request)
            roles, groups, permissions, reports = self._build_access_profile(user)
            profile = AuthProfile(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                full_name=self._full_name(user),
                roles=roles,
                groups=groups,
                permissions=permissions,
                reports=reports,
            )
            return profile

    def logout(self, session_token: str, reason: str = "logout") -> None:
        """Deactivate session and write audit log."""
        with auth_session(self.settings) as session:
            stmt = select(UserSession).where(UserSession.session_token == session_token)
            record = session.execute(stmt).scalar_one_or_none()
            if record:
                record.is_active = False
                record.expires_at = datetime.now(timezone.utc)
                session.add(record)
                self._log_auth(session, username=record.user.username if record.user else None, user=record.user, success=True, action=reason, request=None)
            else:
                self._log_auth(session, username=None, user=None, success=True, action=reason, request=None, error="session_not_found")

    @staticmethod
    def combine_permission_maps(maps: Iterable[Dict[str, Iterable[str]] | None]) -> dict[str, list[str]]:
        """Merge multiple permission dictionaries into a deduplicated, sorted map."""
        combined: dict[str, set[str]] = defaultdict(set)
        for mapping in maps:
            if not mapping:
                continue
            for resource, actions in mapping.items():
                if not actions:
                    continue
                combined[resource].update(action for action in actions if action)
        return {resource: sorted(actions) for resource, actions in combined.items()}

    def _build_access_profile(self, user: User) -> tuple[list[str], list[str], dict[str, list[str]], list[dict[str, Any]]]:
        role_names: set[str] = set()
        group_names: set[str] = set()
        permission_sources: list[Dict[str, Iterable[str]]] = []
        report_map: dict[str, dict[str, Any]] = {}

        for role in user.roles:
            if not role.is_active:
                continue
            role_names.add(role.role_name)
            permission_sources.append(role.permissions or {})
            self._collect_reports(role, report_map)

        for group in user.groups:
            if not group.is_active:
                continue
            group_names.add(group.group_name)
            for role in group.roles:
                if not role.is_active:
                    continue
                role_names.add(role.role_name)
                permission_sources.append(role.permissions or {})
                self._collect_reports(role, report_map)

        permissions = self.combine_permission_maps(permission_sources)

        if "admin" in role_names:
            session = inspect(user).session
            if session:
                all_reports = session.execute(
                    select(Report).where(Report.is_active.is_(True))
                ).scalars().all()
                for report in all_reports:
                    if not report:
                        continue
                    report_map.setdefault(
                        report.report_code,
                        {
                            "code": report.report_code,
                            "name": report.report_name,
                            "route_path": report.route_path,
                        },
                    )

        reports = sorted(report_map.values(), key=lambda item: (item["name"] or item["code"])) if report_map else []
        return sorted(role_names), sorted(group_names), permissions, reports

    @staticmethod
    def _collect_reports(role: Role, report_map: dict[str, dict[str, Any]]) -> None:
        handled = False
        for assignment in getattr(role, "report_assignments", []) or []:
            handled = True
            if not assignment.can_view:
                continue
            report = assignment.report
            if not report or not report.is_active:
                continue
            report_map.setdefault(
                report.report_code,
                {
                    "code": report.report_code,
                    "name": report.report_name,
                    "route_path": report.route_path,
                },
            )

        if handled:
            return

        for report in getattr(role, "reports", []) or []:
            if not report or not report.is_active:
                continue
            report_map.setdefault(
                report.report_code,
                {
                    "code": report.report_code,
                    "name": report.report_name,
                    "route_path": report.route_path,
                },
            )

    @staticmethod
    def _full_name(user: User) -> str | None:
        parts = [user.first_name, user.last_name]
        joined = " ".join(part for part in parts if part)
        return joined or None

    def _log_auth(self, session: SASession, username: str | None, user: User | None, success: bool, action: str, request: Request | None, error: str | None = None) -> None:
        log = AuthLog(
            user_id=user.user_id if user else None,
            username=username,
            action_type=action,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get("User-Agent") if request else None,
            success=success,
            error_message=error,
        )
        session.add(log)
