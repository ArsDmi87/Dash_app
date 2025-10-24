from __future__ import annotations

from functools import lru_cache
from datetime import timedelta

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_title: str = Field(default="Dash Admin Analytics")
    flask_secret_key: str = Field(default="change_me")
    flask_debug: bool = Field(default=False)

    auth_db_dsn: str = Field(alias="AUTH_DB_DSN", default="")
    reporting_db_dsn: str = Field(alias="REPORTING_DB_DSN", default="")
    dwh_db_dsn: str = Field(alias="DWH_DB_DSN", default="")

    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY", default="change_me")
    jwt_algorithm: str = Field(alias="JWT_ALGORITHM", default="HS256")

    session_cookie_name: str = Field(alias="SESSION_COOKIE_NAME", default="dash_session")
    session_timeout_minutes: int = Field(alias="SESSION_TIMEOUT_MINUTES", default=30)

    redis_url: str | None = Field(alias="REDIS_URL", default=None)

    dash_serve_locally: bool = Field(alias="DASH_SERVE_LOCALLY", default=True)

    @property
    def session_lifetime(self) -> timedelta:
        return timedelta(minutes=self.session_timeout_minutes)


@lru_cache
def get_settings() -> Settings:
    return Settings()
