from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html, no_update
from dash.development.base_component import Component
from plotly.colors import sample_colorscale

from app.dwh import ProductDynamicsService, get_product_dynamics_service
from .registry import ReportEntry, add_report

logger = logging.getLogger(__name__)

FIGURE_BG_COLOR = "rgba(0, 0, 0, 0)"
DEFAULT_FONT_FAMILY = "Open Sans, Arial, sans-serif"
FILTER_CARD_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "24px",
    "border": "none",
    "boxShadow": "none",
}
TRANSPARENT_CARD_BODY_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "22px",
}
CHART_CARD_STYLE = {
    "backgroundColor": "transparent",
    "borderRadius": "24px",
    "border": "1px solid rgba(255, 255, 255, 0.12)",
    "boxShadow": "none",
}
ALL_PRODUCTS_VALUE = "__all_products__"
COLOR_SCALE = [
    [0.0, "rgb(213, 217, 224)"],
    [1.0, "rgb(85, 36, 106)"],
]
BASE_REGION_COLOR = "rgba(213, 217, 224, 0.35)"
REGION_BORDER_COLOR = "rgba(255, 255, 255, 0.35)"
REGION_SELECTED_BORDER_COLOR = "rgb(255, 237, 0)"
HOVER_TEMPLATE = (
    "Название региона: %{customdata[0]}<br>"
    "Объём сделок: %{customdata[1]} млн руб.<extra></extra>"
)
MAP_CARD_MIN_HEIGHT = 560


