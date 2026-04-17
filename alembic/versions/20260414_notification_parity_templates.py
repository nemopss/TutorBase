"""Align notification templates with legacy reminder wording.

Revision ID: 20260414_notification_parity
Revises: 20260407_notifications
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260414_notification_parity"
down_revision = "20260407_notifications"
branch_labels = None
depends_on = None


NEW_TEMPLATE_BODIES = {
    "lesson_confirmation_day_before_ru": (
        "Привет, {student_name}! Напоминаю, у тебя завтра занятие {lesson_datetime}. Всё в силе?"
    ),
    "lesson_confirmation_with_homework_ru": (
        "Привет, {student_name}! Напоминаю, у тебя завтра занятие {lesson_datetime}. Всё в силе?\n\n"
        "И не забудь выполнить и отправить домашку как минимум за час до времени твоего урока."
    ),
    "lesson_reminder_soon_ru": (
        "Привет, {student_name}! Напоминаю о занятии {lesson_datetime}."
    ),
    "homework_before_lesson_ru": (
        "Привет, {student_name}! Напоминаю: урок {lesson_datetime}. "
        "Не забудь выполнить и отправить домашку как минимум за час до времени твоего урока."
    ),
    "package_renewal_ru": (
        "Привет, {student_name}! Твой пакет занятий заканчивается {package_end}. "
        "Скажи, пожалуйста, ты планируешь продолжать занятия в следующем месяце?"
    ),
}


OLD_TEMPLATE_BODIES = {
    "lesson_confirmation_day_before_ru": (
        "Привет, {student_name}! Завтра у нас урок в {lesson_time}. Всё в силе?"
    ),
    "lesson_confirmation_with_homework_ru": (
        "Привет, {student_name}! Завтра у нас урок в {lesson_time}. Всё в силе?\n\n"
        "И не забудь домашку."
    ),
    "lesson_reminder_soon_ru": (
        "Привет, {student_name}! Напоминаю: урок сегодня в {lesson_time}."
    ),
    "homework_before_lesson_ru": (
        "Привет, {student_name}! Напоминаю про домашку к уроку {lesson_datetime}."
    ),
    "package_renewal_ru": (
        "Привет, {student_name}! Пакет {package_title} скоро заканчивается. Обсудим продление?"
    ),
}


def upgrade() -> None:
    _update_system_templates(NEW_TEMPLATE_BODIES)


def downgrade() -> None:
    _update_system_templates(OLD_TEMPLATE_BODIES)


def _update_system_templates(template_bodies: dict[str, str]) -> None:
    for key, body in template_bodies.items():
        op.execute(
            sa.text(
                """
                UPDATE notification_templates
                SET body = :body,
                    updated_at = CURRENT_TIMESTAMP
                WHERE key = :key
                  AND tenant_id IS NULL
                  AND system IS TRUE
                  AND locale = 'ru'
                  AND version = 1
                """
            ).bindparams(key=key, body=body)
        )
