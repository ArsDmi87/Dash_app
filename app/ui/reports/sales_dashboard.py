from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Iterable

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, dash_table, dcc, html, ctx
from dash.development.base_component import Component

from app.dwh import (
    DashboardQueryParams,
    DwhDashboardService,
    get_dwh_dashboard_service,
)
from .registry import ReportEntry, add_report

logger = logging.getLogger(__name__)

FIGURE_BG_COLOR = "#ffffff"
DEFAULT_FONT_FAMILY = "Open Sans, Arial, sans-serif"
SPINNER_COLOR = "#55246A"


def _default_interactions() -> dict[str, Any]:
    return {
        "regions": [],
        "categories": [],
        "month_range": [None, None],
        "quantity_range": [None, None],
        "profit_range": [None, None],
    }


TABLE_COLUMNS: list[dict[str, Any]] = [
    {"id": "sale_date", "name": "Дата"},
    {"id": "customer_name", "name": "Клиент"},
    {"id": "region", "name": "Регион"},
    {"id": "customer_segment", "name": "Сегмент"},
    {"id": "category", "name": "Категория"},
    {"id": "product_name", "name": "Товар"},
    {"id": "quantity", "name": "Кол-во"},
    {"id": "total_amount", "name": "Сумма, ₽"},
    {"id": "profit", "name": "Прибыль, ₽"},
    {"id": "sales_channel", "name": "Канал"},
    {"id": "payment_method", "name": "Оплата"},
]


def _service_or_none() -> DwhDashboardService | None:
    try:
        return get_dwh_dashboard_service()
    except ValueError:
        logger.warning("DWH connection is not configured (missing DWH_DB_DSN)")
        return None


