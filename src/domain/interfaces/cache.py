"""Cache service interface.

Requirements: 5.2, 5.5
"""
from typing import Optional, Protocol


class ICacheService(Protocol):
    """Cache service interface.
    
    Uses typing.Protocol for structural subtyping support.
    All cache implementations must conform to this interface.
    """

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        ...
