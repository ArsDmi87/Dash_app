from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Iterable, Sequence

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dash_table, dcc, html, no_update, ctx
from dash.development.base_component import Component
from flask import session as flask_session

from app.dwh import DealPipelineRow, DealPipelineService, get_deal_pipeline_service
from deal_dropdown import DealDropdown
from .registry import ReportEntry, add_report

logger = logging.getLogger(__name__)

DEFAULT_FONT_FAMILY = "Open Sans, Arial, sans-serif"
FILTER_CARD_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "24px",
    "border": "none",
    "boxShadow": "none",
}
FILTER_CARD_BODY_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "22px",
}
TABLE_CARD_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "24px",
    "border": "1px solid rgba(255, 255, 255, 0.12)",
    "boxShadow": "none",
}
SPINNER_COLOR = "#FFFFFF"

STATUS_COLUMNS = ("prkk_status", "ud_status", "dzbi_status", "dakr_status")
STATUS_COLOR_MAP = {
    0: "#f8d7da",
    1: "#d1e7dd",
    2: "#d1e7dd",
}
DECISION_COLOR_MAP = {
    1: "#d1e7dd",
}

TABLE_COLUMNS: list[dict[str, Any]] = [
    {"id": "row_id", "name": "Row ID", "type": "text", "editable": False},
    {"id": "department", "name": "Департамент", "editable": False},
    {"id": "manager", "name": "Менеджер", "editable": False},
    {"id": "client", "name": "Организация", "editable": False},
    {"id": "product", "name": "Продукт", "editable": False},
    {"id": "deal_amount", "name": "Сумма сделки, млн руб.", "editable": False},
    {"id": "sed_load_date", "name": "Дата загрузки в СЭД", "editable": False},
    {"id": "prkk_status", "name": "ПРКК", "editable": False, "type": "numeric"},
    {"id": "prkk_date", "name": "Дата ПРКК", "editable": False},
    {"id": "ud_status", "name": "ЮД", "editable": False, "type": "numeric"},
    {"id": "dzbi_status", "name": "ДЗБИ", "editable": False, "type": "numeric"},
    {"id": "dakr_status", "name": "ДАКР", "editable": False, "type": "numeric"},
    {"id": "kk_decision", "name": "Решение КК", "editable": False, "type": "numeric"},
    {"id": "plan_date", "name": "Плановая дата реализации", "editable": False},
    {"id": "comment", "name": "Комментарий", "type": "text", "editable": True},
    {"id": "_meta", "name": "__meta", "hidden": True},
]


def _pipeline_service_or_none() -> DealPipelineService | None:
    try:
        return get_deal_pipeline_service()
    except ValueError:
        logger.warning("Deal pipeline service is not configured (missing DWH connection)")
        return None


def _current_user_id() -> int | None:
    raw_id = flask_session.get("user_id")
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


