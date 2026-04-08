from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentTenant,
    admin_or_teacher_required,
    get_current_tenant,
    get_current_user,
    get_session,
)
from api.schemas.notifications import (
    MaterializeActiveRulesRequest,
    MaterializeActiveRulesResponse,
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
    NotificationTaskTriggerRequest,
    NotificationTaskTriggerResponse,
    NotificationTemplateCreateRequest,
    NotificationTemplateResponse,
    NotificationTemplateUpdateRequest,
)
from database.models import User
from notifications.application.dto import (
    AudienceSelector,
    CombinedPreviewInstance,
    LearnerNotificationModeRecord,
    NotificationActivityRecord,
    NotificationAuditLogRecord,
    NotificationDeliveryAttemptRecord,
    NotificationInstanceComponentRecord,
    NotificationInstanceRecord,
    LearnerNotificationModeUpdateDraft,
    NotificationRuleCreateDraft,
    NotificationRuleDraft,
    NotificationRuleRecord,
    NotificationRuleUpdateDraft,
    NotificationSettingsRecord,
    NotificationSettingsUpdateDraft,
    NotificationTemplateDraft,
    NotificationJobRecord,
    NotificationTemplateRecord,
    NotificationTemplateUpdateDraft,
    PreviewInstance,
)
from notifications.application.audit import ListNotificationAuditLogUseCase
from notifications.application.instances import (
    CancelNotificationInstanceUseCase,
    GetNotificationInstanceUseCase,
    ListNotificationActivityUseCase,
    ListNotificationInstancesUseCase,
    ScheduleNotificationInstanceNowUseCase,
)
from notifications.application.materialization import MaterializeActiveRulesUseCase
from notifications.application.preview import PreviewRulesUseCase, PreviewRuleUseCase
from notifications.application.reconciliation import QueueNotificationEventReconciliationUseCase
from notifications.application.rules import (
    ActivateNotificationRuleUseCase,
    ArchiveNotificationRuleUseCase,
    CreateNotificationRuleUseCase,
    GetNotificationRuleUseCase,
    ListNotificationRulesUseCase,
    PauseNotificationRuleUseCase,
    UpdateNotificationRuleUseCase,
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
from notifications.domain.enums import EventType, InstanceStatus
from notifications.infrastructure.repositories import SqlAlchemySessionNotificationUnitOfWork
from utils.tasks.notifications import deliver_due_notifications_task, process_notification_jobs_task

router = APIRouter()


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> NotificationSettingsResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    settings = await GetNotificationSettingsUseCase(uow).execute()
    return _settings_response(settings)


@router.patch("/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    payload: NotificationSettingsUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> NotificationSettingsResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    settings = await UpdateNotificationSettingsUseCase(uow).execute(
        _settings_update_from_request(payload)
    )
    return _settings_response(settings)


@router.post("/pilot/process-jobs", response_model=NotificationTaskTriggerResponse)
async def trigger_notification_job_processing(
    payload: NotificationTaskTriggerRequest = Body(default=NotificationTaskTriggerRequest()),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> NotificationTaskTriggerResponse:
    tenant_id = _require_tenant_id(current_tenant)
    task = process_notification_jobs_task.delay(tenant_id=tenant_id, job_type=payload.job_type, limit=payload.limit)
    return NotificationTaskTriggerResponse(
        task_id=task.id,
        task_name=process_notification_jobs_task.name,
        tenant_id=tenant_id,
        limit=payload.limit,
        job_type=payload.job_type,
        queued=True,
    )


@router.post("/pilot/deliver-now", response_model=NotificationTaskTriggerResponse)
async def trigger_notification_delivery_tick(
    payload: NotificationTaskTriggerRequest = Body(default=NotificationTaskTriggerRequest()),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> NotificationTaskTriggerResponse:
    tenant_id = _require_tenant_id(current_tenant)
    task = deliver_due_notifications_task.delay(tenant_id=tenant_id, limit=payload.limit)
    return NotificationTaskTriggerResponse(
        task_id=task.id,
        task_name=deliver_due_notifications_task.name,
        tenant_id=tenant_id,
        limit=payload.limit,
        queued=True,
    )


@router.get("/learner-modes", response_model=list[LearnerNotificationModeResponse])
async def list_learner_notification_modes(
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> list[LearnerNotificationModeResponse]:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    modes = await ListLearnerNotificationModesUseCase(uow).execute()
    return [_learner_mode_response(mode) for mode in modes]


@router.get("/learner-modes/{learner_id}", response_model=LearnerNotificationModeResponse)
async def get_learner_notification_mode(
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> LearnerNotificationModeResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    mode = await GetLearnerNotificationModeUseCase(uow).execute(learner_id)
    if mode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")
    return _learner_mode_response(mode)


@router.patch("/learner-modes/{learner_id}", response_model=LearnerNotificationModeResponse)
async def set_learner_notification_mode(
    learner_id: int,
    payload: LearnerNotificationModeUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> LearnerNotificationModeResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    mode = await SetLearnerNotificationModeUseCase(uow).execute(
        learner_id=learner_id,
        draft=LearnerNotificationModeUpdateDraft(mode_override=payload.mode_override),
    )
    if mode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")
    return _learner_mode_response(mode)


@router.get("/instances", response_model=list[NotificationInstanceResponse])
async def list_notification_instances(
    status_filter: InstanceStatus | None = Query(None, alias="status"),
    learner_id: int | None = None,
    event_type: EventType | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> list[NotificationInstanceResponse]:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    instances = await ListNotificationInstancesUseCase(uow).execute(
        status=status_filter,
        learner_id=learner_id,
        event_type=event_type,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
        limit=limit,
    )
    return [_instance_response(instance) for instance in instances]


@router.get("/instances/{instance_id}", response_model=NotificationInstanceResponse)
async def get_notification_instance(
    instance_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> NotificationInstanceResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    instance = await GetNotificationInstanceUseCase(uow).execute(instance_id)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification instance not found")
    return _instance_response(instance)


@router.post("/instances/{instance_id}/cancel", response_model=NotificationInstanceResponse)
async def cancel_notification_instance(
    instance_id: int,
    payload: NotificationInstanceCancelRequest | None = Body(None),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationInstanceResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    try:
        instance = await CancelNotificationInstanceUseCase(uow).execute(
            instance_id,
            reason=payload.reason if payload is not None else None,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification instance not found")
    return _instance_response(instance)


@router.post("/instances/{instance_id}/send-now", response_model=NotificationInstanceResponse)
async def send_notification_instance_now(
    instance_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationInstanceResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    try:
        instance = await ScheduleNotificationInstanceNowUseCase(uow).execute(
            instance_id,
            now=datetime.now(timezone.utc),
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification instance not found")
    return _instance_response(instance)


@router.get("/activity", response_model=list[NotificationActivityResponse])
async def list_notification_activity(
    learner_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> list[NotificationActivityResponse]:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    activity = await ListNotificationActivityUseCase(uow).execute(
        learner_id=learner_id,
        limit=limit,
    )
    return [_activity_response(item) for item in activity]


@router.get("/audit", response_model=list[NotificationAuditLogResponse])
async def list_notification_audit_log(
    entity_type: str | None = Query(None, max_length=64),
    entity_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> list[NotificationAuditLogResponse]:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    records = await ListNotificationAuditLogUseCase(uow).execute(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return [_audit_response(record) for record in records]


@router.get("/rules", response_model=list[NotificationRuleResponse])
async def list_notification_rules(
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> list[NotificationRuleResponse]:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    rules = await ListNotificationRulesUseCase(uow).execute(include_archived=include_archived)
    return [_rule_response(rule) for rule in rules]


@router.post("/rules", response_model=NotificationRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_rule(
    payload: NotificationRuleCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationRuleResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    try:
        rule = await CreateNotificationRuleUseCase(uow).execute(
            NotificationRuleCreateDraft(
                category=payload.category,
                name=payload.name,
                event_type=payload.event_type,
                trigger_type=payload.trigger_type,
                trigger_config=payload.trigger_config,
                template_id=payload.template_id,
                inline_template_body=payload.inline_template_body,
                inline_template_format=payload.inline_template_format,
                description=payload.description,
                priority=payload.priority,
                status=payload.status,
                combine_policy_key=payload.combine_policy_key,
                delivery_channel=payload.delivery_channel,
                cap_mode=payload.cap_mode,
                quiet_hours_mode=payload.quiet_hours_mode,
                bypass_quiet_hours=payload.bypass_quiet_hours,
                assignments=tuple(_audience_from_request(assignment) for assignment in payload.assignments),
                created_by_user_id=current_user.id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _rule_response(rule)


@router.get("/templates", response_model=list[NotificationTemplateResponse])
async def list_notification_templates(
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> list[NotificationTemplateResponse]:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    templates = await ListNotificationTemplatesUseCase(uow).execute(include_archived=include_archived)
    return [_template_response(template) for template in templates]


@router.post("/templates", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_template(
    payload: NotificationTemplateCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationTemplateResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    try:
        template = await CreateNotificationTemplateUseCase(uow).execute(
            NotificationTemplateDraft(
                category=payload.category,
                key=payload.key,
                name=payload.name,
                body=payload.body,
                description=payload.description,
                locale=payload.locale,
                template_format=payload.template_format,
                created_by_user_id=current_user.id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _template_response(template)


@router.patch("/templates/{template_id}", response_model=NotificationTemplateResponse)
async def update_notification_template(
    template_id: int,
    payload: NotificationTemplateUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationTemplateResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    try:
        template = await UpdateNotificationTemplateUseCase(uow).execute(
            template_id=template_id,
            draft=NotificationTemplateUpdateDraft(
                category=payload.category,
                key=payload.key,
                name=payload.name,
                body=payload.body,
                description=payload.description,
                locale=payload.locale,
                template_format=payload.template_format,
                created_by_user_id=current_user.id,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return _template_response(template)


@router.post("/templates/{template_id}/archive", response_model=NotificationTemplateResponse)
async def archive_notification_template(
    template_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationTemplateResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    try:
        template = await ArchiveNotificationTemplateUseCase(uow).execute(
            template_id,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return _template_response(template)


@router.post("/rules/preview", response_model=NotificationPreviewResponse)
async def preview_notification_rule(
    payload: NotificationRulePreviewRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> NotificationPreviewResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    result = await PreviewRuleUseCase(uow).execute(
        _draft_from_request(payload.rule),
        horizon_days=payload.horizon_days,
        limit=payload.limit,
    )
    return _preview_response(result.instances, result.warnings)


@router.post("/rules/preview-batch", response_model=NotificationPreviewResponse)
async def preview_notification_rules(
    payload: NotificationRulesPreviewRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> NotificationPreviewResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    result = await PreviewRulesUseCase(uow).execute(
        tuple(_draft_from_request(rule) for rule in payload.rules),
        horizon_days=payload.horizon_days,
        limit=payload.limit,
    )
    return _preview_response(result.instances, result.warnings)


@router.get("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def get_notification_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> NotificationRuleResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    rule = await GetNotificationRuleUseCase(uow).execute(rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return _rule_response(rule)


@router.patch("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def update_notification_rule(
    rule_id: int,
    payload: NotificationRuleUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationRuleResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    try:
        rule = await UpdateNotificationRuleUseCase(uow).execute(
            rule_id=rule_id,
            draft=_rule_update_from_request(payload),
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return _rule_response(rule)


@router.post("/rules/{rule_id}/activate", response_model=NotificationRuleResponse)
async def activate_notification_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationRuleResponse:
    return await _set_rule_status_response(
        rule_id,
        session=session,
        current_tenant=current_tenant,
        current_user=current_user,
        use_case_cls=ActivateNotificationRuleUseCase,
    )


@router.post("/rules/{rule_id}/pause", response_model=NotificationRuleResponse)
async def pause_notification_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationRuleResponse:
    return await _set_rule_status_response(
        rule_id,
        session=session,
        current_tenant=current_tenant,
        current_user=current_user,
        use_case_cls=PauseNotificationRuleUseCase,
    )


@router.post("/rules/{rule_id}/archive", response_model=NotificationRuleResponse)
async def archive_notification_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationRuleResponse:
    return await _set_rule_status_response(
        rule_id,
        session=session,
        current_tenant=current_tenant,
        current_user=current_user,
        use_case_cls=ArchiveNotificationRuleUseCase,
    )


@router.post("/materialize-active-rules", response_model=MaterializeActiveRulesResponse)
async def materialize_active_notification_rules(
    payload: MaterializeActiveRulesRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> MaterializeActiveRulesResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    result = await MaterializeActiveRulesUseCase(uow).execute(
        horizon_days=payload.horizon_days,
        limit=payload.limit,
        delivery_enabled=payload.delivery_enabled,
        shadow=payload.shadow,
        created_by_user_id=current_user.id,
    )
    return MaterializeActiveRulesResponse(
        job_id=result.job.job_id,
        job_type=result.job.job_type,
        job_status=result.job.status,
        job_scope=result.job.scope,
        planned_count=result.materialization.upsert_result.planned_count,
        upserted_count=result.materialization.upsert_result.upserted_count,
        warnings=list(result.materialization.warnings),
    )


@router.post("/reconcile/event", response_model=NotificationJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_notification_event_reconciliation(
    payload: NotificationReconcileEventRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
) -> NotificationJobResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    job = await QueueNotificationEventReconciliationUseCase(uow).execute(
        event_type=payload.event_type,
        event_id=payload.event_id,
        reason=payload.reason,
        delivery_enabled=payload.delivery_enabled,
        shadow=payload.shadow,
        horizon_days=payload.horizon_days,
        limit=payload.limit,
        created_by_user_id=current_user.id,
    )
    return _job_response(job)


def _require_tenant_id(current_tenant: CurrentTenant) -> int:
    if current_tenant.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notification APIs require a tenant context",
        )
    return current_tenant.tenant_id


def _draft_from_request(payload: NotificationRuleDraftRequest) -> NotificationRuleDraft:
    return NotificationRuleDraft(
        rule_id=payload.rule_id,
        name=payload.name,
        category=payload.category,
        event_type=payload.event_type,
        trigger_type=payload.trigger_type,
        trigger_config=payload.trigger_config,
        priority=payload.priority,
        template_body=payload.template_body,
        template_key=payload.template_key,
        combine_policy_key=payload.combine_policy_key,
        assignments=tuple(_audience_from_request(assignment) for assignment in payload.assignments),
    )


def _rule_update_from_request(payload: NotificationRuleUpdateRequest) -> NotificationRuleUpdateDraft:
    fields_set = payload.model_fields_set
    return NotificationRuleUpdateDraft(
        category=payload.category,
        name=payload.name,
        event_type=payload.event_type,
        trigger_type=payload.trigger_type,
        trigger_config=payload.trigger_config,
        template_id=payload.template_id,
        template_id_set="template_id" in fields_set,
        inline_template_body=payload.inline_template_body,
        inline_template_body_set="inline_template_body" in fields_set,
        inline_template_format=payload.inline_template_format,
        description=payload.description,
        description_set="description" in fields_set,
        priority=payload.priority,
        status=payload.status,
        combine_policy_key=payload.combine_policy_key,
        combine_policy_key_set="combine_policy_key" in fields_set,
        delivery_channel=payload.delivery_channel,
        cap_mode=payload.cap_mode,
        quiet_hours_mode=payload.quiet_hours_mode,
        bypass_quiet_hours=payload.bypass_quiet_hours,
        assignments=(
            tuple(_audience_from_request(assignment) for assignment in payload.assignments)
            if payload.assignments is not None
            else None
        ),
    )


def _settings_update_from_request(payload: NotificationSettingsUpdateRequest) -> NotificationSettingsUpdateDraft:
    fields_set = payload.model_fields_set
    return NotificationSettingsUpdateDraft(
        mode=payload.mode,
        confirm_global_new=payload.confirm_global_new,
        notifications_enabled=payload.notifications_enabled,
        notifications_enabled_set="notifications_enabled" in fields_set,
        quiet_hours_start=payload.quiet_hours_start,
        quiet_hours_start_set="quiet_hours_start" in fields_set,
        quiet_hours_end=payload.quiet_hours_end,
        quiet_hours_end_set="quiet_hours_end" in fields_set,
        timezone=payload.timezone,
        timezone_set="timezone" in fields_set,
        daily_cap=payload.daily_cap,
        daily_cap_set="daily_cap" in fields_set,
        cap_mode=payload.cap_mode,
        cap_mode_set="cap_mode" in fields_set,
        category_preferences=payload.category_preferences,
        category_preferences_set="category_preferences" in fields_set,
    )


def _audience_from_request(payload: NotificationAudienceSelectorRequest) -> AudienceSelector:
    return AudienceSelector(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        is_exclusion=payload.is_exclusion,
    )


def _instance_response(instance: NotificationInstanceRecord) -> NotificationInstanceResponse:
    return NotificationInstanceResponse(
        id=instance.instance_id,
        rule_id=instance.rule_id,
        category=instance.category,
        event_type=instance.event_type,
        event_id=instance.event_id,
        event_key=instance.event_key,
        recipient_type=instance.recipient_type,
        recipient_id=instance.recipient_id,
        learner_id=instance.learner_id,
        learner_display_name=instance.learner_display_name,
        scheduled_for=instance.scheduled_for,
        effective_scheduled_for=instance.effective_scheduled_for,
        status=instance.status,
        status_reason=instance.status_reason,
        delivery_enabled=instance.delivery_enabled,
        priority=instance.priority,
        channel=instance.channel,
        dedupe_key=instance.dedupe_key,
        combination_key=instance.combination_key,
        explanation=instance.explanation,
        components=[_component_response(component) for component in instance.components],
        latest_attempt=(
            _attempt_response(instance.latest_attempt)
            if instance.latest_attempt is not None
            else None
        ),
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


def _component_response(component: NotificationInstanceComponentRecord) -> NotificationInstanceComponentResponse:
    return NotificationInstanceComponentResponse(
        component_id=component.component_id,
        rule_id=component.rule_id,
        category=component.category,
        template_id=component.template_id,
        component_key=component.component_key,
        metadata=component.metadata,
    )


def _attempt_response(attempt: NotificationDeliveryAttemptRecord) -> NotificationDeliveryAttemptResponse:
    return NotificationDeliveryAttemptResponse(
        attempt_id=attempt.attempt_id,
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        channel=attempt.channel,
        provider=attempt.provider,
        provider_chat_id=attempt.provider_chat_id,
        provider_message_id=attempt.provider_message_id,
        error_code=attempt.error_code,
        error_message=attempt.error_message,
        started_at=attempt.started_at,
        sent_at=attempt.sent_at,
        finished_at=attempt.finished_at,
        created_at=attempt.created_at,
    )


def _activity_response(activity: NotificationActivityRecord) -> NotificationActivityResponse:
    return NotificationActivityResponse(
        activity_type=activity.activity_type,
        activity_id=activity.activity_id,
        notification_instance_id=activity.notification_instance_id,
        category=activity.category,
        event_type=activity.event_type,
        event_id=activity.event_id,
        learner_id=activity.learner_id,
        learner_display_name=activity.learner_display_name,
        status=activity.status,
        action_key=activity.action_key,
        response_value=activity.response_value,
        error_code=activity.error_code,
        error_message=activity.error_message,
        provider_message_id=activity.provider_message_id,
        occurred_at=activity.occurred_at,
        metadata=activity.metadata,
    )


def _audit_response(record: NotificationAuditLogRecord) -> NotificationAuditLogResponse:
    return NotificationAuditLogResponse(
        id=record.audit_id,
        actor_type=record.actor_type,
        actor_id=record.actor_id,
        entity_type=record.entity_type,
        entity_id=record.entity_id,
        action=record.action,
        before=record.before,
        after=record.after,
        reason=record.reason,
        metadata=record.metadata,
        created_at=record.created_at,
    )


def _settings_response(settings: NotificationSettingsRecord) -> NotificationSettingsResponse:
    return NotificationSettingsResponse(
        tenant_id=settings.tenant_id,
        mode=settings.mode,
        notifications_enabled=settings.notifications_enabled,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        timezone=settings.timezone,
        daily_cap=settings.daily_cap,
        cap_mode=settings.cap_mode,
        category_preferences=settings.category_preferences,
        updated_at=settings.updated_at,
    )


def _learner_mode_response(mode: LearnerNotificationModeRecord) -> LearnerNotificationModeResponse:
    return LearnerNotificationModeResponse(
        learner_id=mode.learner_id,
        display_name=mode.display_name,
        mode_override=mode.mode_override,
        effective_mode=mode.effective_mode,
        updated_at=mode.updated_at,
    )


async def _set_rule_status_response(
    rule_id: int,
    *,
    session: AsyncSession,
    current_tenant: CurrentTenant,
    current_user: User,
    use_case_cls,
) -> NotificationRuleResponse:
    tenant_id = _require_tenant_id(current_tenant)
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    rule = await use_case_cls(uow).execute(rule_id, actor_user_id=current_user.id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return _rule_response(rule)


def _rule_response(rule: NotificationRuleRecord) -> NotificationRuleResponse:
    return NotificationRuleResponse(
        id=rule.rule_id,
        tenant_id=rule.tenant_id,
        preset_key=rule.preset_key,
        category=rule.category,
        template_id=rule.template_id,
        template_key=rule.template_key,
        inline_template_body=rule.inline_template_body,
        inline_template_format=rule.inline_template_format,
        name=rule.name,
        description=rule.description,
        event_type=rule.event_type,
        trigger_type=rule.trigger_type,
        trigger_config=rule.trigger_config,
        priority=rule.priority,
        status=rule.status,
        combine_policy_key=rule.combine_policy_key,
        delivery_channel=rule.delivery_channel,
        cap_mode=rule.cap_mode,
        quiet_hours_mode=rule.quiet_hours_mode,
        bypass_quiet_hours=rule.bypass_quiet_hours,
        assignments=[
            NotificationRuleAssignmentResponse(
                scope_type=assignment.scope_type,
                scope_id=assignment.scope_id,
                is_exclusion=assignment.is_exclusion,
            )
            for assignment in rule.assignments
        ],
        created_by_user_id=rule.created_by_user_id,
        activated_at=rule.activated_at,
        paused_at=rule.paused_at,
        archived_at=rule.archived_at,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _preview_response(
    instances: tuple[PreviewInstance | CombinedPreviewInstance, ...],
    warnings: tuple[str, ...],
) -> NotificationPreviewResponse:
    return NotificationPreviewResponse(
        instances=[_preview_instance_response(instance) for instance in instances],
        warnings=list(warnings),
    )


def _template_response(template: NotificationTemplateRecord) -> NotificationTemplateResponse:
    return NotificationTemplateResponse(
        id=template.template_id,
        tenant_id=template.tenant_id,
        category=template.category,
        key=template.key,
        name=template.name,
        body=template.body,
        description=template.description,
        locale=template.locale,
        template_format=template.template_format,
        version=template.version,
        system=template.system,
        based_on_template_id=template.based_on_template_id,
        archived_at=template.archived_at,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _job_response(job: NotificationJobRecord) -> NotificationJobResponse:
    return NotificationJobResponse(
        id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        scope=job.scope,
    )


def _preview_instance_response(
    instance: PreviewInstance | CombinedPreviewInstance,
) -> NotificationPreviewInstanceResponse:
    if isinstance(instance, CombinedPreviewInstance):
        return NotificationPreviewInstanceResponse(
            kind="combined",
            learner_id=instance.learner_id,
            event_type=instance.event_type,
            event_id=instance.event_id,
            category=instance.components[0].category if instance.components else None,
            scheduled_for=instance.scheduled_for,
            effective_scheduled_for=instance.effective_scheduled_for,
            priority=instance.priority,
            status="scheduled",
            warnings=list(instance.warnings),
            combination_key=instance.combination_key,
            components=[
                NotificationPreviewComponentResponse(
                    rule_id=component.rule_id,
                    category=component.category,
                    scheduled_for=component.scheduled_for,
                    effective_scheduled_for=component.effective_scheduled_for,
                    warnings=list(component.warnings),
                    explanation=component.explanation,
                )
                for component in instance.components
            ],
        )

    return NotificationPreviewInstanceResponse(
        kind="single",
        rule_id=instance.rule_id,
        learner_id=instance.learner_id,
        event_type=instance.event_type,
        event_id=instance.event_id,
        category=instance.category,
        scheduled_for=instance.scheduled_for,
        effective_scheduled_for=instance.effective_scheduled_for,
        priority=instance.priority,
        status=instance.status,
        reason=instance.reason,
        warnings=list(instance.warnings),
        explanation=instance.explanation,
    )
