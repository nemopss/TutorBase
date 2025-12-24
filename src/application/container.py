"""DI Container for TutorBase application.

Requirements: 1.1, 1.2, 1.3
"""
import logging
from typing import Optional

from dependency_injector import containers, providers

logger = logging.getLogger(__name__)


class Container(containers.DeclarativeContainer):
    """Main DI container for TutorBase application.
    
    Provides dependency injection for:
    - Configuration settings
    - Database engine and session factory
    - Future: repositories, services, etc.
    
    Requirements:
        1.1: Initialize with all registered providers
        1.2: Provide correct instances based on configuration
        1.3: Support singleton and factory providers
    """

    wiring_config = containers.WiringConfiguration(
        modules=[
            "bot",
            "api.main",
            "api.app",
        ]
    )

    # Configuration - singleton, loaded once
    config = providers.Singleton(
        lambda: __import__("config").config
    )

    # Database URL - derived from config
    database_url = providers.Singleton(
        lambda cfg: cfg.build_async_database_url(),
        config,
    )

    # Database engine - singleton for connection pooling
    db_engine = providers.Singleton(
        lambda url: __import__(
            "sqlalchemy.ext.asyncio", fromlist=["create_async_engine"]
        ).create_async_engine(url, pool_pre_ping=True),
        database_url,
    )

    # Session factory - factory provider, creates new sessions
    session_factory = providers.Factory(
        lambda engine: __import__(
            "sqlalchemy.ext.asyncio", fromlist=["async_sessionmaker"]
        ).async_sessionmaker(engine, expire_on_commit=False),
        db_engine,
    )


class ContainerInitializationError(Exception):
    """Raised when DI container fails to initialize."""
    pass


_container: Optional[Container] = None


def initialize_container() -> Container:
    """Initialize DI container with fallback to existing behavior.
    
    Returns:
        Initialized Container instance.
        
    Raises:
        ContainerInitializationError: If initialization fails.
        
    Requirements:
        1.4: Fall back to existing behavior on error
    """
    global _container
    
    if _container is not None:
        return _container
    
    try:
        _container = Container()
        logger.info("DI container initialized successfully")
        return _container
    except Exception as e:
        logger.error(f"Failed to initialize DI container: {e}")
        logger.warning("Falling back to existing service initialization")
        raise ContainerInitializationError(str(e)) from e


def get_container() -> Optional[Container]:
    """Get the current container instance.
    
    Returns:
        Container instance or None if not initialized.
    """
    return _container


def reset_container() -> None:
    """Reset the container (for testing purposes)."""
    global _container
    _container = None
