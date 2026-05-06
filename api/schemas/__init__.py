"""Pydantic schemas for API request/response validation.

This package contains all Pydantic models used for:
- Request validation at API boundary
- Response serialization
- Data transfer between layers

Structure:
    - base.py: Common base models and mixins
    - pagination.py: Pagination request/response models
    - validators.py: Custom Pydantic validators
    - packages.py: Package-related schemas
    - lessons.py: Lesson-related schemas
    - learners.py: Learner-related schemas
    - templates.py: Template-related schemas
    - reminders.py: Reminder-related schemas
    - users.py: User-related schemas

Design principles:
    - All validation happens at API boundary (not in CRUD/services)
    - Schemas are immutable (use Config.frozen where appropriate)
    - Use Field() for validation rules and documentation
    - Custom validators for complex business rules
"""

from api.schemas.base import (
    TimestampMixin,
    TenantMixin,
    BaseRequest,
    BaseResponse,
)
from api.schemas.pagination import PaginationParams, PaginatedResponse
from api.schemas.common import MessageResponse
from api.schemas.auth import (
    BrowserTutorRegistrationRequest,
    EmailPasswordRequest,
    WebAppLoginRequest,
    RefreshRequest,
    SwitchTenantRequest,
    TelegramLoginWidgetRequest,
    UserPayload,
    BrowserTokenResponse,
    TokenPairResponse,
)
from api.schemas.billing import (
    BillingCheckoutRequest,
    BillingCheckoutPreviewResponse,
    BillingCheckoutResponse,
    BillingPlanResponse,
    BillingSnapshotResponse,
    TenantSubscriptionCancelRequest,
    TenantSubscriptionGrantRequest,
    YooKassaWebhookPayload,
)
from api.schemas.registration import (
    TutorRegistrationRequest,
    StudentRegistrationRequest,
    InviteTokenRequest,
    InviteTokenResponse,
    InviteTokenListResponse,
    RegistrationResponse,
)
from api.schemas.packages import (
    PackageCreateRequest,
    PackageUpdateRequest,
    PackageResponse,
    PackageListResponse,
    PackageProgressModel,
    VALID_PACKAGE_STATUSES,
)
from api.schemas.lessons import (
    LessonCreateRequest,
    LessonUpdateRequest,
    LessonResponse,
    LessonListResponse,
    VALID_LESSON_STATUSES,
)
from api.schemas.learners import (
    CreateLearnerRequest,
    CreateLearnerFromChatIdRequest,
    UpdateLearnerRequest,
    UpdateLearnerNotificationsRequest,
    LearnerResponse,
    StudentLearnerResponse,
    LearnerListResponse,
)
from api.schemas.groups import (
    LearnerGroupCreateRequest,
    LearnerGroupMemberResponse,
    LearnerGroupMembersRequest,
    LearnerGroupResponse,
    LearnerGroupUpdateRequest,
)
from api.schemas.templates import (
    TemplateCreateRequest,
    TemplateUpdateRequest,
    TemplateResponse,
    TemplateListResponse,
)
from api.schemas.reminders import (
    ReminderUpdateRequest,
    ReminderResponse,
    ReminderListResponse,
    VALID_REMINDER_STATUSES,
)
from api.schemas.notifications import (
    MaterializeActiveRulesRequest,
    MaterializeActiveRulesResponse,
    NotificationActivityAcknowledgementRequest,
    NotificationActivityAcknowledgementResponse,
    LearnerNotificationModeResponse,
    LearnerNotificationModeUpdateRequest,
    NotificationActivityResponse,
    NotificationAuditLogResponse,
    NotificationAudienceSelectorRequest,
    NotificationDeliveryAttemptResponse,
    NotificationInstanceCancelRequest,
    NotificationInstanceComponentResponse,
    NotificationInstanceResponse,
    NotificationJobResponse,
    NotificationPreviewComponentResponse,
    NotificationPreviewInstanceResponse,
    NotificationPreviewResponse,
    NotificationReconcileEventRequest,
    NotificationRuleAssignmentResponse,
    NotificationRuleCreateRequest,
    NotificationRuleDraftRequest,
    NotificationRulePreviewRequest,
    NotificationRuleResponse,
    NotificationRuleUpdateRequest,
    NotificationRulesPreviewRequest,
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
    NotificationTemplateCreateRequest,
    NotificationTemplateResponse,
    NotificationTemplateUpdateRequest,
)
from api.schemas.users import (
    UserRole,
    UserResponse,
    UserListResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)
from api.schemas.tenants import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListResponse,
)
from api.schemas.platform import (
    BroadcastAudienceUserResponse,
    BroadcastCampaignResponse,
    BroadcastCreateRequest,
    BroadcastPreviewRequest,
    BroadcastPreviewResponse,
    BroadcastRecipientResponse,
    BroadcastSendRequest,
    PlatformTenantEventResponse,
    PlatformTenantEventsResponse,
    PlatformTenantResponse,
    TenantAccessActionRequest,
    TenantAccessGrantRequest,
    TenantAccessResponse,
    TenantAccessSetRequest,
    TenantAccessSyncResponse,
)
from api.schemas.metrics import (
    DashboardAttentionDismissalRequest,
    DashboardAttentionDismissalResponse,
    DashboardHistoryDayPoint,
    DashboardHistoryHeatmapResponse,
    DashboardHistoryResponse,
    DashboardHistoryWeekPoint,
    DashboardWeeklyLoadResponse,
    MetricsSummary,
    DailyPoint,
    DailyMetricsResponse,
)

