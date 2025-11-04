from __future__ import annotations

import logging
from typing import Any, Iterable

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Input, Output, State, dash_table, dcc, html, ctx, no_update
from dash.development.base_component import Component

from app.dwh import (
    ProductDynamicsService,
    ProductFlows,
    ProductTotals,
    get_product_dynamics_service,
)
from .registry import ReportEntry, add_report

logger = logging.getLogger(__name__)

FIGURE_BG_COLOR = "rgba(0, 0, 0, 0)"
ALL_DEPARTMENTS_VALUE = "__all__"
TOP_BAR_COLOR = "#644F94"
FLOW_POSITIVE_COLOR = "#57b26a"
FLOW_NEGATIVE_COLOR = "#d85756"
SPINNER_COLOR = "#FFFFFF"
PANEL_BORDER_RADIUS = "18px"
CARD_BORDER_COLOR = "#FFFFFF"
CHART_CARD_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "24px",
    "border": f"1px solid {CARD_BORDER_COLOR}",
    "boxShadow": "none",
}
TRANSPARENT_CARD_BODY_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "22px",
}
FILTER_CARD_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "24px",
    "border": "none",
    "boxShadow": "none",
}
PANEL_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": PANEL_BORDER_RADIUS,
    "padding": "18px",
    "border": "none",
    "boxShadow": "none",
}

DELTA_DIVIDER_COLOR = "#3E3861"

DETAIL_COLUMNS: list[dict[str, Any]] = [
    {"id": "department", "name": "Департамент"},
    {"id": "manager", "name": "Менеджер"},
    {"id": "client", "name": "Клиент"},
    {"id": "product", "name": "Продукт"},
    {"id": "value", "name": "Сумма, млн руб."},
]

PERIOD_LABELS = [
    ("day", "День"),
    ("week", "Нед."),
    ("quarter", "Кварт."),
    ("year", "Год"),
]


def _service_or_none() -> ProductDynamicsService | None:
    try:
        return get_product_dynamics_service()
    except ValueError:
        logger.warning("Product dynamics service is not configured (missing DWH connection)")
        return None


