import json
from typing import Optional
from urllib.parse import quote, quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str
    DB_PATH: str = "database/bot.db"
    ADMIN_CHAT_ID: int
    LOGS_CHAT_ID: int
    CANCELLATION_IMAGE_FILE_ID: str
    START_PHOTO_FILE_ID: Optional[str] = None
    ADMINS: list[int]
    REGULATIONS_URL: str = ""
    PROGRAMS_URL: str = ""
    REDIS_URL: str
    REMINDER_NOTIFY_USERNAME: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRES_SECONDS: int = 900
    JWT_REFRESH_EXPIRES_SECONDS: int = 1209600  # 14 days
    TELEGRAM_AUTH_MAX_AGE_SECONDS: int = 86400
    BROWSER_REFRESH_COOKIE_NAME: str = "tutorbase_refresh_token"
    BROWSER_REFRESH_COOKIE_SECURE: bool = True
    BROWSER_REFRESH_COOKIE_SAMESITE: str = "lax"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    MINI_APP_URL: str = "https://app.tutorbase.su/"

    POSTGRESQL_HOST: Optional[str] = None
    POSTGRESQL_PORT: Optional[int] = None
    POSTGRESQL_USER: Optional[str] = None
    POSTGRESQL_PASSWORD: Optional[str] = None
    POSTGRESQL_DBNAME: Optional[str] = None

    DEV_MODE: bool = False
    DEV_TELEGRAM_ID: int = 999_999
    DEV_INIT_DATA: str = "dev"
    DEV_USERNAME: str = "devuser"
    DEV_DISPLAY_NAME: str = "Dev User"
    NOTIFICATIONS_AUTOMATION_ENABLED: bool = False
    NOTIFICATIONS_PROCESS_JOBS_INTERVAL_SECONDS: int = 60
    NOTIFICATIONS_DELIVERY_INTERVAL_SECONDS: int = 30
    NOTIFICATIONS_DELIVERY_GRACE_SECONDS: int = 120
    TENANT_ACCESS_SYNC_ENABLED: bool = True
    TENANT_ACCESS_SYNC_INTERVAL_SECONDS: int = 3600
    TELEGRAM_REQUEST_TIMEOUT_SECONDS: float = 15.0
    TELEGRAM_PROXY_SCHEME: str = "socks5"
    TELEGRAM_PROXY_HOST: Optional[str] = None
    TELEGRAM_PROXY_PORT: Optional[int] = None
    TELEGRAM_PROXY_USERNAME: Optional[str] = None
    TELEGRAM_PROXY_PASSWORD: Optional[str] = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except json.JSONDecodeError:
                pass
            if value:
                return [item.strip() for item in value.split(",") if item.strip()]
            return []
        if isinstance(value, list):
            return [str(x) for x in value]
        return []

    @field_validator("ADMINS", mode="before")
    @classmethod
    def parse_admins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [int(x) for x in parsed]
            except json.JSONDecodeError:
                if value:
                    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]
                return []
        if isinstance(value, list):
            return [int(x) for x in value]
        return []

    @field_validator(
        "NOTIFICATIONS_PROCESS_JOBS_INTERVAL_SECONDS",
        "NOTIFICATIONS_DELIVERY_INTERVAL_SECONDS",
        "NOTIFICATIONS_DELIVERY_GRACE_SECONDS",
        "TENANT_ACCESS_SYNC_INTERVAL_SECONDS",
        "TELEGRAM_REQUEST_TIMEOUT_SECONDS",
    )
    @classmethod
    def validate_positive_interval(cls, value):
        if value <= 0:
            raise ValueError("Timeouts and intervals must be greater than zero")
        return value

    @field_validator("TELEGRAM_PROXY_SCHEME")
    @classmethod
    def validate_telegram_proxy_scheme(cls, value):
        scheme = value.lower()
        if scheme not in {"socks5", "socks5h", "socks4", "http"}:
            raise ValueError("Telegram proxy scheme must be one of: socks5, socks5h, socks4, http")
        return scheme

    @field_validator(
        "TELEGRAM_PROXY_HOST",
        "TELEGRAM_PROXY_PORT",
        "TELEGRAM_PROXY_USERNAME",
        "TELEGRAM_PROXY_PASSWORD",
        mode="before",
    )
    @classmethod
    def empty_telegram_proxy_value_is_none(cls, value):
        if value == "":
            return None
        return value

    def build_async_database_url(self) -> str:
        if self.POSTGRESQL_HOST and self.POSTGRESQL_DBNAME:
            user = self.POSTGRESQL_USER or ""
            password = self.POSTGRESQL_PASSWORD or ""
            auth = ""
            if user:
                auth = quote_plus(user)
                if password:
                    auth = f"{auth}:{quote_plus(password)}"
                auth += "@"
            host = self.POSTGRESQL_HOST
            port = f":{self.POSTGRESQL_PORT}" if self.POSTGRESQL_PORT else ""
            return f"postgresql+asyncpg://{auth}{host}{port}/{self.POSTGRESQL_DBNAME}"
        return f"sqlite+aiosqlite:///{self.DB_PATH}"

    def build_telegram_proxy_url(self) -> str | None:
        if not self.TELEGRAM_PROXY_HOST:
            return None
        if not self.TELEGRAM_PROXY_PORT:
            raise ValueError("TELEGRAM_PROXY_PORT is required when TELEGRAM_PROXY_HOST is set")

        auth = ""
        if self.TELEGRAM_PROXY_USERNAME or self.TELEGRAM_PROXY_PASSWORD:
            if not self.TELEGRAM_PROXY_USERNAME or not self.TELEGRAM_PROXY_PASSWORD:
                raise ValueError(
                    "Both TELEGRAM_PROXY_USERNAME and TELEGRAM_PROXY_PASSWORD are required "
                    "when proxy authentication is enabled"
                )
            auth = (
                f"{quote(self.TELEGRAM_PROXY_USERNAME, safe='')}:"
                f"{quote(self.TELEGRAM_PROXY_PASSWORD, safe='')}@"
            )

        return (
            f"{self.TELEGRAM_PROXY_SCHEME}://"
            f"{auth}{self.TELEGRAM_PROXY_HOST}:{self.TELEGRAM_PROXY_PORT}"
        )


config = Settings()
