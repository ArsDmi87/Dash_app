from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings, get_settings


def _create_engine(url: str) -> Engine:
    if not url:
        raise ValueError("Database DSN is not configured")
    return create_engine(url, pool_pre_ping=True, future=True)


def get_auth_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return _create_engine(settings.auth_db_dsn)


def get_reporting_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return _create_engine(settings.reporting_db_dsn)


def get_dwh_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return _create_engine(settings.dwh_db_dsn)


def get_auth_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_auth_engine(settings), expire_on_commit=False, class_=Session, future=True)


def get_reporting_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_reporting_engine(settings), expire_on_commit=False, class_=Session, future=True)


def get_dwh_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_dwh_engine(settings), expire_on_commit=False, class_=Session, future=True)


@contextmanager
def auth_session(settings: Settings | None = None) -> Iterator[Session]:
    factory = get_auth_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - re-raise for callers
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def reporting_session(settings: Settings | None = None) -> Iterator[Session]:
    factory = get_reporting_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def dwh_session(settings: Settings | None = None) -> Iterator[Session]:
    factory = get_dwh_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover
        session.rollback()
        raise
    finally:
        session.close()
