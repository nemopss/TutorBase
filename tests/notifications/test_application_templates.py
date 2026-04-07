from dataclasses import dataclass, field

import pytest

from notifications.application.dto import (
    NotificationAuditLogDraft,
    NotificationTemplateDraft,
    NotificationTemplateRecord,
    NotificationTemplateUpdateDraft,
)
from notifications.application.templates import (
    ArchiveNotificationTemplateUseCase,
    CreateNotificationTemplateUseCase,
    ListNotificationTemplatesUseCase,
    UpdateNotificationTemplateUseCase,
)
from notifications.domain.enums import CategoryKey


@dataclass
class FakeTemplateRepository:
    templates: tuple[NotificationTemplateRecord, ...] = ()
    created: list[NotificationTemplateDraft] = field(default_factory=list)
    updated: list[tuple[int, NotificationTemplateUpdateDraft]] = field(default_factory=list)
    archived: list[int] = field(default_factory=list)

    async def list_templates(self, *, include_archived=False):
        return self.templates

    async def get_template(self, template_id):
        return next((template for template in self.templates if template.template_id == template_id), None)

    async def create_template(self, draft):
        self.created.append(draft)
        return NotificationTemplateRecord(
            template_id=1,
            tenant_id=1,
            category=draft.category,
            key=draft.key,
            name=draft.name,
            body=draft.body,
            description=draft.description,
            locale=draft.locale,
            template_format=draft.template_format,
            version=1,
            system=False,
        )

    async def create_template_version(self, template_id, draft):
        self.updated.append((template_id, draft))
        return NotificationTemplateRecord(
            template_id=2,
            tenant_id=1,
            category=draft.category or CategoryKey.HOMEWORK,
            key=draft.key or "homework",
            name=draft.name or "Домашка",
            body=draft.body or "Привет",
            description=draft.description,
            locale=draft.locale or "ru",
            template_format=draft.template_format or "plain_text",
            version=2,
            system=False,
            based_on_template_id=template_id,
        )

    async def archive_template(self, template_id):
        self.archived.append(template_id)
        return NotificationTemplateRecord(
            template_id=template_id,
            tenant_id=1,
            category=CategoryKey.HOMEWORK,
            key="homework",
            name="Домашка",
            body="Привет",
            description=None,
            locale="ru",
            template_format="plain_text",
            version=1,
            system=False,
        )


@dataclass
class FakeAuditLogRepository:
    records: list[NotificationAuditLogDraft] = field(default_factory=list)

    async def record_audit(self, draft):
        self.records.append(draft)
        return None


@dataclass
class FakeUnitOfWork:
    templates: FakeTemplateRepository
    audit_log: FakeAuditLogRepository = field(default_factory=FakeAuditLogRepository)
    committed: bool = False

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_list_templates_returns_records_without_commit():
    template = NotificationTemplateRecord(
        template_id=1,
        tenant_id=1,
        category=CategoryKey.HOMEWORK,
        key="homework",
        name="Домашка",
        body="Привет",
        description=None,
        locale="ru",
        template_format="plain_text",
        version=1,
        system=False,
    )
    uow = FakeUnitOfWork(templates=FakeTemplateRepository(templates=(template,)))

    result = await ListNotificationTemplatesUseCase(uow).execute()

    assert result == (template,)
    assert uow.committed is False


@pytest.mark.asyncio
async def test_create_update_and_archive_templates_commit_changes():
    repository = FakeTemplateRepository()
    uow = FakeUnitOfWork(templates=repository)
    create_draft = NotificationTemplateDraft(
        category=CategoryKey.HOMEWORK,
        key="homework",
        name="Домашка",
        body="Привет",
    )
    update_draft = NotificationTemplateUpdateDraft(body="Новый текст")

    created = await CreateNotificationTemplateUseCase(uow).execute(create_draft)
    updated = await UpdateNotificationTemplateUseCase(uow).execute(
        template_id=created.template_id,
        draft=update_draft,
    )
    archived = await ArchiveNotificationTemplateUseCase(uow).execute(created.template_id)

    assert repository.created == [create_draft]
    assert repository.updated == [(1, update_draft)]
    assert repository.archived == [1]
    assert [record.action for record in uow.audit_log.records] == [
        "created",
        "version_created",
        "archived",
    ]
    assert all(record.entity_type == "notification_template" for record in uow.audit_log.records)
    assert updated is not None
    assert updated.version == 2
    assert archived is not None
    assert uow.committed
