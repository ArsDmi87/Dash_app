from __future__ import annotations

import logging
from typing import Any, Iterable

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Input, Output, State, dash_table, dcc, html, ctx, no_update
from dash.development.base_component import Component

from app.dwh import (
    CategoryActivities,
    ClientActivityDetailRow,
    TopClientActivitiesService,
    get_top_client_activities_service,
)
from .registry import ReportEntry, add_report

logger = logging.getLogger(__name__)

FIGURE_BG_COLOR = "rgba(0, 0, 0, 0)"
SPINNER_COLOR = "#55246A"
BAR_COLOR_POSITIVE = "#57b26a"
BAR_COLOR_NEGATIVE = "#d85756"
CARD_BORDER_COLOR = "#414042"
PANEL_BORDER_RADIUS = "18px"
MAX_CATEGORIES = 4
PERIODS = ("day", "week", "quarter")
PERIOD_LABELS = {"day": "День", "week": "Неделя", "quarter": "Квартал"}
METRIC_KEYS = [f"{metric}_{period}" for metric in ("issued", "repaid") for period in PERIODS]
METRIC_LABELS = {"issued": "Выдано", "repaid": "Погашено"}
ALL_DEPARTMENTS_VALUE = "__all__"
STORE_DEFAULT = {"categories": []}

TAB_STYLE = {
    "backgroundColor": "transparent",
    "color": "#FFFFFF",
    "fontWeight": "500",
    "padding": "4px 8px",
    "margin": "0 6px 0 0",
    "border": "1px solid rgba(255, 255, 255, 0.4)",
    "borderRadius": "999px",
    "flex": "0 0 100px",
    "textAlign": "center",
}

TAB_SELECTED_STYLE = {
    "backgroundColor": "#FFFFFF",
    "color": "#18122E",
    "fontWeight": "600",
    "padding": "4px 8px",
    "margin": "0 6px 0 0",
    "border": "1px solid rgba(255, 255, 255, 0.4)",
    "borderRadius": "999px",
    "flex": "0 0 100px",
    "textAlign": "center",
}

DETAIL_COLUMNS: list[dict[str, Any]] = [
    {"id": "department", "name": "Департамент"},
    {"id": "manager", "name": "Менеджер"},
    {"id": "client", "name": "Клиент"},
    {"id": "product", "name": "Продукт"},
    {"id": "deal_amount", "name": "Сумма сделки, млн руб."},
    {"id": "delta_day", "name": "Δ день, млн руб."},
    {"id": "delta_week", "name": "Δ неделя, млн руб."},
    {"id": "delta_quarter", "name": "Δ квартал, млн руб."},
]

PANEL_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": PANEL_BORDER_RADIUS,
    "padding": "12px",
    "border": f"1px solid #FFFFFF",
    "boxShadow": "none",
}

CHART_HEIGHT = "285px"

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


def _service_or_none() -> TopClientActivitiesService | None:
    try:
        return get_top_client_activities_service()
    except ValueError:
        logger.warning("Top client activities service is not configured (missing DWH connection)")
        return None


