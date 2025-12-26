"""Learner domain entity.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
- Contains id, tenant_id, display_name, notes, notifications_enabled, lesson_rate, created_at
- Method to check if notifications are enabled
- Immutable after creation (frozen dataclass)
- No SQLAlchemy or database imports
- Validates display_name is not empty
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from src.domain.entities.base import Entity


@dataclass(frozen=True, eq=False)
class Learner(Entity):
    """Domain entity representing a student/learner.

    Attributes:
        id: Unique identifier
        tenant_id: Associated tenant ID
        display_name: Display name for the learner
        notes: Teacher notes about the learner
        notifications_enabled: Whether to send reminders to this learner
        lesson_rate: Individual lesson rate (price per lesson)
        created_at: Learner creation timestamp
    """

    tenant_id: int
    display_name: str
    notes: Optional[str] = None
    notifications_enabled: bool = True
    lesson_rate: Optional[Decimal] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate entity after creation."""
        if not self.display_name or not self.display_name.strip():
            raise ValueError("display_name cannot be empty")

    def is_notifications_enabled(self) -> bool:
        """Check if notifications are enabled for this learner."""
        return self.notifications_enabled

    def is_active(self) -> bool:
        """Check if learner is active (has notifications enabled)."""
        return self.notifications_enabled

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary for serialization."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "display_name": self.display_name,
            "notes": self.notes,
            "notifications_enabled": self.notifications_enabled,
            "lesson_rate": float(self.lesson_rate) if self.lesson_rate else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_orm(cls, orm_model: Any) -> "Learner":
        """Create Learner from SQLAlchemy model.

        Args:
            orm_model: SQLAlchemy Learner model instance

        Returns:
            Learner domain entity
        """
        return cls(
            id=orm_model.id,
            tenant_id=orm_model.tenant_id,
            display_name=orm_model.display_name,
            notes=orm_model.notes,
            notifications_enabled=orm_model.notifications_enabled,
            lesson_rate=orm_model.lesson_rate,
            created_at=orm_model.created_at,
        )
