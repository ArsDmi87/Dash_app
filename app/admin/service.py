from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Mapping, Sequence

from sqlalchemy import select, inspect
from sqlalchemy.orm import Session as SASession, joinedload, sessionmaker

from app.auth.service import AuthService
from app.core.settings import Settings, get_settings
from app.db.models import Group, Report, Role, RoleReport, User
from app.db.session import get_auth_session_factory


class AdminServiceError(Exception):
    """Base error for admin service operations."""


class DuplicateUserError(AdminServiceError):
    """Raised when attempting to create a user with a duplicate username or email."""


class DuplicateRoleError(AdminServiceError):
    """Raised when attempting to create a role with a duplicate name."""


class DuplicateGroupError(AdminServiceError):
    """Raised when attempting to create a group with a duplicate name."""


class NotFoundError(AdminServiceError):
    """Raised when an expected database entity cannot be located."""


@dataclass(slots=True)
class RoleSummary:
    role_id: int
    role_name: str
    description: str | None
    is_active: bool
    permissions: dict[str, list[str]]
    reports: list[str]
    report_ids: list[int]


@dataclass(slots=True)
class ReportSummary:
    report_id: int
    report_code: str
    report_name: str
    description: str | None
    route_path: str | None
    is_active: bool


@dataclass(slots=True)
class GroupSummary:
    group_id: int
    group_name: str
    description: str | None
    is_active: bool
    roles: list[str]
    role_ids: list[int]


@dataclass(slots=True)
class UserSummary:
    user_id: int
    username: str
    email: str
    full_name: str | None
    first_name: str | None
    last_name: str | None
    is_active: bool
    roles: list[str]
    groups: list[str]
    role_ids: list[int]
    group_ids: list[int]


@dataclass(slots=True)
class CreateUserPayload:
    username: str
    email: str
    password: str
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool = True
    role_ids: list[int] | None = None
    group_ids: list[int] | None = None


@dataclass(slots=True)
class CreateRolePayload:
    role_name: str
    permissions: Mapping[str, Sequence[str]] | None = None
    description: str | None = None
    is_active: bool = True


@dataclass(slots=True)
class CreateGroupPayload:
    group_name: str
    description: str | None = None
    is_active: bool = True
    role_ids: list[int] | None = None


