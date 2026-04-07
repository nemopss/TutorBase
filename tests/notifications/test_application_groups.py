from dataclasses import dataclass, field

import pytest

from notifications.application.dto import (
    LearnerGroupDraft,
    LearnerGroupRecord,
    LearnerGroupUpdateDraft,
    NotificationJobDraft,
    NotificationJobRecord,
    NotificationSettingsRecord,
)
from notifications.application.groups import (
    AddLearnerGroupMembersUseCase,
    CreateLearnerGroupUseCase,
    DeactivateLearnerGroupMemberUseCase,
    ListLearnerGroupsUseCase,
    UpdateLearnerGroupUseCase,
)
from notifications.domain.enums import NotificationSystemMode


@dataclass
class FakeGroupRepository:
    groups: tuple[LearnerGroupRecord, ...] = ()
    created: list[LearnerGroupDraft] = field(default_factory=list)
    updated: list[tuple[int, LearnerGroupUpdateDraft]] = field(default_factory=list)
    added_members: list[tuple[int, tuple[int, ...]]] = field(default_factory=list)
    deactivated_members: list[tuple[int, int]] = field(default_factory=list)

    async def list_groups(self):
        return self.groups

    async def create_group(self, draft):
        self.created.append(draft)
        return LearnerGroupRecord(
            group_id=1,
            name=draft.name,
            description=draft.description,
            color=draft.color,
            status="active",
            member_count=len(draft.learner_ids),
        )

    async def update_group(self, group_id, draft):
        self.updated.append((group_id, draft))
        return LearnerGroupRecord(
            group_id=group_id,
            name=draft.name or "TOPIK",
            description=draft.description,
            color=draft.color,
            status=draft.status or "active",
        )

    async def add_members(self, group_id, learner_ids):
        self.added_members.append((group_id, learner_ids))
        return LearnerGroupRecord(group_id=group_id, name="TOPIK", description=None, color=None, status="active")

    async def deactivate_member(self, group_id, learner_id):
        self.deactivated_members.append((group_id, learner_id))
        return LearnerGroupRecord(group_id=group_id, name="TOPIK", description=None, color=None, status="active")


@dataclass
class FakeJobRepository:
    records: list[NotificationJobRecord] = field(default_factory=list)

    async def create_job(self, draft: NotificationJobDraft):
        record = NotificationJobRecord(
            job_id=len(self.records) + 1,
            job_type=draft.job_type,
            status="queued",
            scope=draft.scope,
        )
        self.records.append(record)
        return record


@dataclass
class FakeSettingsRepository:
    mode: NotificationSystemMode = NotificationSystemMode.SHADOW

    async def get_settings(self):
        return NotificationSettingsRecord(tenant_id=1, mode=self.mode)


@dataclass
class FakeUnitOfWork:
    groups: FakeGroupRepository
    jobs: FakeJobRepository = field(default_factory=FakeJobRepository)
    settings: FakeSettingsRepository = field(default_factory=FakeSettingsRepository)
    committed: bool = False

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_list_groups_returns_repository_records_without_commit():
    uow = FakeUnitOfWork(
        groups=FakeGroupRepository(
            groups=(
                LearnerGroupRecord(
                    group_id=1,
                    name="TOPIK",
                    description=None,
                    color=None,
                    status="active",
                ),
            )
        )
    )

    result = await ListLearnerGroupsUseCase(uow).execute()

    assert result[0].name == "TOPIK"
    assert uow.committed is False


@pytest.mark.asyncio
async def test_create_group_commits_created_record():
    repository = FakeGroupRepository()
    uow = FakeUnitOfWork(groups=repository)
    draft = LearnerGroupDraft(name="TOPIK", learner_ids=(10, 11))

    result = await CreateLearnerGroupUseCase(uow).execute(draft)

    assert uow.committed
    assert repository.created == [draft]
    assert result.member_count == 2


@pytest.mark.asyncio
async def test_update_group_commits_changes():
    repository = FakeGroupRepository()
    uow = FakeUnitOfWork(groups=repository)
    draft = LearnerGroupUpdateDraft(name="TOPIK 2", status="active")

    result = await UpdateLearnerGroupUseCase(uow).execute(group_id=1, draft=draft)

    assert uow.committed
    assert repository.updated == [(1, draft)]
    assert result is not None
    assert result.name == "TOPIK 2"


@pytest.mark.asyncio
async def test_add_and_deactivate_group_members_commit_changes():
    repository = FakeGroupRepository()
    uow = FakeUnitOfWork(groups=repository)

    await AddLearnerGroupMembersUseCase(uow).execute(group_id=1, learner_ids=(10, 11))
    await DeactivateLearnerGroupMemberUseCase(uow).execute(group_id=1, learner_id=10)

    assert repository.added_members == [(1, (10, 11))]
    assert repository.deactivated_members == [(1, 10)]
    assert [job.job_type for job in uow.jobs.records] == [
        "reconcile_group_membership",
        "reconcile_group_membership",
    ]
    assert uow.jobs.records[0].scope["learner_ids"] == [10, 11]
    assert uow.jobs.records[0].scope["reason"] == "group_members_added"
    assert uow.jobs.records[0].scope["shadow"] is True
    assert uow.jobs.records[1].scope["learner_ids"] == [10]
    assert uow.jobs.records[1].scope["reason"] == "group_member_removed"
    assert uow.committed