def _normalize_region_code(value: Any) -> str | None:
    """Normalize region codes to align map geometry and DWH values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            if value != value:  # NaN guard
                return None
            if value.is_integer():
                value = int(value)
        return str(value).strip()
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace(",", ".")
    # Handle float-like codes such as "77.0"
    if normalized.replace(".", "", 1).isdigit():
        try:
            numeric = float(normalized)
        except ValueError:
            pass
        else:
            if numeric.is_integer():
                return str(int(numeric))
    if normalized.isdigit():
        stripped = normalized.lstrip("0")
        return stripped or "0"
    return normalized


def _extract_region_code(point: dict[str, Any]) -> str | None:
    """Extract and normalize the region code from Plotly click data."""
    if not isinstance(point, dict):
        return None
    candidate: Any = None
    customdata = point.get("customdata")
    if isinstance(customdata, (list, tuple)):
        candidate = customdata
        if candidate and isinstance(candidate[0], (list, tuple)):
            candidate = candidate[0]
        if isinstance(candidate, (list, tuple)) and candidate:
            candidate = candidate[-1]
    elif isinstance(customdata, dict):
        for key in ("code", "region_code", "id", "value"):
            if key in customdata:
                candidate = customdata[key]
                break
    if candidate is None:
        candidate = point.get("location") or point.get("text") or point.get("hovertext")
    return _normalize_region_code(candidate)


def _service_or_none() -> ProductDynamicsService | None:
    try:
        return get_product_dynamics_service()
    except ValueError:
        logger.warning("Product dynamics service is not configured (missing DWH connection)")
        return None


def _load_region_geometries() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[3] / "static" / "map" / "russia_map.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("Russia map data not found at %s", path)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse region map data from %s: %s", path, exc)
        return {}

    features = data.get("features") or []
    geometries: dict[str, Any] = {}
    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")

    for feature in features:
        properties = feature.get("properties") or {}
        code_raw = properties.get("name")
        if code_raw is None:
            code_raw = properties.get("я")
        code = _normalize_region_code(code_raw)
        if not code:
            continue

        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates")
        geom_type = geometry.get("type")

        if geom_type == "Polygon":
            polygons = coordinates or []
        elif geom_type == "MultiPolygon":
            polygons = []
            for polygon in coordinates or []:
                polygons.extend(polygon)
        else:
            continue

        processed: list[list[tuple[float, float]]] = []
        for ring in polygons:
            if not isinstance(ring, list):
                continue
            points: list[tuple[float, float]] = []
            for coord in ring:
                if (
                    not isinstance(coord, (list, tuple))
                    or len(coord) < 2
                    or coord[0] is None
                    or coord[1] is None
                ):
                    continue
                x = float(coord[0])
                y = float(coord[1])
                points.append((x, y))
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
            if len(points) >= 3:
                processed.append(points)

        if not processed:
            continue

        center_raw = properties.get("center")
        center: tuple[float, float] | None = None
        if (
            isinstance(center_raw, (list, tuple))
            and len(center_raw) >= 2
            and all(isinstance(value, (int, float)) for value in center_raw[:2])
        ):
            center = (float(center_raw[0]), float(center_raw[1]))

        geometries[code] = {"polygons": processed, "center": center}

    if min_x != float("inf"):
        geometries["_meta"] = {
            "x_min": min_x,
            "x_max": max_x,
            "y_min": min_y,
            "y_max": max_y,
        }

    return geometries


REGION_GEOMETRIES = _load_region_geometries()
META = REGION_GEOMETRIES.get("_meta", {})
MAP_X_RANGE = (
    float(META.get("x_min", 0.0)),
    float(META.get("x_max", 1.0)),
)
MAP_Y_RANGE = (
    float(META.get("y_min", 0.0)),
    float(META.get("y_max", 1.0)),
)


def _load_region_names() -> dict[str, str]:
    """Load official region names from the pre-generated dataset."""
    source = Path(__file__).resolve().parents[3] / "static" / "map" / "russia_regions.json"
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("Fallback region names file %s is unavailable or invalid", source)
        return {}
    names: dict[str, str] = {}
    for item in raw.get("regions") or []:
        code = _normalize_region_code(item.get("code"))
        label = item.get("name")
        if code and isinstance(label, str) and label.strip():
            names[code] = label.strip()
    return names


REGION_NAME_FALLBACKS = _load_region_names()


def layout() -> Component:
    service = _service_or_none()
    product_options: list[dict[str, str]] = []
    dropdown_value = ALL_PRODUCTS_VALUE
    figure = _empty_map_figure("Источник данных недоступен")

    if service:
        try:
            products = service.list_products()
        except Exception as exc:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to fetch product list: %s", exc)
            products = []
        product_options = [{"label": "Все продукты", "value": ALL_PRODUCTS_VALUE}] + [
            {"label": product, "value": product}
            for product in products
            if isinstance(product, str) and product.strip()
        ]
        try:
            totals = service.aggregate_region_totals()
        except Exception as exc:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to fetch initial region totals: %s", exc)
        else:
            figure = _build_map_figure(totals)
    else:
        product_options = [{"label": "Все продукты", "value": ALL_PRODUCTS_VALUE}]

    placeholder_text = "Загрузка..."
    map_card_style = CHART_CARD_STYLE.copy()
    map_card_style["minHeight"] = f"{MAP_CARD_MIN_HEIGHT}px"
    summary_card_style = CHART_CARD_STYLE.copy()
    summary_card_style["minHeight"] = f"{MAP_CARD_MIN_HEIGHT}px"
    map_body_style = TRANSPARENT_CARD_BODY_STYLE.copy()
    map_body_style.update({"height": "100%", "display": "flex", "flexDirection": "column"})
    summary_body_style = TRANSPARENT_CARD_BODY_STYLE.copy()
    summary_body_style.update({
        "height": "100%",
        "display": "flex",
        "flexDirection": "column",
        "gap": "1rem",
        "alignItems": "stretch",
    })

    return dbc.Container(
        [
            dcc.Store(id="regional-selected-region"),
            html.Div(
                html.H3(
                    "Продуктовая аналитика в региональном разрезе",
                    className="mb-0",
                    style={"color": "#FFFFFF", "fontFamily": DEFAULT_FONT_FAMILY},
                )
            ),
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Продукт", className="text-white"),
                                    dcc.Dropdown(
                                        id="regional-product-filter",
                                        options=product_options,
                                        value=dropdown_value if product_options else None,
                                        placeholder="Выберите продукт",
                                        clearable=False,
                                        className="w-100 report-dynamics-dropdown",
                                        style={"backgroundColor": "transparent", "color": "#FFFFFF"},
                                    ),
                                ],
                                xs=12,
                                md=4,
                            )
                        ]
                    ),
                    style=TRANSPARENT_CARD_BODY_STYLE.copy(),
                ),
                className="mt-3",
                style=FILTER_CARD_STYLE.copy(),
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    dcc.Loading(
                                        dcc.Graph(
                                            id="regional-product-map",
                                            figure=figure,
                                            config={"displayModeBar": False},
                                            className="w-100 h-100",
                                            style={"flex": "1 1 auto", "height": "100%"},
                                        ),
                                        type="default",
                                        color="#FFFFFF",
                                        className="dash-spinner flex-fill",
                                        style={"flex": "1 1 auto"},
                                    ),
                                ],
                                style=map_body_style,
                                className="h-100",
                            ),
                            className="mt-3 chart-card flex-fill w-100 h-100",
                            style=map_card_style,
                        ),
                        xs=12,
                        lg=9,
                        className="d-flex",
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5(
                                        "Объём по продуктам",
                                        className="text-white mb-3",
                                        style={"fontFamily": DEFAULT_FONT_FAMILY},
                                    ),
                                    html.Div(
                                        html.Div(placeholder_text, className="text-muted small"),
                                        id="regional-product-summary",
                                        className="d-flex flex-column gap-2",
                                        style={"flex": "0 0 auto", "overflowY": "auto", "maxHeight": f"{MAP_CARD_MIN_HEIGHT // 2}px"},
                                    ),
                                    html.Hr(className="border-secondary my-2"),
                                    html.H5(
                                        "ТОП‑10 сделок",
                                        className="text-white mb-3",
                                        style={"fontFamily": DEFAULT_FONT_FAMILY},
                                    ),
                                    html.Div(
                                        html.Div(placeholder_text, className="text-muted small"),
                                        id="regional-top-deals",
                                        className="d-flex flex-column gap-2",
                                        style={"flex": "1 1 auto", "overflowY": "auto"},
                                    ),
                                ],
                                style=summary_body_style,
                                className="h-100",
                            ),
                            className="mt-3 chart-card flex-fill w-100 h-100",
                            style=summary_card_style,
                        ),
                        xs=12,
                        lg=3,
                        className="d-flex",
                    ),
                ],
                className="g-3 align-items-stretch",
            ),
        ],
        fluid=True,
        className="py-3 report-product-dynamics",
    )


def register_callbacks(app: Dash) -> None:
    @app.callback(
        Output("regional-selected-region", "data"),
        Input("regional-product-map", "clickData"),
        State("regional-selected-region", "data"),
        prevent_initial_call=True,
    )
    def toggle_region(click_data: dict | None, current: str | None):
        if not click_data or not click_data.get("points"):
            return no_update
        point = click_data["points"][0]
        next_code = _extract_region_code(point)
        if not next_code:
            return no_update
        current_normalized = _normalize_region_code(current) if isinstance(current, str) else None
        if current_normalized == next_code:
            return None
        return next_code

    @app.callback(
        Output("regional-product-map", "figure"),
        Output("regional-product-summary", "children"),
        Output("regional-top-deals", "children"),
        Input("regional-product-filter", "value"),
        Input("regional-selected-region", "data"),
    )
    def update_dashboard(selected_value: str | None, selected_region: str | None):
        service = _service_or_none()
        if not service:
            placeholder = _placeholder_message("Источник данных недоступен")
            return _empty_map_figure("Источник данных недоступен"), placeholder, placeholder

        product = None if not selected_value or selected_value == ALL_PRODUCTS_VALUE else selected_value
        selected_code = _normalize_region_code(selected_region) if isinstance(selected_region, str) else None

        try:
            totals_raw = service.aggregate_region_totals(product=product)
            region_name_lookup: dict[str, str] = REGION_NAME_FALLBACKS.copy()
            raw_code_lookup: dict[str, str] = {}
            normalized_totals: list[dict[str, Any]] = []
            for row in totals_raw:
                raw_code = row.get("code")
                normalized_code = _normalize_region_code(raw_code)
                if not normalized_code:
                    continue
                if raw_code is not None:
                    raw_str = str(raw_code).strip()
                    if raw_str:
                        raw_code_lookup.setdefault(normalized_code, raw_str)
                name = row.get("name")
                if isinstance(name, str) and name.strip():
                    region_name_lookup[normalized_code] = name.strip()
                normalized_row = dict(row)
                normalized_row["code"] = normalized_code
                normalized_totals.append(normalized_row)
            totals = normalized_totals
            region_code = raw_code_lookup.get(selected_code) if selected_code else None
            region_filter_name = region_name_lookup.get(selected_code) if selected_code else None
            region_label = region_filter_name or (f"Код {selected_code}" if selected_code else None)
            product_totals = service.aggregate_product_amounts(
                product=product,
                region_code=region_code,
                region_name=region_filter_name,
            )
            top_deals = service.top_deals(
                product=product,
                region_code=region_code,
                region_name=region_filter_name,
                limit=10,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics only
            logger.exception("Failed to update regional analytics for %s: %s", product or "all products", exc)
            placeholder = _placeholder_message("Не удалось загрузить данные")
            return _empty_map_figure("Не удалось загрузить данные"), placeholder, placeholder

        figure = _build_map_figure(totals, selected_region=selected_code)
        return figure, _build_product_summary(product_totals, region_label), _build_top_deals(top_deals, region_label)


def _build_map_figure(rows: list[dict[str, Any]], selected_region: str | None = None) -> go.Figure:
    if not REGION_GEOMETRIES or len(REGION_GEOMETRIES) <= 1:
        return _empty_map_figure("Не найдено данных по карте России")

    values_by_code: dict[str, float] = {}
    labels_by_code: dict[str, str] = {}
    for row in rows:
        normalized_code = _normalize_region_code(row.get("code"))
        if not normalized_code:
            continue
        amount = row.get("total_amount")
        try:
            values_by_code[normalized_code] = float(amount or 0.0)
        except (TypeError, ValueError):
            values_by_code[normalized_code] = 0.0
        label = row.get("name")
        if isinstance(label, str) and label.strip():
            labels_by_code[normalized_code] = label.strip()

    available_codes = {
        _normalize_region_code(code) or str(code)
        for code in REGION_GEOMETRIES
        if code != "_meta"
    }
    missing_codes = sorted(set(values_by_code) - available_codes)
    if missing_codes:
        logger.warning("No geometry found for region codes: %s", ", ".join(missing_codes))

    max_value = max(values_by_code.values(), default=0.0)

    fig = go.Figure()

    font_config = {"family": DEFAULT_FONT_FAMILY, "color": "#FFFFFF"}
    for code_key, geometry in REGION_GEOMETRIES.items():
        if code_key == "_meta":
            continue
        geometry_code = _normalize_region_code(code_key) or str(code_key)
        polygons = geometry.get("polygons") or []
        region_value = values_by_code.get(geometry_code, 0.0)
        color = _color_for_value(region_value, max_value)
        formatted_value = _format_amount(region_value)
        display_label = (
            labels_by_code.get(geometry_code)
            or REGION_NAME_FALLBACKS.get(geometry_code)
            or f"Код {geometry_code}"
        )
        is_selected = bool(selected_region and geometry_code and selected_region == geometry_code)
        border_color = REGION_SELECTED_BORDER_COLOR if is_selected else REGION_BORDER_COLOR
        border_width = 3.0 if is_selected else 0.8
        for polygon in polygons:
            if not isinstance(polygon, list) or len(polygon) < 3:
                continue
            xs = [point[0] for point in polygon]
            ys = [point[1] for point in polygon]
            customdata = [[display_label, formatted_value, geometry_code]] * len(xs)
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="lines",
                    fill="toself",
                    line={"color": border_color, "width": border_width},
                    fillcolor=_selected_fill_color(color) if is_selected else color,
                    hovertemplate=HOVER_TEMPLATE,
                    customdata=customdata,
                    name="",
                    hoverlabel={"bgcolor": "#1f1846", "font": {"color": "#FFFFFF", "family": DEFAULT_FONT_FAMILY}},
                    showlegend=False,
                )
            )

    if max_value > 0:
        fig.add_trace(
            go.Heatmap(
                x=[0, 1],
                y=[0, 1],
                z=[[0, max_value], [0, max_value]],
                colorscale=COLOR_SCALE,
                showscale=True,
                colorbar={
                    "title": {
                        "text": "млн руб.",
                        "side": "top",
                        "font": {"color": "#FFFFFF", "family": DEFAULT_FONT_FAMILY},
                    },
                    "orientation": "h",
                    "outlinecolor": "rgba(0,0,0,0)",
                    "thickness": 14,
                    "tickfont": {"color": "#FFFFFF", "family": DEFAULT_FONT_FAMILY},
                    "ticksuffix": "",
                    "len": 0.45,
                    "x": 0.5,
                    "xanchor": "center",
                    "y": -0.18,
                    "yanchor": "bottom",
                },
                opacity=0,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(
        title="",
        title_font={"family": DEFAULT_FONT_FAMILY, "size": 18, "color": "#FFFFFF"},
        font=font_config,
        margin={"l": 20, "r": 20, "t": 60, "b": 80},
        plot_bgcolor=FIGURE_BG_COLOR,
        paper_bgcolor=FIGURE_BG_COLOR,
        dragmode=False,
        height=MAP_CARD_MIN_HEIGHT,
    )
    fig.update_xaxes(visible=False, range=list(MAP_X_RANGE), fixedrange=True)
    fig.update_yaxes(
        visible=False,
        range=list(MAP_Y_RANGE),
        scaleanchor="x",
        scaleratio=1,
        fixedrange=True,
    )

    if max_value <= 0:
        fig.add_annotation(
            text="Нет данных для выбранного фильтра",
            showarrow=False,
            font={"color": "#FFFFFF", "size": 14, "family": DEFAULT_FONT_FAMILY},
        )

    return fig


def _build_product_summary(rows: list[dict[str, Any]], region_label: str | None = None) -> Component:
    items: list[Component] = []
    for row in rows:
        name = row.get("product")
        if not isinstance(name, str) or not name.strip():
            continue
        amount = _format_amount(row.get("total_amount"))
        items.append(
            html.Div(
                [
                    html.Span(name, className="text-white me-2", title=name),
                    html.Span(f"{amount} млн руб.", className="text-white"),
                ],
                className="d-flex justify-content-between align-items-center small",
            )
        )
    if not items:
        return _placeholder_message("Нет данных")
    content: list[Component] = []
    if region_label:
        content.append(html.Small(f"Регион: {region_label}", className="text-white"))
    content.extend(items)
    return html.Div(content, className="d-flex flex-column gap-2")


def _build_top_deals(rows: list[dict[str, Any]], region_label: str | None = None) -> Component:
    items: list[Component] = []
    for row in rows[:10]:
        client = row.get("client") or "—"
        amount = _format_amount(row.get("amount"))
        items.append(
            html.Div(
                [
                    html.Span(client, className="text-white me-2 text-truncate", style={"maxWidth": "70%"}, title=client),
                    html.Span(f"{amount} млн руб.", className="text-white"),
                ],
                className="d-flex justify-content-between align-items-center small",
            )
        )
    if not items:
        return _placeholder_message("Нет данных")
    content: list[Component] = []
    if region_label:
        content.append(html.Small(f"Регион: {region_label}", className="text-white"))
    content.extend(items)
    return html.Div(content, className="d-flex flex-column gap-2")


def _placeholder_message(text: str) -> Component:
    return html.Div(text, className="text-muted small")


def _empty_map_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font={"color": "#FFFFFF", "size": 14, "family": DEFAULT_FONT_FAMILY},
    )
    fig.update_layout(
        plot_bgcolor=FIGURE_BG_COLOR,
        paper_bgcolor=FIGURE_BG_COLOR,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        font={"family": DEFAULT_FONT_FAMILY, "color": "#FFFFFF"},
        height=MAP_CARD_MIN_HEIGHT,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _color_for_value(value: float, max_value: float) -> str:
    if max_value <= 0 or value <= 0:
        return BASE_REGION_COLOR
    ratio = value / max_value if max_value else 0.0
    ratio = max(0.0, min(1.0, ratio))
    color = sample_colorscale(COLOR_SCALE, [ratio])[0]
    if color.startswith("rgb(") and color.endswith(")"):
        return f"rgba({color[4:-1]}, 0.85)"
    return color


def _selected_fill_color(color: str) -> str:
    try:
        if color.startswith("rgba("):
            parts = color[5:-1].split(",")
        elif color.startswith("rgb("):
            parts = color[4:-1].split(",")
        else:
            return color
        parts = [float(part.strip()) for part in parts]
        if len(parts) >= 3:
            r, g, b = parts[:3]
            alpha = parts[3] if len(parts) > 3 else 1.0
            # lighten colour toward white
            lighten_factor = 0.25
            r = min(255, int(r + (255 - r) * lighten_factor))
            g = min(255, int(g + (255 - g) * lighten_factor))
            b = min(255, int(b + (255 - b) * lighten_factor))
            alpha = min(1.0, alpha + 0.1)
            return f"rgba({r}, {g}, {b}, {alpha:.2f})"
    except Exception:
        return color
    return color


def _format_amount(value: float) -> str:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        normalized = 0.0
    return f"{normalized:,.1f}".replace(",", " ").replace(".", ",")


add_report(
    ReportEntry(
        code="PRODUCT_REGION_ANALYTICS",
        name="Продуктовая аналитика в региональном разрезе",
        route="/reports/product-region-analytics",
        layout=layout,
        register_callbacks=register_callbacks,
        description="Объём сделок по продуктам в разрезе регионов России.",
    )
)