def layout() -> Component:
    service = _service_or_none()
    try:
        snapshot = service.get_filters_snapshot() if service else None
    except Exception as exc:  # pragma: no cover - layout fallback
        logger.exception("Failed to load dashboard filters: %s", exc)
        snapshot = None

    if not snapshot:
        return dbc.Container(
            [
                html.Div(html.H2("Дашборд"), className="report-header"),
                dbc.Alert(
                    "Источник данных не настроен. Проверьте переменную окружения DWH_DB_DSN.",
                    color="warning",
                    className="mt-3",
                ),
            ],
            fluid=True,
            className="gy-4",
            style={"fontFamily": DEFAULT_FONT_FAMILY},
        )

    start_date = snapshot.min_date.isoformat() if snapshot.min_date else None
    end_date = snapshot.max_date.isoformat() if snapshot.max_date else None

    return dbc.Container(
        [
            dcc.Store(id="dashboard-interactions-store", data=_default_interactions()),
            html.Div(html.H2("Продажи и прибыль"), className="report-header"),
            dbc.Alert(id="dashboard-feedback", is_open=False, color="info", className="mt-3"),
            dbc.Card(
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Label("Регион"),
                                        dcc.Dropdown(
                                            id="dashboard-region-filter",
                                            options=[{"label": value, "value": value} for value in snapshot.regions],
                                            value=[],
                                            placeholder="Все регионы",
                                            multi=True,
                                            className="w-100",
                                        ),
                                    ],
                                    md=3,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label("Категория"),
                                        dcc.Dropdown(
                                            id="dashboard-category-filter",
                                            options=[{"label": value, "value": value} for value in snapshot.categories],
                                            value=[],
                                            placeholder="Все категории",
                                            multi=True,
                                            className="w-100",
                                        ),
                                    ],
                                    md=3,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label("Сегмент клиента"),
                                        dcc.Dropdown(
                                            id="dashboard-segment-filter",
                                            options=[{"label": value, "value": value} for value in snapshot.segments],
                                            value=[],
                                            placeholder="Все сегменты",
                                            multi=True,
                                            className="w-100",
                                        ),
                                    ],
                                    md=3,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label("Канал продаж"),
                                        dcc.Dropdown(
                                            id="dashboard-channel-filter",
                                            options=[{"label": value, "value": value} for value in snapshot.channels],
                                            value=[],
                                            placeholder="Все каналы",
                                            multi=True,
                                            className="w-100",
                                        ),
                                    ],
                                    md=3,
                                ),
                            ],
                            className="gy-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Label("Период"),
                                        dcc.DatePickerRange(
                                            id="dashboard-date-filter",
                                            start_date=start_date,
                                            end_date=end_date,
                                            display_format="DD.MM.YYYY",
                                            min_date_allowed=snapshot.min_date,
                                            max_date_allowed=snapshot.max_date,
                                            className="w-100",
                                        ),
                                    ],
                                    md=6,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            "Сбросить взаимодействия",
                                            id="dashboard-reset-interactions",
                                            color="secondary",
                                            className="mt-4",
                                        ),
                                    ],
                                    md=3,
                                ),
                            ],
                            className="gy-3",
                        ),
                    ]
                ),
                className="mt-4 filter-card shadow-sm border-0",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(id="dashboard-graph-region", config={"displayModeBar": False}),
                                    type="default",
                                    color=SPINNER_COLOR,
                                )
                            ),
                            className="h-100 chart-card shadow-sm border-0",
                        ),
                        md=6,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="dashboard-graph-monthly",
                                        config={"displayModeBar": True, "modeBarButtonsToAdd": ["select2d"]},
                                    ),
                                    type="default",
                                    color=SPINNER_COLOR,
                                )
                            ),
                            className="h-100 chart-card shadow-sm border-0",
                        ),
                        md=6,
                    ),
                ],
                className="g-4 mt-4",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(id="dashboard-graph-category", config={"displayModeBar": False}),
                                    type="default",
                                    color=SPINNER_COLOR,
                                )
                            ),
                            className="h-100 chart-card shadow-sm border-0",
                        ),
                        md=6,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="dashboard-graph-scatter",
                                        config={"displayModeBar": True, "modeBarButtonsToAdd": ["select2d", "lasso2d"]},
                                    ),
                                    type="default",
                                    color=SPINNER_COLOR,
                                )
                            ),
                            className="h-100 chart-card shadow-sm border-0",
                        ),
                        md=6,
                    ),
                ],
                className="g-4",
            ),
            html.Div(
                html.H4("Детализация продаж", className="mb-0"),
                className="section-title mt-4",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dash_table.DataTable(
                                    id="dashboard-sales-table",
                                    data=[],
                                    columns=TABLE_COLUMNS,
                                    page_size=20,
                                    sort_action="native",
                                    filter_action="native",
                                    style_table={"overflowX": "auto"},
                                    style_cell={
                                        "whiteSpace": "nowrap",
                                        "textAlign": "left",
                                        "fontFamily": DEFAULT_FONT_FAMILY,
                                    },
                                    style_header={"fontWeight": "bold", "fontFamily": DEFAULT_FONT_FAMILY},
                                )
                            ),
                            className="shadow-sm chart-card border-0",
                        ),
                        md=12,
                    ),
                ],
                className="g-0",
            ),
        ],
        fluid=True,
        className="gy-4",
        style={"fontFamily": DEFAULT_FONT_FAMILY},
    )


