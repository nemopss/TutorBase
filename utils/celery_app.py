"""Celery application configuration for background task processing.

This module configures Celery for asynchronous task processing in TutorBase.
Uses Redis as both broker and result backend for simplicity and performance.

Architecture:
    - Broker: Redis DB 1 (separate from cache which uses DB 0)
    - Backend: Redis DB 1 (same as broker for simplicity)
    - Workers: Separate process(es) running celery worker command
    - Monitoring: Flower UI available for task monitoring

Task patterns:
    - Retry with exponential backoff (up to 3 retries)
    - Task time limits (5 min hard, 4 min soft)
    - Late acknowledgment (retry on worker crash)
    - JSON serialization (security and compatibility)
    - Structured logging with task context

Best practices implemented:
    - Separate Redis DB for tasks (isolation from cache)
    - Task time limits to prevent hanging tasks
    - Exponential backoff for retries
    - Late acks for reliability
    - Prefetch multiplier = 1 for fair distribution
    - Comprehensive error handling and logging
    - Task result expiration (24 hours)

Usage:
    # Define task
    from utils.celery_app import celery_app
    
    @celery_app.task(bind=True, max_retries=3)
    def my_task(self, arg1, arg2):
        try:
            # Task logic
            return result
        except Exception as exc:
            # Retry with exponential backoff
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    
    # Call task
    my_task.delay(arg1, arg2)  # Async execution
    result = my_task.apply_async(args=[arg1, arg2], countdown=60)  # Delayed execution
"""
import logging
from time import monotonic
from importlib import import_module

from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, task_retry
from api.prometheus_metrics import (
    celery_task_duration_seconds,
    celery_task_failed_total,
    celery_task_retried_total,
    celery_task_started_total,
    celery_task_succeeded_total,
)
from config import config

logger = logging.getLogger(__name__)

TASK_MODULES = (
    'utils.tasks.reminders',
    'utils.tasks.metrics',
    'utils.tasks.notifications',
    'utils.tasks.tenant_access',
    'utils.tasks.broadcasts',
)

_task_started_at: dict[str, float] = {}


def _resolve_task_name(sender=None, task=None) -> str:
    if task is not None and getattr(task, "name", None):
        return task.name
    if sender is not None and getattr(sender, "name", None):
        return sender.name
    return "unknown"


def _build_notifications_beat_schedule(
    *,
    notifications_automation_enabled: bool,
    process_jobs_interval_seconds: int,
    delivery_interval_seconds: int,
) -> dict[str, dict]:
    if not notifications_automation_enabled:
        return {}

    process_expires = max(process_jobs_interval_seconds - 5, 1)
    delivery_expires = max(delivery_interval_seconds - 5, 1)

    return {
        'notifications.process-jobs': {
            'task': 'utils.tasks.notifications.process_notification_jobs',
            'schedule': process_jobs_interval_seconds,
            'kwargs': {
                'tenant_id': None,
                'job_type': None,
                'limit': 20,
            },
            'options': {
                'expires': process_expires,
            },
        },
        'notifications.deliver-due': {
            'task': 'utils.tasks.notifications.deliver_due_notifications',
            'schedule': delivery_interval_seconds,
            'kwargs': {
                'tenant_id': None,
                'limit': 100,
            },
            'options': {
                'expires': delivery_expires,
            },
        },
    }


def _build_tenant_access_beat_schedule(
    *,
    tenant_access_sync_enabled: bool,
    sync_interval_seconds: int,
) -> dict[str, dict]:
    if not tenant_access_sync_enabled:
        return {}

    return {
        'tenant-access.sync-lifecycle': {
            'task': 'utils.tasks.tenant_access.sync_lifecycle',
            'schedule': sync_interval_seconds,
            'options': {
                'expires': max(sync_interval_seconds - 60, 1),
            },
        },
    }


# Initialize Celery app
# Note: config.REDIS_URL typically ends with /0, so we replace it with /1 for tasks
_redis_url_base = config.REDIS_URL.rsplit('/', 1)[0]  # Remove /0 if present
celery_app = Celery(
    'tutorbase',
    broker=f'{_redis_url_base}/1',  # Redis DB 1 for tasks (DB 0 for cache)
    backend=f'{_redis_url_base}/1',  # Same as broker for simplicity
)

