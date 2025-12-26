"""Base domain entity class.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
- Entity has id attribute for identity
- Equality based on id
- Hash based on id
- Independent of ORM/database
- Two entities with same id are equal
"""
from dataclasses import dataclass
from abc import ABC


@dataclass(frozen=True, eq=False)
class Entity(ABC):
    """Base class for all domain entities.

    Entities are identified by their id and are equal if their ids match.
    Uses frozen dataclass for immutability.
    Uses eq=False to allow custom __eq__ implementation.

    Attributes:
        id: Unique identifier for the entity
    """

    id: int

    def __eq__(self, other: object) -> bool:
        """Two entities are equal if they have the same id."""
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on id for use in sets and dicts."""
        return hash(self.id)
