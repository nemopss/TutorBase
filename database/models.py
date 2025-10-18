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
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=True, index=True)
    telegram_id = Column(BigInteger, unique=True)
    username = Column(String)
    display_name = Column(String, nullable=False)
    role = Column(String(32), nullable=False, default='viewer')
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    last_login_at = Column(DateTime(timezone=True))

    tenant = relationship('Tenant', back_populates='users')
    updated_packages = relationship('LessonPackage', back_populates='updated_by')
    updated_lessons = relationship('Lesson', back_populates='updated_by')
    created_invite_tokens = relationship('InviteToken', back_populates='created_by')

class Application(Base):
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    name = Column(Text)
    language = Column(Text)
    level = Column(Text)
    preferred_time = Column(Text)
    contact = Column(Text)

    tenant = relationship('Tenant', back_populates='applications')


class InviteToken(Base):
    __tablename__ = 'invite_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    
    # Relationships
    tenant = relationship('Tenant', back_populates='invite_tokens')
    created_by = relationship('User', back_populates='created_invite_tokens')
    
    @property
    def is_expired(self) -> bool:
        """Check if the invite token has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_used(self) -> bool:
        """Check if the invite token has been used."""
        return self.used_at is not None
    
    @property
    def is_valid(self) -> bool:
        """Check if the invite token is valid (not expired and not used)."""
        return not self.is_expired and not self.is_used


class Student(Base):
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    story = Column(Text, nullable=False)
    photo_file_id = Column(String)


class Learner(Base):
    __tablename__ = 'learners'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    bot_user_id = Column(Integer, ForeignKey('bot_users.id', ondelete='CASCADE'), nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    notes = Column(Text)
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    tenant = relationship('Tenant', back_populates='learners')
    bot_user = relationship('BotUser', back_populates='learner', lazy='joined')
    packages = relationship('LessonPackage', back_populates='learner', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_learners_tenant_display_name', 'tenant_id', 'display_name'),
        Index('ix_learners_tenant_created', 'tenant_id', 'created_at'),
    )

class LessonPackageTemplate(Base):
    __tablename__ = 'lesson_package_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    lesson_count = Column(Integer)
    duration_days = Column(Integer)
    default_timezone = Column(String(64), nullable=False, default='Europe/Moscow')
    default_config = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='lesson_package_templates')
    packages = relationship('LessonPackage', back_populates='template')


class LessonPackage(Base):
    __tablename__ = 'lesson_packages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
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

    tenant = relationship('Tenant', back_populates='lesson_packages')

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
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
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

    tenant = relationship('Tenant', back_populates='lessons')

    package = relationship('LessonPackage', back_populates='lessons')
    reminder_rules = relationship('ReminderRule', back_populates='lesson', cascade='all, delete-orphan')
    reminder_instances = relationship('ReminderInstance', back_populates='lesson', cascade='all, delete-orphan')
    updated_by = relationship('User', back_populates='updated_lessons')

    __table_args__ = (
        Index('ix_lessons_package_scheduled_at', 'package_id', 'scheduled_at'),
        Index('ix_lessons_tenant_scheduled', 'tenant_id', 'scheduled_at'),
        Index('ix_lessons_tenant_status', 'tenant_id', 'status'),
    )


class ReminderRule(Base):
    __tablename__ = 'reminder_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey('lesson_packages.id', ondelete='CASCADE'))
    lesson_id = Column(Integer, ForeignKey('lessons.id', ondelete='CASCADE'))
    reminder_type = Column(String(32), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    channel = Column(String(32), nullable=False, default='telegram')
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='reminder_rules')

    package = relationship('LessonPackage', back_populates='reminder_rules')
    lesson = relationship('Lesson', back_populates='reminder_rules')
    instances = relationship('ReminderInstance', back_populates='rule', cascade='all, delete-orphan')


class ReminderInstance(Base):
    __tablename__ = 'reminder_instances'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
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

    tenant = relationship('Tenant', back_populates='reminder_instances')

    rule = relationship('ReminderRule', back_populates='instances')
    package = relationship('LessonPackage', back_populates='reminder_instances')
    lesson = relationship('Lesson', back_populates='reminder_instances')
    learner = relationship('Learner')

    __table_args__ = (
        Index('ix_reminder_instances_tenant_scheduled', 'tenant_id', 'scheduled_for'),
        Index('ix_reminder_instances_tenant_status_active', 'tenant_id', 'status', 'active'),
        Index('ix_reminder_instances_active_scheduled', 'active', 'scheduled_for'),  # For global queries
    )

class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, unique=True, nullable=False)
    contact_email = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    users = relationship('User', back_populates='tenant')
    learners = relationship('Learner', back_populates='tenant')
    lesson_package_templates = relationship('LessonPackageTemplate', back_populates='tenant')
    lesson_packages = relationship('LessonPackage', back_populates='tenant')
    lessons = relationship('Lesson', back_populates='tenant')
    reminder_rules = relationship('ReminderRule', back_populates='tenant')
    reminder_instances = relationship('ReminderInstance', back_populates='tenant')
    applications = relationship('Application', back_populates='tenant')
    invite_tokens = relationship('InviteToken', back_populates='tenant')


