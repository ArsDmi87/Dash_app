from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterator, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings, get_settings
from app.db.session import get_dwh_session_factory

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProductTotals:
    product: str
    ending_balance: float
    delta_day: float
    delta_week: float
    delta_quarter: float
    delta_year: float


@dataclass(frozen=True)
class ProductFlows:
    issued_day: float
    repaid_day: float
    issued_week: float
    repaid_week: float
    issued_quarter: float
    repaid_quarter: float
    issued_year: float
    repaid_year: float


@dataclass(frozen=True)
class DetailRow:
    department: str | None
    manager: str | None
    client: str | None
    product: str | None
    value: float


class ProductDynamicsService:
    """Read analytics for the product dynamics dashboard."""

    _METRIC_COLUMN_MAP: dict[str, str] = {
        "ending_balance": '"Остаток на конец дня, млн руб#"',
        "delta_day": '"Дельта за день, млн руб#"',
        "delta_week": '"Дельта за неделю, млн руб#"',
        "delta_quarter": '"Дельта за квартал, млн руб#"',
        "delta_year": '"Дельта за год, млн руб#"',
        "issued_day": '"Выдано за день, млн руб#"',
        "repaid_day": '"Погашено за день, млн руб#"',
        "issued_week": '"Выдано за неделю, млн руб#"',
        "repaid_week": '"Погашено за неделю, млн руб#"',
        "issued_quarter": '"Выдано за квартал, млн руб#"',
        "repaid_quarter": '"Погашено за квартал, млн руб#"',
        "issued_year": '"Выдано за год, млн руб#"',
        "repaid_year": '"Погашено за год, млн руб#"',
    }

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
        except Exception:  # pragma: no cover - runtime diagnostics only
            session.rollback()
            logger.exception("Failed to execute product dynamics query")
            raise
        finally:
            session.close()

    def list_departments(self) -> list[str]:
        sql = text(
            f"SELECT DISTINCT \"Департамент\" AS department FROM {self.qualified_table} "
            "WHERE \"Департамент\" IS NOT NULL AND TRIM(\"Департамент\") <> '' "
            "ORDER BY department"
        )
        with self._session_scope() as session:
            rows = session.execute(sql).scalars().all()
            return [row for row in rows if isinstance(row, str)]

    def list_products(self, departments: Sequence[str] | None = None) -> list[str]:
        where, bound = self._build_filters(departments=departments)
        product_condition = "\"Продукт\" IS NOT NULL AND TRIM(\"Продукт\") <> ''"
        if where:
            where = f"{where} AND {product_condition}"
        else:
            where = f"WHERE {product_condition}"
        sql = text(
            f'SELECT DISTINCT "Продукт" AS product FROM {self.qualified_table} {where} '
            "ORDER BY product"
        )
        stmt = self._apply_expanding_params(sql, bound)
        with self._session_scope() as session:
            rows = session.execute(stmt, bound).scalars().all()
            return [row for row in rows if isinstance(row, str)]

    def aggregate_product_totals(self, departments: Sequence[str] | None = None) -> list[ProductTotals]:
        where, bound = self._build_filters(departments=departments)
        sql = text(
            "SELECT\n"
            '    "Продукт" AS product,\n'
            '    COALESCE(SUM("Остаток на конец дня, млн руб#"), 0) AS ending_balance,\n'
            '    COALESCE(SUM("Дельта за день, млн руб#"), 0) AS delta_day,\n'
            '    COALESCE(SUM("Дельта за неделю, млн руб#"), 0) AS delta_week,\n'
            '    COALESCE(SUM("Дельта за квартал, млн руб#"), 0) AS delta_quarter,\n'
            '    COALESCE(SUM("Дельта за год, млн руб#"), 0) AS delta_year\n'
            f"FROM {self.qualified_table} {where}\n"
            'GROUP BY "Продукт"\n'
            'ORDER BY ending_balance DESC, product'
        )
        stmt = self._apply_expanding_params(sql, bound)
        with self._session_scope() as session:
            rows = session.execute(stmt, bound).mappings().all()
        totals: list[ProductTotals] = []
        for row in rows:
            product = row.get("product")
            if not isinstance(product, str) or not product.strip():
                continue
            totals.append(
                ProductTotals(
                    product=product,
                    ending_balance=_to_float(row.get("ending_balance")),
                    delta_day=_to_float(row.get("delta_day")),
                    delta_week=_to_float(row.get("delta_week")),
                    delta_quarter=_to_float(row.get("delta_quarter")),
                    delta_year=_to_float(row.get("delta_year")),
                )
            )
        return totals

    def aggregate_product_flows(
        self,
        *,
        product: str | None,
        departments: Sequence[str] | None = None,
    ) -> ProductFlows:
        where, bound = self._build_filters(departments=departments, product=product)
        sql = text(
            'SELECT\n'
            '    COALESCE(SUM("Выдано за день, млн руб#"), 0) AS issued_day,\n'
            '    COALESCE(SUM("Погашено за день, млн руб#"), 0) AS repaid_day,\n'
            '    COALESCE(SUM("Выдано за неделю, млн руб#"), 0) AS issued_week,\n'
            '    COALESCE(SUM("Погашено за неделю, млн руб#"), 0) AS repaid_week,\n'
            '    COALESCE(SUM("Выдано за квартал, млн руб#"), 0) AS issued_quarter,\n'
            '    COALESCE(SUM("Погашено за квартал, млн руб#"), 0) AS repaid_quarter,\n'
            '    COALESCE(SUM("Выдано за год, млн руб#"), 0) AS issued_year,\n'
            '    COALESCE(SUM("Погашено за год, млн руб#"), 0) AS repaid_year\n'
            f"FROM {self.qualified_table} {where}"
        )
        stmt = self._apply_expanding_params(sql, bound)
        with self._session_scope() as session:
            row = session.execute(stmt, bound).mappings().one()
        return ProductFlows(
            issued_day=_to_float(row.get("issued_day")),
            repaid_day=_to_float(row.get("repaid_day")),
            issued_week=_to_float(row.get("issued_week")),
            repaid_week=_to_float(row.get("repaid_week")),
            issued_quarter=_to_float(row.get("issued_quarter")),
            repaid_quarter=_to_float(row.get("repaid_quarter")),
            issued_year=_to_float(row.get("issued_year")),
            repaid_year=_to_float(row.get("repaid_year")),
        )

    def fetch_details(
        self,
        metric_key: str,
        *,
        departments: Sequence[str] | None = None,
        product: str | None = None,
        limit: int = 500,
    ) -> list[DetailRow]:
        column = self._METRIC_COLUMN_MAP.get(metric_key)
        if not column:
            raise ValueError(f"Unsupported metric key: {metric_key}")
        where, bound = self._build_filters(departments=departments, product=product)
        bound["limit"] = max(int(limit), 1)
        sql = text(
            "SELECT\n"
            '    "Департамент" AS department,\n'
            '    "Менеджер" AS manager,\n'
            '    "Клиент" AS client,\n'
            '    "Продукт" AS product,\n'
            f"    COALESCE({column}, 0) AS value\n"
            f"FROM {self.qualified_table} {where}\n"
            "ORDER BY value DESC, client\n"
            "LIMIT :limit"
        )
        stmt = self._apply_expanding_params(sql, bound)
        with self._session_scope() as session:
            rows = session.execute(stmt, bound).mappings().all()
        details: list[DetailRow] = []
        for row in rows:
            details.append(
                DetailRow(
                    department=_ensure_str_or_none(row.get("department")),
                    manager=_ensure_str_or_none(row.get("manager")),
                    client=_ensure_str_or_none(row.get("client")),
                    product=_ensure_str_or_none(row.get("product")),
                    value=_to_float(row.get("value")),
                )
            )
        return details

    def _build_filters(
        self,
        *,
        departments: Sequence[str] | None = None,
        product: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        conditions: list[str] = []
        bound: dict[str, Any] = {}

        departments = [value for value in (departments or []) if isinstance(value, str) and value.strip()]
        if departments:
            conditions.append('"Департамент" IN :departments')
            bound["departments"] = departments

        if product and isinstance(product, str) and product.strip():
            conditions.append('"Продукт" = :product')
            bound["product"] = product

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)
        return where, bound

    @staticmethod
    def _apply_expanding_params(stmt, bound: dict[str, Any]):
        if "departments" in bound:
            stmt = stmt.bindparams(bindparam("departments", expanding=True))
        return stmt


def _ensure_str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive path
        return 0.0


_product_dynamics_service: ProductDynamicsService | None = None


def set_product_dynamics_service(service: ProductDynamicsService | None) -> None:
    global _product_dynamics_service
    _product_dynamics_service = service


def get_product_dynamics_service() -> ProductDynamicsService:
    global _product_dynamics_service
    if _product_dynamics_service is None:
        _product_dynamics_service = ProductDynamicsService()
    return _product_dynamics_service
