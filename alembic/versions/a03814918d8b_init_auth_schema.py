"""init auth schema

Revision ID: a03814918d8b
Revises: 
Create Date: 2025-10-23 15:46:55.529621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a03814918d8b'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    op.create_table(
        "roles",
        sa.Column("role_id", sa.Integer(), primary_key=True),
        sa.Column("role_name", sa.String(length=50), nullable=False, unique=True),
        sa.Column("role_description", sa.Text(), nullable=True),
        sa.Column("permissions", postgresql.JSONB(astext_type=None), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        schema="auth",
    )

    op.create_table(
        "groups",
        sa.Column("group_id", sa.Integer(), primary_key=True),
        sa.Column("group_name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("group_description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        schema="auth",
    )

    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_login", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("password_changed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        schema="auth",
    )

    op.create_table(
        "user_roles",
        sa.Column("user_role_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("auth.roles.role_id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("auth.users.user_id"), nullable=True),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        schema="auth",
    )

    op.create_table(
        "user_groups",
        sa.Column("user_group_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("auth.groups.group_id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("joined_by", sa.Integer(), sa.ForeignKey("auth.users.user_id"), nullable=True),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_group"),
        schema="auth",
    )

    op.create_table(
        "group_roles",
        sa.Column("group_role_id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("auth.groups.group_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("auth.roles.role_id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("auth.users.user_id"), nullable=True),
        sa.UniqueConstraint("group_id", "role_id", name="uq_group_role"),
        schema="auth",
    )

    op.create_table(
        "user_sessions",
        sa.Column("session_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(length=255), nullable=False, unique=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        schema="auth",
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("token_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("reset_token", sa.String(length=255), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        schema="auth",
    )

    # Audit tables
    op.create_table(
        "auth_logs",
        sa.Column("log_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth.users.user_id"), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        schema="audit",
    )

    op.create_table(
        "role_changes",
        sa.Column("change_id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("auth.users.user_id"), nullable=True),
        sa.Column("change_type", sa.String(length=20), nullable=False),
        sa.Column("old_values", postgresql.JSONB(astext_type=None), nullable=True),
        sa.Column("new_values", postgresql.JSONB(astext_type=None), nullable=True),
        sa.Column("changed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        schema="audit",
    )

    op.create_table(
        "user_changes",
        sa.Column("change_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("auth.users.user_id"), nullable=True),
        sa.Column("change_type", sa.String(length=20), nullable=False),
        sa.Column("old_values", postgresql.JSONB(astext_type=None), nullable=True),
        sa.Column("new_values", postgresql.JSONB(astext_type=None), nullable=True),
        sa.Column("changed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        schema="audit",
    )

    # Indexes for auth schema
    op.create_index("idx_users_username", "users", ["username"], unique=False, schema="auth")
    op.create_index("idx_users_email", "users", ["email"], unique=False, schema="auth")
    op.create_index("idx_users_is_active", "users", ["is_active"], unique=False, schema="auth")

    op.create_index("idx_user_sessions_token", "user_sessions", ["session_token"], unique=False, schema="auth")
    op.create_index("idx_user_sessions_user_id", "user_sessions", ["user_id"], unique=False, schema="auth")
    op.create_index("idx_user_sessions_expires", "user_sessions", ["expires_at"], unique=False, schema="auth")

    op.create_index("idx_reset_tokens_token", "password_reset_tokens", ["reset_token"], unique=False, schema="auth")
    op.create_index("idx_reset_tokens_user_id", "password_reset_tokens", ["user_id"], unique=False, schema="auth")
    op.create_index("idx_reset_tokens_expires", "password_reset_tokens", ["expires_at"], unique=False, schema="auth")

    op.create_index("idx_user_roles_user_id", "user_roles", ["user_id"], unique=False, schema="auth")
    op.create_index("idx_user_roles_role_id", "user_roles", ["role_id"], unique=False, schema="auth")
    op.create_index("idx_user_groups_user_id", "user_groups", ["user_id"], unique=False, schema="auth")
    op.create_index("idx_user_groups_group_id", "user_groups", ["group_id"], unique=False, schema="auth")
    op.create_index("idx_group_roles_group_id", "group_roles", ["group_id"], unique=False, schema="auth")
    op.create_index("idx_group_roles_role_id", "group_roles", ["role_id"], unique=False, schema="auth")

    op.create_index("idx_auth_logs_user_id", "auth_logs", ["user_id"], unique=False, schema="audit")
    op.create_index("idx_auth_logs_created_at", "auth_logs", ["created_at"], unique=False, schema="audit")
    op.create_index("idx_role_changes_role_id", "role_changes", ["role_id"], unique=False, schema="audit")
    op.create_index("idx_user_changes_user_id", "user_changes", ["user_id"], unique=False, schema="audit")

    # Triggers
    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth.update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    for table_name in ("users", "roles", "groups"):
        op.execute(
            f"""
            CREATE TRIGGER trigger_update_{table_name}_updated_at
            BEFORE UPDATE ON auth.{table_name}
            FOR EACH ROW
            EXECUTE FUNCTION auth.update_updated_at();
            """
        )

    # Seed data
    op.execute(
        """
        INSERT INTO auth.roles (role_name, role_description, permissions)
        VALUES
            ('admin', 'Администратор системы', '{"*": ["read", "write", "delete"]}'),
            ('user', 'Обычный пользователь', '{"dashboard": ["read"], "profile": ["read", "write"]}'),
            ('viewer', 'Пользователь только для просмотра', '{"dashboard": ["read"]}')
        ON CONFLICT (role_name) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO auth.groups (group_name, group_description)
        VALUES
            ('administrators', 'Группа администраторов'),
            ('default_users', 'Группа по умолчанию для новых пользователей'),
            ('power_users', 'Продвинутые пользователи')
        ON CONFLICT (group_name) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO auth.group_roles (group_id, role_id)
        VALUES (1, 1), (2, 2), (3, 1)
        ON CONFLICT (group_id, role_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Drop triggers
    for table_name in ("users", "roles", "groups"):
        op.execute(f"DROP TRIGGER IF EXISTS trigger_update_{table_name}_updated_at ON auth.{table_name}")
    op.execute("DROP FUNCTION IF EXISTS auth.update_updated_at")

    # Drop indexes
    op.drop_index("idx_group_roles_role_id", table_name="group_roles", schema="auth")
    op.drop_index("idx_group_roles_group_id", table_name="group_roles", schema="auth")
    op.drop_index("idx_user_groups_group_id", table_name="user_groups", schema="auth")
    op.drop_index("idx_user_groups_user_id", table_name="user_groups", schema="auth")
    op.drop_index("idx_user_roles_role_id", table_name="user_roles", schema="auth")
    op.drop_index("idx_user_roles_user_id", table_name="user_roles", schema="auth")
    op.drop_index("idx_reset_tokens_expires", table_name="password_reset_tokens", schema="auth")
    op.drop_index("idx_reset_tokens_user_id", table_name="password_reset_tokens", schema="auth")
    op.drop_index("idx_reset_tokens_token", table_name="password_reset_tokens", schema="auth")
    op.drop_index("idx_user_sessions_expires", table_name="user_sessions", schema="auth")
    op.drop_index("idx_user_sessions_user_id", table_name="user_sessions", schema="auth")
    op.drop_index("idx_user_sessions_token", table_name="user_sessions", schema="auth")
    op.drop_index("idx_users_is_active", table_name="users", schema="auth")
    op.drop_index("idx_users_email", table_name="users", schema="auth")
    op.drop_index("idx_users_username", table_name="users", schema="auth")

    op.drop_index("idx_user_changes_user_id", table_name="user_changes", schema="audit")
    op.drop_index("idx_role_changes_role_id", table_name="role_changes", schema="audit")
    op.drop_index("idx_auth_logs_created_at", table_name="auth_logs", schema="audit")
    op.drop_index("idx_auth_logs_user_id", table_name="auth_logs", schema="audit")

    # Drop tables
    op.drop_table("user_changes", schema="audit")
    op.drop_table("role_changes", schema="audit")
    op.drop_table("auth_logs", schema="audit")

    op.drop_table("password_reset_tokens", schema="auth")
    op.drop_table("user_sessions", schema="auth")
    op.drop_table("group_roles", schema="auth")
    op.drop_table("user_groups", schema="auth")
    op.drop_table("user_roles", schema="auth")
    op.drop_table("users", schema="auth")
    op.drop_table("groups", schema="auth")
    op.drop_table("roles", schema="auth")

    op.execute("DROP SCHEMA IF EXISTS audit CASCADE")
    op.execute("DROP SCHEMA IF EXISTS auth CASCADE")
