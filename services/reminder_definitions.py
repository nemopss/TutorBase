"""Shared constants and definitions for reminder system.

This module defines all reminder types, their timing configurations, and validation
sets used throughout the reminder system. These constants are used by reminder
scheduler, rule creation, and message formatting.

Reminder Types:
    - lesson_confirm: Confirmation reminder sent before lesson (default 60 min)
    - lesson_day_before: Day-before reminder sent at specific time (10:00)
    - payment_week: Payment reminder sent week before due date
    - payment_day: Payment reminder sent day before due date
    - homework: Homework reminder sent day before at specific time (10:00)
    - package_renewal: Package renewal reminder sent 14 days before end

Timing Configuration:
    Each reminder type has associated lead time (minutes/days) and optional
    send time (hour:minute) for scheduled reminders. Lead times determine when
    reminder is triggered relative to the event.

Usage:
    Import these constants when creating reminder rules, validating reminder types,
    or building reminder messages in the scheduler.
"""

REMINDER_TYPE_LESSON_CONFIRM = 'lesson_confirm'
REMINDER_TYPE_LESSON_DAY_BEFORE = 'lesson_day_before'
REMINDER_TYPE_PAYMENT_WEEK = 'payment_week'
REMINDER_TYPE_PAYMENT_DAY = 'payment_day'
REMINDER_TYPE_HOMEWORK = 'homework'
REMINDER_TYPE_PACKAGE_RENEWAL = 'package_renewal'

DEFAULT_LESSON_CONFIRM_LEAD_MINUTES = 60
LESSON_DAY_BEFORE_LEAD_DAYS = 1
LESSON_DAY_BEFORE_SEND_HOUR = 10
LESSON_DAY_BEFORE_SEND_MINUTE = 0
HOMEWORK_LEAD_DAYS = 1
HOMEWORK_SEND_HOUR = 10
HOMEWORK_SEND_MINUTE = 0
PACKAGE_RENEWAL_LEAD_DAYS = 14
PACKAGE_RENEWAL_SEND_HOUR = 10
PACKAGE_RENEWAL_SEND_MINUTE = 0

VALID_REMINDER_TYPES = {
    REMINDER_TYPE_LESSON_CONFIRM,
    REMINDER_TYPE_LESSON_DAY_BEFORE,
    REMINDER_TYPE_PAYMENT_WEEK,
    REMINDER_TYPE_PAYMENT_DAY,
    REMINDER_TYPE_HOMEWORK,
    REMINDER_TYPE_PACKAGE_RENEWAL,
}
