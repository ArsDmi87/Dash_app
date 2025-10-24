from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any, Iterable

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate
from dash.development.base_component import Component

from app.admin import (
    AdminService,
    AdminServiceError,
    CreateGroupPayload,
    CreateRolePayload,
    CreateUserPayload,
    DuplicateGroupError,
    DuplicateRoleError,
    DuplicateUserError,
    GroupSummary,
    ReportSummary,
    RoleSummary,
    UserSummary,
)

logger = logging.getLogger(__name__)

_admin_service: AdminService | None = None


def set_admin_service(service: AdminService | None) -> None:
    """Allow dependency injection for tests and background tasks."""

    global _admin_service
    _admin_service = service


def get_admin_service() -> AdminService:
    global _admin_service
    if _admin_service is None:
        _admin_service = AdminService()
    return _admin_service


def _snapshot(service: AdminService) -> dict[str, list[dict[str, Any]]]:
    try:
        users = [asdict(user) for user in service.list_users(include_inactive=True)]
        roles = [asdict(role) for role in service.list_roles(include_inactive=True)]
        groups = [asdict(group) for group in service.list_groups(include_inactive=True)]
        reports = [asdict(report) for report in service.list_reports(include_inactive=True)]
        return {"users": users, "roles": roles, "groups": groups, "reports": reports}
    except Exception as exc:  # pragma: no cover - defensive logging for runtime issues
        logger.exception("Failed to load admin snapshot: %s", exc)
        return {"users": [], "roles": [], "groups": [], "reports": []}


