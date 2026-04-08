from __future__ import annotations

from notifications.application.dto import ClaimNotificationJobsResult
from notifications.application.ports import NotificationMaterializationUnitOfWork


class ClaimQueuedNotificationJobsUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        job_type: str,
        limit: int = 20,
    ) -> ClaimNotificationJobsResult:
        jobs = await self._uow.jobs.claim_queued_jobs(job_type=job_type, limit=limit)
        await self._uow.commit()
        return ClaimNotificationJobsResult(claimed=jobs)