def layout() -> Component:
    service = _service_or_none()
    departments: list[str] = []
    if service:
        try:
            departments = service.list_departments()
        except Exception as exc:  # pragma: no cover - diagnostics only
            logger.exception("Failed to fetch initial client activities metadata: %s", exc)

    department_options = ([{"label": "Все", "value": ALL_DEPARTMENTS_VALUE}] +
                          [{"label": dep, "value": dep} for dep in departments])
    department_value = ALL_DEPARTMENTS_VALUE if department_options else None

    cards: list[dbc.Col] = []
    for idx in range(MAX_CATEGORIES):
        period_columns = []
        for period in PERIODS:
            graph_id = f"client-activities-chart-{idx}-{period}"
            wrapper_id = f"{graph_id}-wrapper"
            period_columns.append(
                dbc.Col(
                    html.Div(
                        dcc.Loading(
                            dcc.Graph(
                                id=graph_id,
                                config={"displayModeBar": False},
                                style={"height": CHART_HEIGHT},
                            ),
                            type="default",
                            color=SPINNER_COLOR,
                            className="dash-spinner",
                        ),
                        id=wrapper_id,
                        n_clicks=0,
                        className="chart-click-wrapper",
                        style={"cursor": "pointer", "height": CHART_HEIGHT},
                    ),
                    xs=12,
                    md=4,
                )
            )
        cards.append(
            dbc.Col(
                html.Div(
                    [
                        html.H5(
                            "—",
                            id=f"client-activities-card-title-{idx}",
                            className="panel-title text-center mb-2 text-white",
                        ),
                        dbc.Row(period_columns, className="gy-4 gx-2"),
                    ],
                    style=PANEL_STYLE,
                    className="w-100 h-100",
                    id=f"client-activities-card-inner-{idx}",
                ),
                xs=12,
                lg=6,
                className="d-flex",
                id=f"client-activities-card-wrapper-{idx}",
                style={"display": "none"},
            )
        )

    return dbc.Container(
        [
            dcc.Store(id="client-activities-data", data=STORE_DEFAULT),
            dcc.Store(id="client-activities-modal-context"),
            html.Div(html.H2("Активность по ТОП 10 клиентам"), className="report-header"),
            dbc.Alert(id="client-activities-feedback", is_open=False, color="info", className="mt-3"),
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Департамент", className="text-white"),
                                    dcc.Dropdown(
                                        id="client-activities-department-filter",
                                        options=department_options,
                                        value=department_value,
                                        placeholder="Выберите департамент",
                                        clearable=False,
                                        className="w-100 report-dynamics-dropdown",
                                        style={
                                            "backgroundColor": "transparent",
                                            "color": "#FFFFFF",
                                        },
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
            dbc.Row(cards, className="gy-4 mt-2"),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(id="client-activities-detail-title")),
                    dbc.ModalBody(
                        [
                            html.Div(
                                dcc.Tabs(
                                    id="client-activities-detail-tabs",
                                    value="issued",
                                    parent_className="modal-metric-tabs",
                                    className="metric-tabs-control d-flex",
                                    style={"display": "flex", "justifyContent": "flex-start", "gap": "6px"},
                                    children=[
                                        dcc.Tab(
                                            label=METRIC_LABELS["issued"],
                                            value="issued",
                                            style=TAB_STYLE,
                                            selected_style=TAB_SELECTED_STYLE,
                                        ),
                                        dcc.Tab(
                                            label=METRIC_LABELS["repaid"],
                                            value="repaid",
                                            style=TAB_STYLE,
                                            selected_style=TAB_SELECTED_STYLE,
                                        ),
                                    ],
                                ),
                                className="mb-3",
                            ),
                            html.Div(
                                dash_table.DataTable(
                                    id="client-activities-detail-table",
                                    data=[],
                                    columns=DETAIL_COLUMNS,
                                    page_size=15,
                                    style_table={
                                        "overflowX": "auto",
                                        "backgroundColor": "transparent",
                                        "border": "none",
                                        "borderRadius": "0",
                                        "boxShadow": "none",
                                    },
                                    style_cell={
                                        "textAlign": "left",
                                        "whiteSpace": "normal",
                                        "border": "none",
                                        "backgroundColor": "transparent",
                                        "fontFamily": "'Open Sans Light', 'Open Sans', Arial, sans-serif",
                                        "fontWeight": "300",
                                        "color": "#FFFFFF",
                                    },
                                    style_header={
                                        "fontWeight": "700",
                                        "backgroundColor": "transparent",
                                        "color": "#FFFFFF",
                                        "border": "none",
                                        "borderBottom": "1px solid rgba(255, 255, 255, 0.2)",
                                    },
                                    style_data={
                                        "border": "none",
                                        "borderBottom": "1px solid rgba(255, 255, 255, 0.12)",
                                    },
                                    style_data_conditional=[
                                        {
                                            "if": {"state": "selected"},
                                            "backgroundColor": "rgba(255, 255, 255, 0.2)",
                                            "color": "#FFFFFF",
                                        },
                                        {
                                            "if": {"state": "active"},
                                            "backgroundColor": "rgba(255, 255, 255, 0.16)",
                                            "color": "#FFFFFF",
                                        },
                                    ],
                                ),
                                className="modal-table-wrapper",
                                style={
                                    "backgroundColor": "transparent",
                                    "padding": "0",
                                    "border": "none",
                                    "borderRadius": "0",
                                },
                            ),
                        ]
                    ),
                    dbc.ModalFooter(
                        dbc.Button("Закрыть", id="client-activities-modal-close", color="secondary")
                    ),
                ],
                id="client-activities-detail-modal",
                is_open=False,
                size="xl",
                centered=True,
            ),
        ],
        fluid=True,
        className="report-product-dynamics report-client-activities gy-4",
        style={"fontFamily": "'Open Sans', Arial, sans-serif"},
    )