def layout() -> Component:
    service = get_admin_service()
    snapshot = _snapshot(service)
    return dbc.Container(
        [
            dcc.Store(id="admin-data-store", data=snapshot),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H2("Административная панель"),
                            html.P("Управление пользователями, ролями и группами."),
                        ],
                        md=9,
                    ),
                    dbc.Col(
                        dbc.Button("Обновить", id="admin-refresh-button", color="secondary", className="mt-2 mt-md-0", n_clicks=0),
                        md=3,
                        className="text-md-end",
                    ),
                ]
            ),
            dbc.Alert(id="admin-feedback", is_open=False, color="info", className="mt-3"),
            dbc.Tabs(
                [
                    dbc.Tab(
                        tab_id="tab-users",
                        label="Пользователи",
                        children=[
                            html.Div(id="admin-users-table", className="mt-3"),
                            dbc.Card(
                                [
                                    dbc.CardHeader("Создать или обновить пользователя"),
                                    dbc.CardBody(
                                        dbc.Form(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label("Выберите пользователя для редактирования", html_for="admin-user-selector"),
                                                                dcc.Dropdown(
                                                                    id="admin-user-selector",
                                                                    options=[],
                                                                    placeholder="Новый пользователь",
                                                                    clearable=True,
                                                                    className="w-100",
                                                                ),
                                                                dbc.FormText("Очистите выбор, чтобы создать нового пользователя."),
                                                            ],
                                                            md=12,
                                                        ),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col([
                                                            dbc.Label("Логин", html_for="admin-user-username"),
                                                            dbc.Input(id="admin-user-username", type="text", placeholder="Введите логин"),
                                                        ], md=6),
                                                        dbc.Col([
                                                            dbc.Label("Email", html_for="admin-user-email"),
                                                            dbc.Input(id="admin-user-email", type="email", placeholder="Введите email"),
                                                        ], md=6),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col([
                                                            dbc.Label("Пароль", html_for="admin-user-password"),
                                                            dbc.Input(id="admin-user-password", type="password", placeholder="Задайте пароль"),
                                                        ], md=6),
                                                        dbc.Col([
                                                            dbc.Label("Имя", html_for="admin-user-first-name"),
                                                            dbc.Input(id="admin-user-first-name", type="text", placeholder="Имя"),
                                                        ], md=3),
                                                        dbc.Col([
                                                            dbc.Label("Фамилия", html_for="admin-user-last-name"),
                                                            dbc.Input(id="admin-user-last-name", type="text", placeholder="Фамилия"),
                                                        ], md=3),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col([
                                                            dbc.Label("Роли", html_for="admin-user-roles"),
                                                            dcc.Dropdown(id="admin-user-roles", options=[], value=[], multi=True, className="w-100"),
                                                        ], md=6),
                                                        dbc.Col([
                                                            dbc.Label("Группы", html_for="admin-user-groups"),
                                                            dcc.Dropdown(id="admin-user-groups", options=[], value=[], multi=True, className="w-100"),
                                                        ], md=6),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(dbc.Checkbox(id="admin-user-active", label="Активный", value=True), md=3),
                                                        dbc.Col(
                                                            dbc.Button("Создать", id="admin-user-submit", color="primary", className="mt-2", n_clicks=0),
                                                            md=3,
                                                        ),
                                                        dbc.Col(
                                                            dbc.Button(
                                                                "Сохранить изменения",
                                                                id="admin-user-update",
                                                                color="success",
                                                                className="mt-2",
                                                                n_clicks=0,
                                                                disabled=True,
                                                            ),
                                                            md=4,
                                                        ),
                                                    ],
                                                    className="gy-3",
                                                    align="center",
                                                ),
                                            ]
                                        ),
                                    ),
                                ],
                                className="mt-4",
                            ),
                        ],
                    ),
                    dbc.Tab(
                        tab_id="tab-roles",
                        label="Роли",
                        children=[
                            html.Div(id="admin-roles-table", className="mt-3"),
                            dbc.Card(
                                [
                                    dbc.CardHeader("Создать или обновить роль"),
                                    dbc.CardBody(
                                        dbc.Form(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label("Выберите роль для редактирования", html_for="admin-role-selector"),
                                                                dcc.Dropdown(
                                                                    id="admin-role-selector",
                                                                    options=[],
                                                                    placeholder="Новая роль",
                                                                    clearable=True,
                                                                    className="w-100",
                                                                ),
                                                                dbc.FormText("Очистите выбор, чтобы создать новую роль."),
                                                            ],
                                                            md=12,
                                                        ),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col([
                                                            dbc.Label("Название", html_for="admin-role-name"),
                                                            dbc.Input(id="admin-role-name", type="text", placeholder="Например, manager"),
                                                        ], md=6),
                                                        dbc.Col([
                                                            dbc.Label("Описание", html_for="admin-role-description"),
                                                            dbc.Input(id="admin-role-description", type="text", placeholder="Краткое описание"),
                                                        ], md=6),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Label("Права (JSON)", html_for="admin-role-permissions", className="mt-2"),
                                                dbc.Textarea(
                                                    id="admin-role-permissions",
                                                    placeholder='{"resource": ["read", "write"]}',
                                                    rows=3,
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(dbc.Checkbox(id="admin-role-active", label="Активная", value=True), md=3),
                                                        dbc.Col(
                                                            dbc.Button("Создать", id="admin-role-submit", color="primary", className="mt-2", n_clicks=0),
                                                            md=3,
                                                        ),
                                                        dbc.Col(
                                                            dbc.Button(
                                                                "Сохранить изменения",
                                                                id="admin-role-update",
                                                                color="success",
                                                                className="mt-2",
                                                                n_clicks=0,
                                                                disabled=True,
                                                            ),
                                                            md=4,
                                                        ),
                                                    ],
                                                    className="gy-3",
                                                    align="center",
                                                ),
                                            ]
                                        ),
                                    ),
                                ],
                                className="mt-4",
                            ),
                        ],
                    ),
                    dbc.Tab(
                        tab_id="tab-groups",
                        label="Группы",
                        children=[
                            html.Div(id="admin-groups-table", className="mt-3"),
                            dbc.Card(
                                [
                                    dbc.CardHeader("Создать или обновить группу"),
                                    dbc.CardBody(
                                        dbc.Form(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label("Выберите группу для редактирования", html_for="admin-group-selector"),
                                                                dcc.Dropdown(
                                                                    id="admin-group-selector",
                                                                    options=[],
                                                                    placeholder="Новая группа",
                                                                    clearable=True,
                                                                    className="w-100",
                                                                ),
                                                                dbc.FormText("Очистите выбор, чтобы создать новую группу."),
                                                            ],
                                                            md=12,
                                                        ),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col([
                                                            dbc.Label("Название", html_for="admin-group-name"),
                                                            dbc.Input(id="admin-group-name", type="text", placeholder="Например, analysts"),
                                                        ], md=6),
                                                        dbc.Col([
                                                            dbc.Label("Описание", html_for="admin-group-description"),
                                                            dbc.Input(id="admin-group-description", type="text", placeholder="Краткое описание"),
                                                        ], md=6),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col([
                                                            dbc.Label("Роли", html_for="admin-group-roles"),
                                                            dcc.Dropdown(id="admin-group-roles", options=[], value=[], multi=True, className="w-100"),
                                                        ], md=6),
                                                        dbc.Col(dbc.Checkbox(id="admin-group-active", label="Активная", value=True), md=2),
                                                        dbc.Col(
                                                            dbc.Button("Создать", id="admin-group-submit", color="primary", className="mt-2", n_clicks=0),
                                                            md=2,
                                                        ),
                                                        dbc.Col(
                                                            dbc.Button(
                                                                "Сохранить изменения",
                                                                id="admin-group-update",
                                                                color="success",
                                                                className="mt-2",
                                                                n_clicks=0,
                                                                disabled=True,
                                                            ),
                                                            md=2,
                                                        ),
                                                    ],
                                                    className="gy-3",
                                                    align="center",
                                                ),
                                            ]
                                        ),
                                    ),
                                ],
                                className="mt-4",
                            ),
                        ],
                    ),
                    dbc.Tab(
                        tab_id="tab-reports",
                        label="Отчёты",
                        children=[
                            html.Div(id="admin-reports-table", className="mt-3"),
                            dbc.Card(
                                [
                                    dbc.CardHeader("Назначения отчётов"),
                                    dbc.CardBody(
                                        dbc.Form(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label("Отчёт", html_for="admin-report-selector"),
                                                                dcc.Dropdown(
                                                                    id="admin-report-selector",
                                                                    options=[],
                                                                    placeholder="Выберите отчёт",
                                                                    className="w-100",
                                                                ),
                                                            ],
                                                            md=6,
                                                        ),
                                                    ],
                                                    className="gy-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label("Роли с доступом", html_for="admin-report-role-list"),
                                                                dcc.Dropdown(
                                                                    id="admin-report-role-list",
                                                                    options=[],
                                                                    value=[],
                                                                    multi=True,
                                                                    className="w-100",
                                                                ),
                                                                dbc.FormText("Выберите роли, которым должен быть доступен отчёт."),
                                                            ],
                                                            md=8,
                                                        ),
                                                        dbc.Col(
                                                            dbc.Button(
                                                                "Сохранить",
                                                                id="admin-report-save",
                                                                color="primary",
                                                                className="mt-md-4",
                                                                n_clicks=0,
                                                                disabled=True,
                                                            ),
                                                            md=4,
                                                            className="d-flex align-items-end",
                                                        ),
                                                    ],
                                                    className="gy-3",
                                                ),
                                            ]
                                        ),
                                    ),
                                ],
                                className="mt-4",
                            ),
                        ],
                    ),
                ]
            ),
        ],
        fluid=True,
        className="gy-4",
    )


