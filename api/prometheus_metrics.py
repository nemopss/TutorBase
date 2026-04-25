"""Custom Prometheus metrics for business logic and background operations."""
from prometheus_client import Counter, Gauge, Histogram


# Business metrics
packages_created_total = Counter(
    'packages_created_total',
    'Total number of lesson packages created'
)

lessons_created_total = Counter(
    'lessons_created_total',
    'Total number of lessons created',
    ['status']
)

lessons_updated_total = Counter(
    'lessons_updated_total',
    'Total number of lessons updated',
    ['old_status', 'new_status']
)

reminders_sent_total = Counter(
    'reminders_sent_total',
    'Total number of reminders sent',
    ['status']
)

notification_jobs_claimed_total = Counter(
    'notification_jobs_claimed_total',
    'Total number of notification jobs claimed for processing',
    ['job_type']
)

notification_jobs_processed_total = Counter(
    'notification_jobs_processed_total',
    'Total number of notification jobs processed by result',
    ['job_type', 'result']
)

notification_deliveries_claimed_total = Counter(
    'notification_deliveries_claimed_total',
    'Total number of notifications claimed for delivery'
)

notification_deliveries_processed_total = Counter(
    'notification_deliveries_processed_total',
    'Total number of notification deliveries processed by result',
    ['result']
)

payments_recorded_total = Counter(
    'payments_recorded_total',
    'Total number of recorded payments',
    ['currency']
)

payments_recorded_amount_total = Counter(
    'payments_recorded_amount_total',
    'Total amount of recorded payments',
    ['currency']
)

payments_voided_total = Counter(
    'payments_voided_total',
    'Total number of voided payments',
    ['currency']
)

payments_voided_amount_total = Counter(
    'payments_voided_amount_total',
    'Total amount of voided payments',
    ['currency']
)


# Celery metrics
celery_task_started_total = Counter(
    'celery_task_started_total',
    'Total number of started Celery tasks',
    ['task_name']
)

celery_task_succeeded_total = Counter(
    'celery_task_succeeded_total',
    'Total number of successfully completed Celery tasks',
    ['task_name']
)

celery_task_failed_total = Counter(
    'celery_task_failed_total',
    'Total number of failed Celery tasks',
    ['task_name']
)

celery_task_retried_total = Counter(
    'celery_task_retried_total',
    'Total number of retried Celery tasks',
    ['task_name']
)

celery_task_duration_seconds = Histogram(
    'celery_task_duration_seconds',
    'Celery task execution duration in seconds',
    ['task_name'],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600)
)


# Current state gauges
active_packages_gauge = Gauge(
    'active_packages',
    'Current number of active lesson packages'
)

scheduled_lessons_gauge = Gauge(
    'scheduled_lessons',
    'Current number of scheduled lessons'
)

learners_gauge = Gauge(
    'total_learners',
    'Total number of learners in the system'
)


# Performance metrics
db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation']
)

reminder_processing_duration = Histogram(
    'reminder_processing_duration_seconds',
    'Reminder processing duration in seconds'
)