__all__ = [
    # Base
    'TimestampMixin',
    'TenantMixin',
    'BaseRequest',
    'BaseResponse',
    # Pagination
    'PaginationParams',
    'PaginatedResponse',
    # Common
    'MessageResponse',
    # Auth
    'BrowserTutorRegistrationRequest',
    'EmailPasswordRequest',
    'WebAppLoginRequest',
    'RefreshRequest',
    'SwitchTenantRequest',
    'TelegramLoginWidgetRequest',
    'UserPayload',
    'BrowserTokenResponse',
    'TokenPairResponse',
    # Billing
    'BillingCheckoutRequest',
    'BillingCheckoutPreviewResponse',
    'BillingCheckoutResponse',
    'BillingPlanResponse',
    'BillingSnapshotResponse',
    'TenantSubscriptionCancelRequest',
    'TenantSubscriptionGrantRequest',
    'YooKassaWebhookPayload',
    # Registration
    'TutorRegistrationRequest',
    'StudentRegistrationRequest',
    'InviteTokenRequest',
    'InviteTokenResponse',
    'InviteTokenListResponse',
    'RegistrationResponse',
    # Packages
    'PackageCreateRequest',
    'PackageUpdateRequest',
    'PackageResponse',
    'PackageListResponse',
    'PackageProgressModel',
    'VALID_PACKAGE_STATUSES',
    # Lessons
    'LessonCreateRequest',
    'LessonUpdateRequest',
    'LessonResponse',
    'LessonListResponse',
    'VALID_LESSON_STATUSES',
    # Learners
    'CreateLearnerRequest',
    'CreateLearnerFromChatIdRequest',
    'UpdateLearnerRequest',
    'UpdateLearnerNotificationsRequest',
    'LearnerResponse',
    'StudentLearnerResponse',
    'LearnerListResponse',
    # Groups
    'LearnerGroupCreateRequest',
    'LearnerGroupMemberResponse',
    'LearnerGroupMembersRequest',
    'LearnerGroupResponse',
    'LearnerGroupUpdateRequest',
    # Templates
    'TemplateCreateRequest',
    'TemplateUpdateRequest',
    'TemplateResponse',
    'TemplateListResponse',
    # Reminders
    'ReminderUpdateRequest',
    'ReminderResponse',
    'ReminderListResponse',
    'VALID_REMINDER_STATUSES',
    # Notifications
    'MaterializeActiveRulesRequest',
    'MaterializeActiveRulesResponse',
    'NotificationActivityAcknowledgementRequest',
    'NotificationActivityAcknowledgementResponse',
    'LearnerNotificationModeResponse',
    'LearnerNotificationModeUpdateRequest',
    'NotificationActivityResponse',
    'NotificationAuditLogResponse',
    'NotificationAudienceSelectorRequest',
    'NotificationDeliveryAttemptResponse',
    'NotificationInstanceCancelRequest',
    'NotificationInstanceComponentResponse',
    'NotificationInstanceResponse',
    'NotificationJobResponse',
    'NotificationPreviewComponentResponse',
    'NotificationPreviewInstanceResponse',
    'NotificationPreviewResponse',
    'NotificationReconcileEventRequest',
    'NotificationRuleAssignmentResponse',
    'NotificationRuleCreateRequest',
    'NotificationRuleDraftRequest',
    'NotificationRulePreviewRequest',
    'NotificationRuleResponse',
    'NotificationRuleUpdateRequest',
    'NotificationRulesPreviewRequest',
    'NotificationSettingsResponse',
    'NotificationSettingsUpdateRequest',
    'NotificationTemplateCreateRequest',
    'NotificationTemplateResponse',
    'NotificationTemplateUpdateRequest',
    # Users
    'UserRole',
    'UserResponse',
    'UserListResponse',
    'UserRoleUpdateRequest',
    'UserUpdateRequest',
    # Tenants
    'TenantCreate',
    'TenantUpdate',
    'TenantResponse',
    'TenantListResponse',
    'PlatformTenantEventResponse',
    'PlatformTenantEventsResponse',
    'PlatformTenantResponse',
    'TenantAccessActionRequest',
    'TenantAccessGrantRequest',
    'TenantAccessResponse',
    'TenantAccessSetRequest',
    'TenantAccessSyncResponse',
    'BroadcastCampaignResponse',
    'BroadcastAudienceUserResponse',
    'BroadcastCreateRequest',
    'BroadcastPreviewRequest',
    'BroadcastPreviewResponse',
    'BroadcastRecipientResponse',
    'BroadcastSendRequest',
    # Metrics
    'MetricsSummary',
    'DailyPoint',
    'DailyMetricsResponse',
    'DashboardAttentionDismissalRequest',
    'DashboardAttentionDismissalResponse',
    'DashboardHistoryDayPoint',
    'DashboardHistoryWeekPoint',
    'DashboardHistoryHeatmapResponse',
    'DashboardWeeklyLoadResponse',
    'DashboardHistoryResponse',
]
