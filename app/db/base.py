from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""


class TimestampMixin:
    """Reusable mixin for created/updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActivatableMixin:
    """Mixin with is_active flag."""

    is_active: Mapped[bool] = mapped_column(Boolean, server_default=func.true(), nullable=False)


JSONDict = Dict[str, Any]
