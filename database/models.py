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
    Numeric,
    UniqueConstraint,
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
    learner_account_links = relationship('LearnerAccountLink', back_populates='bot_user')
    broadcast_recipients = relationship('BroadcastRecipient', back_populates='bot_user')


class BroadcastCampaign(Base):
    """Platform-wide Telegram broadcast campaign."""
    __tablename__ = 'broadcast_campaigns'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    title = Column(String, nullable=False)
    message_text = Column(Text, nullable=False)
    audience = Column(String(64), nullable=False, default='all_bot_users')
    status = Column(String(32), nullable=False, default='draft')
    recipient_count = Column(Integer, nullable=False, default=0)
    sent_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    rate_limit_per_second = Column(Integer, nullable=False, default=10)
    last_task_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    queued_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_by = relationship('User', foreign_keys=[created_by_user_id])
    recipients = relationship('BroadcastRecipient', back_populates='campaign', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_broadcast_campaigns_status_created', 'status', 'created_at'),
    )


class BroadcastRecipient(Base):
    """Snapshot of a Telegram broadcast recipient and delivery state."""
    __tablename__ = 'broadcast_recipients'

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('broadcast_campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    bot_user_id = Column(Integer, ForeignKey('bot_users.id', ondelete='SET NULL'), nullable=True, index=True)
    chat_id = Column(BigInteger, nullable=False)
    display_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    status = Column(String(32), nullable=False, default='pending')
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    campaign = relationship('BroadcastCampaign', back_populates='recipients')
    bot_user = relationship('BotUser', back_populates='broadcast_recipients')

    __table_args__ = (
        UniqueConstraint('campaign_id', 'chat_id', name='uq_broadcast_recipients_campaign_chat'),
        Index('ix_broadcast_recipients_campaign_status', 'campaign_id', 'status'),
    )


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
    email = Column(String, nullable=True, unique=True)
    email_normalized = Column(String, nullable=True, unique=True)
    password_hash = Column(String, nullable=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    display_name = Column(String, nullable=False)
    role = Column(String(32), nullable=False, default='viewer')
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    last_login_at = Column(DateTime(timezone=True))

    tenant = relationship('Tenant', back_populates='users')
    updated_packages = relationship('LessonPackage', back_populates='updated_by')
    updated_lessons = relationship('Lesson', back_populates='updated_by')
    created_invite_tokens = relationship('InviteToken', back_populates='created_by')
    learner_account_links = relationship(
        'LearnerAccountLink',
        foreign_keys='LearnerAccountLink.user_id',
        back_populates='user',
    )
    legal_acceptances = relationship('LegalAcceptance', back_populates='user')
    email_verification_tokens = relationship('EmailVerificationToken', back_populates='user')


class EmailVerificationToken(Base):
    """One-time token for confirming a user's current email address."""
    __tablename__ = 'email_verification_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    email_normalized = Column(String, nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    user = relationship('User', back_populates='email_verification_tokens')

    __table_args__ = (
        Index('ix_email_verification_tokens_user_unused', 'user_id', 'used_at'),
    )


class LegalAcceptance(Base):
    """Audit record for legal document acceptance during registration."""
    __tablename__ = 'legal_acceptances'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    role = Column(String(32), nullable=False)
    offer_version = Column(String(32), nullable=False)
    privacy_version = Column(String(32), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    ip_address = Column(String(128), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    user = relationship('User', back_populates='legal_acceptances')
    tenant = relationship('Tenant', back_populates='legal_acceptances')

    __table_args__ = (
        Index('ix_legal_acceptances_user_accepted', 'user_id', 'accepted_at'),
        Index('ix_legal_acceptances_tenant_accepted', 'tenant_id', 'accepted_at'),
    )


class TenantAccess(Base):
    """SaaS access state for a tutor tenant."""
    __tablename__ = 'tenant_access'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    status = Column(String(32), nullable=False, default='lifetime')
    access_until = Column(DateTime(timezone=True), nullable=True)
    grace_until = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='access')
    updated_by = relationship('User', foreign_keys=[updated_by_user_id])

    __table_args__ = (
        Index('ix_tenant_access_status_until', 'status', 'access_until'),
    )


class TenantAccessEvent(Base):
    """Audit log for manual tenant access changes."""
    __tablename__ = 'tenant_access_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='access_events')
    actor = relationship('User', foreign_keys=[actor_user_id])


class BillingPlan(Base):
    """Public billing plan and its learner limit."""
    __tablename__ = 'billing_plans'

    code = Column(String(32), primary_key=True)
    name = Column(String(64), nullable=False)
    active_learners_limit = Column(Integer, nullable=False)
    monthly_price_rub = Column(Integer, nullable=False, default=0)
    yearly_price_rub = Column(Integer, nullable=True)
    is_public = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    subscriptions = relationship('TenantSubscription', back_populates='plan')


class TenantSubscription(Base):
    """Billing subscription state for a tenant.

    This controls plan limits and billing-driven feature flags. It does not
    replace TenantAccess, which remains the manual hard-block mechanism.
    """
    __tablename__ = 'tenant_subscriptions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    plan_code = Column(String(32), ForeignKey('billing_plans.code'), nullable=False, default='start', index=True)
    status = Column(String(32), nullable=False, default='active', index=True)
    provider = Column(String(32), nullable=False, default='manual')
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    grace_until = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    provider_customer_id = Column(String, nullable=True)
    provider_payment_id = Column(String, nullable=True)
    provider_subscription_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='subscription')
    plan = relationship('BillingPlan', back_populates='subscriptions')
    updated_by = relationship('User', foreign_keys=[updated_by_user_id])
    events = relationship('BillingEvent', back_populates='subscription', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_tenant_subscriptions_status_period', 'status', 'current_period_end'),
        Index('ix_tenant_subscriptions_provider_subscription', 'provider', 'provider_subscription_id'),
    )


class BillingEvent(Base):
    """Audit log for billing and subscription changes."""
    __tablename__ = 'billing_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey('tenant_subscriptions.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='billing_events')
    subscription = relationship('TenantSubscription', back_populates='events')
    actor = relationship('User', foreign_keys=[actor_user_id])

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
    learner_id = Column(Integer, ForeignKey('learners.id', ondelete='SET NULL'), nullable=True, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    
    # Relationships
    tenant = relationship('Tenant', back_populates='invite_tokens')
    learner = relationship('Learner', back_populates='invite_tokens')
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
        bot_user_id: Linked Telegram bot user ID (unique among active links)
        display_name: Display name for the learner
        notes: Teacher notes about the learner
        notifications_enabled: Whether to send reminders to this learner
        lesson_rate: Individual lesson rate for this learner (price per lesson)
        archived_at: When the learner was softly archived, if archived
        created_at: Learner creation timestamp
        tenant: Related Tenant object
        bot_user: Related BotUser object (eager loaded)
        packages: Lesson packages for this learner
    """
    __tablename__ = 'learners'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    bot_user_id = Column(Integer, ForeignKey('bot_users.id', ondelete='SET NULL'), nullable=True, unique=True)
    display_name = Column(String, nullable=False)
    notes = Column(Text)
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    lesson_rate = Column(Numeric(10, 2), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    tenant = relationship('Tenant', back_populates='learners')
    bot_user = relationship('BotUser', back_populates='learner', lazy='joined')
    packages = relationship('LessonPackage', back_populates='learner', cascade='all, delete-orphan')
    payments = relationship('Payment', back_populates='learner', cascade='all, delete-orphan')
    schedule = relationship('LessonPackageTemplate', back_populates='learner', uselist=False, 
                           foreign_keys='LessonPackageTemplate.learner_id', cascade='all, delete-orphan')
    account_links = relationship(
        'LearnerAccountLink',
        back_populates='learner',
        cascade='all, delete-orphan',
        order_by='LearnerAccountLink.linked_at.desc()',
    )
    invite_tokens = relationship('InviteToken', back_populates='learner')

    __table_args__ = (
        Index('ix_learners_tenant_display_name', 'tenant_id', 'display_name'),
        Index('ix_learners_tenant_created', 'tenant_id', 'created_at'),
        Index('ix_learners_tenant_archived_display_name', 'tenant_id', 'archived_at', 'display_name'),
    )

class LearnerAccountLink(Base):
    """Historical link between a learner and a Telegram account.

    Learners can be unlinked from Telegram accounts without deleting lesson,
    payment, package, or reminder history. The active link is the row with
    unlinked_at set to NULL.
    """
    __tablename__ = 'learner_account_links'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    learner_id = Column(Integer, ForeignKey('learners.id', ondelete='CASCADE'), nullable=False, index=True)
    bot_user_id = Column(Integer, ForeignKey('bot_users.id', ondelete='SET NULL'), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    linked_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    unlinked_at = Column(DateTime(timezone=True), nullable=True)
    unlinked_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    unlink_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='learner_account_links')
    learner = relationship('Learner', back_populates='account_links')
    bot_user = relationship('BotUser', back_populates='learner_account_links')
    user = relationship('User', foreign_keys=[user_id], back_populates='learner_account_links')
    unlinked_by = relationship('User', foreign_keys=[unlinked_by_user_id])

    __table_args__ = (
        Index('ix_learner_account_links_active', 'tenant_id', 'learner_id', 'unlinked_at'),
        Index('ix_learner_account_links_tenant_telegram', 'tenant_id', 'telegram_id'),
    )

class LessonPackageTemplate(Base):
    """Template for creating lesson packages and learner schedules.
    
    This table serves dual purpose:
    1. Reusable templates for lesson packages (legacy, learner_id=NULL)
    2. Learner schedules - weekly recurring rules (learner_id set)
    
    For learner schedules, the default_config stores:
    {
        "schedule": {
            "slots": [{"day": 0, "time": "14:00", "duration": 60}, ...],
            "timezone": "Europe/Moscow"
        }
    }
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID
        learner_id: Learner ID for schedules (NULL for templates)
        name: Template name (not unique, can be empty for schedules)
        description: Template description
        lesson_count: Default number of lessons
        duration_days: Default package duration in days
        default_timezone: Default timezone for lessons
        default_config: JSON configuration (schedule slots for learner schedules)
        created_at: Template creation timestamp
        updated_at: Last template update timestamp
        tenant: Related Tenant object
        learner: Related Learner object (for schedules)
        packages: Lesson packages created from this template
    """
    __tablename__ = 'lesson_package_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    learner_id = Column(Integer, ForeignKey('learners.id', ondelete='CASCADE'), nullable=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    lesson_count = Column(Integer)
    duration_days = Column(Integer)
    default_timezone = Column(String(64), nullable=False, default='Europe/Moscow')
    default_config = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='lesson_package_templates')
    learner = relationship('Learner', back_populates='schedule', foreign_keys=[learner_id])
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
        package_type: Package type (package, one_off)
        title: Package title/name
        status: Package status (draft, active, completed, cancelled)
        start_date: Package start date
        end_date: Package end date
        timezone: Timezone for lesson scheduling
        total_lessons: Total number of lessons in package
        price: Calculated or manual package price
        payment_status: Payment status (unpaid, partial, paid)
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
    package_type = Column(String(32), nullable=False, default='package')
    title = Column(String, nullable=False)
    status = Column(String(32), nullable=False, default='draft')
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    timezone = Column(String(64), nullable=False, default='Europe/Moscow')
    total_lessons = Column(Integer)
    price = Column(Numeric(10, 2), nullable=True)
    payment_status = Column(String(16), nullable=False, default='unpaid')
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
    payments = relationship('Payment', back_populates='package')

    __table_args__ = (
        Index('ix_lesson_packages_learner_status', 'learner_id', 'status'),
        Index('ix_lesson_packages_tenant_type_status', 'tenant_id', 'package_type', 'status'),
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
        price: Price for standalone lessons
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
    price = Column(Numeric(10, 2), nullable=True)
    teacher_notes = Column(Text)
    has_homework = Column(Boolean)
    homework_text = Column(Text)
    homework_due_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))

    tenant = relationship('Tenant', back_populates='lessons')

    package = relationship('LessonPackage', back_populates='lessons')
    reminder_rules = relationship('ReminderRule', back_populates='lesson', cascade='all, delete-orphan')
    reminder_instances = relationship('ReminderInstance', back_populates='lesson', cascade='all, delete-orphan')
    updated_by = relationship('User', back_populates='updated_lessons')
    payments = relationship('Payment', back_populates='lesson')

    __table_args__ = (
        Index('ix_lessons_package_scheduled_at', 'package_id', 'scheduled_at'),
        Index('ix_lessons_tenant_scheduled', 'tenant_id', 'scheduled_at'),
        Index('ix_lessons_tenant_status', 'tenant_id', 'status'),
    )


class DashboardAttentionDismissal(Base):
    """Persist dismissed dashboard attention items for the current tenant.

    Stores acknowledgement state for dismissible dashboard notices such as
    package-ending warnings and learner lesson-decline notices. Dismissals are
    scoped to a tenant and expire automatically after ``dismissed_until``.
    """
    __tablename__ = 'dashboard_attention_dismissals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    item_type = Column(String(64), nullable=False)
    item_key = Column(String(255), nullable=False)
    dismissed_until = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant')

    __table_args__ = (
        UniqueConstraint('tenant_id', 'item_type', 'item_key', name='uq_dashboard_attention_dismissals_item'),
        Index('ix_dashboard_attention_dismissals_active', 'tenant_id', 'item_type', 'dismissed_until'),
    )


class NotificationActivityAcknowledgement(Base):
    """Persist handled state for teacher-facing notification activity items."""
    __tablename__ = 'notification_activity_acknowledgements'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    activity_type = Column(String(64), nullable=False)
    activity_id = Column(Integer, nullable=False)
    acknowledged_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant')
    acknowledged_by_user = relationship('User')

    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'activity_type',
            'activity_id',
            name='uq_notification_activity_acknowledgements_item',
        ),
        Index(
            'ix_notification_activity_acknowledgements_lookup',
            'tenant_id',
            'activity_type',
            'acknowledged_at',
        ),
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
        retry_count: Number of retry attempts for temporary failures (max 3)
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
    retry_count = Column(Integer, nullable=False, default=0)  # Track retry attempts for temporary failures
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

class Payment(Base):
    """Payment record for tracking learner payments.
    
    Stores payment information for packages or standalone lessons.
    Supports multi-tenancy and tracks payment history.
    
    Attributes:
        id: Primary key
        tenant_id: Associated tenant ID for multi-tenancy
        learner_id: Learner who made the payment
        package_id: Associated package (nullable for standalone lessons)
        lesson_id: Associated lesson (for standalone lesson payments)
        amount: Payment amount
        currency: Currency code (default RUB)
        paid_at: Payment date
        notes: Optional payment notes
        created_at: Record creation timestamp
        updated_at: Record update timestamp
        tenant: Related Tenant object
        learner: Related Learner object
        package: Related LessonPackage object (if package payment)
        lesson: Related Lesson object (if standalone lesson payment)
    """
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    learner_id = Column(Integer, ForeignKey('learners.id', ondelete='CASCADE'), nullable=False)
    package_id = Column(Integer, ForeignKey('lesson_packages.id', ondelete='SET NULL'), nullable=True)
    lesson_id = Column(Integer, ForeignKey('lessons.id', ondelete='SET NULL'), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default='RUB')
    paid_at = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text, nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    voided_at = Column(DateTime(timezone=True), nullable=True)
    voided_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    void_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    tenant = relationship('Tenant', back_populates='payments')
    learner = relationship('Learner', back_populates='payments')
    package = relationship('LessonPackage', back_populates='payments')
    lesson = relationship('Lesson', back_populates='payments')
    updated_by = relationship('User', foreign_keys=[updated_by_user_id])
    voided_by = relationship('User', foreign_keys=[voided_by_user_id])
    audit_events = relationship('PaymentAuditEvent', back_populates='payment', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_payments_tenant_learner', 'tenant_id', 'learner_id'),
        Index('ix_payments_tenant_paid_at', 'tenant_id', 'paid_at'),
        Index('ix_payments_tenant_voided', 'tenant_id', 'voided_at'),
    )


class PaymentAuditEvent(Base):
    """Audit log for payment lifecycle changes."""
    __tablename__ = 'payment_audit_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey('payments.id', ondelete='CASCADE'), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    payment = relationship('Payment', back_populates='audit_events')
    tenant = relationship('Tenant')
    actor = relationship('User', foreign_keys=[actor_user_id])


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
        payments: Payment records for this tenant
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
    payments = relationship('Payment', back_populates='tenant')
    learner_account_links = relationship('LearnerAccountLink', back_populates='tenant')
    access = relationship('TenantAccess', back_populates='tenant', uselist=False, cascade='all, delete-orphan')
    access_events = relationship('TenantAccessEvent', back_populates='tenant', cascade='all, delete-orphan')
    subscription = relationship('TenantSubscription', back_populates='tenant', uselist=False, cascade='all, delete-orphan')
    billing_events = relationship('BillingEvent', back_populates='tenant', cascade='all, delete-orphan')
    legal_acceptances = relationship('LegalAcceptance', back_populates='tenant', cascade='all, delete-orphan')


# Import models from the new notification bounded context so they share the same
# SQLAlchemy metadata for create_all and Alembic autogenerate.
import notifications.infrastructure.models  # noqa: E402,F401