def _format_permissions(summary: RoleSummary | dict[str, Any]) -> str:
    permissions = summary["permissions"] if isinstance(summary, dict) else summary.permissions
    if not permissions:
        return "—"
    parts: list[str] = []
    for resource, actions in permissions.items():
        actions_list = ", ".join(actions)
        parts.append(f"{resource}: {actions_list}")
    return "; ".join(parts)


def _render_users_table(users: Iterable[dict[str, Any]]) -> Component:
    users_list = list(users)
    if not users_list:
        return dbc.Alert("Пользователи отсутствуют", color="light")

    header = html.Thead(
        html.Tr(
            [
                html.Th("ID"),
                html.Th("Логин"),
                html.Th("Email"),
                html.Th("Полное имя"),
                html.Th("Роли"),
                html.Th("Группы"),
                html.Th("Статус"),
            ]
        )
    )
    rows = []
    for user in users_list:
        roles = ", ".join(user.get("roles") or []) or "—"
        groups = ", ".join(user.get("groups") or []) or "—"
        full_name = user.get("full_name") or "—"
        status = "Активен" if user.get("is_active") else "Отключен"
        rows.append(
            html.Tr(
                [
                    html.Td(user.get("user_id")),
                    html.Td(user.get("username")),
                    html.Td(user.get("email")),
                    html.Td(full_name),
                    html.Td(roles),
                    html.Td(groups),
                    html.Td(status),
                ]
            )
        )
    body = html.Tbody(rows)
    return dbc.Table([header, body], striped=True, bordered=True, hover=True, responsive=True)