def layout() -> Component:
    service = _service_or_none()
    departments: list[str] = []
    if service:
        try:
            departments = service.list_departments()
        except Exception as exc:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to fetch initial product dynamics metadata: %s", exc)
    department_options = ([{"label": "Все", "value": ALL_DEPARTMENTS_VALUE}] +
                          [{"label": dep, "value": dep} for dep in departments])
    department_value = ALL_DEPARTMENTS_VALUE if department_options else None

    return dbc.Container(
        [
            dbc.Alert(id="product-dynamics-feedback", is_open=False, color="info", className="mt-3"),
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Департамент", className="text-white"),
                                    dcc.Dropdown(
                                        id="product-dynamics-department-filter",
                                        options=department_options,
                                        value=department_value,
                                        placeholder="Выберите департамент",
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
                style=TRANSPARENT_CARD_BODY_STYLE.copy(),
                ),
                className="mt-3 filter-card",
                style=FILTER_CARD_STYLE.copy(),
            ),
            dbc.Card(
                dbc.CardBody(
                    html.Div(
                        [
                            html.Div(html.H4("Оперативные данные по продуктам", className="mb-0"), className="chart-title"),
                            dcc.Loading(
                                dcc.Graph(
                                    id="product-dynamics-top-chart",
                                    config={"displayModeBar": False},
                                ),
                                type="default",
                                color=SPINNER_COLOR,
                                className="dash-spinner",
                            ),
                        ],
                        className="graph-panel",
                    ),
                    style=TRANSPARENT_CARD_BODY_STYLE.copy(),
                ),
                className="mt-3 chart-card",
                style=CHART_CARD_STYLE.copy(),
            ),
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Div(
                            html.H4("Динамика выдач и погашений", className="mb-0"),
                            className="flow-section-title",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.H5(
                                                "—",
                                                id="product-dynamics-flow-title-0",
                                                className="panel-title text-center mb-3",
                                            ),
                                            dcc.Loading(
                                                dcc.Graph(
                                                    id="product-dynamics-flow-chart-0",
                                                    config={"displayModeBar": False},
                                                    style={"height": "260px", "width": "90%", "margin": "0 auto"},
                                                ),
                                                type="default",
                                                color=SPINNER_COLOR,
                                                className="flex-grow-1 dash-spinner d-flex align-items-center justify-content-center",
                                            ),
                                        ],
                                        style=PANEL_STYLE,
                                        className="w-100 h-100 d-flex flex-column",
                                    ),
                                    xs=12,
                                    sm=6,
                                    xl=3,
                                    className="d-flex",
                                ),
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.H5(
                                                "—",
                                                id="product-dynamics-flow-title-1",
                                                className="panel-title text-center mb-3",
                                            ),
                                            dcc.Loading(
                                                dcc.Graph(
                                                    id="product-dynamics-flow-chart-1",
                                                    config={"displayModeBar": False},
                                                    style={"height": "260px", "width": "90%", "margin": "0 auto"},
                                                ),
                                                type="default",
                                                color=SPINNER_COLOR,
                                                className="flex-grow-1 dash-spinner d-flex align-items-center justify-content-center",
                                            ),
                                        ],
                                        style=PANEL_STYLE,
                                        className="w-100 h-100 d-flex flex-column",
                                    ),
                                    xs=12,
                                    sm=6,
                                    xl=3,
                                    className="d-flex",
                                ),
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.H5(
                                                "—",
                                                id="product-dynamics-flow-title-2",
                                                className="panel-title text-center mb-3",
                                            ),
                                            dcc.Loading(
                                                dcc.Graph(
                                                    id="product-dynamics-flow-chart-2",
                                                    config={"displayModeBar": False},
                                                    style={"height": "260px", "width": "90%", "margin": "0 auto"},
                                                ),
                                                type="default",
                                                color=SPINNER_COLOR,
                                                className="flex-grow-1 dash-spinner d-flex align-items-center justify-content-center",
                                            ),
                                        ],
                                        style=PANEL_STYLE,
                                        className="w-100 h-100 d-flex flex-column",
                                    ),
                                    xs=12,
                                    sm=6,
                                    xl=3,
                                    className="d-flex",
                                ),
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.H5(
                                                "—",
                                                id="product-dynamics-flow-title-3",
                                                className="panel-title text-center mb-3",
                                            ),
                                            dcc.Loading(
                                                dcc.Graph(
                                                    id="product-dynamics-flow-chart-3",
                                                    config={"displayModeBar": False},
                                                    style={"height": "260px", "width": "90%", "margin": "0 auto"},
                                                ),
                                                type="default",
                                                color=SPINNER_COLOR,
                                                className="flex-grow-1 dash-spinner d-flex align-items-center justify-content-center",
                                            ),
                                        ],
                                        style=PANEL_STYLE,
                                        className="w-100 h-100 d-flex flex-column",
                                    ),
                                    xs=12,
                                    sm=6,
                                    xl=3,
                                    className="d-flex",
                                ),
                            ],
                            className="gy-4",
                        ),
                    ],
                    style=TRANSPARENT_CARD_BODY_STYLE.copy(),
                ),
                className="mt-4 chart-card",
                style=CHART_CARD_STYLE.copy(),
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(id="product-dynamics-detail-title")),
                    dbc.ModalBody(
                        html.Div(
                            dash_table.DataTable(
                                id="product-dynamics-detail-table",
                                data=[],
                                columns=DETAIL_COLUMNS,
                                page_size=15,
                                style_table={"overflowX": "auto", "backgroundColor": "transparent"},
                                style_cell={
                                    "textAlign": "left",
                                    "whiteSpace": "normal",
                                    "color": "#FFFFFF",
                                    "backgroundColor": "transparent",
                                    "border": "none",
                                    "fontWeight": 300,
                                },
                                style_header={
                                    "fontWeight": "bold",
                                    "backgroundColor": "transparent",
                                    "color": "#FFFFFF",
                                    "border": "none",
                                    "borderBottom": "1px solid rgba(255, 255, 255, 0.2)",
                                },
                                style_data={
                                    "borderBottom": "1px solid rgba(255, 255, 255, 0.12)",
                                    "borderTop": "none",
                                    "borderLeft": "none",
                                    "borderRight": "none",
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
                        )
                    ),
                    dbc.ModalFooter(
                        dbc.Button("Закрыть", id="product-dynamics-modal-close", color="secondary")
                    ),
                ],
                id="product-dynamics-detail-modal",
                is_open=False,
                size="xl",
                centered=True,
            ),
            dcc.Store(id="product-dynamics-flow-products", data=[]),
        ],
        fluid=True,
        className="report-product-dynamics gy-4",
        style={"fontFamily": "'Open Sans', Arial, sans-serif"},
    )


