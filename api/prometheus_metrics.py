"""Custom Prometheus metrics for business logic."""
from prometheus_client import Counter, Gauge, Histogram

# Business metrics
packages_created_total = Counter(
    'packages_created_total',
    'Total number of lesson packages created',
    ['learner_id']
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
