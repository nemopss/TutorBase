"""
Property-based tests for DI container.

Feature: clean-architecture-phase1, Property 1: DI Container Provider Resolution
Validates: Requirements 1.1, 1.2, 1.3
"""
from hypothesis import given, settings, strategies as st

from src.application.container import Container, reset_container


# Providers that should be singletons
SINGLETON_PROVIDERS = ["config", "database_url", "db_engine"]

# Providers that should be factories
FACTORY_PROVIDERS = ["session_factory"]


@given(provider_name=st.sampled_from(SINGLETON_PROVIDERS))
@settings(max_examples=100, deadline=None)
def test_singleton_providers_return_same_instance(provider_name: str) -> None:
    """
    Property 1: DI Container Provider Resolution (Singletons)
    
    For any singleton provider, requesting that provider multiple times
    SHALL return the same instance.
    
    Feature: clean-architecture-phase1, Property 1: DI Container Provider Resolution
    Validates: Requirements 1.1, 1.2, 1.3
    """
    reset_container()
    container = Container()
    
    provider = getattr(container, provider_name, None)
    assert provider is not None, f"Provider '{provider_name}' not found"
    
    # Get instance twice
    instance1 = provider()
    instance2 = provider()
    
    # Singleton should return same instance
    assert instance1 is instance2, (
        f"Singleton provider '{provider_name}' returned different instances"
    )


@given(provider_name=st.sampled_from(FACTORY_PROVIDERS))
@settings(max_examples=100, deadline=None)
def test_factory_providers_return_different_instances(provider_name: str) -> None:
    """
    Property 1: DI Container Provider Resolution (Factories)
    
    For any factory provider, requesting that provider multiple times
    SHALL return different instances.
    
    Feature: clean-architecture-phase1, Property 1: DI Container Provider Resolution
    Validates: Requirements 1.1, 1.2, 1.3
    """
    reset_container()
    container = Container()
    
    provider = getattr(container, provider_name, None)
    assert provider is not None, f"Provider '{provider_name}' not found"
    
    # Get instance twice
    instance1 = provider()
    instance2 = provider()
    
    # Factory should return different instances
    assert instance1 is not instance2, (
        f"Factory provider '{provider_name}' returned same instance"
    )


def test_container_has_required_providers() -> None:
    """Verify container has all required providers."""
    reset_container()
    container = Container()
    
    required = SINGLETON_PROVIDERS + FACTORY_PROVIDERS
    for provider_name in required:
        assert hasattr(container, provider_name), (
            f"Container missing required provider: {provider_name}"
        )


def test_config_provider_returns_settings() -> None:
    """Verify config provider returns Settings instance."""
    reset_container()
    container = Container()
    
    cfg = container.config()
    
    # Should have expected attributes from Settings
    assert hasattr(cfg, "BOT_TOKEN")
    assert hasattr(cfg, "build_async_database_url")
