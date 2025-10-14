import json
from typing import Optional
from urllib.parse import quote_plus

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
    GOOGLE_FORM_URL: str = ""
    ADMIN_CHAT_ID: int
    LOGS_CHAT_ID: int
    CANCELLATION_IMAGE_FILE_ID: str
    ADMINS: list[int]
    REGULATIONS_URL: str
    REDIS_URL: str
    REMINDER_NOTIFY_USERNAME: str = "nemopss"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRES_SECONDS: int = 900
    JWT_REFRESH_EXPIRES_SECONDS: int = 1209600  # 14 days
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    MINI_APP_URL: str = "https://app.xpyrkova23.ru/mini-app"

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


config = Settings()
