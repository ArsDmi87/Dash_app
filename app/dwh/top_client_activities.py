from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterator, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings, get_settings
from app.db.session import get_dwh_session_factory

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClientActivityRow:
    category: str
    client: str
    issued_day: float
    repaid_day: float
    issued_week: float
    repaid_week: float
    issued_quarter: float
    repaid_quarter: float
    score: float


@dataclass(frozen=True)
class CategoryActivities:
    category: str
    clients: list[ClientActivityRow]
    score: float


@dataclass(frozen=True)
class ClientActivityDetailRow:
    department: str | None
    manager: str | None
    client: str | None
    product: str | None
    deal_amount: float
    delta_day: float
    delta_week: float
    delta_quarter: float


class TopClientActivitiesService:
    """Expose aggregated activity metrics by client grouped by product categories."""

    _ISSUED_COLUMNS = {
        "day": '"Выдано за день, млн руб#"',
        "week": '"Выдано за неделю, млн руб#"',
        "quarter": '"Выдано за квартал, млн руб#"',
    }
    _REPAID_COLUMNS = {
        "day": '"Погашено за день, млн руб#"',
        "week": '"Погашено за неделю, млн руб#"',
        "quarter": '"Погашено за квартал, млн руб#"',
    }
    _DELTA_COLUMNS = {
        "day": '"Дельта за день, млн руб#"',
        "week": '"Дельта за неделю, млн руб#"',
        "quarter": '"Дельта за квартал, млн руб#"',
    }
    _CATEGORY_CANDIDATES = [
        "Категория продукта",
        "Категория продуктов",
        "Категория",
        "Группа продуктов",
        "Направление",
        "Продукт",
    ]
    _DEAL_AMOUNT_CANDIDATES = [
        "Сумма сделки, млн руб#",
        "Сумма сделки, млн руб",
        "Сумма сделки",
        "Сумма",
    ]

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
        self._available_columns: set[str] | None = None
        self._category_column_name: str | None = None
        self._deal_amount_column_name: str | None = None

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
            logger.exception("Failed to execute top client activities query")
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

    def aggregate_client_activities(
        self,
        *,
        departments: Sequence[str] | None = None,
        limit_per_category: int = 10,
        category_limit: int = 4,
    ) -> list[CategoryActivities]:
        if limit_per_category <= 0:
            return []
        limit_per_category = int(limit_per_category)
        category_limit = max(int(category_limit), 1)

        with self._session_scope() as session:
            category_column = self._get_category_column(session)
            where_clause, bound = self._build_filters(departments=departments)
            category_expr = self._quote_column(category_column)
            client_expr = '"Клиент"'

            filters = [f"{category_expr} IS NOT NULL", f"TRIM({category_expr}) <> ''", f"{client_expr} IS NOT NULL", f"TRIM({client_expr}) <> ''"]
            if where_clause:
                filters.append(where_clause.replace("WHERE ", ""))
            where = "WHERE " + " AND ".join(filters) if filters else ""

            sql = text(
                "WITH aggregated AS (\n"
                f"    SELECT {category_expr} AS category,\n"
                f"           {client_expr} AS client,\n"
                f"           COALESCE(SUM({self._ISSUED_COLUMNS['day']}), 0) AS issued_day,\n"
                f"           COALESCE(SUM({self._REPAID_COLUMNS['day']}), 0) AS repaid_day,\n"
                f"           COALESCE(SUM({self._ISSUED_COLUMNS['week']}), 0) AS issued_week,\n"
                f"           COALESCE(SUM({self._REPAID_COLUMNS['week']}), 0) AS repaid_week,\n"
                f"           COALESCE(SUM({self._ISSUED_COLUMNS['quarter']}), 0) AS issued_quarter,\n"
                f"           COALESCE(SUM({self._REPAID_COLUMNS['quarter']}), 0) AS repaid_quarter\n"
                f"    FROM {self.qualified_table} {where}\n"
                f"    GROUP BY {category_expr}, {client_expr}\n"
                "), scored AS (\n"
                "    SELECT category, client, issued_day, repaid_day, issued_week, repaid_week,\n"
                "           issued_quarter, repaid_quarter,\n"
                "           GREATEST(\n"
                "               ABS(issued_day), ABS(repaid_day),\n"
                "               ABS(issued_week), ABS(repaid_week),\n"
                "               ABS(issued_quarter), ABS(repaid_quarter)\n"
                "           ) AS score\n"
                "    FROM aggregated\n"
                "), ranked AS (\n"
                "    SELECT category, client, issued_day, repaid_day, issued_week, repaid_week,\n"
                "           issued_quarter, repaid_quarter, score,\n"
                "           ROW_NUMBER() OVER (PARTITION BY category ORDER BY score DESC, client) AS rn\n"
                "    FROM scored\n"
                "    WHERE score > 0\n"
                ")\n"
                "SELECT category, client, issued_day, repaid_day, issued_week, repaid_week,\n"
                "       issued_quarter, repaid_quarter, score\n"
                "FROM ranked\n"
                "WHERE rn <= :limit_per_category\n"
                "ORDER BY score DESC, category, rn"
            )
            if "departments" in bound:
                sql = sql.bindparams(bindparam("departments", expanding=True))
            bound["limit_per_category"] = limit_per_category

            rows = session.execute(sql, bound).mappings().all()

        grouped: dict[str, list[ClientActivityRow]] = {}
        category_scores: dict[str, float] = {}
        for row in rows:
            category = _ensure_str(row.get("category"))
            client = _ensure_str(row.get("client"))
            if not category or not client:
                continue
            issued_day = _to_float(row.get("issued_day"))
            repaid_day = _to_float(row.get("repaid_day"))
            issued_week = _to_float(row.get("issued_week"))
            repaid_week = _to_float(row.get("repaid_week"))
            issued_quarter = _to_float(row.get("issued_quarter"))
            repaid_quarter = _to_float(row.get("repaid_quarter"))
            score = _to_float(row.get("score"))
            grouped.setdefault(category, []).append(
                ClientActivityRow(
                    category=category,
                    client=client,
                    issued_day=issued_day,
                    repaid_day=repaid_day,
                    issued_week=issued_week,
                    repaid_week=repaid_week,
                    issued_quarter=issued_quarter,
                    repaid_quarter=repaid_quarter,
                    score=score,
                )
            )
            category_scores[category] = max(category_scores.get(category, 0.0), score)

        categories: list[CategoryActivities] = []
        for category, clients in grouped.items():
            clients.sort(key=lambda row: row.score, reverse=True)
            categories.append(
                CategoryActivities(category=category, clients=clients, score=category_scores.get(category, 0.0))
            )
        categories.sort(key=lambda item: item.score, reverse=True)
        return categories[:category_limit]

    def fetch_details(
        self,
        *,
        category: str,
        client: str | None,
        metric: str,
        period: str,
        departments: Sequence[str] | None = None,
        limit: int = 500,
    ) -> list[ClientActivityDetailRow]:
        metric = metric.lower().strip()
        period = period.lower().strip()
        metric_column = None
        if metric == "issued":
            metric_column = self._ISSUED_COLUMNS.get(period)
        elif metric == "repaid":
            metric_column = self._REPAID_COLUMNS.get(period)
        if metric_column is None:
            raise ValueError(f"Unsupported metric/period combination: {metric}/{period}")

        normalized_category = category.strip()
        normalized_client = client.strip() if isinstance(client, str) else ""
        if not normalized_category:
            return []
        if client is not None and not normalized_client:
            return []

        with self._session_scope() as session:
            category_column = self._get_category_column(session)
            dep_filter, bound = self._build_filters(departments=departments)
            bound["category"] = normalized_category
            if normalized_client:
                bound["client"] = normalized_client
            bound["metric_threshold"] = 0.0
            bound["limit"] = max(int(limit), 1)
            category_expr = self._quote_column(category_column)
            client_expr = '"Клиент"'
            deal_amount_expr = self._deal_amount_expression(session, metric=metric, period=period)

            conditions: list[str] = [f"{category_expr} = :category", f"COALESCE({metric_column}, 0) > :metric_threshold"]
            if normalized_client:
                conditions.append(f"{client_expr} = :client")
            if dep_filter:
                conditions.append(dep_filter.replace("WHERE ", "", 1))
            where = "WHERE " + " AND ".join(conditions)

            sql = text(
                "SELECT\n"
                "    COALESCE(\"Департамент\", '') AS department,\n"
                "    COALESCE(\"Менеджер\", '') AS manager,\n"
                "    COALESCE(\"Клиент\", '') AS client,\n"
                "    COALESCE(\"Продукт\", '') AS product,\n"
                f"    COALESCE(SUM({deal_amount_expr}), 0) AS deal_amount,\n"
                f"    COALESCE(SUM({self._DELTA_COLUMNS['day']}), 0) AS delta_day,\n"
                f"    COALESCE(SUM({self._DELTA_COLUMNS['week']}), 0) AS delta_week,\n"
                f"    COALESCE(SUM({self._DELTA_COLUMNS['quarter']}), 0) AS delta_quarter\n"
                f"FROM {self.qualified_table}\n"
                f"{where}\n"
                "GROUP BY department, manager, client, product\n"
                "ORDER BY deal_amount DESC, client\n"
                "LIMIT :limit"
            )
            if "departments" in bound:
                sql = sql.bindparams(bindparam("departments", expanding=True))

            rows = session.execute(sql, bound).mappings().all()

        details: list[ClientActivityDetailRow] = []
        for row in rows:
            details.append(
                ClientActivityDetailRow(
                    department=_ensure_str(row.get("department")),
                    manager=_ensure_str(row.get("manager")),
                    client=_ensure_str(row.get("client")),
                    product=_ensure_str(row.get("product")),
                    deal_amount=_to_float(row.get("deal_amount")),
                    delta_day=_to_float(row.get("delta_day")),
                    delta_week=_to_float(row.get("delta_week")),
                    delta_quarter=_to_float(row.get("delta_quarter")),
                )
            )
        return details

    def _get_category_column(self, session: Session) -> str:
        if self._category_column_name:
            return self._category_column_name
        available = self._load_available_columns(session)
        for candidate in self._CATEGORY_CANDIDATES:
            if candidate in available:
                self._category_column_name = candidate
                return candidate
        if not available:
            fallback = "Продукт"
            logger.warning(
                "Falling back to '%s' column for client activity categories (metadata unavailable)",
                fallback,
            )
            self._category_column_name = fallback
            return fallback
        raise ValueError("Category column was not found in the data source")

    def _deal_amount_expression(self, session: Session, *, metric: str, period: str) -> str:
        column = self._get_deal_amount_column(session)
        if column:
            return f"COALESCE({self._quote_column(column)}, 0)"
        if metric == "issued":
            metric_column = self._ISSUED_COLUMNS.get(period)
        else:
            metric_column = self._REPAID_COLUMNS.get(period)
        if metric_column is None:
            raise ValueError(f"Unsupported metric/period combination: {metric}/{period}")
        return f"COALESCE({metric_column}, 0)"

    def _get_deal_amount_column(self, session: Session) -> str | None:
        if self._deal_amount_column_name is not None:
            return self._deal_amount_column_name
        available = self._load_available_columns(session)
        for candidate in self._DEAL_AMOUNT_CANDIDATES:
            if candidate in available:
                self._deal_amount_column_name = candidate
                return candidate
        self._deal_amount_column_name = None
        return None

    def _load_available_columns(self, session: Session) -> set[str]:
        if self._available_columns is not None:
            return self._available_columns
        query: str
        params: dict[str, Any]
        if self.schema:
            query = (
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :table"
            )
            params = {"schema": self.schema, "table": self.table}
        else:
            query = (
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = :table"
            )
            params = {"table": self.table}
        try:
            rows = session.execute(text(query), params).scalars().all()
            self._available_columns = {str(row) for row in rows if isinstance(row, str)}
        except SQLAlchemyError:  # pragma: no cover - fallback when metadata is unavailable
            logger.warning("Failed to introspect columns for %s", self.qualified_table)
            self._available_columns = set()
        return self._available_columns

    def _build_filters(
        self,
        *,
        departments: Sequence[str] | None = None,
        category: str | None = None,
        client: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        conditions: list[str] = []
        bound: dict[str, Any] = {}

        dep_values = [value for value in (departments or []) if isinstance(value, str) and value.strip()]
        if dep_values:
            conditions.append('\"Департамент\" IN :departments')
            bound["departments"] = dep_values

        if category and category.strip():
            bound["category"] = category.strip()

        if client and client.strip():
            bound["client"] = client.strip()

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)
        return where, bound

    @staticmethod
    def _quote_column(name: str) -> str:
        escaped = name.replace('"', '""')
        return f'"{escaped}"'


def _ensure_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive fallback
        return 0.0


_top_client_activities_service: TopClientActivitiesService | None = None


def set_top_client_activities_service(service: TopClientActivitiesService | None) -> None:
    global _top_client_activities_service
    _top_client_activities_service = service


def get_top_client_activities_service() -> TopClientActivitiesService:
    global _top_client_activities_service
    if _top_client_activities_service is None:
        _top_client_activities_service = TopClientActivitiesService()
    return _top_client_activities_service
