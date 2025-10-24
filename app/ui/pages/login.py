from __future__ import annotations

import dash
from typing import cast
from dash import Input, Output, State, dcc, html
import dash_bootstrap_components as dbc
from flask import session as flask_session, request
from dash.development.base_component import Component

from app.auth.service import AuthService, AuthProfile


def _can_access_admin(profile: AuthProfile) -> bool:
    if "admin" in profile.roles:
        return True
    permissions = profile.permissions or {}
    if "*" in permissions and "read" in permissions["*"]:
        return True
    admin_actions = permissions.get("admin") or []
    return "read" in admin_actions


def _default_redirect(profile: AuthProfile) -> str:
    return "/admin" if _can_access_admin(profile) else "/dashboard"


def layout() -> Component:
    return dbc.Row(
        [
            dbc.Col(md=4),
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(html.H4("Вход в систему")),
                        dbc.CardBody(
                            [
                                dbc.Alert(id="login-alert", color="danger", is_open=False),
                                dbc.Form(
                                    [
                                        dbc.Label("Логин", html_for="login-username"),
                                        dbc.Input(id="login-username", type="text", autoFocus=True, placeholder="Введите логин"),
                                        dbc.Label("Пароль", html_for="login-password", className="mt-3"),
                                        dbc.Input(id="login-password", type="password", placeholder="Введите пароль"),
                                        dbc.Checkbox(id="login-remember", label="Запомнить меня", className="mt-3"),
                                        dbc.Button("Войти", id="login-submit", color="primary", className="mt-4 w-100", n_clicks=0),
                                        dcc.Loading(id="login-loading", type="default", parent_className="mt-3"),
                                    ]
                                ),
                            ]
                        ),
                    ]
                ),
                md=4,
            ),
            dbc.Col(md=4),
        ],
        className="justify-content-center",
    )


def register_callbacks(app: dash.Dash) -> None:
    auth_service = AuthService()

    @app.callback(
        Output("login-alert", "is_open"),
        Output("login-alert", "children"),
        Output("global-redirect", "pathname", allow_duplicate=True),
        Input("login-submit", "n_clicks"),
        State("login-username", "value"),
        State("login-password", "value"),
        State("login-remember", "value"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def process_login(n_clicks: int, username: str | None, password: str | None, remember: bool | None, current_path: str | None):
        if not username or not password:
            return True, "Введите логин и пароль", dash.no_update

        profile = auth_service.authenticate(username=username, password=password, request=request)
        if not profile:
            return True, "Неверные учетные данные", dash.no_update

        flask_session.clear()
        session_data = profile.to_dict()
        session_data["remember"] = bool(remember)
        flask_session.update(session_data)

        def _is_admin_path(path: str | None) -> bool:
            return bool(path) and path.startswith("/admin")

        def _valid_target(path: str | None) -> bool:
            if not path or path == "/login":
                return False
            if _is_admin_path(path) and not _can_access_admin(profile):
                return False
            return True

        requested_target = request.args.get("next")
        if _valid_target(requested_target):
            target = cast(str, requested_target)
        elif _valid_target(current_path):
            target = cast(str, current_path)
        else:
            target = _default_redirect(profile)

        return False, "", target