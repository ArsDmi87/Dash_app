from __future__ import annotations

from app import create_dash_app


def run():
    dash_app = create_dash_app()
    dash_app.run_server(debug=dash_app.server.config.get("DEBUG", False))


if __name__ == "__main__":
    run()
