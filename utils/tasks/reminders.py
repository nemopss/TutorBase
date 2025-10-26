"""Celery tasks for reminder generation and processing.

This module contains background tasks for reminder operations that can be
time-consuming and should not block API responses.

Tasks:
    - regenerate_package_reminders_task: Regenerate all reminders for a package
    
Best practices:
    - Tasks are idempotent (safe to retry)
    - Database sessions created per task (not shared)
    - Proper error handling with structured logging
    - Exponential backoff on retries
    - Task time limits to prevent hanging
"""
import logging
from typing import Optional

from utils.celery_app import celery_app
from database.engine import async_session

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='utils.tasks.reminders.regenerate_package_reminders',
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,  # 5 minutes
    soft_time_limit=240,  # 4 minutes
)
def regenerate_package_reminders_task(self, package_id: int, tenant_id: Optional[int] = None):
    """Regenerate all reminder rules and instances for a lesson package.
    
    This task rebuilds the entire reminder schedule for a package. It's idempotent
    and safe to retry. Runs asynchronously to avoid blocking API responses.
    
    Args:
        package_id: ID of the lesson package
        tenant_id: Optional tenant ID for multi-tenancy isolation
        
    Returns:
        dict: Task result with status and statistics
        
    Raises:
        Retry: On transient failures (with exponential backoff)
        
    Example:
        # Async execution
        regenerate_package_reminders_task.delay(package_id=123, tenant_id=1)
        
        # With custom countdown
        regenerate_package_reminders_task.apply_async(
            args=[123, 1],
            countdown=60  # Run in 1 minute
        )
    """
    import asyncio
    
    logger.info(
        f"Starting reminder regeneration for package {package_id}",
        extra={'package_id': package_id, 'tenant_id': tenant_id, 'task_id': self.request.id}
    )
    
    try:
        # Run async code in sync context
        # Use new_event_loop() instead of run() to avoid conflicts with Celery's event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_regenerate_reminders_async(package_id, tenant_id))
        finally:
            loop.close()
        
        logger.info(
            f"Reminder regeneration completed for package {package_id}",
            extra={
                'package_id': package_id,
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'result': result,
            }
        )
        
        return result
        
    except Exception as exc:
        logger.error(
            f"Reminder regeneration failed for package {package_id}: {exc}",
            extra={
                'package_id': package_id,
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'error': str(exc),
                'retry_count': self.request.retries,
            },
            exc_info=True,
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)  # 60s, 120s, 240s
            raise self.retry(exc=exc, countdown=countdown)
        
        # Max retries reached, fail permanently
        raise


async def _regenerate_reminders_async(package_id: int, tenant_id: Optional[int]) -> dict:
    """Async helper to regenerate reminders.
    
    Args:
        package_id: Package ID
        tenant_id: Tenant ID for isolation
        
    Returns:
        dict: Result with statistics
    """
    from services.package_scheduler import regenerate_package_reminders
    from database import crud
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from config import config
    from api.dependencies import CurrentTenant
    
    # Create a new engine with NullPool for this task to avoid event loop conflicts
    task_engine = create_async_engine(
        config.build_async_database_url(),
        poolclass=NullPool,  # No connection pooling to avoid event loop issues
        pool_pre_ping=True
    )
    task_session = async_sessionmaker(task_engine, expire_on_commit=False)
    
    async with task_session() as session:
        try:
            # Create tenant context
            current_tenant = CurrentTenant(
                tenant_id=tenant_id,
                is_super_admin=tenant_id is None,
                tenant=None,
            )
            
            # Get package
            package = await crud.get_lesson_package(session, current_tenant, package_id)
            if not package:
                raise ValueError(f"Package {package_id} not found")
            
            # Regenerate reminders
            await regenerate_package_reminders(session, current_tenant, package)
            
            # Commit transaction
            await session.commit()
            
            result = {
                'status': 'success',
                'package_id': package_id,
                'tenant_id': tenant_id,
            }
            
        except Exception:
            await session.rollback()
            raise
        finally:
            # Dispose engine to clean up connections
            await task_engine.dispose()
        
        return result


__all__ = ['regenerate_package_reminders_task']
