"""Property-based tests for domain entities.

Feature: clean-architecture-phase2
"""
from dataclasses import dataclass
from datetime import datetime

import pytest
from hypothesis import given, settings, strategies as st

from src.domain.entities.base import Entity


# Concrete implementation for testing (Entity is abstract)
@dataclass(frozen=True, eq=False)
class ConcreteEntity(Entity):
    """Concrete entity for testing purposes."""
    name: str = "test"


class TestEntityIdentityEquality:
    """Property 1: Entity Identity Equality.
    
    For any two domain entities of the same type with the same id,
    they SHALL be considered equal regardless of other attribute values.
    
    **Validates: Requirements 1.2, 1.5**
    """

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        name1=st.text(min_size=1, max_size=50),
        name2=st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=100)
    def test_entities_with_same_id_are_equal(
        self, entity_id: int, name1: str, name2: str
    ):
        """Feature: clean-architecture-phase2, Property 1: Entity Identity Equality
        
        Two entities with the same id are equal regardless of other attributes.
        """
        entity1 = ConcreteEntity(id=entity_id, name=name1)
        entity2 = ConcreteEntity(id=entity_id, name=name2)
        
        assert entity1 == entity2
        assert hash(entity1) == hash(entity2)

    @given(
        id1=st.integers(min_value=1, max_value=10_000_000),
        id2=st.integers(min_value=1, max_value=10_000_000),
    )
    @settings(max_examples=100)
    def test_entities_with_different_ids_are_not_equal(self, id1: int, id2: int):
        """Feature: clean-architecture-phase2, Property 1: Entity Identity Equality
        
        Two entities with different ids are not equal.
        """
        if id1 == id2:
            return  # Skip when ids happen to be equal
        
        entity1 = ConcreteEntity(id=id1)
        entity2 = ConcreteEntity(id=id2)
        
        assert entity1 != entity2

    @given(entity_id=st.integers(min_value=1, max_value=10_000_000))
    @settings(max_examples=100)
    def test_entity_hash_is_consistent(self, entity_id: int):
        """Feature: clean-architecture-phase2, Property 1: Entity Identity Equality
        
        Entity hash is based on id and is consistent.
        """
        entity = ConcreteEntity(id=entity_id)
        
        # Hash should be consistent across multiple calls
        assert hash(entity) == hash(entity)
        # Hash should be based on id
        entity2 = ConcreteEntity(id=entity_id, name="different")
        assert hash(entity) == hash(entity2)

    @given(entity_id=st.integers(min_value=1, max_value=10_000_000))
    @settings(max_examples=100)
    def test_entity_not_equal_to_non_entity(self, entity_id: int):
        """Feature: clean-architecture-phase2, Property 1: Entity Identity Equality
        
        Entity is not equal to non-Entity objects.
        """
        entity = ConcreteEntity(id=entity_id)
        
        assert entity != entity_id
        assert entity != str(entity_id)
        assert entity != {"id": entity_id}
        assert entity != None



from src.domain.entities.learner import Learner


