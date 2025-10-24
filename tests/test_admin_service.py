from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine, event, text as sa_text
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session as SASession, sessionmaker

from app.admin import (
    AdminService,
    CreateGroupPayload,
    CreateRolePayload,
    CreateUserPayload,
    DuplicateRoleError,
    NotFoundError,
)
from app.core.settings import Settings
from app.db.base import Base
from app.db.models import Report, User


@pytest.fixture()
def admin_service(tmp_path: Path) -> Iterator[AdminService]:
    main_db = tmp_path / "main.db"
    auth_db = tmp_path / "auth.db"
    audit_db = tmp_path / "audit.db"

    if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
        def _visit_jsonb(self, type_, **kw):  # type: ignore[override]
            return "TEXT"

        SQLiteTypeCompiler.visit_JSONB = _visit_jsonb  # type: ignore[attr-defined]

    if not hasattr(SQLiteTypeCompiler, "visit_INET"):
        def _visit_inet(self, type_, **kw):  # type: ignore[override]
            return "TEXT"

        SQLiteTypeCompiler.visit_INET = _visit_inet  # type: ignore[attr-defined]

    engine = create_engine(f"sqlite:///{main_db}", future=True)

    for table in Base.metadata.tables.values():
        for column in table.columns:
            default = column.server_default
            if default is None:
                continue
            default_sql = str(getattr(default, "arg", default))
            if "::jsonb" in default_sql:
                column.server_default = None

    @event.listens_for(engine, "connect")
    def _attach_schemas(dbapi_connection, connection_record):  # type: ignore[override]
        cursor = dbapi_connection.cursor()
        dbapi_connection.create_function("true", 0, lambda: 1)
        dbapi_connection.create_function("false", 0, lambda: 0)
        cursor.execute("ATTACH DATABASE ? AS auth", (str(auth_db),))
        cursor.execute("ATTACH DATABASE ? AS audit", (str(audit_db),))
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True, class_=SASession)
    settings = Settings()
    service = AdminService(session_factory=session_factory, settings=settings)

    class _StubAuthService:
        @staticmethod
        def hash_password(password: str) -> str:
            return f"stub::{password}"

    service._auth_service = _StubAuthService()  # type: ignore[attr-defined]
    try:
        yield service
    finally:
        engine.dispose()


def test_create_role_returns_summary(admin_service: AdminService) -> None:
    payload = CreateRolePayload(role_name="auditor", permissions={"reports": ["read"]})
    summary = admin_service.create_role(payload)

    assert summary.role_id > 0
    assert summary.role_name == "auditor"
    assert summary.permissions == {"reports": ["read"]}
    assert summary.reports == []
    assert summary.report_ids == []


def test_duplicate_role_name_raises(admin_service: AdminService) -> None:
    payload = CreateRolePayload(role_name="manager", permissions=None)
    admin_service.create_role(payload)

    with pytest.raises(DuplicateRoleError):
        admin_service.create_role(payload)


def test_create_user_assigns_roles_and_groups(admin_service: AdminService) -> None:
    role = admin_service.create_role(CreateRolePayload(role_name="analyst", permissions={"reports": ["view"]}))
    group = admin_service.create_group(
        CreateGroupPayload(group_name="analytics", description=None, role_ids=[role.role_id])
    )

    summary = admin_service.create_user(
        CreateUserPayload(
            username="alena",
            email="alena@example.com",
            password="password123",
            first_name="Alena",
            last_name="Ivanova",
            role_ids=[role.role_id],
            group_ids=[group.group_id],
        )
    )

    assert summary.username == "alena"
    assert summary.roles == ["analyst"]
    assert summary.groups == ["analytics"]
    assert summary.role_ids == [role.role_id]
    assert summary.group_ids == [group.group_id]

    with admin_service._session_scope() as session:  # type: ignore[attr-defined]
        user = session.get(User, summary.user_id)
        assert user is not None
        assert user.password_hash != "password123"


def test_assign_role_to_user_is_idempotent(admin_service: AdminService) -> None:
    role = admin_service.create_role(CreateRolePayload(role_name="support", permissions={}))
    user = admin_service.create_user(
        CreateUserPayload(
            username="supporter",
            email="supporter@example.com",
            password="secret",
        )
    )

    updated = admin_service.assign_role_to_user(user.user_id, role.role_id)
    assert updated.roles == ["support"]

    updated_again = admin_service.assign_role_to_user(user.user_id, role.role_id)
    assert updated_again.roles == ["support"]


def test_deactivate_user_excludes_from_active_listing(admin_service: AdminService) -> None:
    user = admin_service.create_user(
        CreateUserPayload(
            username="inactive",
            email="inactive@example.com",
            password="secret",
        )
    )

    admin_service.deactivate_user(user.user_id)

    active_users = admin_service.list_users()
    assert all(summary.is_active for summary in active_users) is True
    assert not active_users

    all_users = admin_service.list_users(include_inactive=True)
    assert len(all_users) == 1
    assert all_users[0].is_active is False


