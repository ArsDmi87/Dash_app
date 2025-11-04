from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import ActivatableMixin, Base, TimestampMixin


class Role(TimestampMixin, ActivatableMixin, Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "auth"}

    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    role_description: Mapped[Optional[str]] = mapped_column(Text)
    permissions: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)

    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=lambda: UserRole.__table__,
        primaryjoin=lambda: Role.role_id == UserRole.role_id,
        secondaryjoin=lambda: User.user_id == UserRole.user_id,
        back_populates="roles",
    )
    groups: Mapped[list["Group"]] = relationship(
        secondary="auth.group_roles",
        back_populates="roles",
    )

    user_assignments: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
        overlaps="users",
    )
    group_assignments: Mapped[list["GroupRole"]] = relationship(
        "GroupRole",
        back_populates="role",
        cascade="all, delete-orphan",
        overlaps="groups",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        secondary=lambda: RoleReport.__table__,
        primaryjoin=lambda: Role.role_id == RoleReport.role_id,
        secondaryjoin=lambda: Report.report_id == RoleReport.report_id,
        back_populates="roles",
    )
    report_assignments: Mapped[list["RoleReport"]] = relationship(
        "RoleReport",
        back_populates="role",
        cascade="all, delete-orphan",
        overlaps="reports",
    )


class Group(TimestampMixin, ActivatableMixin, Base):
    __tablename__ = "groups"
    __table_args__ = {"schema": "auth"}

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    group_description: Mapped[Optional[str]] = mapped_column(Text)

    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=lambda: UserGroup.__table__,
        primaryjoin=lambda: Group.group_id == UserGroup.group_id,
        secondaryjoin=lambda: User.user_id == UserGroup.user_id,
        back_populates="groups",
        overlaps="group_assignments,users",
    )
    roles: Mapped[list[Role]] = relationship(
        secondary="auth.group_roles",
        back_populates="groups",
        overlaps="group_assignments",
    )

    user_assignments: Mapped[list["UserGroup"]] = relationship(
        "UserGroup",
        back_populates="group",
        cascade="all, delete-orphan",
        overlaps="users",
    )
    role_assignments: Mapped[list["GroupRole"]] = relationship(
        "GroupRole",
        back_populates="group",
        cascade="all, delete-orphan",
        overlaps="roles,groups",
    )


class Report(TimestampMixin, ActivatableMixin, Base):
    __tablename__ = "reports"
    __table_args__ = {"schema": "auth"}

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    report_name: Mapped[str] = mapped_column(String(150), nullable=False)
    report_description: Mapped[Optional[str]] = mapped_column(Text)
    route_path: Mapped[Optional[str]] = mapped_column(String(255))

    roles: Mapped[list[Role]] = relationship(
        "Role",
        secondary=lambda: RoleReport.__table__,
        primaryjoin=lambda: Report.report_id == RoleReport.report_id,
        secondaryjoin=lambda: Role.role_id == RoleReport.role_id,
        back_populates="reports",
        overlaps="report_assignments",
    )
    role_links: Mapped[list["RoleReport"]] = relationship(
        "RoleReport",
        back_populates="report",
        cascade="all, delete-orphan",
        overlaps="roles,report_assignments,reports",
    )


class User(TimestampMixin, ActivatableMixin, Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default=func.false(), nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    roles: Mapped[list[Role]] = relationship(
        "Role",
        secondary=lambda: UserRole.__table__,
        primaryjoin=lambda: User.user_id == UserRole.user_id,
        secondaryjoin=lambda: Role.role_id == UserRole.role_id,
        back_populates="users",
        overlaps="user_assignments",
    )
    groups: Mapped[list[Group]] = relationship(
        "Group",
        secondary=lambda: UserGroup.__table__,
        primaryjoin=lambda: User.user_id == UserGroup.user_id,
        secondaryjoin=lambda: Group.group_id == UserGroup.group_id,
        back_populates="users",
        overlaps="group_assignments,user_assignments",
    )

    role_links: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        foreign_keys=lambda: [UserRole.user_id],
        back_populates="user",
        cascade="all, delete-orphan",
        overlaps="roles,user_assignments,users",
    )
    group_links: Mapped[list["UserGroup"]] = relationship(
        "UserGroup",
        foreign_keys=lambda: [UserGroup.user_id],
        back_populates="user",
        cascade="all, delete-orphan",
        overlaps="groups,user_assignments,users",
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        {"schema": "auth"},
    )

    user_role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("auth.roles.role_id", ondelete="CASCADE"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    assigned_by: Mapped[Optional[int]] = mapped_column(ForeignKey("auth.users.user_id"))

    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="role_links",
        overlaps="roles,users",
    )
    role: Mapped[Role] = relationship(
        "Role",
        back_populates="user_assignments",
        overlaps="users",
    )
    assigned_by_user: Mapped[Optional[User]] = relationship("User", foreign_keys=[assigned_by])


class UserGroup(Base):
    __tablename__ = "user_groups"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_user_group"),
        {"schema": "auth"},
    )

    user_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("auth.groups.group_id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    joined_by: Mapped[Optional[int]] = mapped_column(ForeignKey("auth.users.user_id"))

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], back_populates="group_links")
    group: Mapped[Group] = relationship("Group", back_populates="user_assignments", overlaps="groups,users")
    joined_by_user: Mapped[Optional[User]] = relationship("User", foreign_keys=[joined_by])


class GroupRole(Base):
    __tablename__ = "group_roles"
    __table_args__ = (
        UniqueConstraint("group_id", "role_id", name="uq_group_role"),
        {"schema": "auth"},
    )

    group_role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("auth.groups.group_id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("auth.roles.role_id", ondelete="CASCADE"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    assigned_by: Mapped[Optional[int]] = mapped_column(ForeignKey("auth.users.user_id"))

    group: Mapped[Group] = relationship("Group", back_populates="role_assignments")
    role: Mapped[Role] = relationship("Role", back_populates="group_assignments")
    assigned_by_user: Mapped[Optional[User]] = relationship("User", foreign_keys=[assigned_by])


class RoleReport(Base):
    __tablename__ = "role_reports"
    __table_args__ = (
        UniqueConstraint("role_id", "report_id", name="uq_role_report"),
        {"schema": "auth"},
    )

    role_id: Mapped[int] = mapped_column(ForeignKey("auth.roles.role_id", ondelete="CASCADE"), primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("auth.reports.report_id", ondelete="CASCADE"), primary_key=True)
    can_view: Mapped[bool] = mapped_column(Boolean, server_default=func.true(), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    role: Mapped[Role] = relationship("Role", back_populates="report_assignments", overlaps="reports")
    report: Mapped[Report] = relationship("Report", back_populates="role_links", overlaps="roles")


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = {"schema": "auth"}

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=func.true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    session_data: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="sessions")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = {"schema": "auth"}

    token_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False)
    reset_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, server_default=func.false(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User")


class AuthLog(Base):
    __tablename__ = "auth_logs"
    __table_args__ = {"schema": "audit"}

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("auth.users.user_id"))
    username: Mapped[Optional[str]] = mapped_column(String(50))
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[Optional[User]] = relationship("User")


class RoleChange(Base):
    __tablename__ = "role_changes"
    __table_args__ = {"schema": "audit"}

    change_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("auth.users.user_id"))
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    changed_by_user: Mapped[Optional[User]] = relationship("User")


class UserChange(Base):
    __tablename__ = "user_changes"
    __table_args__ = {"schema": "audit"}

    change_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("auth.users.user_id"))
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    changed_by_user: Mapped[Optional[User]] = relationship("User")
