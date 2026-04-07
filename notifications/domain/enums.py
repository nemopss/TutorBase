from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    LESSON = "lesson"
    PACKAGE = "package"
    CUSTOM_DATE = "custom_date"


class TriggerType(StrEnum):
    RELATIVE_OFFSET = "relative_offset"
    DAY_OFFSET_AT_TIME = "day_offset_at_time"
    AFTER_EVENT_OFFSET = "after_event_offset"
    ABSOLUTE_DATETIME = "absolute_datetime"


class CategoryKey(StrEnum):
    LESSON_CONFIRMATION = "lesson_confirmation"
    LESSON_REMINDER = "lesson_reminder"
    HOMEWORK = "homework"
    PACKAGE_RENEWAL = "package_renewal"
    PAYMENT = "payment"
    CUSTOM = "custom"
    TEACHER_ALERT = "teacher_alert"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class RuleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class InstanceStatus(StrEnum):
    SHADOW = "shadow"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    SENT = "sent"
    CANCELLED = "cancelled"
    SUPPRESSED = "suppressed"
    SKIPPED = "skipped"
    FAILED = "failed"
    EXPIRED = "expired"


class PreferenceScope(StrEnum):
    GLOBAL = "global"
    GROUP = "group"
    LEARNER = "learner"
    PACKAGE = "package"


class QuietHoursMode(StrEnum):
    SHIFT = "shift"
    WARN_ONLY = "warn_only"
    OFF = "off"


class CapMode(StrEnum):
    WARN_ONLY = "warn_only"
    ENFORCE = "enforce"


class NotificationSystemMode(StrEnum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    NEW = "new"
    INHERIT = "inherit"
