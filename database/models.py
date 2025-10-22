"""SQLAlchemy models for all database entities.

This module contains all database table definitions using SQLAlchemy ORM,
including models for users, lessons, packages, reminders, and multi-tenancy.

Main models:
    - Tenant: Organizations for multi-tenancy isolation
    - User: System users (teachers, admins) with role-based access
    - BotUser: Telegram bot users with chat information
    - Learner: Students linked to bot users and tenants
    - LessonPackageTemplate: Reusable templates for lesson packages
    - LessonPackage: Collections of lessons for learners
    - Lesson: Individual lesson sessions with scheduling
    - ReminderRule: Rules for automated reminders
    - ReminderInstance: Scheduled reminder executions
    - Application: Student applications from bot
    - InviteToken: Invitation tokens for user registration
    - Student: Legacy student model (deprecated)
"""
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
    """Get current UTC datetime.
    
    Returns:
        Current datetime in UTC timezone
    """
    return datetime.now(timezone.utc)

class BotUser(Base):
    """Telegram bot user model.
    
    Stores information about users interacting with the Telegram bot.
    Tracks user profile data and activity timestamps.
    
    Attributes:
        id: Primary key
        chat_id: Telegram chat ID (unique identifier)
        username: Telegram username (without @)
        first_name: User's first name from Telegram
        last_name: User's last name from Telegram
        language_code: User's language code (e.g., 'ru', 'en')
        is_bot: Flag indicating if this is a bot account
        created_at: Account creation timestamp
        updated_at: Last profile update timestamp
        last_seen_at: Last activity timestamp
        learner: Related Learner object (one-to-one)
    """
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
    """System user model for teachers and administrators.
    
    Represents users who access the system through the web interface.
    Supports role-based access control and multi-tenancy.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID for multi-tenancy
        telegram_id: Optional Telegram ID for linking
        username: Username for login
        display_name: Display name shown in UI
        role: User role (admin, teacher, viewer)
        created_at: Account creation timestamp
        updated_at: Last profile update timestamp
        last_login_at: Last login timestamp
        tenant: Related Tenant object
        updated_packages: Lesson packages updated by this user
        updated_lessons: Lessons updated by this user
        created_invite_tokens: Invite tokens created by this user
    """
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
    """Student application model from Telegram bot.
    
    Stores applications submitted by potential students through the bot.
    Used for lead generation and student onboarding workflow.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID
        created_at: Application submission timestamp
        name: Applicant's name
        language: Language they want to learn
        level: Current language level
        preferred_time: Preferred lesson time
        contact: Contact information
        tenant: Related Tenant object
    """
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
    """Invitation token model for user registration.
    
    Manages invitation tokens for registering new users to tenants.
    Tokens have expiration dates and can only be used once.
    
    Attributes:
        id: Primary key
        tenant_id: Tenant this invitation is for
        token: Unique token string
        expires_at: Token expiration timestamp
        used_at: Timestamp when token was used (None if unused)
        created_by_user_id: User who created this token
        created_at: Token creation timestamp
        tenant: Related Tenant object
        created_by: User who created this token
    """
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
        """Check if token has expired.
        
        Returns:
            True if current time is past expiration date
        """
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_used(self) -> bool:
        """Check if token has been used.
        
        Returns:
            True if used_at is set
        """
        return self.used_at is not None
    
    @property
    def is_valid(self) -> bool:
        """Check if token is valid for use.
        
        Returns:
            True if token is not expired and not used
        """
        return not self.is_expired and not self.is_used


class Student(Base):
    """Legacy student model (deprecated).
    
    This model is deprecated and kept for backward compatibility.
    Use Learner model for new implementations.
    
    Attributes:
        id: Primary key
        name: Student name
        story: Student story/description
        photo_file_id: Telegram file ID for student photo
    """
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    story = Column(Text, nullable=False)
    photo_file_id = Column(String)


