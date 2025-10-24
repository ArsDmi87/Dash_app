from __future__ import annotations

from dash import html
import dash_bootstrap_components as dbc
from dash.development.base_component import Component


def unauthorized_layout() -> Component:
    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    dbc.Alert(
                        [
                            html.H4("Недостаточно прав", className="alert-heading"),
                            html.P("У вас нет доступа к выбранному разделу."),
                        ],
                        color="danger",
                    )
                )
            )
        ],
        fluid=True,
        className="py-5",
    )


def not_found_layout(pathname: str | None = None) -> Component:
    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    dbc.Alert(
                        [
                            html.H4("Страница не найдена", className="alert-heading"),
                            html.P(f"Путь {pathname or ''} не существует."),
                        ],
                        color="secondary",
                    )
                )
            )
        ],
        fluid=True,
        className="py-5",
    )
