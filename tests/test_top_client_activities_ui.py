from __future__ import annotations

from typing import cast

import plotly.graph_objects as go
import pytest

from app.ui.reports.top_client_activities import (
    _build_period_figure,
    _build_period_title,
    _deserialize_departments,
    _empty_figure,
    _parse_chart_wrapper,
)


def _sample_category_entry() -> dict:
    return {
        "name": "Кредиты",
        "clients": [
            {
                "client": "Клиент 1",
                "issued_day": 15.0,
                "repaid_day": 2.5,
                "issued_week": 30.0,
                "repaid_week": 5.0,
                "issued_quarter": 45.0,
                "repaid_quarter": 7.5,
            },
            {
                "client": "Клиент 2",
                "issued_day": 10.0,
                "repaid_day": 6.0,
                "issued_week": 18.0,
                "repaid_week": 9.0,
                "issued_quarter": 25.0,
                "repaid_quarter": 12.0,
            },
        ],
    }


def test_build_period_figure_produces_dual_traces():
    category_entry = _sample_category_entry()
    figure = _build_period_figure(category_entry, "day")

    assert isinstance(figure, go.Figure)
    figure_obj = cast(go.Figure, figure)
    traces = list(figure_obj.data)
    assert len(traces) == 2

    issued_trace = cast(go.Bar, traces[0])
    repaid_trace = cast(go.Bar, traces[1])
    assert issued_trace.orientation == "h"
    assert repaid_trace.orientation == "h"

    # Issued values remain positive while repaid values are rendered negative for symmetry.
    issued_values = list(issued_trace.x or [])
    repaid_values = list(repaid_trace.x or [])
    assert all(value >= 0 for value in issued_values)
    assert any(value < 0 for value in repaid_values)

    # Custom payload should be present to support drill-down interactions.
    issued_custom = issued_trace.customdata or []
    repaid_custom = repaid_trace.customdata or []
    issued_payloads = [item for item in issued_custom if isinstance(item, dict)]
    repaid_payloads = [item for item in repaid_custom if isinstance(item, dict)]
    assert issued_payloads and issued_payloads[0]["metric"] == "issued"
    assert repaid_payloads and repaid_payloads[0]["metric"] == "repaid"

    # X-axes should mirror for the two panels.
    top_range = figure_obj.layout.xaxis.range
    bottom_range = figure_obj.layout.xaxis2.range
    assert top_range[0] < 0 < top_range[1]
    assert bottom_range[0] < 0 < bottom_range[1]
    assert top_range == pytest.approx(bottom_range)
    assert figure_obj.layout.yaxis.visible is False
    assert figure_obj.layout.yaxis2.visible is False

    assert not figure_obj.layout.title.text


def test_build_period_figure_returns_empty_placeholder_when_no_data():
    category_entry = {"name": "Кредиты", "clients": []}
    figure = _build_period_figure(category_entry, "day")
    annotations = list(figure.layout.annotations)
    assert annotations and annotations[0]["text"] == "Данные отсутствуют"


def test_parse_chart_wrapper_extracts_index_and_period():
    assert _parse_chart_wrapper("client-activities-chart-0-day-wrapper") == (0, "day")
    assert _parse_chart_wrapper("client-activities-chart-2-week-wrapper") == (2, "week")
    assert _parse_chart_wrapper("unexpected") is None


def test_build_period_title_formats_label():
    entry = {"name": "кредиты"}
    assert _build_period_title(entry, "day") == "Кредиты — День"
    assert _build_period_title({}, "week") == "— — Неделя"


def test_deserialize_departments_handles_multiple_shapes():
    assert _deserialize_departments("ДРПГО") == ["ДРПГО"]
    assert _deserialize_departments(["ДРПГО", "__all__"]) == ["ДРПГО"]
    assert _deserialize_departments(None) is None


def test_empty_figure_contains_message():
    figure = _empty_figure("Сообщение")
    annotations = list(figure.layout.annotations)
    assert annotations and annotations[0]["text"] == "Сообщение"