def _render_roles_table(roles: Iterable[dict[str, Any]]) -> Component:
    roles_list = list(roles)
    if not roles_list:
        return dbc.Alert("Роли отсутствуют", color="light")

    header = html.Thead(
        html.Tr(
            [
                html.Th("ID"),
                html.Th("Название"),
                html.Th("Описание"),
                html.Th("Права"),
                html.Th("Статус"),
            ]
        )
    )
    rows = []
    for role in roles_list:
        permissions = _format_permissions(role)
        status = "Активна" if role.get("is_active") else "Отключена"
        rows.append(
            html.Tr(
                [
                    html.Td(role.get("role_id")),
                    html.Td(role.get("role_name")),
                    html.Td(role.get("description") or "—"),
                    html.Td(permissions),
                    html.Td(status),
                ]
            )
        )
    body = html.Tbody(rows)
    return dbc.Table([header, body], striped=True, bordered=True, hover=True, responsive=True)


def _render_groups_table(groups: Iterable[dict[str, Any]]) -> Component:
    groups_list = list(groups)
    if not groups_list:
        return dbc.Alert("Группы отсутствуют", color="light")

    header = html.Thead(
        html.Tr(
            [
                html.Th("ID"),
                html.Th("Название"),
                html.Th("Описание"),
                html.Th("Роли"),
                html.Th("Статус"),
            ]
        )
    )
    rows = []
    for group in groups_list:
        role_names = ", ".join(group.get("roles") or []) or "—"
        status = "Активна" if group.get("is_active") else "Отключена"
        rows.append(
            html.Tr(
                [
                    html.Td(group.get("group_id")),
                    html.Td(group.get("group_name")),
                    html.Td(group.get("description") or "—"),
                    html.Td(role_names),
                    html.Td(status),
                ]
            )
        )
    body = html.Tbody(rows)
    return dbc.Table([header, body], striped=True, bordered=True, hover=True, responsive=True)


def _options_from_roles(roles: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"label": role["role_name"], "value": role["role_id"]}
        for role in roles
        if role.get("is_active")
    ]


def _options_from_groups(groups: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"label": group["group_name"], "value": group["group_id"]}
        for group in groups
        if group.get("is_active")
    ]


def _options_from_users(users: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for user in users:
        user_id = user.get("user_id")
        username = user.get("username") or "—"
        full_name = user.get("full_name")
        label = f"{username} — {full_name}" if full_name else username
        status_suffix = " (отключен)" if not user.get("is_active") else ""
        options.append({"label": f"{label}{status_suffix}", "value": user_id})
    return options


def _options_from_reports(reports: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": f"{report.get('report_name') or report.get('report_code')} ({report.get('report_code')})",
            "value": report.get("report_id"),
        }
        for report in reports
        if report.get("is_active")
    ]


def _render_reports_table(reports: Iterable[dict[str, Any]], roles: Iterable[dict[str, Any]]) -> Component:
    reports_list = list(reports)
    if not reports_list:
        return dbc.Alert("Отчёты отсутствуют", color="light")

    role_map: dict[int, list[str]] = {}
    for role in roles:
        for report_id in role.get("report_ids", []) or []:
            role_map.setdefault(report_id, []).append(role.get("role_name"))

    header = html.Thead(
        html.Tr(
            [
                html.Th("ID"),
                html.Th("Код"),
                html.Th("Название"),
                html.Th("Маршрут"),
                html.Th("Статус"),
                html.Th("Роли"),
            ]
        )
    )

    rows = []
    for report in reports_list:
        roles_for_report = ", ".join(sorted(role_map.get(report.get("report_id"), []))) or "—"
        status = "Активен" if report.get("is_active") else "Отключен"
        rows.append(
            html.Tr(
                [
                    html.Td(report.get("report_id")),
                    html.Td(report.get("report_code")),
                    html.Td(report.get("report_name") or "—"),
                    html.Td(report.get("route_path") or "—"),
                    html.Td(status),
                    html.Td(roles_for_report),
                ]
            )
        )

    body = html.Tbody(rows)
    return dbc.Table([header, body], striped=True, bordered=True, hover=True, responsive=True)


