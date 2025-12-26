"""Reminder domain entity.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
- Contains id, tenant_id, learner_id, scheduled_for, status, reminder_type, channel
- Method to check if reminder is pending
- Method to check if reminder should be sent now
- Validates status is one of: scheduled, sent, confirmed, declined, cancelled
- No SQLAlchemy or database imports
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.domain.entities.base import Entity


class ReminderStatus:
    """Valid reminder status values."""

    SCHEDULED = "scheduled"
    SENT = "sent"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    CANCELLED = "cancelled"

    ALL = {SCHEDULED, SENT, CONFIRMED, DECLINED, CANCELLED}


@dataclass(frozen=True, eq=False)
class Reminder(Entity):
    """Domain entity representing a reminder instance.

    Attributes:
        id: Unique identifier
        tenant_id: Associated tenant ID
        learner_id: Learner to receive this reminder
        scheduled_for: When to send this reminder
        reminder_type: Type of reminder (e.g., lesson, payment)
        status: Instance status (scheduled, sent, confirmed, declined, cancelled)
        channel: Delivery channel (e.g., telegram)
        created_at: Instance creation timestamp
        updated_at: Last instance update timestamp
    """

    tenant_id: int
    learner_id: int
    scheduled_for: datetime
    reminder_type: str
    status: str = ReminderStatus.SCHEDULED
    channel: str = "telegram"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate entity after creation."""
        if self.status not in ReminderStatus.ALL:
            raise ValueError(f"Invalid status: {self.status}")

    def is_pending(self) -> bool:
        """Check if reminder is pending (scheduled)."""
        return self.status == ReminderStatus.SCHEDULED

    def should_send_now(self) -> bool:
        """Check if reminder should be sent now."""
        return self.is_pending() and self.scheduled_for <= datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary for serialization."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "learner_id": self.learner_id,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "reminder_type": self.reminder_type,
            "status": self.status,
            "channel": self.channel,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_orm(cls, orm_model: Any) -> "Reminder":
        """Create Reminder from SQLAlchemy model.

        Args:
            orm_model: SQLAlchemy ReminderInstance model instance

        Returns:
            Reminder domain entity
        """
        # Get reminder_type from the rule if available
        reminder_type = "unknown"
        if hasattr(orm_model, "rule") and orm_model.rule:
            reminder_type = getattr(orm_model.rule, "kind", "unknown")

        return cls(
            id=orm_model.id,
            tenant_id=orm_model.tenant_id,
            learner_id=orm_model.learner_id,
            scheduled_for=orm_model.scheduled_for,
            reminder_type=reminder_type,
            status=orm_model.status,
            channel=orm_model.chat_identifier or "telegram",
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
        )