class TestLearnerValidation:
    """Property 3: Status Validation (Learner display_name).
    
    For any Learner entity, creating with an empty or whitespace-only
    display_name SHALL raise a ValueError.
    
    **Validates: Requirements 2.5**
    """

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        display_name=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100)
    def test_learner_with_valid_display_name_is_created(
        self, entity_id: int, tenant_id: int, display_name: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Learner)
        
        Learner with valid (non-empty) display_name is created successfully.
        """
        learner = Learner(
            id=entity_id,
            tenant_id=tenant_id,
            display_name=display_name,
        )
        assert learner.display_name == display_name
        assert learner.id == entity_id
        assert learner.tenant_id == tenant_id

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        whitespace=st.text(alphabet=" \t\n\r", min_size=0, max_size=10),
    )
    @settings(max_examples=100)
    def test_learner_with_empty_display_name_raises_error(
        self, entity_id: int, tenant_id: int, whitespace: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Learner)
        
        Learner with empty or whitespace-only display_name raises ValueError.
        """
        with pytest.raises(ValueError, match="display_name cannot be empty"):
            Learner(
                id=entity_id,
                tenant_id=tenant_id,
                display_name=whitespace,
            )

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        display_name=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        notifications=st.booleans(),
    )
    @settings(max_examples=100)
    def test_learner_notifications_method_matches_attribute(
        self, entity_id: int, tenant_id: int, display_name: str, notifications: bool
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Learner)
        
        is_notifications_enabled() returns the same value as notifications_enabled attribute.
        """
        learner = Learner(
            id=entity_id,
            tenant_id=tenant_id,
            display_name=display_name,
            notifications_enabled=notifications,
        )
        assert learner.is_notifications_enabled() == notifications
        assert learner.is_active() == notifications



from src.domain.entities.package import Package, PackageStatus, PaymentStatus


class TestPackageStatusValidation:
    """Property 3: Status Validation (Package).
    
    For any Package entity, creating with an invalid status SHALL raise a ValueError.
    
    **Validates: Requirements 3.4**
    """

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        learner_id=st.integers(min_value=1, max_value=10_000_000),
        title=st.text(min_size=1, max_size=100),
        status=st.sampled_from(list(PackageStatus.ALL)),
    )
    @settings(max_examples=100)
    def test_package_with_valid_status_is_created(
        self, entity_id: int, tenant_id: int, learner_id: int, title: str, status: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Package)
        
        Package with valid status is created successfully.
        """
        package = Package(
            id=entity_id,
            tenant_id=tenant_id,
            learner_id=learner_id,
            title=title,
            status=status,
        )
        assert package.status == status
        assert package.status in PackageStatus.ALL

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        learner_id=st.integers(min_value=1, max_value=10_000_000),
        title=st.text(min_size=1, max_size=100),
        invalid_status=st.text(min_size=1, max_size=20).filter(
            lambda x: x not in PackageStatus.ALL
        ),
    )
    @settings(max_examples=100)
    def test_package_with_invalid_status_raises_error(
        self, entity_id: int, tenant_id: int, learner_id: int, title: str, invalid_status: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Package)
        
        Package with invalid status raises ValueError.
        """
        with pytest.raises(ValueError, match="Invalid status"):
            Package(
                id=entity_id,
                tenant_id=tenant_id,
                learner_id=learner_id,
                title=title,
                status=invalid_status,
            )

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        learner_id=st.integers(min_value=1, max_value=10_000_000),
        title=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_package_status_methods_match_status(
        self, entity_id: int, tenant_id: int, learner_id: int, title: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Package)
        
        is_active(), is_completed(), is_cancelled() return correct values based on status.
        """
        # Test active
        active_pkg = Package(
            id=entity_id, tenant_id=tenant_id, learner_id=learner_id,
            title=title, status=PackageStatus.ACTIVE
        )
        assert active_pkg.is_active() is True
        assert active_pkg.is_completed() is False
        assert active_pkg.is_cancelled() is False

        # Test completed
        completed_pkg = Package(
            id=entity_id, tenant_id=tenant_id, learner_id=learner_id,
            title=title, status=PackageStatus.COMPLETED
        )
        assert completed_pkg.is_active() is False
        assert completed_pkg.is_completed() is True
        assert completed_pkg.is_cancelled() is False

        # Test cancelled
        cancelled_pkg = Package(
            id=entity_id, tenant_id=tenant_id, learner_id=learner_id,
            title=title, status=PackageStatus.CANCELLED
        )
        assert cancelled_pkg.is_active() is False
        assert cancelled_pkg.is_completed() is False
        assert cancelled_pkg.is_cancelled() is True



from datetime import timezone as tz
from src.domain.entities.lesson import Lesson, LessonStatus


