from datetime import datetime, timezone

from api.app import create_app
from api.routes.notifications import (
    _activity_response,
    _audit_response,
    _draft_from_request,
    _instance_response,
    _job_response,
    _learner_mode_response,
    _preview_instance_response,
    _rule_response,
    _rule_update_from_request,
    _settings_response,
    _settings_update_from_request,
    _template_response,
)
from api.schemas.notifications import (
    LearnerNotificationModeUpdateRequest,
    NotificationAudienceSelectorRequest,
    NotificationRuleDraftRequest,
    NotificationRuleUpdateRequest,
    NotificationSettingsUpdateRequest,
)
from notifications.application.dto import (
    AudienceSelector,
    CombinedPreviewInstance,
    LearnerNotificationModeRecord,
    NotificationActivityRecord,
    NotificationAuditLogRecord,
    NotificationDeliveryAttemptRecord,
    NotificationInstanceComponentRecord,
    NotificationInstanceRecord,
    NotificationJobRecord,
    NotificationRuleRecord,
    NotificationSettingsRecord,
    PreviewInstance,
)
from notifications.application.dto import NotificationTemplateRecord
from notifications.domain.enums import (
    CapMode,
    CategoryKey,
    EventType,
    NotificationSystemMode,
    Priority,
    QuietHoursMode,
    RuleStatus,
    TriggerType,
    InstanceStatus,
)


def test_notification_routes_are_registered():
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/api/v1/notifications/rules/preview" in paths
    assert "/api/v1/notifications/rules/preview-batch" in paths
    assert "/api/v1/notifications/rules" in paths
    assert "/api/v1/notifications/rules/{rule_id}" in paths
    assert "/api/v1/notifications/rules/{rule_id}/activate" in paths
    assert "/api/v1/notifications/rules/{rule_id}/pause" in paths
    assert "/api/v1/notifications/rules/{rule_id}/archive" in paths
    assert "/api/v1/notifications/settings" in paths
    assert "/api/v1/notifications/pilot/process-jobs" in paths
    assert "/api/v1/notifications/pilot/deliver-now" in paths
    assert "/api/v1/notifications/learner-modes" in paths
    assert "/api/v1/notifications/learner-modes/{learner_id}" in paths
    assert "/api/v1/notifications/instances" in paths
    assert "/api/v1/notifications/instances/{instance_id}" in paths
    assert "/api/v1/notifications/instances/{instance_id}/cancel" in paths
    assert "/api/v1/notifications/instances/{instance_id}/send-now" in paths
    assert "/api/v1/notifications/activity" in paths
    assert "/api/v1/notifications/audit" in paths
    assert "/api/v1/notifications/materialize-active-rules" in paths
    assert "/api/v1/notifications/reconcile/event" in paths
    assert "/api/v1/notifications/templates" in paths
    assert "/api/v1/notifications/templates/{template_id}" in paths
    assert "/api/v1/notifications/templates/{template_id}/archive" in paths


def test_rule_draft_request_maps_to_application_dto():
    request = NotificationRuleDraftRequest(
        rule_id=1,
        name="Домашка",
        category=CategoryKey.HOMEWORK,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        priority=Priority.NORMAL,
        template_body="Привет",
        template_key="homework",
        assignments=[
            NotificationAudienceSelectorRequest(scope_type="group", scope_id=7),
            NotificationAudienceSelectorRequest(
                scope_type="learner",
                scope_id=10,
                is_exclusion=True,
            ),
        ],
    )

    draft = _draft_from_request(request)

    assert draft.rule_id == 1
    assert draft.category == CategoryKey.HOMEWORK
    assert draft.template_key == "homework"
    assert [(item.scope_type, item.scope_id, item.is_exclusion) for item in draft.assignments] == [
        ("group", 7, False),
        ("learner", 10, True),
    ]


