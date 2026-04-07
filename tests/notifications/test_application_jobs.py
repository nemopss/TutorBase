from dataclasses import dataclass, field

import pytest

from notifications.application.dto import NotificationJobRecord
from notifications.application.jobs import ClaimQueuedNotificationJobsUseCase


@dataclass
class FakeJobRepository:
    claimed: tuple[NotificationJobRecord, ...] = ()
    calls: list[dict] = field(default_factory=list)

    async def claim_queued_jobs(self, *, job_type: str, limit: int):
        self.calls.append({"job_type": job_type, "limit": limit})
        return self.claimed


@dataclass
class FakeUnitOfWork:
    jobs: FakeJobRepository
    committed: bool = False

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_claim_queued_notification_jobs_commits_claim():
    job = NotificationJobRecord(
        job_id=1,
        job_type="materialize_active_rules",
        status="running",
        scope={"shadow": True},
    )
    repository = FakeJobRepository(claimed=(job,))
    uow = FakeUnitOfWork(jobs=repository)

    result = await ClaimQueuedNotificationJobsUseCase(uow).execute(
        job_type="materialize_active_rules",
        limit=10,
    )

    assert result.claimed == (job,)
    assert repository.calls == [{"job_type": "materialize_active_rules", "limit": 10}]
    assert uow.committed
