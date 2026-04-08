from __future__ import annotations

from notifications.application.dto import (
    NotificationTemplateDraft,
    NotificationTemplateRecord,
    NotificationTemplateUpdateDraft,
)
from notifications.application.audit import record_notification_audit
from notifications.application.ports import NotificationMaterializationUnitOfWork


class ListNotificationTemplatesUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, include_archived: bool = False) -> tuple[NotificationTemplateRecord, ...]:
        return await self._uow.templates.list_templates(include_archived=include_archived)


class CreateNotificationTemplateUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, draft: NotificationTemplateDraft) -> NotificationTemplateRecord:
        template = await self._uow.templates.create_template(draft)
        await record_notification_audit(
            self._uow,
            entity_type="notification_template",
            entity_id=template.template_id,
            action="created",
            actor_user_id=draft.created_by_user_id,
            after=template,
        )
        await self._uow.commit()
        return template


class UpdateNotificationTemplateUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        template_id: int,
        draft: NotificationTemplateUpdateDraft,
    ) -> NotificationTemplateRecord | None:
        before = await self._uow.templates.get_template(template_id)
        template = await self._uow.templates.create_template_version(template_id, draft)
        if template is not None:
            await record_notification_audit(
                self._uow,
                entity_type="notification_template",
                entity_id=template.template_id,
                action="version_created",
                actor_user_id=draft.created_by_user_id,
                before=before,
                after=template,
                metadata={"source_template_id": template_id},
            )
        await self._uow.commit()
        return template


class ArchiveNotificationTemplateUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        template_id: int,
        *,
        actor_user_id: int | None = None,
    ) -> NotificationTemplateRecord | None:
        before = await self._uow.templates.get_template(template_id)
        template = await self._uow.templates.archive_template(template_id)
        if template is not None:
            await record_notification_audit(
                self._uow,
                entity_type="notification_template",
                entity_id=template.template_id,
                action="archived",
                actor_user_id=actor_user_id,
                before=before,
                after=template,
            )
        await self._uow.commit()
        return template