def layout() -> Component:
    service = _pipeline_service_or_none()
    departments: list[str] = []
    if service:
        try:
            departments = service.list_departments()
        except Exception as exc:  # pragma: no cover - diagnostics only
            logger.exception("Failed to load initial deal pipeline filters: %s", exc)
    department_options = [{"label": dep, "value": dep} for dep in departments] or []
    department_value = departments or []

    return dbc.Container(
        [
            dcc.Store(id="deal-pipeline-comments-store", data={}),
            html.Div(html.H2("Воронка сделок"), className="report-header"),
            dbc.Alert(id="deal-pipeline-feedback", is_open=False, color="info", className="mt-3"),
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Департамент", className="text-white"),
                                    DealDropdown(
                                        id="deal-pipeline-department-filter",
                                        options=department_options,
                                        value=department_value,
                                        placeholder="Выберите департамент",
                                        multi=True,
                                        clearable=False,
                                        className="w-100 report-dynamics-dropdown",
                                        style={"backgroundColor": "transparent", "color": "#FFFFFF"},
                                    ),
                                ],
                                xs=12,
                                md=4,
                            ),
                        ],
                        className="gy-3",
                    ),
                    style=FILTER_CARD_BODY_STYLE.copy(),
                ),
                className="mt-2 filter-card",
                style=FILTER_CARD_STYLE.copy(),
            ),
            dbc.Card(
                dbc.CardBody(
                    dcc.Loading(
                        dash_table.DataTable(
                            id="deal-pipeline-table",
                            columns=TABLE_COLUMNS,
                            data=[],
                            page_size=20,
                            sort_action="native",
                            filter_action="native",
                            filter_options={"placeholder_text": "Введите значение"},
                            style_table={
                                "overflowX": "auto",
                                "backgroundColor": "transparent",
                                "width": "100%",
                                "minWidth": "100%",
                                "maxWidth": "none",
                                "margin": "0",
                            },
                            css=[
                                {
                                    "selector": ".dash-spreadsheet-container table.cell-table",
                                    "rule": "--hover: rgba(255, 255, 255, 0.2); --text-color: #FFFFFF;",
                                },
                                {
                                    "selector": ".dash-table-container__editor",
                                    "rule": "--text-color: #FFFFFF; color: #FFFFFF;",
                                },
                                {
                                    "selector": ".dash-table-container__editor textarea, .dash-table-container__editor input",
                                    "rule": "color: #FFFFFF !important; caret-color: #FFFFFF !important;",
                                },
                            ],
                            style_cell={
                                "textAlign": "left",
                                "whiteSpace": "normal",
                                "color": "#FFFFFF",
                                "backgroundColor": "transparent",
                                "border": "none",
                                "fontWeight": 300,
                                "minWidth": "110px",
                                "width": "140px",
                                "maxWidth": "240px",
                                "padding": "6px 10px",
                            },
                            style_header={
                                "fontWeight": "600",
                                "backgroundColor": "transparent",
                                "color": "#FFFFFF",
                                "border": "none",
                                "borderBottom": "1px solid rgba(255, 255, 255, 0.2)",
                                "whiteSpace": "normal",
                                "padding": "6px 10px",
                            },
                            style_data={
                                "borderBottom": "1px solid rgba(255, 255, 255, 0.12)",
                                "borderTop": "none",
                                "borderLeft": "none",
                                "borderRight": "none",
                                "padding": "6px 10px",
                            },
                            style_data_conditional=_build_style_conditions(),
                            style_header_conditional=[
                                {"if": {"column_id": "row_id"}, "display": "none"},
                                {"if": {"column_id": "_meta"}, "display": "none"},
                            ],
                            style_filter_conditional=[
                                {"if": {"column_id": "row_id"}, "display": "none"},
                                {"if": {"column_id": "_meta"}, "display": "none"},
                            ],
                            style_cell_conditional=[
                                {"if": {"column_id": "row_id"}, "display": "none"},
                                {"if": {"column_id": "_meta"}, "display": "none"},
                                {
                                    "if": {"column_id": "deal_amount"},
                                    "textAlign": "right",
                                    "minWidth": "120px",
                                },
                                {
                                    "if": {"column_id": "prkk_status"},
                                    "textAlign": "center",
                                },
                                {
                                    "if": {"column_id": "ud_status"},
                                    "textAlign": "center",
                                },
                                {
                                    "if": {"column_id": "dzbi_status"},
                                    "textAlign": "center",
                                },
                                {
                                    "if": {"column_id": "dakr_status"},
                                    "textAlign": "center",
                                },
                                {
                                    "if": {"column_id": "kk_decision"},
                                    "textAlign": "center",
                                },
                                {
                                    "if": {"column_id": "comment"},
                                    "minWidth": "240px",
                                    "width": "320px",
                                    "maxWidth": "420px",
                                    "whiteSpace": "pre-line",
                                },
                            ],
                        ),
                        type="default",
                        color=SPINNER_COLOR,
                        className="dash-spinner",
                    ),
                    style={"padding": "0"},
                    className="p-0",
                ),
                className="mt-4 table-card",
                style=TABLE_CARD_STYLE.copy(),
            ),
        ],
        fluid=True,
        className="report-deal-pipeline gy-4",
        style={
            "fontFamily": DEFAULT_FONT_FAMILY,
            "width": "100%",
            "maxWidth": "100%",
            "paddingLeft": "0",
            "paddingRight": "0",
        },
    )


