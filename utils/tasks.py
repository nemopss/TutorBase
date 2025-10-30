"""Background tasks for asynchronous processing.

This module contains Celery tasks for operations that should run asynchronously:
- Reminder generation (can take several seconds for large packages)
- Metric synchronization (batch operations)
- Other long-running operations

All tasks follow best practices:
- Retry with exponential backoff
- Structured logging with task context
- Time limits to prevent hanging
- Proper error handling
"""
import logging
from utils.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='utils.tasks.regenerate_package_reminders', max_retries=3)
def regenerate_package_reminders_task(self, package_id: int, tenant_id: int | None):
    """Regenerate reminders for a lesson package (background task).
    
    This task runs asynchronously to avoid blocking API responses when
    lessons are created/updated/deleted.
    
    Args:
        package_id: ID of the lesson package
        tenant_id: Tenant ID for multi-tenancy context
        
    Returns:
        dict: Task result with status
        
    Raises:
        Exception: Re-raises after retry attempts exhausted
    """
    try:
        logger.info(f"Regenerating reminders for package {package_id} (tenant: {tenant_id})")
        
        # Import here to avoid circular dependencies
        from database.engine import async_session
        from services import reminder_service
        from api.dependencies import CurrentTenant
        import asyncio
        
        async def _regenerate():
            async with async_session() as session:
                current_tenant = CurrentTenant(
                    tenant_id=tenant_id,
                    is_super_admin=False,
                    tenant=None
                )
                await reminder_service.regenerate_package_reminders(
                    session, 
                    current_tenant, 
                    package_id
                )
                await session.commit()
        
        # Run async function in sync context
        asyncio.run(_regenerate())
        
        logger.info(f"Successfully regenerated reminders for package {package_id}")
        return {'status': 'success', 'package_id': package_id}
        
    except Exception as exc:
        logger.error(f"Failed to regenerate reminders for package {package_id}: {exc}")
        # Retry with exponential backoff: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, name='utils.tasks.sync_package_metrics', max_retries=3)
def sync_package_metrics_task(self, package_id: int, tenant_id: int | None):
    """Synchronize package metrics (background task).
    
    Updates calculated metrics like completion percentage, lesson counts, etc.
    Runs asynchronously to avoid blocking API responses.
    
    Args:
        package_id: ID of the lesson package
        tenant_id: Tenant ID for multi-tenancy context
        
    Returns:
        dict: Task result with status
        
    Raises:
        Exception: Re-raises after retry attempts exhausted
    """
    try:
        logger.info(f"Syncing metrics for package {package_id} (tenant: {tenant_id})")
        
        # Import here to avoid circular dependencies
        from database.engine import async_session
        from services import package_service
        from api.dependencies import CurrentTenant
        import asyncio
        
        async def _sync_metrics():
            async with async_session() as session:
                current_tenant = CurrentTenant(
                    tenant_id=tenant_id,
                    is_super_admin=False,
                    tenant=None
                )
                await package_service.sync_package_metrics(
                    session,
                    current_tenant,
                    package_id
                )
                await session.commit()
        
        # Run async function in sync context
        asyncio.run(_sync_metrics())
        
        logger.info(f"Successfully synced metrics for package {package_id}")
        return {'status': 'success', 'package_id': package_id}
        
    except Exception as exc:
        logger.error(f"Failed to sync metrics for package {package_id}: {exc}")
        # Retry with exponential backoff: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


__all__ = [
    'regenerate_package_reminders_task',
    'sync_package_metrics_task',
]