def register_callbacks(app):
    @app.callback(
        Output("dashboard-interactions-store", "data"),
        Input("dashboard-graph-region", "clickData"),
        Input("dashboard-graph-category", "clickData"),
        Input("dashboard-graph-monthly", "relayoutData"),
        Input("dashboard-graph-scatter", "selectedData"),
        Input("dashboard-reset-interactions", "n_clicks"),
        State("dashboard-interactions-store", "data"),
        prevent_initial_call=True,
    )
    def update_interactions(region_click, category_click, monthly_relayout, scatter_selected, reset_clicks, current):
        current = deepcopy(current) if current else _default_interactions()
        trigger = ctx.triggered_id
        if trigger == "dashboard-reset-interactions":
            return _default_interactions()

        if trigger == "dashboard-graph-region":
            selection = _extract_label(region_click)
            current["regions"] = [] if not selection or current.get("regions") == [selection] else [selection]
        elif trigger == "dashboard-graph-category":
            selection = _extract_x(category_click)
            current["categories"] = [] if not selection or current.get("categories") == [selection] else [selection]
        elif trigger == "dashboard-graph-monthly":
            current["month_range"] = _extract_month_range(monthly_relayout)
        elif trigger == "dashboard-graph-scatter":
            qty_range, profit_range = _extract_scatter_ranges(scatter_selected)
            current["quantity_range"] = qty_range
            current["profit_range"] = profit_range

        return current

    @app.callback(
        Output("dashboard-graph-region", "figure"),
        Output("dashboard-graph-monthly", "figure"),
        Output("dashboard-graph-category", "figure"),
        Output("dashboard-graph-scatter", "figure"),
        Output("dashboard-sales-table", "data"),
        Output("dashboard-sales-table", "columns"),
        Output("dashboard-feedback", "children"),
        Output("dashboard-feedback", "color"),
        Output("dashboard-feedback", "is_open"),
        Input("dashboard-region-filter", "value"),
        Input("dashboard-category-filter", "value"),
        Input("dashboard-segment-filter", "value"),
        Input("dashboard-channel-filter", "value"),
        Input("dashboard-date-filter", "start_date"),
        Input("dashboard-date-filter", "end_date"),
        Input("dashboard-interactions-store", "data"),
    )
    def refresh_dashboard(region_filter, category_filter, segment_filter, channel_filter, start_date, end_date, interactions):
        service = _service_or_none()
        if not service:
            message = "Источник данных не настроен. Укажите DWH_DB_DSN."
            empty = _empty_figure(message)
            return (
                empty,
                empty,
                empty,
                empty,
                [],
                TABLE_COLUMNS,
                message,
                "warning",
                True,
            )

        interactions = interactions or _default_interactions()
        params = _compose_query_params(
            region_filter,
            category_filter,
            segment_filter,
            channel_filter,
            start_date,
            end_date,
            interactions,
        )

        try:
            region_data = service.region_totals(params)
            monthly_data = service.monthly_revenue(params)
            category_data = service.category_totals(params)
            scatter_data = service.profit_vs_quantity(params)
            table_rows = service.detailed_sales(params)

            return (
                _build_region_figure(region_data),
                _build_monthly_figure(monthly_data),
                _build_category_figure(category_data),
                _build_scatter_figure(scatter_data),
                _prepare_table_rows(table_rows),
                TABLE_COLUMNS,
                "",
                "info",
                False,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            logger.exception("Dashboard refresh failed: %s", exc)
            message = "Не удалось загрузить данные. Проверьте соединение с DWH."
            empty = _empty_figure(message)
            return (
                empty,
                empty,
                empty,
                empty,
                [],
                TABLE_COLUMNS,
                message,
                "danger",
                True,
            )


def _extract_label(click_data: Any) -> str | None:
    if not click_data:
        return None
    points = click_data.get("points") or []
    if not points:
        return None
    return points[0].get("label")


def _extract_x(click_data: Any) -> str | None:
    if not click_data:
        return None
    points = click_data.get("points") or []
    if not points:
        return None
    value = points[0].get("x")
    return str(value) if value is not None else None


def _extract_month_range(relayout: Any) -> list[str | None]:
    if not relayout:
        return [None, None]
    if relayout.get("xaxis.autorange"):
        return [None, None]
    start = relayout.get("xaxis.range[0]")
    end = relayout.get("xaxis.range[1]")
    if start and end:
        return [start, end]
    return [None, None]


def _extract_scatter_ranges(selected: Any) -> tuple[list[float | None], list[float | None]]:
    if not selected:
        return ([None, None], [None, None])
    range_box = selected.get("range") or {}
    qty_range = range_box.get("x")
    profit_range = range_box.get("y")
    if qty_range and profit_range:
        return ([float(qty_range[0]), float(qty_range[1])], [float(profit_range[0]), float(profit_range[1])])

    points = selected.get("points") or []
    if not points:
        return ([None, None], [None, None])
    quantities = [float(point.get("x")) for point in points if point.get("x") is not None]
    profits = [float(point.get("y")) for point in points if point.get("y") is not None]
    if not quantities or not profits:
        return ([None, None], [None, None])
    return ([min(quantities), max(quantities)], [min(profits), max(profits)])


def _compose_query_params(
    regions: Iterable[str] | None,
    categories: Iterable[str] | None,
    segments: Iterable[str] | None,
    channels: Iterable[str] | None,
    start_date: str | None,
    end_date: str | None,
    interactions: dict[str, Any],
) -> DashboardQueryParams:
    def parse_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None

    region_list = list(regions or [])
    if not region_list:
        region_list = list(interactions.get("regions") or [])

    category_list = list(categories or [])
    if not category_list:
        category_list = list(interactions.get("categories") or [])

    start = parse_date(start_date)
    end = parse_date(end_date)

    month_range = interactions.get("month_range") or [None, None]
    month_start = parse_date(month_range[0]) if month_range[0] else None
    month_end = parse_date(month_range[1]) if len(month_range) > 1 and month_range[1] else None

    if month_start:
        start = max(start, month_start) if start else month_start
    if month_end:
        end = min(end, month_end) if end else month_end

    qty_range = interactions.get("quantity_range") or [None, None]
    profit_range = interactions.get("profit_range") or [None, None]

    params = DashboardQueryParams(
        regions=region_list or None,
        categories=category_list or None,
        segments=list(segments or []) or None,
        channels=list(channels or []) or None,
        start_date=start,
        end_date=end,
    )

    qty_min = qty_range[0] if isinstance(qty_range, list) and qty_range else None
    qty_max = qty_range[1] if isinstance(qty_range, list) and len(qty_range) > 1 else None
    profit_min = profit_range[0] if isinstance(profit_range, list) and profit_range else None
    profit_max = profit_range[1] if isinstance(profit_range, list) and len(profit_range) > 1 else None

    if qty_min is not None:
        params.quantity_min = float(qty_min)
    if qty_max is not None:
        params.quantity_max = float(qty_max)
    if profit_min is not None:
        params.profit_min = float(profit_min)
    if profit_max is not None:
        params.profit_max = float(profit_max)

    return params


def _build_region_figure(data: list[dict[str, Any]]) -> go.Figure:
    if not data:
        return _empty_figure("Нет данных по регионам")
    labels = [item["region"] for item in data]
    values = [item["total_amount"] for item in data]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.35,
                hovertemplate="Регион: %{label}<br>Продажи: %{value:,.0f} ₽<extra></extra>",
            )
        ]
    )
    fig.update_layout(title="Распределение продаж по регионам")
    fig.update_layout(plot_bgcolor=FIGURE_BG_COLOR, paper_bgcolor=FIGURE_BG_COLOR)
    fig.update_layout(font={"family": DEFAULT_FONT_FAMILY})
    return fig