def register_callbacks(app) -> None:
    @app.callback(
        Output("client-activities-data", "data"),
        Output("client-activities-feedback", "children"),
        Output("client-activities-feedback", "color"),
        Output("client-activities-feedback", "is_open"),
        *[Output(f"client-activities-card-title-{idx}", "children") for idx in range(MAX_CATEGORIES)],
        *[Output(f"client-activities-card-wrapper-{idx}", "style") for idx in range(MAX_CATEGORIES)],
        Input("client-activities-department-filter", "value"),
    )
    def refresh_categories(department_value):
        service = _service_or_none()
        titles = ["—"] * MAX_CATEGORIES
        styles = [{"display": "none"} for _ in range(MAX_CATEGORIES)]
        if not service:
            message = "Источник данных не настроен. Укажите DWH_DB_DSN."
            return STORE_DEFAULT, message, "warning", True, *titles, *styles

        departments = _deserialize_departments(department_value)
        try:
            categories = service.aggregate_client_activities(
                departments=departments,
                limit_per_category=10,
                category_limit=MAX_CATEGORIES,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to load client activity data: %s", exc)
            message = "Не удалось загрузить данные. Проверьте соединение с DWH."
            return STORE_DEFAULT, message, "danger", True, *titles, *styles

        if not categories:
            message = "Данные отсутствуют для выбранных фильтров."
            return STORE_DEFAULT, message, "secondary", True, *titles, *styles

        store_data = _serialize_categories(categories)
        for idx, entry in enumerate(store_data.get("categories", [])):
            if idx >= MAX_CATEGORIES:
                break
            titles[idx] = _format_category_title(entry.get("name"))
            styles[idx] = {}
        return store_data, "", "info", False, *titles, *styles

    @app.callback(
        *[
            Output(f"client-activities-chart-{idx}-{period}", "figure")
            for idx in range(MAX_CATEGORIES)
            for period in PERIODS
        ],
        Input("client-activities-data", "data"),
    )
    def render_figures(store_data):
        categories = store_data.get("categories") if isinstance(store_data, dict) else []
        outputs: list[go.Figure] = []
        for idx in range(MAX_CATEGORIES):
            category_entry = categories[idx] if isinstance(categories, list) and idx < len(categories) else None
            for period in PERIODS:
                if category_entry:
                    max_value = _max_category_magnitude(category_entry)
                    figure = _build_period_figure(category_entry, period, max_value)
                else:
                    figure = _empty_figure("Нет данных")
                outputs.append(figure)
        return outputs

    wrapper_inputs = [
        Input(f"client-activities-chart-{idx}-{period}-wrapper", "n_clicks_timestamp")
        for idx in range(MAX_CATEGORIES)
        for period in PERIODS
    ]

    @app.callback(
        Output("client-activities-detail-modal", "is_open"),
    Output("client-activities-detail-title", "children"),
    Output("client-activities-detail-tabs", "value"),
        Output("client-activities-modal-context", "data"),
        *wrapper_inputs,
        Input("client-activities-modal-close", "n_clicks"),
        State("client-activities-detail-modal", "is_open"),
        State("client-activities-data", "data"),
        prevent_initial_call=True,
    )
    def toggle_modal(*args):
        *_timestamps, _close_clicks, _is_open, store_data = args

        triggered = ctx.triggered_id
        if triggered == "client-activities-modal-close":
            return False, no_update, "issued", None

        context_info = _parse_chart_wrapper(triggered)
        if not context_info:
            return no_update, no_update, no_update, no_update

        idx, period = context_info
        categories = store_data.get("categories") if isinstance(store_data, dict) else []
        if not isinstance(categories, list) or idx >= len(categories):
            return no_update, no_update, no_update, no_update

        category_entry = categories[idx]
        title = _build_period_title(category_entry, period)
        payload = {
            "category": category_entry.get("name"),
            "period": period,
        }
        return True, title, "issued", payload

    @app.callback(
        Output("client-activities-detail-table", "data"),
        Input("client-activities-modal-context", "data"),
    Input("client-activities-detail-tabs", "value"),
        State("client-activities-department-filter", "value"),
        prevent_initial_call=True,
    )
    def update_detail_table(context_data, metric_value, department_value):
        if not context_data or not metric_value:
            return []

        category = context_data.get("category")
        period = context_data.get("period")
        if not (isinstance(category, str) and isinstance(period, str)):
            return []

        service = _service_or_none()
        if not service:
            return []

        departments = _deserialize_departments(department_value)
        try:
            details = service.fetch_details(
                category=category,
                client=None,
                metric=metric_value,
                period=period,
                departments=departments,
                limit=500,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to load client activity details: %s", exc)
            return []

        return _prepare_detail_rows(details)


def _serialize_categories(categories: Iterable[CategoryActivities]) -> dict[str, Any]:
    prepared: list[dict[str, Any]] = []
    for category in categories:
        clients: list[dict[str, Any]] = []
        for client in category.clients:
            clients.append(
                {
                    "client": client.client,
                    "issued_day": client.issued_day,
                    "repaid_day": client.repaid_day,
                    "issued_week": client.issued_week,
                    "repaid_week": client.repaid_week,
                    "issued_quarter": client.issued_quarter,
                    "repaid_quarter": client.repaid_quarter,
                }
            )
        prepared.append({"name": category.category, "clients": clients, "score": category.score})
    return {"categories": prepared}


def _max_category_magnitude(category_entry: dict[str, Any]) -> float:
    clients = category_entry.get("clients") if isinstance(category_entry, dict) else []
    if not isinstance(clients, list):
        return 0.0
    max_value = 0.0
    for client in clients:
        if not isinstance(client, dict):
            continue
        for key in METRIC_KEYS:
            value = client.get(key)
            try:
                numeric = abs(float(value))
            except (TypeError, ValueError):
                continue
            if numeric > max_value:
                max_value = numeric
    return max_value



def _build_period_figure(category_entry: dict[str, Any], period: str, max_abs_value: float | None = None) -> go.Figure:
    clients = category_entry.get("clients") if isinstance(category_entry, dict) else []
    if not isinstance(clients, list):
        return _empty_figure("Нет данных")

    issued_key = f"issued_{period}"
    repaid_key = f"repaid_{period}"

    positive = [row for row in clients if row.get(issued_key, 0) > 0]
    negative = [row for row in clients if row.get(repaid_key, 0) > 0]

    positive.sort(key=lambda row: row.get(issued_key, 0), reverse=True)
    negative.sort(key=lambda row: row.get(repaid_key, 0), reverse=True)

    positive = positive[:5]
    negative = negative[:5]

    if not positive and not negative:
        return _empty_figure("Данные отсутствуют")

    y_positive: list[str] = [row.get("client") for row in positive]
    x_positive: list[float] = [row.get(issued_key, 0) for row in positive]
    custom_positive: list[Any] = [
        {"category": category_entry.get("name"), "client": row.get("client"), "period": period, "metric": "issued"}
        for row in positive
    ]

    y_negative: list[str] = [row.get("client") for row in negative]
    x_negative: list[float] = [-row.get(repaid_key, 0) for row in negative]
    custom_negative: list[Any] = [
        {"category": category_entry.get("name"), "client": row.get("client"), "period": period, "metric": "repaid"}
        for row in negative
    ]

    max_positive = max(x_positive) if x_positive else 0
    max_negative = max(abs(value) for value in x_negative) if x_negative else 0
    local_limit = max(max_positive, max_negative)
    if max_abs_value is not None and max_abs_value > 0:
        x_limit = max_abs_value
    else:
        x_limit = local_limit if local_limit > 0 else 1

    positive_text = [_format_number(value) for value in x_positive]
    negative_abs = [abs(value) for value in x_negative]
    negative_text = [_format_number(value) for value in negative_abs]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0)

    fig.add_trace(
        go.Bar(
            x=x_positive,
            y=y_positive,
            orientation="h",
            name="Выдано",
            marker_color=BAR_COLOR_POSITIVE,
            customdata=custom_positive,
            text=positive_text,
            hovertemplate="Клиент: %{y}<br>Выдано: %{text} млн руб.<extra></extra>",
            width=0.7,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=x_negative,
            y=y_negative,
            orientation="h",
            name="Погашено",
            marker_color=BAR_COLOR_NEGATIVE,
            customdata=custom_negative,
            text=negative_text,
            hovertemplate="Клиент: %{y}<br>Погашено: %{text} млн руб.<extra></extra>",
            width=0.7,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        bargap=0.3,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    margin={"l": 8, "r": 8, "t": 36, "b": 12},
        showlegend=False,
        font=dict(family="Open Sans, Arial, sans-serif"),
        hoverlabel=dict(font=dict(family="Open Sans, Arial, sans-serif")),
    )

    fig.update_traces(textfont={"size": 9, "family": "Open Sans, Arial, sans-serif"})

    x_range = [-x_limit * 1.05, x_limit * 1.05]
    fig.update_xaxes(
        range=x_range,
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        row=1,
        col=1,
    )
    fig.update_xaxes(
        range=x_range,
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        row=2,
        col=1,
    )

    fig.update_yaxes(
        autorange="reversed",
        visible=False,
        row=1,
        col=1,
    )
    fig.update_yaxes(
        autorange="reversed",
        visible=False,
        row=2,
        col=1,
    )

    for label in y_positive:
        fig.add_annotation(
            x=0,
            y=label,
            xref="x1",
            yref="y1",
            text=label,
            showarrow=False,
            xanchor="right",
            xshift=-4,
            align="right",
            font=dict(size=9, family="Open Sans, Arial, sans-serif", color="#FFFFFF"),
        )

    for label in y_negative:
        fig.add_annotation(
            x=0,
            y=label,
            xref="x2",
            yref="y2",
            text=label,
            showarrow=False,
            xanchor="left",
            xshift=4,
            align="left",
            font=dict(size=9, family="Open Sans, Arial, sans-serif", color="#FFFFFF"),
        )

    period_label = PERIOD_LABELS.get(period, period.title())
    fig.update_layout(
        title=dict(text=period_label, x=0.5, xanchor="center", y=0.98, font=dict(color="#FFFFFF", size=16)),
    )

    return fig


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color="#6e6f7a", size=14),
            )
        ],
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
    )
    return fig


