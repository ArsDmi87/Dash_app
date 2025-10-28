from __future__ import annotations

from typing import Any, Iterable, Mapping

import dash_bootstrap_components as dbc
from dash import html
from dash.development.base_component import Component

from app.ui.reports import iter_reports, ReportEntry


def _normalize_actions(raw: Any) -> set[str]:
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, Iterable):
        return {str(item) for item in raw if item is not None}
    return set()


def _has_permission(session_data: Mapping[str, Any], resource: str, action: str = "read") -> bool:
    permissions = session_data.get("permissions")
    if not isinstance(permissions, Mapping):
        return False
    if action in _normalize_actions(permissions.get("*")):
        return True
    return action in _normalize_actions(permissions.get(resource))


def _is_admin_user(session_data: Mapping[str, Any]) -> bool:
    roles = session_data.get("roles")
    if isinstance(roles, str):
        normalized_roles = [roles]
    elif isinstance(roles, Iterable):
        normalized_roles = list(roles)
    else:
        normalized_roles = []

    if any(str(role).strip() == "admin" for role in normalized_roles):
        return True
    return _has_permission(session_data, "admin", "read")


def layout(session_data: Mapping[str, Any]) -> Component:
    """Render the library page with links to accessible dashboards and reports."""
    entries = list(iter_reports())
    registry_by_code = {entry.code: entry for entry in entries if entry.code}
    registry_by_route = {entry.route: entry for entry in entries}
    report_items = _normalize_reports(session_data.get("reports"), registry_by_code, registry_by_route)
    report_items = _ensure_registry_coverage(report_items, entries, include_all=_is_admin_user(session_data))
    cards = [
        _render_card(
            title=report.name,
            subtitle=report.description,
            href=report.href,
            badge=report.code,
            disabled=report.href is None,
        )
        for report in report_items
    ]

    if not cards:
        return dbc.Container(
            dbc.Row(
                dbc.Col(
                    dbc.Alert(
                        "Доступных отчётов пока нет. Обратитесь к администратору для назначения прав.",
                        color="info",
                        className="mt-4",
                    ),
                    md=8,
                    lg=6,
                ),
                className="justify-content-center",
            ),
            fluid=True,
        )

    return dbc.Container(
        [
            html.H2("Мои отчёты"),
            html.P(
                "Выберите отчёт или дашборд из списка ниже, чтобы открыть его в новой вкладке приложения.",
                className="text-muted",
            ),
            dbc.Row(cards, className="gy-4"),
        ],
        fluid=True,
        className="py-3",
    )


class _ReportItem:
    __slots__ = ("code", "name", "href", "description")

    def __init__(self, code: str, name: str, href: str | None, description: str | None) -> None:
        self.code = code
        self.name = name
        self.href = href
        self.description = description or ""


def _normalize_reports(
    raw_reports: Any,
    registry_by_code: Mapping[str, ReportEntry],
    registry_by_route: Mapping[str, ReportEntry],
) -> list[_ReportItem]:
    if not isinstance(raw_reports, Iterable):
        return []

    items: list[_ReportItem] = []
    for raw in raw_reports:
        if not isinstance(raw, Mapping):
            continue
        code = str(raw.get("code") or "").strip()
        if not code:
            continue
        route_path = raw.get("route_path")
        href = str(route_path).strip() or None if isinstance(route_path, str) else None
        description = raw.get("description") if isinstance(raw.get("description"), str) else None
        entry = registry_by_code.get(code) or (registry_by_route.get(href) if href else None)
        name = entry.name if entry else str(raw.get("name") or code).strip()
        description = description or (entry.description if entry else None)
        items.append(_ReportItem(code=code, name=name, href=href, description=description))

    # Preserve ordering while removing duplicates by code.
    seen: set[str] = set()
    deduped: list[_ReportItem] = []
    for item in items:
        if item.code in seen:
            continue
        seen.add(item.code)
        deduped.append(item)
    return deduped


def _ensure_registry_coverage(
    items: list[_ReportItem],
    entries: Iterable[ReportEntry],
    *,
    include_all: bool,
) -> list[_ReportItem]:
    if not include_all:
        return items

    items = list(items)
    existing_codes = {item.code for item in items}
    for entry in entries:
        code = entry.code or entry.route
        if not code or code in existing_codes:
            continue
        items.append(
            _ReportItem(
                code=entry.code or code,
                name=entry.name,
                href=entry.route,
                description=entry.description,
            )
        )
        existing_codes.add(code)
    return items


def _render_card(title: str, subtitle: str, href: str | None, badge: str, disabled: bool = False) -> dbc.Col:
    button_kwargs: dict[str, Any] = {"color": "primary", "disabled": disabled}
    if href and not disabled:
        button_kwargs["href"] = href
    elif not href:
        button_kwargs["color"] = "secondary"

    return dbc.Col(
        dbc.Card(
            [
                dbc.CardBody(
                    [
                        dbc.Badge(badge, pill=True, color="secondary", className="mb-2"),
                        html.H4(title, className="card-title"),
                        html.P(subtitle or "", className="card-text text-muted"),
                        dbc.Button("Открыть", **button_kwargs),
                    ]
                )
            ],
            className="h-100 shadow-sm",
        ),
        xs=12,
        sm=6,
        lg=4,
    )