class TestLessonStatusValidation:
    """Property 3: Status Validation (Lesson).
    
    For any Lesson entity, creating with an invalid status SHALL raise a ValueError.
    
    **Validates: Requirements 4.4**
    """

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        package_id=st.integers(min_value=1, max_value=10_000_000),
        scheduled_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
        status=st.sampled_from(list(LessonStatus.ALL)),
    )
    @settings(max_examples=100)
    def test_lesson_with_valid_status_is_created(
        self, entity_id: int, tenant_id: int, package_id: int, scheduled_at: datetime, status: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Lesson)
        
        Lesson with valid status is created successfully.
        """
        # Make datetime timezone-aware
        scheduled_at_aware = scheduled_at.replace(tzinfo=tz.utc)
        lesson = Lesson(
            id=entity_id,
            tenant_id=tenant_id,
            package_id=package_id,
            scheduled_at=scheduled_at_aware,
            status=status,
        )
        assert lesson.status == status
        assert lesson.status in LessonStatus.ALL

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        package_id=st.integers(min_value=1, max_value=10_000_000),
        scheduled_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
        invalid_status=st.text(min_size=1, max_size=20).filter(
            lambda x: x not in LessonStatus.ALL
        ),
    )
    @settings(max_examples=100)
    def test_lesson_with_invalid_status_raises_error(
        self, entity_id: int, tenant_id: int, package_id: int, scheduled_at: datetime, invalid_status: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Lesson)
        
        Lesson with invalid status raises ValueError.
        """
        scheduled_at_aware = scheduled_at.replace(tzinfo=tz.utc)
        with pytest.raises(ValueError, match="Invalid status"):
            Lesson(
                id=entity_id,
                tenant_id=tenant_id,
                package_id=package_id,
                scheduled_at=scheduled_at_aware,
                status=invalid_status,
            )

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        package_id=st.integers(min_value=1, max_value=10_000_000),
    )
    @settings(max_examples=100)
    def test_lesson_is_scheduled_method(
        self, entity_id: int, tenant_id: int, package_id: int
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Lesson)
        
        is_scheduled() returns True only for scheduled status.
        """
        future_time = datetime(2030, 1, 1, tzinfo=tz.utc)
        
        scheduled_lesson = Lesson(
            id=entity_id, tenant_id=tenant_id, package_id=package_id,
            scheduled_at=future_time, status=LessonStatus.SCHEDULED
        )
        assert scheduled_lesson.is_scheduled() is True

        completed_lesson = Lesson(
            id=entity_id, tenant_id=tenant_id, package_id=package_id,
            scheduled_at=future_time, status=LessonStatus.COMPLETED
        )
        assert completed_lesson.is_scheduled() is False



from src.domain.entities.reminder import Reminder, ReminderStatus


class TestReminderStatusValidation:
    """Property 3: Status Validation (Reminder).
    
    For any Reminder entity, creating with an invalid status SHALL raise a ValueError.
    
    **Validates: Requirements 5.4**
    """

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        learner_id=st.integers(min_value=1, max_value=10_000_000),
        scheduled_for=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
        reminder_type=st.text(min_size=1, max_size=50),
        status=st.sampled_from(list(ReminderStatus.ALL)),
    )
    @settings(max_examples=100)
    def test_reminder_with_valid_status_is_created(
        self, entity_id: int, tenant_id: int, learner_id: int, 
        scheduled_for: datetime, reminder_type: str, status: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Reminder)
        
        Reminder with valid status is created successfully.
        """
        scheduled_for_aware = scheduled_for.replace(tzinfo=tz.utc)
        reminder = Reminder(
            id=entity_id,
            tenant_id=tenant_id,
            learner_id=learner_id,
            scheduled_for=scheduled_for_aware,
            reminder_type=reminder_type,
            status=status,
        )
        assert reminder.status == status
        assert reminder.status in ReminderStatus.ALL

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        learner_id=st.integers(min_value=1, max_value=10_000_000),
        scheduled_for=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
        reminder_type=st.text(min_size=1, max_size=50),
        invalid_status=st.text(min_size=1, max_size=20).filter(
            lambda x: x not in ReminderStatus.ALL
        ),
    )
    @settings(max_examples=100)
    def test_reminder_with_invalid_status_raises_error(
        self, entity_id: int, tenant_id: int, learner_id: int,
        scheduled_for: datetime, reminder_type: str, invalid_status: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Reminder)
        
        Reminder with invalid status raises ValueError.
        """
        scheduled_for_aware = scheduled_for.replace(tzinfo=tz.utc)
        with pytest.raises(ValueError, match="Invalid status"):
            Reminder(
                id=entity_id,
                tenant_id=tenant_id,
                learner_id=learner_id,
                scheduled_for=scheduled_for_aware,
                reminder_type=reminder_type,
                status=invalid_status,
            )

    @given(
        entity_id=st.integers(min_value=1, max_value=10_000_000),
        tenant_id=st.integers(min_value=1, max_value=10_000_000),
        learner_id=st.integers(min_value=1, max_value=10_000_000),
        reminder_type=st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=100)
    def test_reminder_is_pending_method(
        self, entity_id: int, tenant_id: int, learner_id: int, reminder_type: str
    ):
        """Feature: clean-architecture-phase2, Property 3: Status Validation (Reminder)
        
        is_pending() returns True only for scheduled status.
        """
        future_time = datetime(2030, 1, 1, tzinfo=tz.utc)
        
        scheduled_reminder = Reminder(
            id=entity_id, tenant_id=tenant_id, learner_id=learner_id,
            scheduled_for=future_time, reminder_type=reminder_type,
            status=ReminderStatus.SCHEDULED
        )
        assert scheduled_reminder.is_pending() is True

        sent_reminder = Reminder(
            id=entity_id, tenant_id=tenant_id, learner_id=learner_id,
            scheduled_for=future_time, reminder_type=reminder_type,
            status=ReminderStatus.SENT
        )
        assert sent_reminder.is_pending() is False
