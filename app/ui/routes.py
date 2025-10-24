from __future__ import annotations

from dash import Dash, Input, Output, html, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from flask import session as flask_session, request

from app.auth.service import AuthService
from app.core.settings import get_settings
from app.ui.pages import admin, common, dashboard, login


def _has_permission(session_data: dict, resource: str, action: str = "read") -> bool:
    permissions = session_data.get("permissions") or {}
    if "*" in permissions and action in permissions["*"]:
        return True
    allowed = permissions.get(resource) or []
    return action in allowed


def _can_view_report(session_data: dict, report_code: str) -> bool:
    reports = session_data.get("reports") or []
    if not reports:
        return False
    return any(isinstance(report, dict) and report.get("code") == report_code for report in reports)


def register_routes(app: Dash) -> None:
    """Register page routers and global callbacks."""

    login.register_callbacks(app)
    dashboard.register_callbacks(app)
    admin.register_callbacks(app)
    auth_service = AuthService()

    @app.callback(
        Output("page-content", "children"),
        Output("navbar-user", "children"),
        Output("nav-links", "style"),
        Output("nav-admin", "style"),
        Output("nav-admin", "disabled"),
        Output("nav-dashboard", "style"),
        Output("nav-dashboard", "disabled"),
        Output("global-redirect", "pathname", allow_duplicate=True),
        Input("url", "pathname"),
        prevent_initial_call="initial_duplicate",
    )
    def render_page(pathname: str | None):
        pathname = pathname or "/"
        session_data = dict(flask_session)
        user_id = session_data.get("user_id")

        nav_links_style = {"display": "none"}
        nav_admin_style = {"display": "none"}
        nav_admin_disabled = True
        nav_dashboard_style = {"display": "none"}
        nav_dashboard_disabled = True

        if not user_id:
            if pathname == "/login":
                return (
                    login.layout(),
                    [],
                    nav_links_style,
                    nav_admin_style,
                    nav_admin_disabled,
                    nav_dashboard_style,
                    nav_dashboard_disabled,
                    no_update,
                )
            if pathname == "/":
                return (
                    login.layout(),
                    [],
                    nav_links_style,
                    nav_admin_style,
                    nav_admin_disabled,
                    nav_dashboard_style,
                    nav_dashboard_disabled,
                    no_update,
                )
            return (
                login.layout(),
                [],
                nav_links_style,
                nav_admin_style,
                nav_admin_disabled,
                nav_dashboard_style,
                nav_dashboard_disabled,
                "/login",
            )

        user_display = [
            html.Span(session_data.get("full_name") or session_data.get("username"), className="text-white"),
            dbc.Button("Выйти", id="logout-button", color="outline-light", size="sm"),
        ]

        nav_links_style = None
        nav_dashboard_style = None
        nav_dashboard_disabled = False
        admin_disabled = not (
            "admin" in (session_data.get("roles") or [])
            or _has_permission(session_data, "admin", "read")
        )
        nav_admin_style = None if not admin_disabled else {"display": "none"}
        nav_admin_disabled = admin_disabled

        if pathname in ("/", "/dashboard"):
            can_view_dashboard = (
                _has_permission(session_data, "dashboard", "read")
                or _can_view_report(session_data, "sales_dashboard")
                or not admin_disabled
            )
            if not can_view_dashboard:
                nav_dashboard_style = {"display": "none"}
                nav_dashboard_disabled = True
            else:
                nav_dashboard_style = None
                nav_dashboard_disabled = False
            if not can_view_dashboard and admin_disabled:
                return (
                    common.unauthorized_layout(),
                    user_display,
                    nav_links_style,
                    nav_admin_style,
                    nav_admin_disabled,
                    nav_dashboard_style,
                    nav_dashboard_disabled,
                    no_update,
                )
            return (
                dashboard.layout(),
                user_display,
                nav_links_style,
                nav_admin_style,
                nav_admin_disabled,
                nav_dashboard_style,
                nav_dashboard_disabled,
                no_update,
            )

        if pathname == "/admin":
            if admin_disabled:
                return (
                    common.unauthorized_layout(),
                    user_display,
                    nav_links_style,
                    nav_admin_style,
                    nav_admin_disabled,
                    nav_dashboard_style,
                    nav_dashboard_disabled,
                    no_update,
                )
            return (
                admin.layout(),
                user_display,
                nav_links_style,
                nav_admin_style,
                nav_admin_disabled,
                nav_dashboard_style,
                nav_dashboard_disabled,
                no_update,
            )

        if pathname == "/login":
            return (
                dashboard.layout(),
                user_display,
                nav_links_style,
                nav_admin_style,
                nav_admin_disabled,
                nav_dashboard_style,
                nav_dashboard_disabled,
                "/dashboard",
            )

        return (
            common.not_found_layout(pathname),
            user_display,
            nav_links_style,
            nav_admin_style,
            nav_admin_disabled,
            nav_dashboard_style,
            nav_dashboard_disabled,
            no_update,
        )

    @app.callback(
        Output("global-redirect", "pathname", allow_duplicate=True),
        Input("logout-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_logout(n_clicks: int | None) -> str | None:
        if not n_clicks:
            raise PreventUpdate

        session_token = request.cookies.get(get_settings().session_cookie_name)
        if session_token:
            auth_service.logout(session_token, reason="logout")
        flask_session.clear()
        return "/login"  # type: ignore[return-value]