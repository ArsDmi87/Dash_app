from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings, get_settings
from app.db.session import get_dwh_session_factory

logger = logging.getLogger(__name__)

DEFAULT_DEPARTMENTS: tuple[str, ...] = ("ДОПК", "ДРПГО")


@dataclass(frozen=True)
class DealPipelineRow:
    row_id: str
    department: str | None
    manager: str | None
    client: str | None
    product: str | None
    deal_amount: float
    sed_load_date: date | None
    prkk_status: int | None
    prkk_date: date | None
    ud_status: int | None
    dzbi_status: int | None
    dakr_status: int | None
    kk_decision: int | None
    plan_date: date | None
    source_comment: str | None
    organization_raw: str | None = None
    client_raw: str | None = None


class DealPipelineService:
    """Expose deal funnel data prepared for the Dash report."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        *,
        settings: Settings | None = None,
        schema: str | None = "demo",
        table: str = "novikom",
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or get_dwh_session_factory(self.settings)
        self.schema = schema
        self.table = table

    @property
    def qualified_table(self) -> str:
        if self.schema:
            return f"{self.schema}.{self.table}"
        return self.table

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:  # pragma: no cover - diagnostics only
            session.rollback()
            logger.exception("Failed to execute deal pipeline query")
            raise
        finally:
            session.close()

    def list_departments(self) -> list[str]:
        sql = text(
            f'SELECT DISTINCT "Департамент" AS department FROM {self.qualified_table} '
            'WHERE "Департамент" IS NOT NULL AND TRIM("Департамент") <> \'\' '
            "ORDER BY department"
        )
        try:
            with self._session_scope() as session:
                result = session.execute(sql).scalars().all()
        except SQLAlchemyError:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to fetch deal pipeline departments")
            return list(DEFAULT_DEPARTMENTS)

        departments = [value for value in result if isinstance(value, str)]
        normalized = [value for value in departments if value in DEFAULT_DEPARTMENTS]
        return normalized or departments or list(DEFAULT_DEPARTMENTS)

    def fetch_pipeline(self, *, departments: Sequence[str] | None = None) -> list[DealPipelineRow]:
        selected_departments = [
            value.strip()
            for value in (departments or DEFAULT_DEPARTMENTS)
            if isinstance(value, str) and value.strip()
        ]

        try:
            with self._session_scope() as session:
                params: dict[str, Any] = {
                    "departments": list(selected_departments or DEFAULT_DEPARTMENTS),
                }
                sql = text(
                    "SELECT\n"
                    '    "Департамент" AS department,\n'
                    '    "Менеджер" AS manager,\n'
                    '    "Клиент" AS client,\n'
                    '    "Продукт" AS product,\n'
                    '    COALESCE("Сумма сделки, млн руб#", 0) AS deal_amount,\n'
                    '    "Загрузка в СЭД" AS sed_load_date,\n'
                    '    "Подготовка ПРКК" AS prkk_status,\n'
                    '    "Подготовка ПРКК (дата)" AS prkk_date,\n'
                    '    "ЮД" AS ud_status,\n'
                    '    "ДБЗИ" AS dzbi_status,\n'
                    '    "ДАКР" AS dakr_status,\n'
                    '    "Принято решение КК  (0/1)" AS kk_decision,\n'
                    '    "Плановая дата реализации" AS plan_date,\n'
                    '    "Комментарий к согласованию" AS source_comment\n'
                    f"FROM {self.qualified_table}\n"
                    "WHERE COALESCE(\"Департамент\", '') <> ''\n"
                    "  AND \"Департамент\" IN :departments\n"
                    "  AND COALESCE(\"Профинансировано\", 0) = 0\n"
                    "ORDER BY \"Плановая дата реализации\" NULLS LAST, \"Подготовка ПРКК (дата)\" NULLS LAST, \"Загрузка в СЭД\" NULLS LAST"
                )

                sql = sql.bindparams(bindparam("departments", expanding=True))

                rows = session.execute(sql, params).mappings().all()
        except SQLAlchemyError:  # pragma: no cover - diagnostics only
            logger.exception("Failed to fetch deal pipeline rows")
            return []

        results: list[DealPipelineRow] = []
        for row in rows:
            department = _ensure_str(row.get("department"))
            manager = _ensure_str(row.get("manager"))
            client = _ensure_str(row.get("client"))
            product = _ensure_str(row.get("product"))
            sed_load_date = _normalize_date(row.get("sed_load_date"))
            plan_date = _normalize_date(row.get("plan_date"))
            results.append(
                DealPipelineRow(
                    row_id=_make_row_id(
                        department=department,
                        manager=manager,
                        client=client,
                        product=product,
                        sed_load_date=sed_load_date,
                        plan_date=plan_date,
                    ),
                    department=department,
                    manager=manager,
                    client=client,
                    product=product,
                    deal_amount=_to_float(row.get("deal_amount")),
                    sed_load_date=sed_load_date,
                    prkk_status=_to_optional_int(row.get("prkk_status")),
                    prkk_date=_normalize_date(row.get("prkk_date")),
                    ud_status=_to_optional_int(row.get("ud_status")),
                    dzbi_status=_to_optional_int(row.get("dzbi_status")),
                    dakr_status=_to_optional_int(row.get("dakr_status")),
                    kk_decision=_to_optional_int(row.get("kk_decision")),
                    plan_date=plan_date,
                    source_comment=_ensure_comment(row.get("source_comment")),
                )
            )
        return results

    def update_comment(
        self,
        *,
        row_key: dict[str, Any],
        comment: str | None,
        user_id: int | None = None,
    ) -> None:
        if not isinstance(row_key, dict):
            raise ValueError("Row metadata is required for comment update")

        normalized_comment = (comment or "").strip()
        comment_value: Any = normalized_comment if normalized_comment else None

        with self._session_scope() as session:
            params: dict[str, Any] = {"comment": comment_value}
            conditions: list[str] = []

            def _bind(column: str, key: str) -> None:
                value = row_key.get(key)
                if value is None or value == "":
                    return
                params[key] = value
                conditions.append(f"{column} = :{key}")

            _bind('"Департамент"', "department")
            _bind('"Менеджер"', "manager")
            _bind('"Продукт"', "product")

            client = row_key.get("client")
            if client:
                params["client"] = client
                conditions.append('"Клиент" = :client')

            sed_value = _parse_date(row_key.get("sed_load_date"))
            if sed_value is not None:
                params["sed_load_date"] = sed_value
                conditions.append('"Загрузка в СЭД" = :sed_load_date')

            plan_value = _parse_date(row_key.get("plan_date"))
            if plan_value is not None:
                params["plan_date"] = plan_value
                conditions.append('"Плановая дата реализации" = :plan_date')

            if not conditions:
                raise ValueError("Insufficient data to locate the deal row for comment update")

            sql = text(
                f'UPDATE {self.qualified_table} SET "Комментарий к согласованию" = :comment '
                + " WHERE " + " AND ".join(conditions)
            )

            result = session.execute(sql, params)
            if result.rowcount == 0:  # pragma: no cover - diagnostic logging
                logger.warning(
                    "No deal rows matched for comment update %s", row_key,
                )


def _ensure_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _ensure_comment(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:  # pragma: no cover - defensive
        return None


def _normalize_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.strptime(text_value, fmt)
            except ValueError:
                continue
            return parsed.date()
        try:
            parsed = datetime.fromisoformat(text_value)
        except ValueError:
            return None
        return parsed.date()
    return None


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return 0.0


def _to_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int,)):
        return int(value)
    if isinstance(value, Decimal):
        return int(value)
    try:
        text_value = str(value).strip()
    except Exception:  # pragma: no cover - defensive
        return None
    if not text_value:
        return None
    try:
        return int(float(text_value))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value if not isinstance(value, datetime) else value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text_value, fmt).date()
            except ValueError:
                continue
    return None


def _make_row_id(
    *,
    department: str | None,
    manager: str | None,
    client: str | None,
    product: str | None,
    sed_load_date: date | None,
    plan_date: date | None,
) -> str:
    parts = [
        department or "",
        manager or "",
        client or "",
        product or "",
        (sed_load_date.isoformat() if sed_load_date else ""),
        (plan_date.isoformat() if plan_date else ""),
    ]
    combined = "|".join(parts).encode("utf-8")
    return hashlib.md5(combined, usedforsecurity=False).hexdigest()


_deal_pipeline_service: DealPipelineService | None = None


def set_deal_pipeline_service(service: DealPipelineService | None) -> None:
    global _deal_pipeline_service
    _deal_pipeline_service = service


def get_deal_pipeline_service() -> DealPipelineService:
    global _deal_pipeline_service
    if _deal_pipeline_service is None:
        _deal_pipeline_service = DealPipelineService()
    return _deal_pipeline_service