def _build_style_conditions() -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    circle_style = {
        "backgroundRepeat": "no-repeat",
        "backgroundPosition": "center",
        "backgroundColor": "transparent",
    }

    for column in STATUS_COLUMNS:
        conditions.append(
            {
                "if": {"column_id": column},
                "color": "rgba(0, 0, 0, 0)",
                "backgroundColor": "transparent",
                "background": "transparent",
            }
        )
        for value, color in STATUS_COLOR_MAP.items():
            gradient = (
                f"radial-gradient(circle, {color} 0%, {color} 25%, "
                "transparent 25%, transparent 100%)"
            )
            circle = circle_style | {
                "if": {"filter_query": f"{{{column}}} = {value}", "column_id": column},
                "backgroundImage": gradient,
                "backgroundSize": "25% 25%",
            }
            conditions.append(circle)

    conditions.append(
        {
            "if": {"column_id": "kk_decision"},
            "color": "rgba(0, 0, 0, 0)",
            "backgroundColor": "transparent",
            "background": "transparent",
        }
    )

    for value, color in DECISION_COLOR_MAP.items():
        gradient = (
            f"radial-gradient(circle, {color} 0%, {color} 25%, transparent 25%, transparent 100%)"
        )
        conditions.append(
            circle_style
            | {
                "if": {"filter_query": f"{{kk_decision}} = {value}", "column_id": "kk_decision"},
                "color": "rgba(0, 0, 0, 0)",
                "backgroundImage": gradient,
                "backgroundSize": "25% 25%",
            }
        )
    conditions.extend(
        [
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(255, 255, 255, 0.08)",
            },
            {
                "if": {"state": "active"},
                "backgroundColor": "rgba(255, 255, 255, 0.05)",
            },
        ]
    )
    return conditions


def _format_rows(rows: Iterable[DealPipelineRow], comments: dict[str, str]) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for row in rows:
        comment_value = comments.get(row.row_id)
        if comment_value is None:
            comment_value = row.source_comment or ""
        payload = _build_row_payload(row)
        formatted.append(
            {
                "row_id": row.row_id,
                "department": row.department or "",
                "manager": row.manager or "",
                "client": row.client or "",
                "product": row.product or "",
                "deal_amount": _format_amount(row.deal_amount),
                "sed_load_date": _format_date(row.sed_load_date),
                "prkk_status": row.prkk_status,
                "prkk_date": _format_date(row.prkk_date),
                "ud_status": row.ud_status,
                "dzbi_status": row.dzbi_status,
                "dakr_status": row.dakr_status,
                "kk_decision": row.kk_decision,
                "plan_date": _format_date(row.plan_date),
                "comment": comment_value,
                "_meta": json.dumps(payload, ensure_ascii=False),
            }
        )
    return formatted


def _format_amount(value: float) -> str:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        normalized = 0.0
    return f"{normalized:,.2f}".replace(",", " ").replace(".", ",")


def _format_date(value: date | None) -> str:
    if not value:
        return ""
    return value.strftime("%d.%m.%Y")