def register_callbacks(app) -> None:
    @app.callback(
        Output("product-dynamics-top-chart", "figure"),
        Output("product-dynamics-feedback", "children"),
        Output("product-dynamics-feedback", "color"),
        Output("product-dynamics-feedback", "is_open"),
        Input("product-dynamics-department-filter", "value"),
    )
    def refresh_totals(department_value):
        service = _service_or_none()
        if not service:
            message = "Источник данных не настроен. Укажите DWH_DB_DSN."
            empty_figure = _empty_figure(message)
            return (
                empty_figure,
                message,
                "warning",
                True,
            )

        departments = _deserialize_departments(department_value)
        try:
            totals = service.aggregate_product_totals(departments=departments)
        except Exception as exc:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to refresh product totals: %s", exc)
            message = "Не удалось загрузить данные. Проверьте соединение с DWH."
            empty_figure = _empty_figure(message)
            return (
                empty_figure,
                message,
                "danger",
                True,
            )

        if not totals:
            message = "Данные отсутствуют для выбранных фильтров."
            return (
                _empty_figure(message),
                message,
                "secondary",
                True,
            )

        return (
            _build_combined_totals_figure(totals),
            "",
            "info",
            False,
        )

    @app.callback(
        Output("product-dynamics-flow-chart-0", "figure"),
        Output("product-dynamics-flow-chart-1", "figure"),
        Output("product-dynamics-flow-chart-2", "figure"),
        Output("product-dynamics-flow-chart-3", "figure"),
        Output("product-dynamics-flow-title-0", "children"),
        Output("product-dynamics-flow-title-1", "children"),
        Output("product-dynamics-flow-title-2", "children"),
        Output("product-dynamics-flow-title-3", "children"),
        Output("product-dynamics-flow-products", "data"),
        Input("product-dynamics-department-filter", "value"),
    )
    def refresh_flow_charts(department_value):
        service = _service_or_none()
        if not service:
            empty = _empty_figure("Источник данных не настроен. Укажите DWH_DB_DSN.")
            titles = ["—"] * 4
            return (*[empty] * 4, *titles, [None] * 4)

        departments = _deserialize_departments(department_value)
        try:
            totals = service.aggregate_product_totals(departments=departments)
        except Exception as exc:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to load products for flow charts: %s", exc)
            empty = _empty_figure("Не удалось загрузить данные. Проверьте соединение с DWH.")
            titles = ["—"] * 4
            return (*[empty] * 4, *titles, [None] * 4)

        top_products = [row.product for row in totals[:4]]
        figures: list[go.Figure] = []
        titles: list[str] = []
        meta: list[str | None] = []

        for product in top_products:
            try:
                flows = service.aggregate_product_flows(product=product, departments=departments)
            except Exception as exc:  # pragma: no cover - runtime diagnostics only
                logger.exception("Failed to load flows for %s: %s", product, exc)
                figures.append(_empty_figure("Ошибка загрузки данных"))
                titles.append(_normalize_product_title(product))
                meta.append(product)
                continue
            figures.append(_build_flow_figure(flows, product))
            titles.append(_normalize_product_title(product))
            meta.append(product)

        while len(figures) < 4:
            figures.append(_empty_figure("Данные отсутствуют"))
            titles.append("—")
            meta.append(None)

        return (*figures, *titles, meta)

    @app.callback(
        Output("product-dynamics-detail-modal", "is_open"),
        Output("product-dynamics-detail-title", "children"),
        Output("product-dynamics-detail-table", "data"),
        Input("product-dynamics-top-chart", "clickData"),
        Input("product-dynamics-flow-chart-0", "clickData"),
        Input("product-dynamics-flow-chart-1", "clickData"),
        Input("product-dynamics-flow-chart-2", "clickData"),
        Input("product-dynamics-flow-chart-3", "clickData"),
        Input("product-dynamics-modal-close", "n_clicks"),
        State("product-dynamics-detail-modal", "is_open"),
        State("product-dynamics-department-filter", "value"),
        State("product-dynamics-flow-products", "data"),
        prevent_initial_call=True,
    )
    def handle_detail_click(
        top_click,
        flow_click_0,
        flow_click_1,
        flow_click_2,
        flow_click_3,
        close_clicks,
        is_open,
        department_value,
        flow_products,
    ):
        trigger = ctx.triggered_id
        if trigger == "product-dynamics-modal-close":
            return False, no_update, no_update

        service = _service_or_none()
        if not service:
            return no_update, no_update, no_update
        departments = _deserialize_departments(department_value)

        if trigger == "product-dynamics-top-chart":
            product = _extract_top_product(top_click)
            if not product:
                return no_update, no_update, no_update
            details = _safe_fetch_details(service, "ending_balance", departments, product)
            if details is None:
                return no_update, no_update, no_update
            title = f"Детализация: Остаток на конец дня — {product}"
            return True, title, _prepare_detail_rows(details)

        flow_clicks = {
            "product-dynamics-flow-chart-0": flow_click_0,
            "product-dynamics-flow-chart-1": flow_click_1,
            "product-dynamics-flow-chart-2": flow_click_2,
            "product-dynamics-flow-chart-3": flow_click_3,
        }

        if trigger in flow_clicks:
            metric_key, period_label, product = _extract_flow_metric(flow_clicks[trigger])
            if not product and isinstance(flow_products, list):
                try:
                    index = int(trigger.split("-")[-1])
                except ValueError:
                    index = -1
                if 0 <= index < len(flow_products):
                    candidate = flow_products[index]
                    product = candidate if isinstance(candidate, str) else product
            if not metric_key:
                return no_update, no_update, no_update
            details = _safe_fetch_details(service, metric_key, departments, product)
            if details is None:
                return no_update, no_update, no_update
            period_text = period_label or ""
            metric_text = "Выдано" if metric_key.startswith("issued") else "Погашено"
            product_text = product or ""
            title = f"Детализация: {metric_text} - {period_text} - {product_text}".strip(" -")
            return True, title, _prepare_detail_rows(details)

        return no_update, no_update, no_update


