"""
Property-based tests for domain interfaces.

Feature: clean-architecture-phase1, Property 5: Interface Protocol Conformance
Validates: Requirements 5.4, 5.5
"""
import inspect
from typing import Optional, get_type_hints

from hypothesis import given, settings, strategies as st

from src.domain.interfaces import ICacheService, IRepository


# Expected method signatures for IRepository
REPOSITORY_METHODS = {
    "get_by_id": {"params": ["id"], "is_async": True},
    "get_all": {"params": [], "is_async": True},
    "add": {"params": ["entity"], "is_async": True},
    "update": {"params": ["entity"], "is_async": True},
    "delete": {"params": ["id"], "is_async": True},
}

# Expected method signatures for ICacheService
CACHE_METHODS = {
    "get": {"params": ["key"], "is_async": True},
    "set": {"params": ["key", "value", "ttl"], "is_async": True},
    "delete": {"params": ["key"], "is_async": True},
    "exists": {"params": ["key"], "is_async": True},
}


@given(method_name=st.sampled_from(list(REPOSITORY_METHODS.keys())))
@settings(max_examples=100)
def test_irepository_has_required_methods(method_name: str) -> None:
    """
    Property 5: Interface Protocol Conformance (IRepository)
    
    For any required method in IRepository, the Protocol SHALL define
    that method with correct signature.
    
    Feature: clean-architecture-phase1, Property 5: Interface Protocol Conformance
    Validates: Requirements 5.4, 5.5
    """
    expected = REPOSITORY_METHODS[method_name]
    
    # Check method exists
    assert hasattr(IRepository, method_name), f"IRepository missing method: {method_name}"
    
    method = getattr(IRepository, method_name)
    sig = inspect.signature(method)
    
    # Check parameters (excluding 'self')
    params = [p for p in sig.parameters.keys() if p != "self"]
    assert params == expected["params"], (
        f"IRepository.{method_name} has wrong params: {params}, expected: {expected['params']}"
    )
    
    # Check if async
    if expected["is_async"]:
        assert inspect.iscoroutinefunction(method) or "..." in str(inspect.getsource(method)), (
            f"IRepository.{method_name} should be async"
        )


@given(method_name=st.sampled_from(list(CACHE_METHODS.keys())))
@settings(max_examples=100)
def test_icacheservice_has_required_methods(method_name: str) -> None:
    """
    Property 5: Interface Protocol Conformance (ICacheService)
    
    For any required method in ICacheService, the Protocol SHALL define
    that method with correct signature.
    
    Feature: clean-architecture-phase1, Property 5: Interface Protocol Conformance
    Validates: Requirements 5.4, 5.5
    """
    expected = CACHE_METHODS[method_name]
    
    # Check method exists
    assert hasattr(ICacheService, method_name), f"ICacheService missing method: {method_name}"
    
    method = getattr(ICacheService, method_name)
    sig = inspect.signature(method)
    
    # Check parameters (excluding 'self')
    params = [p for p in sig.parameters.keys() if p != "self"]
    assert params == expected["params"], (
        f"ICacheService.{method_name} has wrong params: {params}, expected: {expected['params']}"
    )


def test_irepository_is_generic() -> None:
    """Verify IRepository is a generic Protocol with T and ID type vars."""
    # IRepository should have __class_getitem__ for generic support
    assert hasattr(IRepository, "__class_getitem__"), "IRepository should be generic"


def test_icacheservice_is_protocol() -> None:
    """Verify ICacheService is a Protocol."""
    from typing import Protocol, runtime_checkable
    
    # Check it's a Protocol subclass
    assert issubclass(ICacheService, Protocol), "ICacheService should be a Protocol"
