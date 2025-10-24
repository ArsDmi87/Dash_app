from __future__ import annotations

import pytest

from app.auth.service import AuthService
from app.db.models import Group, Role, RoleReport, Report, User


@pytest.fixture()
def auth_service() -> AuthService:
    return AuthService()


def test_combine_permission_maps_merges_entries(auth_service: AuthService) -> None:
    result = auth_service.combine_permission_maps(
        [
            {"dashboard": ["read", "write"], "profile": ["read"]},
            {"dashboard": ["write", "delete"], "reports": ["read"]},
            None,
            {"*": ["read"]},
        ]
    )

    assert result == {
        "*": ["read"],
        "dashboard": ["delete", "read", "write"],
        "profile": ["read"],
        "reports": ["read"],
    }


def test_build_access_profile_collects_roles_and_groups(auth_service: AuthService) -> None:
    user = User(username="alice", email="alice@example.com", password_hash="hash")

    role_admin = Role(role_name="admin", permissions={"*": ["read", "write"]})
    role_admin.is_active = True
    role_viewer = Role(role_name="viewer", permissions={"dashboard": ["read"]})
    role_viewer.is_active = True

    group_power = Group(group_name="power_users")
    group_power.is_active = True
    group_power.roles.append(role_viewer)

    user.roles.append(role_admin)
    user.groups.append(group_power)

    report_sales = Report(report_code="sales_dashboard", report_name="Продажи")
    report_sales.is_active = True
    role_admin.report_assignments.append(RoleReport(report=report_sales, role=role_admin, can_view=True))

    roles, groups, permissions, reports = auth_service._build_access_profile(user)

    assert roles == ["admin", "viewer"]
    assert groups == ["power_users"]
    assert permissions["dashboard"] == ["read"]
    assert set(permissions["*"]) == {"read", "write"}
    assert any(report["code"] == "sales_dashboard" for report in reports)


def test_full_name_returns_combined_value(auth_service: AuthService) -> None:
    user = User(username="bob", email="bob@example.com", password_hash="hash", first_name="Bob", last_name="Builder")
    assert auth_service._full_name(user) == "Bob Builder"

    user_no_last = User(username="eve", email="eve@example.com", password_hash="hash", first_name="Eve")
    assert auth_service._full_name(user_no_last) == "Eve"

    user_empty = User(username="ivan", email="ivan@example.com", password_hash="hash")
    assert auth_service._full_name(user_empty) is None
