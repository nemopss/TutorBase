from __future__ import annotations

from notifications.application.dto import (
    LearnerGroupDraft,
    LearnerGroupRecord,
    LearnerGroupUpdateDraft,
)
from notifications.application.ports import NotificationMaterializationUnitOfWork
from notifications.application.reconciliation import QueueNotificationGroupMembershipReconciliationUseCase


class ListLearnerGroupsUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> tuple[LearnerGroupRecord, ...]:
        return await self._uow.groups.list_groups()


class GetLearnerGroupUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, group_id: int) -> LearnerGroupRecord | None:
        return await self._uow.groups.get_group(group_id)


class CreateLearnerGroupUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, draft: LearnerGroupDraft) -> LearnerGroupRecord:
        group = await self._uow.groups.create_group(draft)
        await self._uow.commit()
        return group


class UpdateLearnerGroupUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        group_id: int,
        draft: LearnerGroupUpdateDraft,
    ) -> LearnerGroupRecord | None:
        group = await self._uow.groups.update_group(group_id, draft)
        await self._uow.commit()
        return group


class AddLearnerGroupMembersUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        group_id: int,
        learner_ids: tuple[int, ...],
    ) -> LearnerGroupRecord | None:
        group = await self._uow.groups.add_members(group_id, learner_ids)
        if group is not None and learner_ids:
            await QueueNotificationGroupMembershipReconciliationUseCase(self._uow).execute(
                group_id=group_id,
                learner_ids=learner_ids,
                reason="group_members_added",
                commit=False,
            )
        await self._uow.commit()
        return group


class DeactivateLearnerGroupMemberUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        group_id: int,
        learner_id: int,
    ) -> LearnerGroupRecord | None:
        group = await self._uow.groups.deactivate_member(group_id, learner_id)
        if group is not None:
            await QueueNotificationGroupMembershipReconciliationUseCase(self._uow).execute(
                group_id=group_id,
                learner_ids=(learner_id,),
                reason="group_member_removed",
                commit=False,
            )
        await self._uow.commit()
        return group