def register_callbacks(app: Dash) -> None:
    @app.callback(
        Output("deal-pipeline-table", "data"),
        Output("deal-pipeline-comments-store", "data"),
        Output("deal-pipeline-feedback", "children"),
        Output("deal-pipeline-feedback", "is_open"),
        Input("deal-pipeline-department-filter", "value"),
    )
    def update_deal_pipeline(value: Any):
        service = _pipeline_service_or_none()
        if not service:
            return [], {}, "Источник данных не настроен. Проверьте переменную окружения DWH_DB_DSN.", True

        departments = _normalize_departments(value)
        try:
            rows = service.fetch_pipeline(departments=departments)
        except Exception as exc:  # pragma: no cover - diagnostics only
            logger.exception("Failed to load deal pipeline data: %s", exc)
            return [], {}, "Не удалось загрузить данные. Попробуйте позже.", True

        table_data = _format_rows(rows, {})
        store_data = {row["row_id"]: row["comment"] for row in table_data}
        message = ""
        if not rows:
            message = "Данные не найдены по выбранным фильтрам."
        return table_data, store_data, message, bool(message)

    @app.callback(
        Output("deal-pipeline-comments-store", "data", allow_duplicate=True),
        Output("deal-pipeline-feedback", "children", allow_duplicate=True),
        Output("deal-pipeline-feedback", "is_open", allow_duplicate=True),
        Input("deal-pipeline-table", "data"),
        State("deal-pipeline-comments-store", "data"),
        prevent_initial_call=True,
    )
    def persist_comment(table_data: list[dict[str, Any]], store: dict[str, str]):
        if ctx.triggered_id != "deal-pipeline-table":
            return no_update, no_update, no_update

        if not isinstance(store, dict):
            store = {}
        else:
            store = store or {}
        table_data = table_data or []
        pending_updates: dict[str, str] = {}
        for row in table_data:
            row_id = row.get("row_id")
            if not isinstance(row_id, str) or not row_id.strip():
                continue
            comment_value = row.get("comment")
            if comment_value is None:
                comment = ""
            elif isinstance(comment_value, str):
                comment = comment_value
            else:
                comment = str(comment_value)
            previous = store.get(row_id, "")
            if comment != previous:
                pending_updates[row_id] = comment

        if not pending_updates:
            return store, "", False

        service = _pipeline_service_or_none()
        user_id = _current_user_id()
        success = True
        if service:
            for row_id, comment in pending_updates.items():
                row_payload = _extract_row_payload(table_data, row_id)
                if row_payload is None:
                    continue
                try:
                    service.update_comment(row_key=row_payload, comment=comment, user_id=user_id)
                except Exception as exc:  # pragma: no cover - diagnostics only
                    success = False
                    logger.exception("Failed to save comment for row %s: %s", row_id, exc)
        else:
            success = False

        new_store = {**store, **pending_updates} if success else store
        feedback_message = "Комментарий сохранён." if success else "Не удалось сохранить комментарий."
        return new_store, feedback_message, True


def _build_row_payload(row: DealPipelineRow) -> dict[str, Any]:
    return {
        "row_id": row.row_id,
        "department": row.department,
        "manager": row.manager,
        "client": row.client,
        "product": row.product,
        "sed_load_date": row.sed_load_date.isoformat() if row.sed_load_date else None,
        "plan_date": row.plan_date.isoformat() if row.plan_date else None,
    }


def _extract_row_payload(table_data: list[dict[str, Any]], row_id: str) -> dict[str, Any] | None:
    for row in table_data or []:
        if row.get("row_id") == row_id:
            meta = row.get("_meta")
            if isinstance(meta, str):
                try:
                    return json.loads(meta)
                except json.JSONDecodeError:
                    return None
            if isinstance(meta, dict):
                return meta
            return None
    return None

def _normalize_departments(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, Sequence):
        normalized = []
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip())
        return normalized
    return []


add_report(
    ReportEntry(
        code="deal_pipeline",
        name="Воронка сделок",
        route="/reports/deal-funnel",
        layout=layout,
        register_callbacks=register_callbacks,
        description="Текущий pipeline сделок в работе с контрольными статусами.",
    )
)
