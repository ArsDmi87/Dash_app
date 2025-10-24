from __future__ import annotations

from dash import Dash
import dash_bootstrap_components as dbc
from flask import Flask

from app.auth.session import DatabaseSessionInterface
from app.core.settings import Settings, get_settings


def create_flask_app(settings: Settings | None = None) -> Flask:
    """Create and configure the underlying Flask application."""
    settings = settings or get_settings()
    server = Flask(__name__)
    server.config.update(
        SECRET_KEY=settings.flask_secret_key,
        SESSION_COOKIE_NAME=settings.session_cookie_name,
        PERMANENT_SESSION_LIFETIME=settings.session_lifetime,
    )
    server.session_interface = DatabaseSessionInterface(settings=settings)
    return server


def create_dash_app(settings: Settings | None = None) -> Dash:
    """Instantiate Dash with Bootstrap styling and core configuration."""
    settings = settings or get_settings()
    server = create_flask_app(settings)
    dash_app = Dash(
        __name__,
        server=server,
        suppress_callback_exceptions=True,
        title=settings.app_title,
        external_stylesheets=[dbc.themes.SOLAR],
        serve_locally=settings.dash_serve_locally,
    )

    # Placeholder layouts; will be extended as modules are implemented.
    from app.ui.layout import get_layout  # lazy import to avoid circular deps
    from app.ui.routes import register_routes

    dash_app.layout = get_layout()
    register_routes(dash_app)
    return dash_app
