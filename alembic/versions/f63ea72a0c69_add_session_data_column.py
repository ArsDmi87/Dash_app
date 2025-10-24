"""add session data column

Revision ID: f63ea72a0c69
Revises: a03814918d8b
Create Date: 2025-10-23 16:17:13.955260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f63ea72a0c69'
down_revision: Union[str, Sequence[str], None] = 'a03814918d8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column(
            "session_data",
            postgresql.JSONB(astext_type=None),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("user_sessions", "session_data", schema="auth")