def _parse_permissions(raw: str | None) -> dict[str, tuple[str, ...]] | None:
    if not raw or not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - trivial parsing guard
        raise ValueError("Неверный формат JSON для прав доступа") from exc

    if not isinstance(payload, dict):
        raise ValueError("JSON должен описывать объект с ресурсами и действиями")

    normalized: dict[str, tuple[str, ...]] = {}
    for resource, actions in payload.items():
        if not isinstance(resource, str):
            raise ValueError("Название ресурса должно быть строкой")
        if isinstance(actions, str):
            actions_list = [actions]
        elif isinstance(actions, Iterable):
            actions_list = [str(action) for action in actions if action]
        else:
            raise ValueError("Действия для ресурса должны быть списком строк")
        if actions_list:
            normalized[resource] = tuple(actions_list)
    return normalized or None


def _translate_error(err: Exception) -> str:
    if isinstance(err, DuplicateUserError):
        return "Пользователь с таким логином или email уже существует"
    if isinstance(err, DuplicateRoleError):
        return "Роль с таким названием уже существует"
    if isinstance(err, DuplicateGroupError):
        return "Группа с таким названием уже существует"
    if isinstance(err, AdminServiceError):
        return str(err)
    if isinstance(err, ValueError):
        return str(err)
    return "Произошла ошибка при выполнении операции"


