from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

APP_FONT_FAMILY = "'Open Sans'"  # , Arial, sans-serif"
GRADIENT_START = "#000000"
GRADIENT_END = "rgb(103, 72, 142)"
NAVBAR_TEXT_COLOR = "#FFFFFF"
NAVBAR_CUTOFF = "140px"
DEFAULT_APP_STYLE: dict[str, str] = {
    "fontFamily": APP_FONT_FAMILY,
    "minHeight": "100vh",
    "padding": "24px",
    "--navbar-cutoff": NAVBAR_CUTOFF,
    "backgroundColor": GRADIENT_START,
    "backgroundImage": (
        "linear-gradient(to bottom, "
        f"{GRADIENT_START} 0px, "
        f"{GRADIENT_START} 90px, "
        "#130925 170px, "
        "#2f1750 40%, "
        f"{GRADIENT_END} 100%)"
    ),
    "backgroundRepeat": "no-repeat",
    "backgroundAttachment": "fixed",
}

DEFAULT_NAVBAR_STYLE: dict[str, str] = {
    "backgroundColor": "transparent",
    "borderBottom": "none",
    "borderRadius": "24px",
    "boxShadow": "none",
    "padding": "0.75rem 1rem",
}

DEFAULT_FRAME_STYLE: dict[str, str] = {
    "border": "1px solid rgba(255, 255, 255, 0.12)",
    "borderRadius": "24px",
    "background": "rgba(20, 10, 40, 0.45)",
    "padding": "24px",
    "margin": "0 auto",
    "maxWidth": "1280px",
    "boxShadow": "0 18px 36px rgba(0, 0, 0, 0.4)",
    "backdropFilter": "blur(6px)",
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
                        dbc.NavbarBrand("NOVIKOM.Analytics", href="/", className="text-white fw-semibold"),
                        dbc.Nav(
                            [
                                dbc.NavLink(
                                    "Отчёты",
                                    href="/library",
                                    id="nav-library",
                                    active="exact",
                                    className="navbar-link",
                                    style={"color": NAVBAR_TEXT_COLOR},
                                ),
                                dbc.NavLink(
                                    "Админка",
                                    href="/admin",
                                    id="nav-admin",
                                    disabled=True,
                                    className="navbar-link",
                                    style={"display": "none", "color": NAVBAR_TEXT_COLOR},
                                ),
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
                id="main-navbar",
                dark=True,
                className="main-navbar mb-4 border-0",
                style=DEFAULT_NAVBAR_STYLE.copy(),
            ),
            html.Div(
                dbc.Container(
                    html.Div(id="page-content"),
                    fluid=True,
                ),
                id="page-frame",
                className="px-3",
                style=DEFAULT_FRAME_STYLE.copy(),
            ),
        ],
        id="app-root",
        style=DEFAULT_APP_STYLE.copy(),
    )