def _build_monthly_figure(data: list[dict[str, Any]]) -> go.Figure:
    if not data:
        return _empty_figure("Нет данных по месяцам")
    x_values = [datetime.combine(item["month_start"], datetime.min.time()) for item in data]
    y_values = [item["total_revenue"] for item in data]
    months_ru = [_format_month(value) for value in x_values]
    fig = go.Figure(
        data=[
            go.Scatter(
                x=x_values,
                y=y_values,
                customdata=months_ru,
                mode="lines+markers",
                hovertemplate="Месяц: %{customdata}<br>Выручка: %{y:,.0f} ₽<extra></extra>",
            )
        ]
    )
    fig.update_layout(title="Динамика продаж по месяцам", xaxis_title="Месяц", yaxis_title="Выручка, ₽")
    fig.update_xaxes(tickvals=x_values, ticktext=months_ru)
    fig.update_layout(plot_bgcolor=FIGURE_BG_COLOR, paper_bgcolor=FIGURE_BG_COLOR)
    fig.update_layout(font={"family": DEFAULT_FONT_FAMILY})
    return fig


def _build_category_figure(data: list[dict[str, Any]]) -> go.Figure:
    if not data:
        return _empty_figure("Нет данных по категориям")
    fig = go.Figure(
        data=[
            go.Bar(
                x=[item["category"] for item in data],
                y=[item["total_amount"] for item in data],
                hovertemplate="Категория: %{x}<br>Продажи: %{y:,.0f} ₽<extra></extra>",
            )
        ]
    )
    fig.update_layout(title="Продажи по категориям", xaxis_title="Категория", yaxis_title="Выручка, ₽")
    fig.update_layout(plot_bgcolor=FIGURE_BG_COLOR, paper_bgcolor=FIGURE_BG_COLOR)
    fig.update_layout(font={"family": DEFAULT_FONT_FAMILY})
    return fig


