from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import config
from notifications.application.materialization import MaterializeActiveRulesUseCase
from notifications.infrastructure.repositories import (
    SqlAlchemySessionNotificationUnitOfWork,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run notification materialization directly against the database."
    )
    parser.add_argument(
        "--tenant-id", type=int, required=True, help="Tenant id to rebuild"
    )
    parser.add_argument(
        "--mode",
        choices=("live", "shadow"),
        default="live",
        help="Materialization mode. Use live for production delivery rebuilds.",
    )
    parser.add_argument(
        "--horizon-days",
        type=int,
        default=30,
        help="Future horizon to materialize",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=1000,
        help="Batch size for paged preview/materialization",
    )
    parser.add_argument(
        "--created-by-user-id",
        type=int,
        default=None,
        help="Optional actor user id to store on the job record",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict:
    engine = create_async_engine(
        config.build_async_database_url(),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            uow = SqlAlchemySessionNotificationUnitOfWork(
                session, tenant_id=args.tenant_id
            )
            live = args.mode == "live"
            result = await MaterializeActiveRulesUseCase(uow).execute(
                horizon_days=args.horizon_days,
                limit=args.page_size,
                delivery_enabled=live,
                shadow=not live,
                created_by_user_id=args.created_by_user_id,
            )
            return {
                "tenant_id": args.tenant_id,
                "mode": args.mode,
                "job_id": result.job.job_id,
                "job_type": result.job.job_type,
                "job_status": result.job.status,
                "job_scope": result.job.scope,
                "planned_count": result.materialization.upsert_result.planned_count,
                "upserted_count": result.materialization.upsert_result.upserted_count,
                "skipped_count": result.materialization.upsert_result.skipped_count,
                "warnings": list(result.materialization.warnings),
            }
    finally:
        await engine.dispose()


def main() -> None:
    args = _parser().parse_args()
    print(
        json.dumps(asyncio.run(_run(args)), ensure_ascii=False, indent=2, default=str)
    )


if __name__ == "__main__":
    main()
