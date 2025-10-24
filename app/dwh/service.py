from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterator

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings, get_settings
from app.db.session import get_dwh_session_factory

logger = logging.getLogger(__name__)

_ARRAY_TEXT = ARRAY(TEXT())


@dataclass(slots=True)
class DashboardFiltersSnapshot:
    regions: list[str]
    categories: list[str]
    segments: list[str]
    channels: list[str]
    min_date: date | None
    max_date: date | None


@dataclass(slots=True)
class DashboardQueryParams:
    regions: list[str] | None = None
    categories: list[str] | None = None
    segments: list[str] | None = None
    channels: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    quantity_min: float | None = None
    quantity_max: float | None = None
    profit_min: float | None = None
    profit_max: float | None = None


class DwhDashboardService:
    """Query facade for the analytical dashboard."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        *,
        settings: Settings | None = None,
        schema: str = "test",
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory or get_dwh_session_factory(self.settings)
        self.schema = schema

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:  # pragma: no cover - runtime diagnostics only
            session.rollback()
            logger.exception("Failed to execute DWH query")
            raise
        finally:
            session.close()

    def get_filters_snapshot(self) -> DashboardFiltersSnapshot:
        with self._session_scope() as session:
            regions = self._fetch_scalar_list(session, f"SELECT DISTINCT region FROM {self.schema}.customers ORDER BY region")
            categories = self._fetch_scalar_list(session, f"SELECT DISTINCT category FROM {self.schema}.products ORDER BY category")
            segments = self._fetch_scalar_list(session, f"SELECT DISTINCT customer_segment FROM {self.schema}.customers ORDER BY customer_segment")
            channels = self._fetch_scalar_list(session, f"SELECT DISTINCT sales_channel FROM {self.schema}.sales ORDER BY sales_channel")
            bounds_stmt = text(
                f"SELECT MIN(sale_date) AS min_date, MAX(sale_date) AS max_date FROM {self.schema}.sales"
            )
            bounds = session.execute(bounds_stmt).mappings().one()
            return DashboardFiltersSnapshot(
                regions=regions,
                categories=categories,
                segments=segments,
                channels=channels,
                min_date=bounds.get("min_date"),
                max_date=bounds.get("max_date"),
            )

    def region_totals(self, params: DashboardQueryParams) -> list[dict[str, Any]]:
        sql = (
            f"SELECT region, SUM(total_amount) AS total_amount "
            f"FROM {self.schema}.sales_analysis {{where}} "
            "GROUP BY region ORDER BY total_amount DESC"
        )
        rows = self._run_query(sql, params)
        return [
            {"region": row["region"], "total_amount": _to_float(row["total_amount"])}
            for row in rows
            if row.get("region")
        ]

    def monthly_revenue(self, params: DashboardQueryParams) -> list[dict[str, Any]]:
        sql = (
            f"SELECT DATE_TRUNC('month', sale_date)::date AS month_start, "
            "SUM(total_amount) AS total_revenue "
            f"FROM {self.schema}.sales_analysis {{where}} "
            "GROUP BY month_start ORDER BY month_start"
        )
        rows = self._run_query(sql, params)
        return [
            {
                "month_start": row["month_start"],
                "total_revenue": _to_float(row["total_revenue"]),
            }
            for row in rows
            if row.get("month_start") is not None
        ]

    def category_totals(self, params: DashboardQueryParams) -> list[dict[str, Any]]:
        sql = (
            f"SELECT category, SUM(total_amount) AS total_amount "
            f"FROM {self.schema}.sales_analysis {{where}} "
            "GROUP BY category ORDER BY total_amount DESC"
        )
        rows = self._run_query(sql, params)
        return [
            {"category": row["category"], "total_amount": _to_float(row["total_amount"])}
            for row in rows
            if row.get("category")
        ]

    def profit_vs_quantity(self, params: DashboardQueryParams, *, limit: int = 1000) -> list[dict[str, Any]]:
        sql = (
            f"SELECT sale_id, sale_date, quantity, profit, category, total_amount "
            f"FROM {self.schema}.sales_analysis {{where}} "
            "ORDER BY sale_date LIMIT :limit"
        )
        rows = self._run_query(sql, params, extra_params={"limit": limit})
        prepared: list[dict[str, Any]] = []
        for row in rows:
            prepared.append(
                {
                    "sale_id": row["sale_id"],
                    "sale_date": row["sale_date"],
                    "quantity": row.get("quantity"),
                    "profit": _to_float(row.get("profit")),
                    "category": row.get("category"),
                    "total_amount": _to_float(row.get("total_amount")),
                }
            )
        return prepared

    def detailed_sales(self, params: DashboardQueryParams, *, limit: int = 200) -> list[dict[str, Any]]:
        sql = (
            "SELECT sale_id, sale_date, customer_name, region, customer_segment, "
            "category, product_name, quantity, total_amount, profit, sales_channel, payment_method "
            f"FROM {self.schema}.sales_analysis {{where}} "
            "ORDER BY sale_date DESC, sale_id DESC LIMIT :limit"
        )
        rows = self._run_query(sql, params, extra_params={"limit": limit})
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "sale_id": row.get("sale_id"),
                    "sale_date": row.get("sale_date"),
                    "customer_name": row.get("customer_name"),
                    "region": row.get("region"),
                    "customer_segment": row.get("customer_segment"),
                    "category": row.get("category"),
                    "product_name": row.get("product_name"),
                    "quantity": row.get("quantity"),
                    "total_amount": _to_float(row.get("total_amount")),
                    "profit": _to_float(row.get("profit")),
                    "sales_channel": row.get("sales_channel"),
                    "payment_method": row.get("payment_method"),
                }
            )
        return result

    def _run_query(
        self,
        sql_template: str,
        params: DashboardQueryParams,
        *,
        extra_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, bound_params, array_names = self._build_filters(params)
        if extra_params:
            bound_params.update(extra_params)
        sql = sql_template.format(where=where_clause)
        stmt = text(sql)
        for name in array_names:
            stmt = stmt.bindparams(bindparam(name, type_=_ARRAY_TEXT))
        with self._session_scope() as session:
            result = session.execute(stmt, bound_params)
            return [dict(row) for row in result.mappings().all()]

    def _build_filters(self, params: DashboardQueryParams) -> tuple[str, dict[str, Any], list[str]]:
        conditions: list[str] = []
        bound: dict[str, Any] = {}
        array_names: list[str] = []

        if params.regions:
            conditions.append("region = ANY(:regions)")
            bound["regions"] = list(params.regions)
            array_names.append("regions")
        if params.categories:
            conditions.append("category = ANY(:categories)")
            bound["categories"] = list(params.categories)
            array_names.append("categories")
        if params.segments:
            conditions.append("customer_segment = ANY(:segments)")
            bound["segments"] = list(params.segments)
            array_names.append("segments")
        if params.channels:
            conditions.append("sales_channel = ANY(:channels)")
            bound["channels"] = list(params.channels)
            array_names.append("channels")

        if params.start_date and params.end_date:
            conditions.append("sale_date BETWEEN :start_date AND :end_date")
            bound["start_date"] = params.start_date
            bound["end_date"] = params.end_date
        elif params.start_date:
            conditions.append("sale_date >= :start_date")
            bound["start_date"] = params.start_date
        elif params.end_date:
            conditions.append("sale_date <= :end_date")
            bound["end_date"] = params.end_date

        if params.quantity_min is not None:
            conditions.append("quantity >= :quantity_min")
            bound["quantity_min"] = params.quantity_min
        if params.quantity_max is not None:
            conditions.append("quantity <= :quantity_max")
            bound["quantity_max"] = params.quantity_max
        if params.profit_min is not None:
            conditions.append("profit >= :profit_min")
            bound["profit_min"] = params.profit_min
        if params.profit_max is not None:
            conditions.append("profit <= :profit_max")
            bound["profit_max"] = params.profit_max

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        return where_clause, bound, array_names

    @staticmethod
    def _fetch_scalar_list(session: Session, sql: str) -> list[str]:
        rows = session.execute(text(sql)).scalars().all()
        return [row for row in rows if row]


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive fallback
        return 0.0


_dashboard_service: DwhDashboardService | None = None


def set_dwh_dashboard_service(service: DwhDashboardService | None) -> None:
    global _dashboard_service
    _dashboard_service = service


def get_dwh_dashboard_service() -> DwhDashboardService:
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DwhDashboardService()
    return _dashboard_service