def _deserialize_departments(value: Any) -> list[str] | None:
    if value in (None, ALL_DEPARTMENTS_VALUE):
        return None
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else None
    if isinstance(value, Iterable):
        items = [str(item).strip() for item in value if item not in (None, ALL_DEPARTMENTS_VALUE)]
        return items or None
    return None


def _prepare_detail_rows(rows: Iterable[ClientActivityDetailRow]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            prepared.append(
                {
                    "department": row.get("department"),
                    "manager": row.get("manager"),
                    "client": row.get("client"),
                    "product": row.get("product"),
                    "deal_amount": _format_number(row.get("deal_amount")),
                    "delta_day": _format_number(row.get("delta_day")),
                    "delta_week": _format_number(row.get("delta_week")),
                    "delta_quarter": _format_number(row.get("delta_quarter")),
                }
            )
            continue
        prepared.append(
            {
                "department": getattr(row, "department", None),
                "manager": getattr(row, "manager", None),
                "client": getattr(row, "client", None),
                "product": getattr(row, "product", None),
                "deal_amount": _format_number(getattr(row, "deal_amount", 0.0)),
                "delta_day": _format_number(getattr(row, "delta_day", 0.0)),
                "delta_week": _format_number(getattr(row, "delta_week", 0.0)),
                "delta_quarter": _format_number(getattr(row, "delta_quarter", 0.0)),
            }
        )
    return prepared


def _parse_chart_wrapper(component_id: Any) -> tuple[int, str] | None:
    if not isinstance(component_id, str):
        return None
    if not component_id.startswith("client-activities-chart-") or not component_id.endswith("-wrapper"):
        return None
    trimmed = component_id[len("client-activities-chart-") : -len("-wrapper")]
    parts = trimmed.split("-")
    if len(parts) < 2:
        return None
    idx_str = parts[0]
    period = "-".join(parts[1:])
    try:
        idx = int(idx_str)
    except (TypeError, ValueError):
        return None
    if period not in PERIODS:
        return None
    return idx, period


def _build_period_title(category_entry: dict[str, Any], period: str) -> str:
    category = _format_category_title(category_entry.get("name")) if isinstance(category_entry, dict) else "—"
    period_label = PERIOD_LABELS.get(period, period.title())
    return f"{category} — {period_label}"


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive fallback
        return "0"
    return f"{number:,.2f}".replace(",", " ").replace(".", ",")


def _format_category_title(raw: Any) -> str:
    if not isinstance(raw, str):
        return "—"
    name = raw.strip()
    if not name:
        return "—"
    first = name[0]
    if first.isalpha():
        return first.upper() + name[1:]
    return name


add_report(
    ReportEntry(
        code="CLIENT_ACTIVITY_TOP",
        name="Активность по ТОП 10 клиентам",
        route="/reports/client-activities",
        layout=layout,
        register_callbacks=register_callbacks,
        description="Выдачи и погашения по ключевым клиентам.",
    )
)
