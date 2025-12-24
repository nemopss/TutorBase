"""Base repository interface for all entities.

Requirements: 5.1, 5.5
"""
from typing import Generic, List, Optional, Protocol, TypeVar

T = TypeVar("T")
ID = TypeVar("ID")


class IRepository(Protocol[T, ID]):
    """Base repository interface for all entities.
    
    Uses typing.Protocol for structural subtyping support.
    All repository implementations must conform to this interface.
    """

    async def get_by_id(self, id: ID) -> Optional[T]:
        """Get entity by ID."""
        ...

    async def get_all(self) -> List[T]:
        """Get all entities."""
        ...

    async def add(self, entity: T) -> T:
        """Add new entity."""
        ...

    async def update(self, entity: T) -> T:
        """Update existing entity."""
        ...

    async def delete(self, id: ID) -> bool:
        """Delete entity by ID."""
        ...