def _build_scatter_figure(data: list[dict[str, Any]]) -> go.Figure:
    if not data:
        return _empty_figure("Нет данных для точечной диаграммы")

    by_category: dict[str | None, list[dict[str, Any]]] = {}
    for row in data:
        by_category.setdefault(row.get("category"), []).append(row)

    max_amount = max((row.get("total_amount") or 0) for row in data) or 1
    scale = max_amount / 30

    fig = go.Figure()
    for category, rows in by_category.items():
        quantities = [row.get("quantity") for row in rows]
        profits = [row.get("profit") for row in rows]
        amounts = [row.get("total_amount") or 0 for row in rows]
        sizes = [max(8, min(32, amount / scale)) for amount in amounts]
        custom = [
            (
                row.get("sale_id"),
                row.get("sale_date"),
                amount,
            )
            for row, amount in zip(rows, amounts)
        ]
        fig.add_trace(
            go.Scatter(
                x=quantities,
                y=profits,
                mode="markers",
                marker={"size": sizes, "opacity": 0.7},
                name=category or "Без категории",
                customdata=custom,
                hovertemplate=(
                    "Категория: %{fullData.name}<br>"
                    "Количество: %{x}<br>Прибыль: %{y:,.0f} ₽<br>"
                    "Сумма: %{customdata[2]:,.0f} ₽<br>"
                    "ID продажи: %{customdata[0]}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="Прибыль vs Количество", xaxis_title="Количество", yaxis_title="Прибыль, ₽", dragmode="select"
    )
    fig.update_layout(plot_bgcolor=FIGURE_BG_COLOR, paper_bgcolor=FIGURE_BG_COLOR)
    fig.update_layout(font={"family": DEFAULT_FONT_FAMILY})
    return fig


def _prepare_table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in rows:
        new_row = dict(row)
        sale_date = new_row.get("sale_date")
        if isinstance(sale_date, (date, datetime)):
            new_row["sale_date"] = sale_date.strftime("%d.%m.%Y")

        total_amount = new_row.get("total_amount")
        if isinstance(total_amount, (int, float)):
            formatted = f"{total_amount:,.1f}".replace(",", " ").replace(".", ",")
            new_row["total_amount"] = formatted

        profit = new_row.get("profit")
        if isinstance(profit, (int, float)):
            formatted_profit = f"{profit:,.1f}".replace(",", " ").replace(".", ",")
            new_row["profit"] = formatted_profit

        prepared.append(new_row)
    return prepared


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 14},
            }
        ],
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )
    fig.update_layout(plot_bgcolor=FIGURE_BG_COLOR, paper_bgcolor=FIGURE_BG_COLOR)
    fig.update_layout(font={"family": DEFAULT_FONT_FAMILY})
    return fig


def _format_month(value: datetime) -> str:
    month_map = {
        1: "янв",
        2: "фев",
        3: "мар",
        4: "апр",
        5: "май",
        6: "июн",
        7: "июл",
        8: "авг",
        9: "сен",
        10: "окт",
        11: "ноя",
        12: "дек",
    }
    month = month_map.get(value.month, "")
    return f"{value.day} {month} {value.year}".strip()


add_report(
    ReportEntry(
        code="sales_dashboard",
        name="Интерактивный дашборд",
        route="/dashboard",
        layout=layout,
        register_callbacks=register_callbacks,
        permission_resource="dashboard",
        description="Просмотр ключевых метрик продаж и прибыли в режиме реального времени.",
    )
)
