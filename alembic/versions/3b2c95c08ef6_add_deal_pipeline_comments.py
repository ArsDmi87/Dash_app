"""add deal pipeline comments table

Revision ID: 3b2c95c08ef6
Revises: f63ea72a0c69
Create Date: 2025-02-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3b2c95c08ef6"
down_revision: Union[str, Sequence[str], None] = "f63ea72a0c69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:  # pragma: no cover
    pass


def downgrade() -> None:  # pragma: no cover
    pass