def register_callbacks(app: dash.Dash) -> None:
    service = get_admin_service()

    @app.callback(
        Output("admin-users-table", "children"),
        Output("admin-roles-table", "children"),
        Output("admin-groups-table", "children"),
        Output("admin-reports-table", "children"),
        Output("admin-user-selector", "options"),
        Output("admin-user-roles", "options"),
        Output("admin-user-groups", "options"),
        Output("admin-role-selector", "options"),
        Output("admin-group-selector", "options"),
        Output("admin-group-roles", "options"),
        Output("admin-report-selector", "options"),
        Output("admin-report-role-list", "options"),
        Input("admin-data-store", "data"),
    )
    def update_tables(data: dict[str, Any] | None):
        data = data or {"users": [], "roles": [], "groups": [], "reports": []}
        users_children = _render_users_table(data.get("users", []))
        roles_children = _render_roles_table(data.get("roles", []))
        groups_children = _render_groups_table(data.get("groups", []))
        reports_children = _render_reports_table(data.get("reports", []), data.get("roles", []))
        user_options = _options_from_users(data.get("users", []))
        role_options = _options_from_roles(data.get("roles", []))
        group_options = _options_from_groups(data.get("groups", []))
        report_options = _options_from_reports(data.get("reports", []))
        role_selector_options = [
            {
                "label": f"{role.get('role_name')} (неактивна)" if not role.get("is_active") else role.get("role_name"),
                "value": role.get("role_id"),
            }
            for role in data.get("roles", [])
        ]
        group_selector_options = [
            {
                "label": f"{group.get('group_name')} (неактивна)" if not group.get("is_active") else group.get("group_name"),
                "value": group.get("group_id"),
            }
            for group in data.get("groups", [])
        ]
        return (
            users_children,
            roles_children,
            groups_children,
            reports_children,
            user_options,
            role_options,
            group_options,
            role_selector_options,
            group_selector_options,
            role_options,
            report_options,
            role_options,
        )

    @app.callback(
        Output("admin-report-role-list", "value"),
        Output("admin-report-save", "disabled"),
        Input("admin-report-selector", "value"),
        State("admin-data-store", "data"),
        prevent_initial_call=True,
    )
    def populate_report_form(report_id: Any | None, data: dict[str, Any] | None):
        data = data or {"roles": []}
        if not report_id:
            return [], True

        try:
            target_id = int(report_id)
        except (TypeError, ValueError):
            return [], True

        selected_roles: list[int] = []
        for role in data.get("roles", []):
            ids = role.get("report_ids") or []
            if target_id in ids:
                selected_roles.append(int(role.get("role_id")))

        return selected_roles, False

    @app.callback(
        Output("admin-user-username", "value"),
        Output("admin-user-email", "value"),
        Output("admin-user-first-name", "value"),
        Output("admin-user-last-name", "value"),
        Output("admin-user-active", "value"),
        Output("admin-user-roles", "value"),
        Output("admin-user-groups", "value"),
        Output("admin-user-password", "value", allow_duplicate=True),
        Output("admin-user-username", "disabled"),
        Output("admin-user-submit", "disabled"),
        Output("admin-user-update", "disabled"),
        Input("admin-user-selector", "value"),
        State("admin-data-store", "data"),
        prevent_initial_call=True,
    )
    def populate_user_form(user_id: Any | None, data: dict[str, Any] | None):
        data = data or {"users": []}
        defaults = ("", "", "", "", True, [], [], "", False, False, True)
        if not user_id:
            return defaults

        users = data.get("users", [])
        try:
            target_id = int(user_id)
        except (TypeError, ValueError):
            return defaults

        selected = next((user for user in users if user.get("user_id") == target_id), None)
        if not selected:
            return defaults

        username = selected.get("username") or ""
        email = selected.get("email") or ""
        first_name = selected.get("first_name") or ""
        last_name = selected.get("last_name") or ""
        is_active = bool(selected.get("is_active"))
        role_values = [int(role_id) for role_id in (selected.get("role_ids") or [])]
        group_values = [int(group_id) for group_id in (selected.get("group_ids") or [])]

        return (
            username,
            email,
            first_name,
            last_name,
            is_active,
            role_values,
            group_values,
            "",
            True,
            True,
            False,
        )

    @app.callback(
        Output("admin-role-name", "value"),
        Output("admin-role-description", "value"),
        Output("admin-role-permissions", "value"),
        Output("admin-role-active", "value"),
        Output("admin-role-submit", "disabled"),
        Output("admin-role-update", "disabled"),
        Input("admin-role-selector", "value"),
        Input("admin-data-store", "data"),
        prevent_initial_call=True,
    )
    def populate_role_form(role_id: Any | None, data: dict[str, Any] | None):
        data = data or {"roles": []}
        defaults = ("", "", "", True, False, True)
        if not role_id:
            return defaults

        try:
            target_id = int(role_id)
        except (TypeError, ValueError):
            return defaults

        roles = data.get("roles", [])
        selected = next((role for role in roles if role.get("role_id") == target_id), None)
        if not selected:
            return defaults

        name = selected.get("role_name") or ""
        description = selected.get("description") or ""
        permissions_data = selected.get("permissions") or {}
        permissions_text = json.dumps(permissions_data, ensure_ascii=False, indent=2) if permissions_data else ""
        is_active = bool(selected.get("is_active"))

        return (
            name,
            description,
            permissions_text,
            is_active,
            True,
            False,
        )

    @app.callback(
        Output("admin-group-name", "value"),
        Output("admin-group-description", "value"),
        Output("admin-group-roles", "value"),
        Output("admin-group-active", "value"),
        Output("admin-group-submit", "disabled"),
        Output("admin-group-update", "disabled"),
        Input("admin-group-selector", "value"),
        Input("admin-data-store", "data"),
        prevent_initial_call=True,
    )
    def populate_group_form(group_id: Any | None, data: dict[str, Any] | None):
        data = data or {"groups": []}
        defaults = ("", "", [], True, False, True)
        if not group_id:
            return defaults

        try:
            target_id = int(group_id)
        except (TypeError, ValueError):
            return defaults

        groups = data.get("groups", [])
        selected = next((group for group in groups if group.get("group_id") == target_id), None)
        if not selected:
            return defaults

        name = selected.get("group_name") or ""
        description = selected.get("description") or ""
        role_ids = [int(role_id) for role_id in (selected.get("role_ids") or [])]
        is_active = bool(selected.get("is_active"))

        return (
            name,
            description,
            role_ids,
            is_active,
            True,
            False,
        )

    @app.callback(
        Output("admin-data-store", "data", allow_duplicate=True),
        Output("admin-feedback", "children"),
        Output("admin-feedback", "color"),
        Output("admin-feedback", "is_open"),
        Output("admin-user-password", "value", allow_duplicate=True),
        Input("admin-refresh-button", "n_clicks"),
        Input("admin-user-submit", "n_clicks"),
        Input("admin-user-update", "n_clicks"),
    Input("admin-role-submit", "n_clicks"),
    Input("admin-role-update", "n_clicks"),
    Input("admin-group-submit", "n_clicks"),
    Input("admin-group-update", "n_clicks"),
        Input("admin-report-save", "n_clicks"),
        State("admin-user-username", "value"),
        State("admin-user-email", "value"),
        State("admin-user-password", "value"),
        State("admin-user-first-name", "value"),
        State("admin-user-last-name", "value"),
        State("admin-user-active", "value"),
        State("admin-user-roles", "value"),
        State("admin-user-groups", "value"),
        State("admin-user-selector", "value"),
        State("admin-role-name", "value"),
        State("admin-role-description", "value"),
        State("admin-role-active", "value"),
        State("admin-role-permissions", "value"),
        State("admin-role-selector", "value"),
        State("admin-group-name", "value"),
        State("admin-group-description", "value"),
        State("admin-group-active", "value"),
        State("admin-group-roles", "value"),
        State("admin-group-selector", "value"),
        State("admin-report-selector", "value"),
        State("admin-report-role-list", "value"),
        prevent_initial_call=True,
    )
    def handle_actions(
        refresh_clicks: int | None,
        user_clicks: int | None,
        update_clicks: int | None,
        role_clicks: int | None,
        role_update_clicks: int | None,
        group_clicks: int | None,
        group_update_clicks: int | None,
        report_clicks: int | None,
        username: str | None,
        email: str | None,
        password: str | None,
        first_name: str | None,
        last_name: str | None,
        is_active: bool | None,
        role_ids: list[Any] | None,
        group_ids: list[Any] | None,
        selected_user_id: Any | None,
        role_name: str | None,
        role_description: str | None,
        role_active: bool | None,
        role_permissions: str | None,
        selected_role_id: Any | None,
        group_name: str | None,
        group_description: str | None,
        group_active: bool | None,
        group_role_ids: list[Any] | None,
        selected_group_id: Any | None,
        report_id: Any | None,
        report_role_ids: list[Any] | None,
    ):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate

        trigger = ctx.triggered[0]["prop_id"].split(".")[0]

        try:
            if trigger == "admin-refresh-button":
                return _snapshot(service), "Данные обновлены", "success", True, no_update

            if trigger == "admin-role-submit":
                if not role_name or not role_name.strip():
                    return no_update, "Укажите название роли", "warning", True, no_update
                permissions_payload = _parse_permissions(role_permissions)
                if permissions_payload is None and role_permissions is not None and not role_permissions.strip():
                    permissions_payload = {}
                payload = CreateRolePayload(
                    role_name=role_name.strip(),
                    description=role_description.strip() if role_description else None,
                    is_active=bool(role_active),
                    permissions=permissions_payload,
                )
                service.create_role(payload)
                return _snapshot(service), f"Роль «{payload.role_name}» создана", "success", True, ""

            if trigger == "admin-role-update":
                if not selected_role_id:
                    return no_update, "Выберите роль для обновления", "warning", True, no_update
                if not role_name or not role_name.strip():
                    return no_update, "Укажите название роли", "warning", True, no_update
                try:
                    target_role_id = int(selected_role_id)
                except (TypeError, ValueError):
                    return no_update, "Не удалось определить роль", "danger", True, no_update

                permissions_payload = _parse_permissions(role_permissions)
                if permissions_payload is None and role_permissions is not None and not role_permissions.strip():
                    permissions_payload = {}

                updated_role = service.update_role(
                    target_role_id,
                    role_name=role_name.strip(),
                    description=role_description.strip() if role_description else None,
                    is_active=bool(role_active),
                    permissions=permissions_payload,
                )

                return _snapshot(service), f"Роль «{updated_role.role_name}» обновлена", "success", True, ""

            if trigger == "admin-group-submit":
                if not group_name or not group_name.strip():
                    return no_update, "Укажите название группы", "warning", True, no_update
                parsed_role_ids = [int(role_id) for role_id in (group_role_ids or [])]
                payload = CreateGroupPayload(
                    group_name=group_name.strip(),
                    description=group_description.strip() if group_description else None,
                    is_active=bool(group_active),
                    role_ids=parsed_role_ids or None,
                )
                service.create_group(payload)
                return _snapshot(service), f"Группа «{payload.group_name}» создана", "success", True, ""

            if trigger == "admin-group-update":
                if not selected_group_id:
                    return no_update, "Выберите группу для обновления", "warning", True, no_update
                if not group_name or not group_name.strip():
                    return no_update, "Укажите название группы", "warning", True, no_update
                try:
                    target_group_id = int(selected_group_id)
                except (TypeError, ValueError):
                    return no_update, "Не удалось определить группу", "danger", True, no_update

                parsed_role_ids = [int(role_id) for role_id in (group_role_ids or [])]

                updated_group = service.update_group(
                    target_group_id,
                    group_name=group_name.strip(),
                    description=group_description.strip() if group_description else None,
                    is_active=bool(group_active),
                    role_ids=parsed_role_ids,
                )

                return _snapshot(service), f"Группа «{updated_group.group_name}» обновлена", "success", True, ""

            if trigger == "admin-report-save":
                if not report_id:
                    return no_update, "Выберите отчёт", "warning", True, no_update
                try:
                    target_report_id = int(report_id)
                except (TypeError, ValueError):
                    return no_update, "Неверный идентификатор отчёта", "danger", True, no_update

                desired_roles = {int(role_id) for role_id in (report_role_ids or [])}
                current_roles = {
                    role.role_id
                    for role in service.list_roles(include_inactive=True)
                    if target_report_id in (role.report_ids or [])
                }

                to_add = desired_roles - current_roles
                to_remove = current_roles - desired_roles

                for role_id in to_add:
                    service.assign_report_to_role(role_id, target_report_id, can_view=True)
                for role_id in to_remove:
                    service.remove_report_from_role(role_id, target_report_id)

                return _snapshot(service), "Назначения отчёта обновлены", "success", True, ""

            if trigger == "admin-user-submit":
                if not username or not email or not password:
                    return no_update, "Укажите логин, email и пароль", "warning", True, no_update
                parsed_role_ids = [int(role_id) for role_id in (role_ids or [])]
                parsed_group_ids = [int(group_id) for group_id in (group_ids or [])]
                payload = CreateUserPayload(
                    username=username.strip(),
                    email=email.strip(),
                    password=password,
                    first_name=first_name.strip() if first_name else None,
                    last_name=last_name.strip() if last_name else None,
                    is_active=bool(is_active),
                    role_ids=parsed_role_ids or None,
                    group_ids=parsed_group_ids or None,
                )
                service.create_user(payload)
                return _snapshot(service), f"Пользователь «{payload.username}» создан", "success", True, ""

            if trigger == "admin-user-update":
                if not selected_user_id:
                    return no_update, "Выберите пользователя для обновления", "warning", True, no_update
                if not email:
                    return no_update, "Укажите email пользователя", "warning", True, no_update

                try:
                    target_id = int(selected_user_id)
                except (TypeError, ValueError):
                    return no_update, "Не удалось определить пользователя", "danger", True, no_update

                parsed_role_ids = [int(role_id) for role_id in (role_ids or [])]
                parsed_group_ids = [int(group_id) for group_id in (group_ids or [])]

                updated = service.update_user(
                    target_id,
                    email=email.strip(),
                    first_name=first_name.strip() if first_name else None,
                    last_name=last_name.strip() if last_name else None,
                    is_active=bool(is_active),
                    role_ids=parsed_role_ids,
                    group_ids=parsed_group_ids,
                    password=password if password else None,
                )

                return _snapshot(service), f"Пользователь «{updated.username}» обновлён", "success", True, ""

            raise PreventUpdate
        except Exception as exc:  # pragma: no cover - orchestrates feedback for UI consumers
            message = _translate_error(exc)
            return no_update, message, "danger", True, no_update

