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
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, task_retry
from config import config

logger = logging.getLogger(__name__)

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
)


# Signal handlers for structured logging
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log when task starts execution."""
    logger.info(
        f"Task started: {task.name}",
        extra={
            'task_id': task_id,
            'task_name': task.name,
            'task_args': str(args)[:100],  # Limit arg length in logs
            'task_kwargs': str(kwargs)[:100],
        }
    )


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, **extra):
    """Log when task completes successfully."""
    logger.info(
        f"Task completed: {task.name}",
        extra={
            'task_id': task_id,
            'task_name': task.name,
            'result': str(retval)[:100] if retval else None,
        }
    )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, **extra):
    """Log when task fails."""
    logger.error(
        f"Task failed: {sender.name}",
        extra={
            'task_id': task_id,
            'task_name': sender.name,
            'exception': str(exception),
            'task_args': str(args)[:100],
            'task_kwargs': str(kwargs)[:100],
        },
        exc_info=exception,
    )


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, **extra):
    """Log when task is retried."""
    logger.warning(
        f"Task retry: {sender.name}",
        extra={
            'task_id': task_id,
            'task_name': sender.name,
            'reason': str(reason),
            'retry_count': extra.get('request', {}).get('retries', 0),
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


# Auto-discover tasks from utils.tasks module
# This ensures all task modules are imported and registered with Celery
celery_app.autodiscover_tasks(['utils.tasks'], force=True)


__all__ = ['celery_app', 'health_check']
