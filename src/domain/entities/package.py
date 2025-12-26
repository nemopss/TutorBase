"""Package domain entity.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
- Contains id, tenant_id, learner_id, title, status, start_date, end_date, timezone, total_lessons, price, payment_status
- Method to check if package is active
- Method to check if package is completed
- Validates status is one of: draft, active, completed, cancelled
- No SQLAlchemy or database imports
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from src.domain.entities.base import Entity


class PackageStatus:
    """Valid package status values."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    ALL = {DRAFT, ACTIVE, COMPLETED, CANCELLED}


class PaymentStatus:
    """Valid payment status values."""

    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"

    ALL = {UNPAID, PARTIAL, PAID}


@dataclass(frozen=True, eq=False)
class Package(Entity):
    """Domain entity representing a lesson package.

    Attributes:
        id: Unique identifier
        tenant_id: Associated tenant ID
        learner_id: Learner this package belongs to
        title: Package title/name
        status: Package status (draft, active, completed, cancelled)
        start_date: Package start date
        end_date: Package end date
        timezone: Timezone for lesson scheduling
        total_lessons: Total number of lessons in package
        price: Package price
        payment_status: Payment status (unpaid, partial, paid)
        notes: Teacher notes about the package
        created_at: Package creation timestamp
        updated_at: Last package update timestamp
    """

    tenant_id: int
    learner_id: int
    title: str
    status: str = PackageStatus.DRAFT
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    timezone: str = "Europe/Moscow"
    total_lessons: Optional[int] = None
    price: Optional[Decimal] = None
    payment_status: str = PaymentStatus.UNPAID
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate entity after creation."""
        if self.status not in PackageStatus.ALL:
            raise ValueError(f"Invalid status: {self.status}")
        if self.payment_status not in PaymentStatus.ALL:
            raise ValueError(f"Invalid payment_status: {self.payment_status}")

    def is_active(self) -> bool:
        """Check if package is active."""
        return self.status == PackageStatus.ACTIVE

    def is_completed(self) -> bool:
        """Check if package is completed."""
        return self.status == PackageStatus.COMPLETED

    def is_cancelled(self) -> bool:
        """Check if package is cancelled."""
        return self.status == PackageStatus.CANCELLED

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary for serialization."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "learner_id": self.learner_id,
            "title": self.title,
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "timezone": self.timezone,
            "total_lessons": self.total_lessons,
            "price": float(self.price) if self.price else None,
            "payment_status": self.payment_status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_orm(cls, orm_model: Any) -> "Package":
        """Create Package from SQLAlchemy model.

        Args:
            orm_model: SQLAlchemy LessonPackage model instance

        Returns:
            Package domain entity
        """
        return cls(
            id=orm_model.id,
            tenant_id=orm_model.tenant_id,
            learner_id=orm_model.learner_id,
            title=orm_model.title,
            status=orm_model.status,
            start_date=orm_model.start_date,
            end_date=orm_model.end_date,
            timezone=orm_model.timezone,
            total_lessons=orm_model.total_lessons,
            price=orm_model.price,
            payment_status=orm_model.payment_status,
            notes=orm_model.notes,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
        )