class Learner(Base):
    """Student/learner model linked to bot users.
    
    Represents students who take lessons. Each learner is linked to
    a Telegram bot user and belongs to a tenant for multi-tenancy.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID
        bot_user_id: Linked Telegram bot user ID (unique)
        display_name: Display name for the learner
        notes: Teacher notes about the learner
        notifications_enabled: Whether to send reminders to this learner
        created_at: Learner creation timestamp
        tenant: Related Tenant object
        bot_user: Related BotUser object (eager loaded)
        packages: Lesson packages for this learner
    """
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
    """Template for creating lesson packages.
    
    Reusable templates that define package structure, lesson count,
    duration, and default configuration for creating new packages.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID
        name: Unique template name
        description: Template description
        lesson_count: Default number of lessons
        duration_days: Default package duration in days
        default_timezone: Default timezone for lessons
        default_config: JSON configuration for template settings
        created_at: Template creation timestamp
        updated_at: Last template update timestamp
        tenant: Related Tenant object
        packages: Lesson packages created from this template
    """
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
    """Lesson package model for grouping lessons.
    
    Represents a collection of lessons for a learner. Packages can be
    created from templates and track overall progress and status.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID
        learner_id: Learner this package belongs to
        template_id: Template used to create this package (optional)
        title: Package title/name
        status: Package status (draft, active, completed, cancelled)
        start_date: Package start date
        end_date: Package end date
        timezone: Timezone for lesson scheduling
        total_lessons: Total number of lessons in package
        notes: Teacher notes about the package
        created_at: Package creation timestamp
        updated_at: Last package update timestamp
        updated_by_user_id: User who last updated the package
        tenant: Related Tenant object
        learner: Related Learner object
        template: Related template (if created from template)
        lessons: All lessons in this package
        reminder_rules: Reminder rules for this package
        reminder_instances: Reminder instances for this package
        updated_by: User who last updated the package
    """
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
    """Individual lesson model.
    
    Represents a single lesson session within a package. Tracks scheduling,
    status, duration, and teacher notes.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID
        package_id: Parent lesson package ID
        scheduled_at: Scheduled lesson datetime
        duration_minutes: Lesson duration in minutes
        status: Lesson status (scheduled, completed, cancelled, missed)
        sequence_index: Order of lesson in package
        teacher_notes: Notes from teacher about the lesson
        homework_due_at: Homework deadline datetime
        created_at: Lesson creation timestamp
        updated_at: Last lesson update timestamp
        updated_by_user_id: User who last updated the lesson
        tenant: Related Tenant object
        package: Related LessonPackage object
        reminder_rules: Reminder rules for this lesson
        reminder_instances: Reminder instances for this lesson
        updated_by: User who last updated the lesson
    """
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
    """Reminder rule model for automated notifications.
    
    Defines rules for creating reminder instances. Rules can be attached
    to packages or individual lessons and specify timing and content.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID
        package_id: Package this rule applies to (optional)
        lesson_id: Lesson this rule applies to (optional)
        reminder_type: Type of reminder (lesson_reminder, homework_reminder, etc.)
        config: JSON configuration for reminder timing and content
        channel: Notification channel (telegram, email, etc.)
        active: Whether this rule is active
        created_at: Rule creation timestamp
        updated_at: Last rule update timestamp
        tenant: Related Tenant object
        package: Related LessonPackage (if package-level rule)
        lesson: Related Lesson (if lesson-level rule)
        instances: Reminder instances created from this rule
    """
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
    """Reminder instance model for scheduled notifications.
    
    Represents a specific scheduled reminder to be sent to a learner.
    Tracks delivery status, responses, and interaction history.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID
        rule_id: Reminder rule that created this instance
        package_id: Related lesson package
        lesson_id: Related lesson (optional)
        learner_id: Learner to receive this reminder
        scheduled_for: When to send this reminder
        status: Instance status (scheduled, sent, confirmed, declined, cancelled)
        payload: JSON data for reminder content
        chat_identifier: Telegram chat ID for sending
        comment: Additional comment or context
        active: Whether this instance is active
        last_notified_at: Last notification send timestamp
        last_response: Last response from learner
        last_response_at: Last response timestamp
        last_decline_reason: Reason if learner declined
        created_at: Instance creation timestamp
        updated_at: Last instance update timestamp
        tenant: Related Tenant object
        rule: Related ReminderRule object
        package: Related LessonPackage object
        lesson: Related Lesson object (if lesson-specific)
        learner: Related Learner object
    """
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
    """Tenant model for multi-tenancy support.
    
    Represents an organization or school using the system. All data
    is isolated by tenant for security and data separation.
    
    Attributes:
        id: Primary key
        name: Tenant display name
        slug: URL-friendly unique identifier
        contact_email: Contact email for tenant
        is_active: Whether tenant is active
        created_at: Tenant creation timestamp
        updated_at: Last tenant update timestamp
        users: System users belonging to this tenant
        learners: Learners belonging to this tenant
        lesson_package_templates: Templates for this tenant
        lesson_packages: Lesson packages for this tenant
        lessons: Lessons for this tenant
        reminder_rules: Reminder rules for this tenant
        reminder_instances: Reminder instances for this tenant
        applications: Student applications for this tenant
        invite_tokens: Invitation tokens for this tenant
    """
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