def test_combined_preview_response_keeps_components_for_ui_explanation():
    scheduled_for = datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    confirmation = PreviewInstance(
        rule_id=1,
        learner_id=10,
        event_type=EventType.LESSON,
        event_id=617,
        category=CategoryKey.LESSON_CONFIRMATION,
        scheduled_for=scheduled_for,
        effective_scheduled_for=scheduled_for,
        priority=Priority.NORMAL,
        status="scheduled",
        explanation={"rule_name": "Подтверждение"},
    )
    homework = PreviewInstance(
        rule_id=2,
        learner_id=10,
        event_type=EventType.LESSON,
        event_id=617,
        category=CategoryKey.HOMEWORK,
        scheduled_for=scheduled_for,
        effective_scheduled_for=scheduled_for,
        priority=Priority.NORMAL,
        status="scheduled",
        explanation={"rule_name": "Домашка"},
    )
    combined = CombinedPreviewInstance(
        combination_key="lesson_confirmation_homework",
        learner_id=10,
        event_type=EventType.LESSON,
        event_id=617,
        scheduled_for=scheduled_for,
        effective_scheduled_for=scheduled_for,
        priority=Priority.NORMAL,
        components=(confirmation, homework),
        warnings=("combined",),
    )

    response = _preview_instance_response(combined)

    assert response.kind == "combined"
    assert response.combination_key == "lesson_confirmation_homework"
    assert response.warnings == ["combined"]
    assert [component.category for component in response.components] == [
        CategoryKey.LESSON_CONFIRMATION,
        CategoryKey.HOMEWORK,
    ]


def test_template_response_maps_application_record():
    record = NotificationTemplateRecord(
        template_id=1,
        tenant_id=1,
        category=CategoryKey.HOMEWORK,
        key="homework",
        name="Домашка",
        body="Привет, {student_name}",
        description=None,
        locale="ru",
        template_format="plain_text",
        version=2,
        system=False,
        based_on_template_id=1,
    )

    response = _template_response(record)

    assert response.id == 1
    assert response.category == CategoryKey.HOMEWORK
    assert response.version == 2
    assert response.based_on_template_id == 1


def test_rule_update_request_tracks_nullable_field_updates():
    update = NotificationRuleUpdateRequest(
        template_id=None,
        inline_template_body=None,
        description=None,
        combine_policy_key=None,
        assignments=[],
    )

    draft = _rule_update_from_request(update)

    assert draft.template_id is None
    assert draft.template_id_set is True
    assert draft.inline_template_body is None
    assert draft.inline_template_body_set is True
    assert draft.description is None
    assert draft.description_set is True
    assert draft.combine_policy_key is None
    assert draft.combine_policy_key_set is True
    assert draft.assignments == ()


def test_rule_response_maps_application_record_for_ui():
    record = NotificationRuleRecord(
        rule_id=42,
        tenant_id=1,
        preset_key="homework_before_lesson",
        category=CategoryKey.HOMEWORK,
        template_id=3,
        template_key="homework",
        inline_template_body=None,
        inline_template_format="plain_text",
        name="Домашка",
        description=None,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        priority=Priority.NORMAL,
        status=RuleStatus.ACTIVE,
        combine_policy_key="lesson_confirmation_homework",
        delivery_channel="telegram",
        cap_mode=CapMode.WARN_ONLY,
        quiet_hours_mode=QuietHoursMode.SHIFT,
        bypass_quiet_hours=False,
        assignments=(AudienceSelector(scope_type="group", scope_id=7),),
    )

    response = _rule_response(record)

    assert response.id == 42
    assert response.preset_key == "homework_before_lesson"
    assert response.status == RuleStatus.ACTIVE
    assert response.template_key == "homework"
    assert response.assignments[0].scope_type == "group"
    assert response.assignments[0].scope_id == 7


def test_settings_update_request_tracks_nullable_fields():
    request = NotificationSettingsUpdateRequest(
        mode=NotificationSystemMode.SHADOW,
        confirm_global_new=False,
        notifications_enabled=None,
        quiet_hours_start=None,
        daily_cap=None,
        cap_mode=None,
        category_preferences={"homework": False},
    )

    draft = _settings_update_from_request(request)

    assert draft.mode == NotificationSystemMode.SHADOW
    assert draft.confirm_global_new is False
    assert draft.notifications_enabled is None
    assert draft.notifications_enabled_set is True
    assert draft.quiet_hours_start is None
    assert draft.quiet_hours_start_set is True
    assert draft.daily_cap is None
    assert draft.daily_cap_set is True
    assert draft.cap_mode is None
    assert draft.cap_mode_set is True
    assert draft.category_preferences == {"homework": False}
    assert draft.category_preferences_set is True


