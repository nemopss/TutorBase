"""Lesson domain entity.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
- Contains id, tenant_id, package_id, scheduled_at, duration_minutes, status, sequence_index, price, teacher_notes
- Method to check if lesson is scheduled
- Method to check if lesson is in the past
- Validates status is one of: scheduled, completed, cancelled, missed, rescheduled
- No SQLAlchemy or database imports
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from src.domain.entities.base import Entity


class LessonStatus:
    """Valid lesson status values."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"
    RESCHEDULED = "rescheduled"

    ALL = {SCHEDULED, COMPLETED, CANCELLED, MISSED, RESCHEDULED}


@dataclass(frozen=True, eq=False)
class Lesson(Entity):
    """Domain entity representing an individual lesson.

    Attributes:
        id: Unique identifier
        tenant_id: Associated tenant ID
        package_id: Parent lesson package ID
        scheduled_at: Scheduled lesson datetime
        status: Lesson status (scheduled, completed, cancelled, missed, rescheduled)
        duration_minutes: Lesson duration in minutes
        sequence_index: Order of lesson in package
        price: Price for standalone lessons
        teacher_notes: Notes from teacher about the lesson
        created_at: Lesson creation timestamp
        updated_at: Last lesson update timestamp
    """

    tenant_id: int
    package_id: int
    scheduled_at: datetime
    status: str = LessonStatus.SCHEDULED
    duration_minutes: Optional[int] = None
    sequence_index: Optional[int] = None
    price: Optional[Decimal] = None
    teacher_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate entity after creation."""
        if self.status not in LessonStatus.ALL:
            raise ValueError(f"Invalid status: {self.status}")

    def is_scheduled(self) -> bool:
        """Check if lesson is scheduled."""
        return self.status == LessonStatus.SCHEDULED

    def is_in_past(self) -> bool:
        """Check if lesson is in the past."""
        return self.scheduled_at < datetime.now(timezone.utc)

    def is_upcoming(self) -> bool:
        """Check if lesson is upcoming (scheduled and not in past)."""
        return self.is_scheduled() and not self.is_in_past()

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary for serialization."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "package_id": self.package_id,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "status": self.status,
            "duration_minutes": self.duration_minutes,
            "sequence_index": self.sequence_index,
            "price": float(self.price) if self.price else None,
            "teacher_notes": self.teacher_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_orm(cls, orm_model: Any) -> "Lesson":
        """Create Lesson from SQLAlchemy model.

        Args:
            orm_model: SQLAlchemy Lesson model instance

        Returns:
            Lesson domain entity
        """
        return cls(
            id=orm_model.id,
            tenant_id=orm_model.tenant_id,
            package_id=orm_model.package_id,
            scheduled_at=orm_model.scheduled_at,
            status=orm_model.status,
            duration_minutes=orm_model.duration_minutes,
            sequence_index=orm_model.sequence_index,
            price=orm_model.price,
            teacher_notes=orm_model.teacher_notes,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
        )
