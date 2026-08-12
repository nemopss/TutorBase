import pytest

from config import config


def test_production_database_url_never_silently_falls_back_to_sqlite():
    settings = config.model_copy(
        update={
            "DEV_MODE": False,
            "POSTGRESQL_HOST": None,
            "POSTGRESQL_DBNAME": None,
        }
    )

    with pytest.raises(ValueError, match="PostgreSQL configuration is required"):
        settings.build_async_database_url()


def test_development_database_url_can_use_explicit_sqlite_fallback():
    settings = config.model_copy(
        update={
            "DEV_MODE": True,
            "POSTGRESQL_HOST": None,
            "POSTGRESQL_DBNAME": None,
            "DB_PATH": "database/test.db",
        }
    )

    assert settings.build_async_database_url() == "sqlite+aiosqlite:///database/test.db"