def _deserialize_departments(value: str | None) -> list[str] | None:
    if not value or value == ALL_DEPARTMENTS_VALUE:
        return None
    return [value]


def _build_combined_totals_figure(totals: Iterable[ProductTotals]) -> go.Figure:
    rows = list(totals)
    if not rows:
        return _empty_figure("Нет данных для отображения")

    products = [row.product for row in rows]
    display_products = [_normalize_product_title(p) for p in products]
    balances = [row.ending_balance for row in rows]
    text_values = [_format_number(value) for value in balances]
    hover_texts = [f"{product}: {text_values[i]} млн руб." for i, product in enumerate(products)]

    fig = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.04,
        specs=[[{"type": "bar"}, {"type": "scatter"}]],
        column_widths=[0.55, 0.45],
        shared_yaxes=True,
    )

    fig.add_trace(
        go.Bar(
            x=balances,
            y=products,
            orientation="h",
            text=text_values,
            textposition="inside",
            textfont=dict(size=15, color="#FFFFFF", family="Open Sans, Arial, sans-serif"),
            marker_color=TOP_BAR_COLOR,
            hovertext=hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    delta_specs = [
        ("День", "delta_day"),
        ("Неделя", "delta_week"),
        ("Квартал", "delta_quarter"),
        ("Год", "delta_year"),
    ]

    for idx, (label, attr_name) in enumerate(delta_specs):
        values = [getattr(row, attr_name) for row in rows]
        texts = [_format_delta_html(value) for value in values]
        hovers = [
            f"{label}: {'+' if value >= 0 else '-'}{_format_number(abs(value))} млн руб."
            for value in values
        ]
        fig.add_trace(
            go.Scatter(
                x=[idx] * len(products),
                y=products,
                mode="text",
                text=texts,
                textposition="middle center",
                textfont=dict(size=16, color="#FFFFFF", family="Open Sans, Arial, sans-serif"),
                hovertext=hovers,
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=2,
        )
        fig.add_annotation(
            x=idx - 0.35,
            y=1.08,
            xref="x2",
            yref="paper",
            text=label,
            showarrow=False,
            font=dict(size=16, color="#FFFFFF", family="Open Sans, Arial, sans-serif"),
            xanchor="left",
            align="left",
        )

    fig.update_layout(
        height=max(320, 75 * len(rows)),
        margin=dict(l=110, r=60, t=60, b=30),
        plot_bgcolor=FIGURE_BG_COLOR,
        paper_bgcolor=FIGURE_BG_COLOR,
        showlegend=False,
        font=dict(family="Open Sans, Arial, sans-serif"),
    )
    fig.update_xaxes(
        row=1,
        col=1,
        title_text="",
        showticklabels=False,
        showgrid=False,
        zeroline=False,
    )
    fig.update_xaxes(
        row=1,
        col=2,
        range=[-0.5, len(delta_specs) - 0.5],
        visible=False,
        zeroline=False,
        showline=False,
        showgrid=False,
    )
    fig.update_yaxes(
        row=1,
        col=1,
        automargin=True,
        autorange="reversed",
        visible=True,
        tickmode="array",
        ticklen=5,
        ticklabelstandoff=20,
        tickvals=products,
        ticktext=display_products,
        tickfont=dict(color="#FFFFFF", size=18, family="Open Sans, Arial, sans-serif"),
    )
    fig.update_yaxes(
        row=1,
        col=2,
        showticklabels=False,
        autorange="reversed",
        showgrid=False,
        gridcolor="rgba(0,0,0,0)",
    )
    return fig


def _format_delta_html(value: float) -> str:
    arrow_color = "#2e7d32" if value >= 0 else "#c62828"
    arrow = "▲" if value >= 0 else "▼"
    sign = "+" if value >= 0 else "-"
    formatted = _format_number(abs(value)).replace(" ", "&nbsp;")
    return (
        f"<span style='color:{arrow_color}; font-weight:600'>{arrow}</span>"
        f"&nbsp;<span style='color:#FFFFFF'>{sign}&nbsp;{formatted}</span>"
    )

def _build_flow_figure(flows: ProductFlows, product: str) -> go.Figure:
    periods = [label for (_, label) in PERIOD_LABELS]
    x_positions = list(range(len(PERIOD_LABELS)))
    issued_values = [
        flows.issued_day,
        flows.issued_week,
        flows.issued_quarter,
        flows.issued_year,
    ]
    issued_texts = [_format_flow_label(value) for value in issued_values]
    repaid_values = [
        -flows.repaid_day,
        -flows.repaid_week,
        -flows.repaid_quarter,
        -flows.repaid_year,
    ]
    repaid_texts = [_format_flow_label(value) for value in repaid_values]
    issued_hovers = [
        f"{label}: {_format_number(value)} млн руб."
        for value, label in zip(issued_values, periods)
    ]
    repaid_hovers = [
        f"{label}: -{_format_number(abs(value))} млн руб."
        for value, label in zip(repaid_values, periods)
    ]
    width = 0.45
    label_offset = width / 2
    issued_customdata = [
        {"metric": metric, "period": period, "product": product}
        for metric, (period, _) in zip(
            ["issued_day", "issued_week", "issued_quarter", "issued_year"], PERIOD_LABELS
        )
    ]
    repaid_customdata = [
        {"metric": metric, "period": period, "product": product}
        for metric, (period, _) in zip(
            ["repaid_day", "repaid_week", "repaid_quarter", "repaid_year"], PERIOD_LABELS
        )
    ]

    figure = go.Figure(
        data=[
            go.Bar(
                x=x_positions,
                y=issued_values,
                name="Выдано",
                marker=dict(color=FLOW_POSITIVE_COLOR, line=dict(width=0)),
                customdata=issued_customdata,
                hovertext=issued_hovers,
                hovertemplate="%{hovertext}<extra></extra>",
                offset=-width / 2,
                width=width,
                cliponaxis=False,
                text=issued_texts,
                textposition="outside",
                texttemplate="%{text}",
                textfont=dict(color="#FFFFFF", size=13),
            ),
            go.Bar(
                x=x_positions,
                y=repaid_values,
                name="Погашено",
                marker=dict(color=FLOW_NEGATIVE_COLOR, line=dict(width=0)),
                customdata=repaid_customdata,
                hovertext=repaid_hovers,
                hovertemplate="%{hovertext}<extra></extra>",
                offset=width / 2,
                width=width,
                cliponaxis=False,
                text=repaid_texts,
                textposition="outside",
                texttemplate="%{text}",
                textfont=dict(color="#FFFFFF", size=13),
            ),
        ]
    )

    figure.update_layout(
        barmode="overlay",
        bargap=0.6,
        bargroupgap=0,
        plot_bgcolor=FIGURE_BG_COLOR,
        paper_bgcolor=FIGURE_BG_COLOR,
        margin=dict(l=20, r=30, t=20, b=30),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            visible=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(family="Open Sans, Arial, sans-serif"),
        showlegend=False,
    )
    figure.update_xaxes(
        tickmode="array",
        tickvals=[pos + label_offset for pos in x_positions],
        ticktext=periods,
        tickangle=0,
   # title="",
        range=[-0.6, len(PERIOD_LABELS) - 0.2],
    tickfont=dict(color="#FFFFFF"),
    showgrid=False,
    showline=False,
    zeroline=False,
    )
    figure.update_yaxes(visible=False)
    return figure


def _format_number(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def _format_flow_label(value: float) -> str:
    scaled = value / 1000.0
    abs_scaled = abs(scaled)
    if abs_scaled >= 100:
        formatted = f"{scaled:,.0f}"
    elif abs_scaled >= 10:
        formatted = f"{scaled:,.1f}"
    else:
        formatted = f"{scaled:,.2f}"
    return formatted.replace(",", " ")


def _empty_figure(message: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        margin=dict(l=40, r=40, t=40, b=40),
        plot_bgcolor=FIGURE_BG_COLOR,
        paper_bgcolor=FIGURE_BG_COLOR,
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
                font=dict(size=16, color="#6c757d", family="Open Sans, Arial, sans-serif"),
            )
        ],
    )
    return figure


def _ensure_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_product_title(product: Any) -> str:
    if not isinstance(product, str):
        return str(product) if product is not None else "—"
    trimmed = product.strip()
    if not trimmed:
        return "—"
    return trimmed[0].upper() + trimmed[1:]


def _extract_top_product(click_data: Any) -> str | None:
    if not click_data:
        return None
    points = click_data.get("points") or []
    if not points:
        return None
    product = points[0].get("y")
    return product if isinstance(product, str) else None


def _extract_flow_metric(click_data: Any) -> tuple[str | None, str | None, str | None]:
    if not click_data:
        return None, None, None
    points = click_data.get("points") or []
    if not points:
        return None, None, None
    payload = points[0].get("customdata")
    if isinstance(payload, dict):
        metric = payload.get("metric") if isinstance(payload.get("metric"), str) else None
        period = payload.get("period") if isinstance(payload.get("period"), str) else None
        product = payload.get("product") if isinstance(payload.get("product"), str) else None
        return metric, _label_for_period(period), product
    return None, None, None


def _label_for_period(period_code: str | None) -> str | None:
    if not period_code:
        return None
    for code, label in PERIOD_LABELS:
        if code == period_code:
            return label
    return None


def _safe_fetch_details(
    service: ProductDynamicsService,
    metric_key: str,
    departments: list[str] | None,
    product: str | None,
) -> list[Any] | None:
    try:
        return service.fetch_details(metric_key, departments=departments, product=product, limit=500)
    except Exception as exc:  # pragma: no cover - runtime diagnostics only
        logger.exception("Failed to fetch detail rows for %s: %s", metric_key, exc)
        return None


def _prepare_detail_rows(rows: Iterable[Any]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            prepared.append(
                {
                    "department": row.get("department"),
                    "manager": row.get("manager"),
                    "client": row.get("client"),
                    "product": row.get("product"),
                    "value": _format_number(_ensure_float(row.get("value"))),
                }
            )
        else:
            prepared.append(
                {
                    "department": getattr(row, "department", None),
                    "manager": getattr(row, "manager", None),
                    "client": getattr(row, "client", None),
                    "product": getattr(row, "product", None),
                    "value": _format_number(_ensure_float(getattr(row, "value", 0.0))),
                }
            )
    return prepared


add_report(
    ReportEntry(
        code="product_dynamics",
        name="Динамика по продуктам",
        route="/reports/product-dynamics",
        layout=layout,
        register_callbacks=register_callbacks,
        description="Оперативные данные и динамика выдач / погашений по продуктам.",
    )
)
