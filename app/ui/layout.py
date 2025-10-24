from __future__ import annotations

from dash import dcc, html
import dash_bootstrap_components as dbc


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
                                dbc.NavLink("Дашборд", href="/dashboard", id="nav-dashboard", active="exact"),
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
                color="dark",
                dark=True,
                className="mb-4",
            ),
            dbc.Container(
                html.Div(id="page-content"),
                fluid=True,
            ),
        ]
    )