def test_settings_and_learner_mode_responses_map_application_records():
    settings_response = _settings_response(
        NotificationSettingsRecord(
            tenant_id=1,
            mode=NotificationSystemMode.SHADOW,
            daily_cap=3,
            category_preferences={"homework": True},
        )
    )
    learner_mode_response = _learner_mode_response(
        LearnerNotificationModeRecord(
            learner_id=10,
            display_name="Вика",
            mode_override=NotificationSystemMode.INHERIT,
            effective_mode=NotificationSystemMode.SHADOW,
        )
    )
    learner_mode_update = LearnerNotificationModeUpdateRequest(mode_override=NotificationSystemMode.NEW)

    assert settings_response.mode == NotificationSystemMode.SHADOW
    assert settings_response.daily_cap == 3
    assert settings_response.category_preferences == {"homework": True}
    assert learner_mode_response.learner_id == 10
    assert learner_mode_response.effective_mode == NotificationSystemMode.SHADOW
    assert learner_mode_update.mode_override == NotificationSystemMode.NEW


def test_instance_response_maps_components_and_latest_attempt():
    scheduled_for = datetime(2026, 4, 8, 7, 0, tzinfo=timezone.utc)
    record = NotificationInstanceRecord(
        instance_id=16016,
        rule_id=16017,
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        learner_display_name="Вика",
        scheduled_for=scheduled_for,
        effective_scheduled_for=scheduled_for,
        status=InstanceStatus.SCHEDULED,
        status_reason=None,
        delivery_enabled=True,
        priority=Priority.NORMAL,
        channel="telegram",
        dedupe_key="single|lesson_confirmation|rule:16017|2026-04-08T07:00:00+00:00",
        combination_key=None,
        explanation={"rule_name": "Подтверждение"},
        components=(
            NotificationInstanceComponentRecord(
                component_id=1,
                rule_id=16017,
                category=CategoryKey.LESSON_CONFIRMATION,
                template_id=3,
                component_key="lesson_confirmation:default",
            ),
        ),
        latest_attempt=NotificationDeliveryAttemptRecord(
            attempt_id=201,
            attempt_no=1,
            status="sent",
            channel="telegram",
            provider="telegram",
            provider_message_id="777",
            sent_at=scheduled_for,
        ),
    )

    response = _instance_response(record)

    assert response.id == 16016
    assert response.learner_display_name == "Вика"
    assert response.components[0].component_key == "lesson_confirmation:default"
    assert response.latest_attempt is not None
    assert response.latest_attempt.provider_message_id == "777"


def test_activity_response_maps_delivery_and_response_events():
    occurred_at = datetime(2026, 4, 8, 7, 1, tzinfo=timezone.utc)
    delivery = _activity_response(
        NotificationActivityRecord(
            activity_type="delivery_attempt",
            activity_id=201,
            notification_instance_id=16016,
            category=CategoryKey.LESSON_CONFIRMATION,
            event_type=EventType.LESSON,
            event_id=617,
            learner_id=10,
            learner_display_name="Вика",
            status="sent",
            provider_message_id="777",
            occurred_at=occurred_at,
        )
    )
    response = _activity_response(
        NotificationActivityRecord(
            activity_type="response",
            activity_id=301,
            notification_instance_id=16016,
            category=CategoryKey.LESSON_CONFIRMATION,
            event_type=EventType.LESSON,
            event_id=617,
            learner_id=10,
            learner_display_name="Вика",
            status="confirmed",
            action_key="confirm_lesson",
            response_value="confirmed",
            occurred_at=occurred_at,
        )
    )

    assert delivery.activity_type == "delivery_attempt"
    assert delivery.provider_message_id == "777"
    assert response.activity_type == "response"
    assert response.action_key == "confirm_lesson"


def test_audit_response_maps_management_event():
    created_at = datetime(2026, 4, 8, 7, 1, tzinfo=timezone.utc)

    response = _audit_response(
        NotificationAuditLogRecord(
            audit_id=501,
            actor_type="teacher",
            actor_id=42,
            entity_type="notification_rule",
            entity_id=7,
            action="updated",
            before={"status": "draft"},
            after={"status": "active"},
            reason="manual",
            metadata={"source": "test"},
            created_at=created_at,
        )
    )

    assert response.id == 501
    assert response.actor_type == "teacher"
    assert response.entity_type == "notification_rule"
    assert response.after == {"status": "active"}


def test_job_response_maps_reconciliation_job():
    response = _job_response(
        NotificationJobRecord(
            job_id=7,
            job_type="reconcile_event",
            status="queued",
            scope={"event_type": "lesson", "event_id": 617},
        )
    )

    assert response.id == 7
    assert response.job_type == "reconcile_event"
    assert response.scope["event_id"] == 617
