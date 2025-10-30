"""Celery tasks for package metrics synchronization.

This module contains background tasks for metrics operations that can be
time-consuming, especially for bulk updates.

Tasks:
    - sync_package_metrics_task: Sync metrics for single package
    - bulk_sync_package_metrics_task: Sync metrics for multiple packages
    
Best practices:
    - Tasks are idempotent (safe to retry)
    - Database sessions created per task
    - Proper error handling with structured logging
    - Exponential backoff on retries
    - Bulk operations chunked for reliability
"""
import logging
from typing import List, Optional

from utils.celery_app import celery_app
from database.engine import async_session

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='utils.tasks.metrics.sync_package_metrics',
    max_retries=3,
    default_retry_delay=60,
    time_limit=180,  # 3 minutes
    soft_time_limit=150,  # 2.5 minutes
)
def sync_package_metrics_task(self, package_id: int, tenant_id: Optional[int] = None):
    """Synchronize metrics for a single lesson package.
    
    Recalculates and updates package metrics based on current lesson states.
    Idempotent and safe to retry.
    
    Args:
        package_id: ID of the lesson package
        tenant_id: Optional tenant ID for multi-tenancy isolation
        
    Returns:
        dict: Task result with updated metrics
        
    Raises:
        Retry: On transient failures (with exponential backoff)
        
    Example:
        # Async execution
        sync_package_metrics_task.delay(package_id=123, tenant_id=1)
    """
    import asyncio
    
    logger.info(
        f"Starting metrics sync for package {package_id}",
        extra={'package_id': package_id, 'tenant_id': tenant_id, 'task_id': self.request.id}
    )
    
    try:
        # Run async code in sync context
        # Use new_event_loop() instead of run() to avoid conflicts with Celery's event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_sync_metrics_async(package_id, tenant_id))
        finally:
            loop.close()
        
        logger.info(
            f"Metrics sync completed for package {package_id}",
            extra={
                'package_id': package_id,
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'metrics': result,
            }
        )
        
        return result
        
    except Exception as exc:
        logger.error(
            f"Metrics sync failed for package {package_id}: {exc}",
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
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)
        
        raise


@celery_app.task(
    bind=True,
    name='utils.tasks.metrics.bulk_sync_package_metrics',
    max_retries=3,
    default_retry_delay=120,
    time_limit=600,  # 10 minutes for bulk
    soft_time_limit=540,  # 9 minutes
)
def bulk_sync_package_metrics_task(
    self,
    package_ids: List[int],
    tenant_id: Optional[int] = None,
    chunk_size: int = 10,
):
    """Synchronize metrics for multiple lesson packages in chunks.
    
    Processes packages in chunks to avoid overwhelming the database and
    to provide better error isolation. If one package fails, others continue.
    
    Args:
        package_ids: List of package IDs to sync
        tenant_id: Optional tenant ID for multi-tenancy isolation
        chunk_size: Number of packages to process in each chunk (default: 10)
        
    Returns:
        dict: Task result with success/failure statistics
        
    Example:
        # Async execution for bulk sync
        bulk_sync_package_metrics_task.delay(
            package_ids=[1, 2, 3, 4, 5],
            tenant_id=1,
            chunk_size=10
        )
    """
    import asyncio
    
    logger.info(
        f"Starting bulk metrics sync for {len(package_ids)} packages",
        extra={
            'package_count': len(package_ids),
            'tenant_id': tenant_id,
            'task_id': self.request.id,
            'chunk_size': chunk_size,
        }
    )
    
    try:
        # Run async code in sync context
        # Use new_event_loop() instead of run() to avoid conflicts with Celery's event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_bulk_sync_metrics_async(package_ids, tenant_id, chunk_size))
        finally:
            loop.close()
        
        logger.info(
            f"Bulk metrics sync completed: {result['success_count']}/{result['total_count']} succeeded",
            extra={
                'task_id': self.request.id,
                'result': result,
            }
        )
        
        return result
        
    except Exception as exc:
        logger.error(
            f"Bulk metrics sync failed: {exc}",
            extra={
                'package_count': len(package_ids),
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'error': str(exc),
                'retry_count': self.request.retries,
            },
            exc_info=True,
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 120 * (2 ** self.request.retries)  # 120s, 240s, 480s
            raise self.retry(exc=exc, countdown=countdown)
        
        raise


async def _sync_metrics_async(package_id: int, tenant_id: Optional[int]) -> dict:
    """Async helper to sync metrics for single package.
    
    Args:
        package_id: Package ID
        tenant_id: Tenant ID for isolation
        
    Returns:
        dict: Updated metrics
    """
    from services.package_service import sync_metrics
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
            
            # Sync metrics
            package_dto = await sync_metrics(session, current_tenant, package_id)
            
            # Commit transaction
            await session.commit()
            
            result = {
                'status': 'success',
                'package_id': package_id,
                'completed_lessons': package_dto.progress.completed,
                'total_lessons': package_dto.progress.total,
            }
            
        except Exception:
            await session.rollback()
            raise
        finally:
            # Dispose engine to clean up connections
            await task_engine.dispose()
        
        return result


async def _bulk_sync_metrics_async(
    package_ids: List[int],
    tenant_id: Optional[int],
    chunk_size: int,
) -> dict:
    """Async helper to sync metrics for multiple packages in chunks.
    
    Args:
        package_ids: List of package IDs
        tenant_id: Tenant ID for isolation
        chunk_size: Chunk size for processing
        
    Returns:
        dict: Statistics about sync operation
    """
    from services.package_service import sync_metrics
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
    
    success_count = 0
    failure_count = 0
    failed_packages = []
    
    try:
        # Process in chunks
        for i in range(0, len(package_ids), chunk_size):
            chunk = package_ids[i:i + chunk_size]
            
            for package_id in chunk:
                try:
                    async with task_session() as session:
                        # Create tenant context
                        current_tenant = CurrentTenant(
                            tenant_id=tenant_id,
                            is_super_admin=tenant_id is None,
                            tenant=None,
                        )
                        
                        # Sync metrics
                        package_dto = await sync_metrics(session, current_tenant, package_id)
                        
                        # Commit transaction
                        await session.commit()
                        
                    success_count += 1
                except Exception as exc:
                    failure_count += 1
                    failed_packages.append({
                        'package_id': package_id,
                        'error': str(exc),
                    })
                    logger.warning(
                        f"Failed to sync metrics for package {package_id}: {exc}",
                        extra={'package_id': package_id, 'error': str(exc)}
                    )
    finally:
        # Dispose engine to clean up connections
        await task_engine.dispose()
    
    return {
        'status': 'completed',
        'total_count': len(package_ids),
        'success_count': success_count,
        'failure_count': failure_count,
        'failed_packages': failed_packages,
    }


__all__ = [
    'sync_package_metrics_task',
    'bulk_sync_package_metrics_task',
]
