from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Optional: Ignore extra env vars
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
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRES_SECONDS: int = 900
    JWT_REFRESH_EXPIRES_SECONDS: int = 1209600  # 14 days
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    MINI_APP_URL: str = "https://app.xpyrkova23.ru/mini-app"  # Update with actual URL

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
        if isinstance(v, str):
            v = v.strip()
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except json.JSONDecodeError:
                if v:
                    return [str(x.strip()) for x in v.split(",")]
                return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    @field_validator("ADMINS", mode="before")
    @classmethod
    def parse_admins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [int(x) for x in parsed]
            except json.JSONDecodeError:
                if v:
                    return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
                return []
        if isinstance(v, list):
            return [int(x) for x in v]
        return []


config = Settings()
