"""Background tasks for TutorBase.

This package contains all Celery task definitions organized by domain:
    - reminders: Reminder generation and processing tasks
    - metrics: Package metrics synchronization tasks
    - maintenance: System maintenance and cleanup tasks

All tasks follow best practices:
    - Idempotent (safe to retry)
    - Atomic (all-or-nothing operations)
    - Logged (structured logging with context)
    - Time-limited (prevent hanging tasks)
    - Retry-enabled (exponential backoff)

Usage:
    from utils.tasks import regenerate_package_reminders_task
    
    # Async execution
    regenerate_package_reminders_task.delay(package_id=123)
    
    # Delayed execution (run in 5 minutes)
    regenerate_package_reminders_task.apply_async(
        args=[123],
        countdown=300
    )
    
    # With custom retry
    regenerate_package_reminders_task.apply_async(
        args=[123],
        retry=True,
        retry_policy={
            'max_retries': 5,
            'interval_start': 0,
            'interval_step': 60,
            'interval_max': 300,
        }
    )
"""

# Import tasks for easy access
from utils.tasks.reminders import (
    regenerate_package_reminders_task,
)
from utils.tasks.metrics import (
    sync_package_metrics_task,
    bulk_sync_package_metrics_task,
)

__all__ = [
    'regenerate_package_reminders_task',
    'sync_package_metrics_task',
    'bulk_sync_package_metrics_task',
]
