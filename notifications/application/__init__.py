"""Application use cases for the notification bounded context."""

from notifications.application.delivery import (
    ClaimDueNotificationsUseCase,
    ExecuteClaimedNotificationDeliveryUseCase,
    NotificationDeliveryError,
)
from notifications.application.jobs import ClaimQueuedNotificationJobsUseCase
from notifications.application.materialization import (
    MaterializeActiveRulesUseCase,
    MaterializeRulesUseCase,
    RunMaterializeActiveRulesJobUseCase,
)
from notifications.application.instances import (
    CancelNotificationInstanceUseCase,
    GetNotificationInstanceUseCase,
    ListNotificationActivityUseCase,
    ListNotificationInstancesUseCase,
    ScheduleNotificationInstanceNowUseCase,
)
from notifications.application.preview import PreviewRulesUseCase, PreviewRuleUseCase
from notifications.application.reconciliation import (
    QueueNotificationEventReconciliationUseCase,
    RunReconcileNotificationEventJobUseCase,
)
from notifications.application.rendering import FallbackNotificationRenderer
from notifications.application.responses import RecordNotificationResponseUseCase
from notifications.application.rules import (
    ActivateNotificationRuleUseCase,
    ArchiveNotificationRuleUseCase,
    CreateNotificationRuleUseCase,
    GetNotificationRuleUseCase,
    ListNotificationRulesUseCase,
    PauseNotificationRuleUseCase,
    UpdateNotificationRuleUseCase,
)
from notifications.application.groups import (
    AddLearnerGroupMembersUseCase,
    CreateLearnerGroupUseCase,
    DeactivateLearnerGroupMemberUseCase,
    GetLearnerGroupUseCase,
    ListLearnerGroupsUseCase,
    UpdateLearnerGroupUseCase,
)
from notifications.application.settings import (
    GetLearnerNotificationModeUseCase,
    GetNotificationSettingsUseCase,
    ListLearnerNotificationModesUseCase,
    SetLearnerNotificationModeUseCase,
    UpdateNotificationSettingsUseCase,
)
from notifications.application.templates import (
    ArchiveNotificationTemplateUseCase,
    CreateNotificationTemplateUseCase,
    ListNotificationTemplatesUseCase,
    UpdateNotificationTemplateUseCase,
)

__all__ = (
    "ClaimDueNotificationsUseCase",
    "ExecuteClaimedNotificationDeliveryUseCase",
    "NotificationDeliveryError",
    "ClaimQueuedNotificationJobsUseCase",
    "MaterializeRulesUseCase",
    "MaterializeActiveRulesUseCase",
    "RunMaterializeActiveRulesJobUseCase",
    "ListNotificationInstancesUseCase",
    "GetNotificationInstanceUseCase",
    "ListNotificationActivityUseCase",
    "CancelNotificationInstanceUseCase",
    "ScheduleNotificationInstanceNowUseCase",
    "PreviewRuleUseCase",
    "PreviewRulesUseCase",
    "QueueNotificationEventReconciliationUseCase",
    "RunReconcileNotificationEventJobUseCase",
    "FallbackNotificationRenderer",
    "RecordNotificationResponseUseCase",
    "ListNotificationRulesUseCase",
    "GetNotificationRuleUseCase",
    "CreateNotificationRuleUseCase",
    "UpdateNotificationRuleUseCase",
    "ActivateNotificationRuleUseCase",
    "PauseNotificationRuleUseCase",
    "ArchiveNotificationRuleUseCase",
    "ListLearnerGroupsUseCase",
    "GetLearnerGroupUseCase",
    "CreateLearnerGroupUseCase",
    "UpdateLearnerGroupUseCase",
    "AddLearnerGroupMembersUseCase",
    "DeactivateLearnerGroupMemberUseCase",
    "GetNotificationSettingsUseCase",
    "UpdateNotificationSettingsUseCase",
    "ListLearnerNotificationModesUseCase",
    "GetLearnerNotificationModeUseCase",
    "SetLearnerNotificationModeUseCase",
    "ListNotificationTemplatesUseCase",
    "CreateNotificationTemplateUseCase",
    "UpdateNotificationTemplateUseCase",
    "ArchiveNotificationTemplateUseCase",
)
