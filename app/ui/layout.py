from __future__ import annotations

from dash import dcc, html
import dash_bootstrap_components as dbc

APP_BACKGROUND = "#D5DAE0"
APP_FONT_FAMILY = "'Open Sans'"#, Arial, sans-serif"
NAVBAR_COLOR = "#55246A"
FRAME_BORDER_COLOR = "#414042"
FRAME_STYLE = {
    "border": f"2px solid {FRAME_BORDER_COLOR}",
    "borderRadius": "24px",
    "background": "linear-gradient(145deg, #d9dce3, #f0f2f7)",
    "padding": "24px",
    "margin": "0 auto",
    "maxWidth": "1280px",
    "boxShadow": "0 8px 24px rgba(33, 33, 33, 0.08)",
}


def get_layout():
    """Application shell with navbar, routing anchors, and content placeholder."""
    return html.Div(
        [
            dcc.Location(id="url"),
            dcc.Location(id="global-redirect", refresh=True),
            dbc.Navbar(
                dbc.Container(
                    [
                        dbc.NavbarBrand("Dash Admin Analytics", href="/"),
                        dbc.Nav(
                            [
                                dbc.NavLink("Мои отчёты", href="/library", id="nav-library", active="exact"),
                                dbc.NavLink("Админка", href="/admin", id="nav-admin", disabled=True, style={"display": "none"}),
                            ],
                            className="me-auto",
                            pills=True,
                            id="nav-links",
                            style={"display": "none"},
                        ),
                        html.Div(id="navbar-user", className="d-flex align-items-center gap-2"),
                    ],
                    fluid=True,
                ),
                color=NAVBAR_COLOR,
                dark=True,
                className="mb-4 border-0",
                style={
                    "backgroundColor": NAVBAR_COLOR,
                    "borderBottom": f"2px solid {FRAME_BORDER_COLOR}",
                    "boxShadow": "0 12px 24px rgba(17, 14, 31, 0.28)",
                },
            ),
            html.Div(
                [
                    html.Div(className="header-divider__beam"),
                    html.Div(className="header-divider__accent"),
                    html.Div(className="header-divider__accent header-divider__accent--right"),
                ],
                className="header-divider",
            ),
            html.Div(
                dbc.Container(
                    html.Div(id="page-content"),
                    fluid=True,
                ),
                className="px-3",
                style=FRAME_STYLE,
            ),
        ],
        style={
            "fontFamily": APP_FONT_FAMILY,
            "backgroundColor": NAVBAR_COLOR,
            "minHeight": "100vh",
            "padding": "24px",
        },
    )