# Celery configuration with best practices
celery_app.conf.update(
    # Serialization (JSON for security and compatibility)
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    # Timezone
    timezone='Europe/Moscow',
    enable_utc=True,
    
    # Task execution
    task_track_started=True,  # Track when task starts (for monitoring)
    task_time_limit=300,  # 5 minutes hard limit (kills task)
    task_soft_time_limit=240,  # 4 minutes soft limit (raises exception)
    task_acks_late=True,  # Acknowledge after task completes (retry on crash)
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    
    # Worker configuration
    worker_prefetch_multiplier=1,  # Fetch one task at a time (fair distribution)
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)
    
    # Result backend
    result_expires=86400,  # Results expire after 24 hours
    result_backend_transport_options={
        'master_name': 'mymaster',  # For Redis Sentinel (future-proofing)
    },
    
    # Retry configuration
    task_default_retry_delay=60,  # Default retry delay: 1 minute
    task_max_retries=3,  # Default max retries
    
    # Broker configuration
    broker_connection_retry_on_startup=True,  # Retry connection on startup
    broker_connection_retry=True,  # Retry on connection loss
    broker_connection_max_retries=10,  # Max connection retries
    
    # Task routing disabled for now - all tasks go to default 'celery' queue
    # Future: Enable different queues for different priorities
    # task_routes={
    #     'utils.tasks.reminders.*': {'queue': 'reminders'},
    #     'utils.tasks.metrics.*': {'queue': 'metrics'},
    #     'utils.tasks.*': {'queue': 'default'},
    # },
    
    # Task priority (0-9, higher = more important)
    task_default_priority=5,
    
    # Monitoring
    worker_send_task_events=True,  # Send events for monitoring (Flower)
    task_send_sent_event=True,  # Send event when task is sent
    beat_schedule={
        **_build_notifications_beat_schedule(
            notifications_automation_enabled=config.NOTIFICATIONS_AUTOMATION_ENABLED,
            process_jobs_interval_seconds=config.NOTIFICATIONS_PROCESS_JOBS_INTERVAL_SECONDS,
            delivery_interval_seconds=config.NOTIFICATIONS_DELIVERY_INTERVAL_SECONDS,
        ),
        **_build_tenant_access_beat_schedule(
            tenant_access_sync_enabled=config.TENANT_ACCESS_SYNC_ENABLED,
            sync_interval_seconds=config.TENANT_ACCESS_SYNC_INTERVAL_SECONDS,
        ),
    },
)

# Import task modules explicitly so the worker always registers them at startup.
# This avoids relying on Celery autodiscovery for a codebase that has both
# `utils/tasks.py` and the `utils/tasks/` package.
for module_name in TASK_MODULES:
    import_module(module_name)


# Signal handlers for structured logging
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log when task starts execution."""
    task_name = _resolve_task_name(sender=sender, task=task)
    if task_id is not None:
        _task_started_at[task_id] = monotonic()
    celery_task_started_total.labels(task_name=task_name).inc()
    args_count = len(args) if args is not None else 0
    kwargs_keys = sorted(kwargs.keys()) if isinstance(kwargs, dict) else []
    logger.info(
        f"Task started: {task_name}",
        extra={
            'task_id': task_id,
            'task_name': task_name,
            'args_count': args_count,
            'kwargs_keys': kwargs_keys,
        }
    )


@task_postrun.connect
def task_postrun_handler(
    sender=None,
    task_id=None,
    task=None,
    args=None,
    kwargs=None,
    retval=None,
    state=None,
    **extra,
):
    """Log when task finishes and record terminal state metrics."""
    task_name = _resolve_task_name(sender=sender, task=task)
    started_at = _task_started_at.pop(task_id, None) if task_id is not None else None
    if started_at is not None:
        celery_task_duration_seconds.labels(task_name=task_name).observe(
            monotonic() - started_at
        )
    if state == 'SUCCESS':
        celery_task_succeeded_total.labels(task_name=task_name).inc()
    logger.info(
        f"Task finished: {task_name}",
        extra={
            'task_id': task_id,
            'task_name': task_name,
            'state': state,
            'result_type': type(retval).__name__ if retval is not None else None,
        }
    )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, **extra):
    """Log when task fails."""
    task_name = _resolve_task_name(sender=sender)
    celery_task_failed_total.labels(task_name=task_name).inc()
    args_count = len(args) if args is not None else 0
    kwargs_keys = sorted(kwargs.keys()) if isinstance(kwargs, dict) else []
    logger.error(
        f"Task failed: {task_name}",
        extra={
            'task_id': task_id,
            'task_name': task_name,
            'exception_type': type(exception).__name__ if exception else None,
            'args_count': args_count,
            'kwargs_keys': kwargs_keys,
        },
    )


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, **extra):
    """Log when task is retried."""
    task_name = _resolve_task_name(sender=sender)
    request = extra.get('request')
    retry_count = getattr(request, 'retries', 0) if request is not None else 0
    celery_task_retried_total.labels(task_name=task_name).inc()
    logger.warning(
        f"Task retry: {task_name}",
        extra={
            'task_id': task_id,
            'task_name': task_name,
            'reason_type': type(reason).__name__ if reason is not None else None,
            'retry_count': retry_count,
        }
    )


# Health check task for monitoring
@celery_app.task(name='utils.tasks.health_check')
def health_check():
    """Health check task for monitoring worker availability.
    
    Returns:
        dict: Status information
    """
    return {
        'status': 'healthy',
        'worker': 'available',
    }


__all__ = [
    'celery_app',
    'health_check',
    '_build_notifications_beat_schedule',
    '_build_tenant_access_beat_schedule',
]