class AdminService:
    """Application layer for managing users, roles, groups, and permissions."""

    def __init__(
        self,
        session_factory: sessionmaker[SASession] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or get_auth_session_factory(self.settings)
        self._auth_service = AuthService(self.settings)

    @contextmanager
    def _session_scope(self) -> Iterator[SASession]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_users(self, include_inactive: bool = False) -> list[UserSummary]:
        with self._session_scope() as session:
            stmt = select(User).options(
                joinedload(User.roles),
                joinedload(User.groups),
            )
            if not include_inactive:
                stmt = stmt.where(User.is_active.is_(True))
            users = session.execute(stmt).scalars().unique().all()
            return [self._to_user_summary(user) for user in users]

    def list_roles(self, include_inactive: bool = False) -> list[RoleSummary]:
        with self._session_scope() as session:
            stmt = select(Role).options(
                joinedload(Role.report_assignments).joinedload(RoleReport.report)
            )
            if not include_inactive:
                stmt = stmt.where(Role.is_active.is_(True))
            roles = session.execute(stmt).scalars().unique().all()
            return [self._to_role_summary(role) for role in roles]

    def list_groups(self, include_inactive: bool = False) -> list[GroupSummary]:
        with self._session_scope() as session:
            stmt = select(Group).options(joinedload(Group.roles))
            if not include_inactive:
                stmt = stmt.where(Group.is_active.is_(True))
            groups = session.execute(stmt).scalars().unique().all()
            return [self._to_group_summary(group) for group in groups]

    def list_reports(self, include_inactive: bool = False) -> list[ReportSummary]:
        with self._session_scope() as session:
            stmt = select(Report)
            if not include_inactive:
                stmt = stmt.where(
                    (Report.is_active.is_(True)) | (Report.is_active.is_(None))
                )
            reports = session.execute(stmt).scalars().all()
            return [self._to_report_summary(report) for report in reports]

    def create_user(self, payload: CreateUserPayload) -> UserSummary:
        with self._session_scope() as session:
            if self._user_exists(session, username=payload.username, email=payload.email):
                raise DuplicateUserError("User with the given username or email already exists")

            user = User(
                username=payload.username,
                email=payload.email,
                password_hash=self._auth_service.hash_password(payload.password),
                first_name=payload.first_name,
                last_name=payload.last_name,
                is_active=payload.is_active,
            )

            self._attach_roles(session, user, payload.role_ids)
            self._attach_groups(session, user, payload.group_ids)

            session.add(user)
            session.flush()
            session.refresh(user)
            return self._to_user_summary(user)

    def create_role(self, payload: CreateRolePayload) -> RoleSummary:
        with self._session_scope() as session:
            if self._role_exists(session, role_name=payload.role_name):
                raise DuplicateRoleError("Role with the given name already exists")

            role = Role(
                role_name=payload.role_name,
                role_description=payload.description,
                permissions=self._normalize_permissions(payload.permissions),
                is_active=payload.is_active,
            )

            session.add(role)
            session.flush()
            session.refresh(role)
            return self._to_role_summary(role)

    def create_group(self, payload: CreateGroupPayload) -> GroupSummary:
        with self._session_scope() as session:
            if self._group_exists(session, group_name=payload.group_name):
                raise DuplicateGroupError("Group with the given name already exists")

            group = Group(
                group_name=payload.group_name,
                group_description=payload.description,
                is_active=payload.is_active,
            )
            if payload.role_ids:
                roles = self._load_roles(session, payload.role_ids)
                group.roles.extend(roles)

            session.add(group)
            session.flush()
            session.refresh(group)
            return self._to_group_summary(group)

    def assign_role_to_user(self, user_id: int, role_id: int) -> UserSummary:
        with self._session_scope() as session:
            user = session.get(User, user_id)
            if not user:
                raise NotFoundError("User not found")
            role = session.get(Role, role_id)
            if not role:
                raise NotFoundError("Role not found")
            if role not in user.roles:
                user.roles.append(role)
                session.add(user)
            session.flush()
            session.refresh(user)
            return self._to_user_summary(user)

    def assign_role_to_group(self, group_id: int, role_id: int) -> GroupSummary:
        with self._session_scope() as session:
            group = session.get(Group, group_id)
            if not group:
                raise NotFoundError("Group not found")
            role = session.get(Role, role_id)
            if not role:
                raise NotFoundError("Role not found")
            if role not in group.roles:
                group.roles.append(role)
                session.add(group)
            session.flush()
            session.refresh(group)
            return self._to_group_summary(group)

    def assign_report_to_role(self, role_id: int, report_id: int, *, can_view: bool = True) -> RoleSummary:
        with self._session_scope() as session:
            role = session.get(Role, role_id)
            if not role:
                raise NotFoundError("Role not found")
            report = session.get(Report, report_id)
            if not report:
                raise NotFoundError("Report not found")

            existing = next((link for link in role.report_assignments if link.report_id == report_id), None)
            if existing:
                existing.can_view = bool(can_view)
            else:
                role.report_assignments.append(RoleReport(report=report, can_view=bool(can_view)))

            session.add(role)
            session.flush()
            session.refresh(role)
            return self._to_role_summary(role)

    def remove_report_from_role(self, role_id: int, report_id: int) -> RoleSummary:
        with self._session_scope() as session:
            role = session.get(Role, role_id)
            if not role:
                raise NotFoundError("Role not found")

            assignment = next((link for link in role.report_assignments if link.report_id == report_id), None)
            if not assignment:
                raise NotFoundError("Report assignment not found")

            role.report_assignments.remove(assignment)
            session.add(role)
            session.flush()
            session.refresh(role)
            return self._to_role_summary(role)

    def update_role_permissions(self, role_id: int, permissions: dict[str, Sequence[str]] | None) -> RoleSummary:
        with self._session_scope() as session:
            role = session.get(Role, role_id)
            if not role:
                raise NotFoundError("Role not found")
            role.permissions = self._normalize_permissions(permissions)
            session.add(role)
            session.flush()
            session.refresh(role)
            return self._to_role_summary(role)

    def deactivate_user(self, user_id: int) -> UserSummary:
        with self._session_scope() as session:
            user = session.get(User, user_id)
            if not user:
                raise NotFoundError("User not found")
            user.is_active = False
            session.add(user)
            session.flush()
            session.refresh(user)
            return self._to_user_summary(user)

    def update_user(
        self,
        user_id: int,
        *,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_active: bool | None = None,
        role_ids: Sequence[int] | None = None,
        group_ids: Sequence[int] | None = None,
        password: str | None = None,
    ) -> UserSummary:
        with self._session_scope() as session:
            user = session.get(User, user_id)
            if not user:
                raise NotFoundError("User not found")

            if email and email != user.email and self._email_exists(session, email, exclude_user_id=user_id):
                raise DuplicateUserError("User with the given email already exists")

            if email is not None:
                user.email = email.strip()
            if first_name is not None:
                user.first_name = first_name.strip() or None
            if last_name is not None:
                user.last_name = last_name.strip() or None
            if is_active is not None:
                user.is_active = bool(is_active)

            if role_ids is not None:
                roles = self._load_roles(session, role_ids) if role_ids else []
                user.roles = roles

            if group_ids is not None:
                groups = self._load_groups(session, group_ids) if group_ids else []
                user.groups = groups

            if password is not None:
                cleaned = password.strip()
                if cleaned:
                    user.password_hash = self._auth_service.hash_password(cleaned)

            session.add(user)
            session.flush()
            session.refresh(user)
            return self._to_user_summary(user)

    def delete_user(self, user_id: int) -> None:
        with self._session_scope() as session:
            user = session.get(User, user_id)
            if not user:
                raise NotFoundError("User not found")
            session.delete(user)

    def update_role(
        self,
        role_id: int,
        *,
        role_name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        permissions: dict[str, Sequence[str]] | None = None,
    ) -> RoleSummary:
        with self._session_scope() as session:
            role = session.get(Role, role_id)
            if not role:
                raise NotFoundError("Role not found")

            if role_name and role_name != role.role_name and self._role_exists(session, role_name=role_name):
                raise DuplicateRoleError("Role with the given name already exists")

            if role_name is not None:
                role.role_name = role_name.strip()
            if description is not None:
                role.role_description = description.strip() or None
            if is_active is not None:
                role.is_active = bool(is_active)
            if permissions is not None:
                role.permissions = self._normalize_permissions(permissions)

            session.add(role)
            session.flush()
            session.refresh(role)
            return self._to_role_summary(role)

    def delete_role(self, role_id: int) -> None:
        with self._session_scope() as session:
            role = session.get(Role, role_id)
            if not role:
                raise NotFoundError("Role not found")
            session.delete(role)

    def update_group(
        self,
        group_id: int,
        *,
        group_name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        role_ids: Sequence[int] | None = None,
    ) -> GroupSummary:
        with self._session_scope() as session:
            group = session.get(Group, group_id)
            if not group:
                raise NotFoundError("Group not found")

            if group_name and group_name != group.group_name and self._group_exists(session, group_name=group_name):
                raise DuplicateGroupError("Group with the given name already exists")

            if group_name is not None:
                group.group_name = group_name.strip()
            if description is not None:
                group.group_description = description.strip() or None
            if is_active is not None:
                group.is_active = bool(is_active)
            if role_ids is not None:
                roles = self._load_roles(session, role_ids) if role_ids else []
                group.roles = roles

            session.add(group)
            session.flush()
            session.refresh(group)
            return self._to_group_summary(group)

    def delete_group(self, group_id: int) -> None:
        with self._session_scope() as session:
            group = session.get(Group, group_id)
            if not group:
                raise NotFoundError("Group not found")
            session.delete(group)

    def _user_exists(self, session: SASession, *, username: str, email: str) -> bool:
        stmt = select(User.user_id).where((User.username == username) | (User.email == email))
        return session.execute(stmt).first() is not None

    def _email_exists(self, session: SASession, email: str, *, exclude_user_id: int | None = None) -> bool:
        stmt = select(User.user_id).where(User.email == email)
        if exclude_user_id is not None:
            stmt = stmt.where(User.user_id != exclude_user_id)
        return session.execute(stmt).first() is not None

    def _role_exists(self, session: SASession, *, role_name: str) -> bool:
        stmt = select(Role.role_id).where(Role.role_name == role_name)
        return session.execute(stmt).first() is not None

    def _group_exists(self, session: SASession, *, group_name: str) -> bool:
        stmt = select(Group.group_id).where(Group.group_name == group_name)
        return session.execute(stmt).first() is not None

    def _attach_roles(self, session: SASession, user: User, role_ids: list[int] | None) -> None:
        if not role_ids:
            return
        roles = self._load_roles(session, role_ids)
        for role in roles:
            if role not in user.roles:
                user.roles.append(role)

    def _attach_groups(self, session: SASession, user: User, group_ids: list[int] | None) -> None:
        if not group_ids:
            return
        groups = self._load_groups(session, group_ids)
        for group in groups:
            if group not in user.groups:
                user.groups.append(group)

    def _load_roles(self, session: SASession, role_ids: Sequence[int]) -> list[Role]:
        stmt = select(Role).where(Role.role_id.in_(role_ids))
        roles = list(session.execute(stmt).scalars().all())
        if len(roles) != len(set(role_ids)):
            raise NotFoundError("One or more roles were not found")
        return roles

    def _load_groups(self, session: SASession, group_ids: Sequence[int]) -> list[Group]:
        stmt = select(Group).where(Group.group_id.in_(group_ids))
        groups = list(session.execute(stmt).scalars().all())
        if len(groups) != len(set(group_ids)):
            raise NotFoundError("One or more groups were not found")
        return groups

    def _load_reports(self, session: SASession, report_ids: Sequence[int]) -> list[Report]:
        stmt = select(Report).where(Report.report_id.in_(report_ids))
        reports = list(session.execute(stmt).scalars().all())
        if len(reports) != len(set(report_ids)):
            raise NotFoundError("One or more reports were not found")
        return reports

    @staticmethod
    def _normalize_permissions(permissions: Mapping[str, Sequence[str]] | None) -> dict[str, list[str]]:
        if not permissions:
            return {}
        normalized: dict[str, list[str]] = {}
        for resource, actions in permissions.items():
            unique_actions = sorted({action for action in actions if action})
            if unique_actions:
                normalized[resource] = unique_actions
        return normalized

    def _to_user_summary(self, user: User) -> UserSummary:
        full_name = AuthService._full_name(user)
        roles = sorted({role.role_name for role in user.roles if role.is_active})
        groups = sorted({group.group_name for group in user.groups if group.is_active})
        role_ids = sorted({role.role_id for role in user.roles})
        group_ids = sorted({group.group_id for group in user.groups})
        return UserSummary(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=full_name,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=bool(user.is_active),
            roles=roles,
            groups=groups,
            role_ids=role_ids,
            group_ids=group_ids,
        )

    def _to_role_summary(self, role: Role) -> RoleSummary:
        permissions = {resource: sorted(actions) for resource, actions in (role.permissions or {}).items()}
        report_codes: set[str] = set()
        report_ids: set[int] = set()
        handled = False

        for assignment in getattr(role, "report_assignments", []) or []:
            handled = True
            if not assignment.can_view:
                continue
            report = assignment.report
            if not report or not report.is_active:
                continue
            report_codes.add(report.report_code)
            report_ids.add(report.report_id)

        if not handled and getattr(role, "reports", None):
            for report in role.reports:
                if not report or not report.is_active:
                    continue
                report_codes.add(report.report_code)
                report_ids.add(report.report_id)

        if role.role_name == "admin":
            session = inspect(role).session
            if session:
                all_reports = session.execute(select(Report).where(Report.is_active.is_(True))).scalars().all()
                for report in all_reports:
                    if not report or not report.is_active:
                        continue
                    report_codes.add(report.report_code)
                    report_ids.add(report.report_id)

        return RoleSummary(
            role_id=role.role_id,
            role_name=role.role_name,
            description=role.role_description,
            is_active=bool(role.is_active),
            permissions=permissions,
            reports=sorted(report_codes),
            report_ids=sorted(report_ids),
        )

    def _to_group_summary(self, group: Group) -> GroupSummary:
        role_names = sorted({role.role_name for role in group.roles if role.is_active})
        role_ids = sorted({role.role_id for role in group.roles})
        return GroupSummary(
            group_id=group.group_id,
            group_name=group.group_name,
            description=group.group_description,
            is_active=bool(group.is_active),
            roles=role_names,
            role_ids=role_ids,
        )

    def _to_report_summary(self, report: Report) -> ReportSummary:
        return ReportSummary(
            report_id=report.report_id,
            report_code=report.report_code,
            report_name=report.report_name,
            description=report.report_description,
            route_path=report.route_path,
            is_active=bool(report.is_active),
        )