def test_update_role_changes_attributes(admin_service: AdminService) -> None:
    role = admin_service.create_role(CreateRolePayload(role_name="viewer", permissions={"reports": ["read"]}))

    updated = admin_service.update_role(
        role.role_id,
        role_name="editor",
        description="Может редактировать отчеты",
        is_active=False,
        permissions={"reports": ["write"]},
    )

    assert updated.role_name == "editor"
    assert updated.description == "Может редактировать отчеты"
    assert updated.is_active is False
    assert updated.permissions == {"reports": ["write"]}
    assert updated.reports == []
    assert updated.report_ids == []


def test_update_user_modifies_profile(admin_service: AdminService) -> None:
    role = admin_service.create_role(CreateRolePayload(role_name="reader", permissions={"reports": ["read"]}))
    group = admin_service.create_group(CreateGroupPayload(group_name="ops", description=None, role_ids=[role.role_id]))
    user = admin_service.create_user(
        CreateUserPayload(
            username="katya",
            email="katya@example.com",
            password="secret",
            role_ids=[role.role_id],
            group_ids=[group.group_id],
        )
    )

    updated = admin_service.update_user(
        user.user_id,
        email="katya.new@example.com",
        first_name="Katya",
        last_name="Smirnova",
        is_active=False,
        role_ids=[role.role_id],
        group_ids=[],
    )

    assert updated.email == "katya.new@example.com"
    assert updated.full_name == "Katya Smirnova"
    assert updated.is_active is False
    assert updated.group_ids == []


def test_update_user_changes_password(admin_service: AdminService) -> None:
    user = admin_service.create_user(
        CreateUserPayload(
            username="dmitry",
            email="dmitry@example.com",
            password="old-pass",
        )
    )

    admin_service.update_user(user.user_id, password="new-pass")

    with admin_service._session_scope() as session:  # type: ignore[attr-defined]
        db_user = session.get(User, user.user_id)
        assert db_user is not None
        assert db_user.password_hash == "stub::new-pass"


def test_update_group_assigns_roles(admin_service: AdminService) -> None:
    analyst = admin_service.create_role(CreateRolePayload(role_name="analyst", permissions={"reports": ["read"]}))
    reviewer = admin_service.create_role(CreateRolePayload(role_name="reviewer", permissions={"reports": ["approve"]}))
    group = admin_service.create_group(CreateGroupPayload(group_name="reviewers", description=None, role_ids=[analyst.role_id]))

    updated = admin_service.update_group(
        group.group_id,
        description="Группа ревьюеров",
        is_active=False,
        role_ids=[reviewer.role_id],
    )

    assert updated.description == "Группа ревьюеров"
    assert updated.is_active is False
    assert updated.role_ids == [reviewer.role_id]


def test_assign_and_remove_report_from_role(admin_service: AdminService) -> None:
    role = admin_service.create_role(CreateRolePayload(role_name="auditor", permissions={"dashboard": ["read"]}))

    with admin_service._session_scope() as session:  # type: ignore[attr-defined]
        report = Report(report_code="sales_dashboard", report_name="Продажи и прибыль")
        report.is_active = True
        session.add(report)
        session.flush()
        report_id = report.report_id

    summary = admin_service.assign_report_to_role(role.role_id, report_id)
    assert summary.report_ids == [report_id]
    assert summary.reports == ["sales_dashboard"]

    summary = admin_service.assign_report_to_role(role.role_id, report_id, can_view=False)
    assert summary.report_ids == []
    assert summary.reports == []

    summary = admin_service.assign_report_to_role(role.role_id, report_id, can_view=True)
    assert summary.report_ids == [report_id]

    summary = admin_service.remove_report_from_role(role.role_id, report_id)
    assert summary.report_ids == []
    assert summary.reports == []


def test_admin_role_receives_all_reports(admin_service: AdminService) -> None:
    admin_role = admin_service.create_role(CreateRolePayload(role_name="admin", permissions={"admin": ["read"]}))

    with admin_service._session_scope() as session:  # type: ignore[attr-defined]
        report = Report(report_code="finance_dashboard", report_name="Финансы")
        report.is_active = True
        session.add(report)
        session.flush()
        report_id = report.report_id

    refreshed = next(role for role in admin_service.list_roles(include_inactive=True) if role.role_name == "admin")
    assert report_id in refreshed.report_ids


def test_delete_user_and_group(admin_service: AdminService) -> None:
    role = admin_service.create_role(CreateRolePayload(role_name="auditor", permissions={"reports": ["read"]}))
    group = admin_service.create_group(CreateGroupPayload(group_name="auditors", description=None, role_ids=[role.role_id]))
    user = admin_service.create_user(
        CreateUserPayload(
            username="mark",
            email="mark@example.com",
            password="secret",
            role_ids=[role.role_id],
            group_ids=[group.group_id],
        )
    )

    admin_service.delete_user(user.user_id)
    admin_service.delete_group(group.group_id)

    assert admin_service.list_users(include_inactive=True) == []
    assert admin_service.list_groups(include_inactive=True) == []

    with pytest.raises(NotFoundError):
        admin_service.delete_user(user.user_id)

    with pytest.raises(NotFoundError):
        admin_service.delete_group(group.group_id)