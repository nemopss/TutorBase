from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    BigInteger,
    ForeignKey,
    DateTime,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

class BotUser(Base):
    __tablename__ = 'bot_users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, unique=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    language_code = Column(String(10))
    is_bot = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)

    learner = relationship('Learner', back_populates='bot_user', uselist=False)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True)
    username = Column(String)
    display_name = Column(String, nullable=False)
    role = Column(String(32), nullable=False, default='teacher')
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    last_login_at = Column(DateTime(timezone=True))

    updated_packages = relationship('LessonPackage', back_populates='updated_by')
    updated_lessons = relationship('Lesson', back_populates='updated_by')

class Application(Base):
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    name = Column(Text)
    language = Column(Text)
    level = Column(Text)
    preferred_time = Column(Text)
    contact = Column(Text)

class Student(Base):
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    story = Column(Text, nullable=False)
    photo_file_id = Column(String)


class Learner(Base):
    __tablename__ = 'learners'

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_user_id = Column(Integer, ForeignKey('bot_users.id', ondelete='CASCADE'), nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)

    bot_user = relationship('BotUser', back_populates='learner', lazy='joined')
    packages = relationship('LessonPackage', back_populates='learner', cascade='all, delete-orphan')


class LessonReminder(Base):
    __tablename__ = 'lesson_reminders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_name = Column(String, nullable=False)
    chat_identifier = Column(String, nullable=False)
    is_recurring = Column(Boolean, nullable=False, default=True)
    days = Column(String)
    lesson_time = Column(String)
    lesson_datetime = Column(DateTime(timezone=True))
    lead_minutes = Column(Integer, nullable=False, default=60)
    kind = Column(String(32), nullable=False, default='lesson')
    template_key = Column(String(64))
    next_run_at = Column(DateTime(timezone=True))
    last_notified_at = Column(DateTime(timezone=True))
    last_response = Column(String)
    last_response_at = Column(DateTime(timezone=True))
    last_decline_reason = Column(Text)
    comment = Column(Text)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
class LessonPackageTemplate(Base):
    __tablename__ = 'lesson_package_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    lesson_count = Column(Integer)
    duration_days = Column(Integer)
    default_timezone = Column(String(64), nullable=False, default='Europe/Moscow')
    default_config = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    packages = relationship('LessonPackage', back_populates='template')


class LessonPackage(Base):
    __tablename__ = 'lesson_packages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(Integer, ForeignKey('learners.id', ondelete='CASCADE'), nullable=False)
    template_id = Column(Integer, ForeignKey('lesson_package_templates.id', ondelete='SET NULL'))
    title = Column(String, nullable=False)
    status = Column(String(32), nullable=False, default='draft')
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    timezone = Column(String(64), nullable=False, default='Europe/Moscow')
    total_lessons = Column(Integer)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))

    learner = relationship('Learner', back_populates='packages')
    template = relationship('LessonPackageTemplate', back_populates='packages')
    lessons = relationship('Lesson', back_populates='package', cascade='all, delete-orphan')
    reminder_rules = relationship('ReminderRule', back_populates='package', cascade='all, delete-orphan')
    reminder_instances = relationship('ReminderInstance', back_populates='package', cascade='all, delete-orphan')
    updated_by = relationship('User', back_populates='updated_packages')

    __table_args__ = (
        Index('ix_lesson_packages_learner_status', 'learner_id', 'status'),
    )


class Lesson(Base):
    __tablename__ = 'lessons'

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(Integer, ForeignKey('lesson_packages.id', ondelete='CASCADE'), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer)
    status = Column(String(32), nullable=False, default='scheduled')
    sequence_index = Column(Integer)
    teacher_notes = Column(Text)
    homework_due_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))

    package = relationship('LessonPackage', back_populates='lessons')
    reminder_rules = relationship('ReminderRule', back_populates='lesson', cascade='all, delete-orphan')
    reminder_instances = relationship('ReminderInstance', back_populates='lesson', cascade='all, delete-orphan')
    updated_by = relationship('User', back_populates='updated_lessons')

    __table_args__ = (
        Index('ix_lessons_package_scheduled_at', 'package_id', 'scheduled_at'),
    )


class ReminderRule(Base):
    __tablename__ = 'reminder_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(Integer, ForeignKey('lesson_packages.id', ondelete='CASCADE'))
    lesson_id = Column(Integer, ForeignKey('lessons.id', ondelete='CASCADE'))
    reminder_type = Column(String(32), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    channel = Column(String(32), nullable=False, default='telegram')
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    package = relationship('LessonPackage', back_populates='reminder_rules')
    lesson = relationship('Lesson', back_populates='reminder_rules')
    instances = relationship('ReminderInstance', back_populates='rule', cascade='all, delete-orphan')


class ReminderInstance(Base):
    __tablename__ = 'reminder_instances'

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey('reminder_rules.id', ondelete='CASCADE'), nullable=False)
    package_id = Column(Integer, ForeignKey('lesson_packages.id', ondelete='CASCADE'), nullable=False)
    lesson_id = Column(Integer, ForeignKey('lessons.id', ondelete='CASCADE'))
    learner_id = Column(Integer, ForeignKey('learners.id', ondelete='CASCADE'), nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), nullable=False, default='scheduled')
    payload = Column(JSON, default=dict)
    chat_identifier = Column(String)
    comment = Column(Text)
    active = Column(Boolean, nullable=False, default=True)
    last_notified_at = Column(DateTime(timezone=True))
    last_response = Column(String)
    last_response_at = Column(DateTime(timezone=True))
    last_decline_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    rule = relationship('ReminderRule', back_populates='instances')
    package = relationship('LessonPackage', back_populates='reminder_instances')
    lesson = relationship('Lesson', back_populates='reminder_instances')
    learner = relationship('Learner')
