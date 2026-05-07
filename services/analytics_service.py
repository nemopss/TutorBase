from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import CurrentTenant
from api.schemas.analytics import (
    AnalyticsInsight,
    AnalyticsLearnerBreakdown,
    AnalyticsMetricComparison,
    AnalyticsNotifications,
    AnalyticsOverviewResponse,
    AnalyticsPackageBreakdown,
    AnalyticsSummary,
    AnalyticsTimePoint,
    AnalyticsWeekdayPoint,
)
from database.models import Learner, Lesson, LessonPackage, Payment, ReminderInstance
from services import finance_service
from utils.tenant import resolve_tenant_id


COMPLETED_STATUS = "completed"
PLANNED_STATUSES = {"scheduled", "rescheduled"}
CANCELLED_STATUS = "cancelled"
DELIVERED_REMINDER_STATUSES = {"sent", "delivered", "confirmed"}
FAILED_REMINDER_STATUSES = {"failed", "failed_retryable"}
PACKAGE_ENDING_SOON_DAYS = 3
CANCELLATION_RISK_THRESHOLD = 0.2
DEFAULT_LESSON_DURATION_MINUTES = 60


@dataclass
class PeriodFacts:
    completed_lessons: int = 0
    planned_lessons: int = 0
    cancelled_lessons: int = 0
    completed_hours: float = 0.0
    planned_hours: float = 0.0
    cash_revenue: Decimal = Decimal("0")
    earned_revenue: Decimal = Decimal("0")
    planned_revenue: Decimal = Decimal("0")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _period_dates(start: datetime, end: datetime) -> list[date]:
    first = start.date()
    last = end.date()
    if first > last:
        return []
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def _lesson_hours(lesson: Lesson) -> float:
    return round((lesson.duration_minutes or DEFAULT_LESSON_DURATION_MINUTES) / 60, 2)


def _lesson_value(lesson: Lesson) -> Decimal:
    package = lesson.package
    learner = package.learner if package else None
    value = lesson.price or (learner.lesson_rate if learner else None) or Decimal("0")
    return Decimal(value)


def _safe_rate(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total, 4)


def _comparison(current: float | Decimal, previous: float | Decimal) -> AnalyticsMetricComparison:
    current_float = round(float(current), 2)
    previous_float = round(float(previous), 2)
    delta = round(current_float - previous_float, 2)
    change_percent = None if previous_float == 0 else round((delta / previous_float) * 100, 1)
    return AnalyticsMetricComparison(
        current=current_float,
        previous=previous_float,
        delta=delta,
        change_percent=change_percent,
    )


async def build_analytics_overview(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    from_date: datetime,
    to_date: datetime,
) -> AnalyticsOverviewResponse:
    tenant_id = resolve_tenant_id(current_tenant)
    period_start = _as_utc(from_date)
    period_end = _as_utc(to_date)
    period_delta = period_end - period_start
    previous_period_end = period_start - timedelta(microseconds=1)
    previous_period_start = previous_period_end - period_delta
    now = datetime.now(timezone.utc)
    ending_soon_cutoff = now + timedelta(days=PACKAGE_ENDING_SOON_DAYS)

    learners = (
        await session.execute(
            select(Learner)
            .where(Learner.tenant_id == tenant_id)
            .options(selectinload(Learner.bot_user))
            .order_by(Learner.display_name.asc())
        )
    ).scalars().all()
    active_learners = [learner for learner in learners if learner.archived_at is None]
    active_learner_ids = {learner.id for learner in active_learners}

    packages = (
        await session.execute(
            select(LessonPackage)
            .where(LessonPackage.tenant_id == tenant_id)
            .options(
                selectinload(LessonPackage.learner),
                selectinload(LessonPackage.lessons),
            )
            .order_by(LessonPackage.created_at.desc(), LessonPackage.id.desc())
        )
    ).scalars().all()

    all_lessons: list[Lesson] = []
    for package in packages:
        all_lessons.extend(package.lessons)

    analysis_start = previous_period_start
    analysis_end = max(period_end, ending_soon_cutoff)
    period_lessons = [
        lesson for lesson in all_lessons
        if analysis_start <= _as_utc(lesson.scheduled_at) <= analysis_end
    ]

    payments = (
        await session.execute(
            select(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.voided_at.is_(None),
                Payment.paid_at >= previous_period_start,
                Payment.paid_at <= period_end,
            )
        )
    ).scalars().all()

    reminders = (
        await session.execute(
            select(ReminderInstance)
            .where(
                ReminderInstance.tenant_id == tenant_id,
                ReminderInstance.scheduled_for >= period_start,
                ReminderInstance.scheduled_for <= period_end,
            )
        )
    ).scalars().all()

    debtor_items, _ = await finance_service.get_debtors(session, current_tenant, limit=1000, offset=0)
    outstanding_by_learner = {
        item.learner_id: item.outstanding_balance
        for item in debtor_items
    }
    total_outstanding = sum(outstanding_by_learner.values(), Decimal("0"))

    day_facts: dict[date, PeriodFacts] = {day: PeriodFacts() for day in _period_dates(period_start, period_end)}
    weekday_facts: dict[int, PeriodFacts] = {weekday: PeriodFacts() for weekday in range(7)}
    learner_facts: dict[int, PeriodFacts] = defaultdict(PeriodFacts)
    current = PeriodFacts()
    previous = PeriodFacts()

    def apply_lesson(facts: PeriodFacts, lesson: Lesson) -> None:
        hours = _lesson_hours(lesson)
        value = _lesson_value(lesson)
        if lesson.status == COMPLETED_STATUS:
            facts.completed_lessons += 1
            facts.completed_hours = round(facts.completed_hours + hours, 2)
            facts.earned_revenue += value
        elif lesson.status in PLANNED_STATUSES:
            facts.planned_lessons += 1
            facts.planned_hours = round(facts.planned_hours + hours, 2)
            facts.planned_revenue += value
        elif lesson.status == CANCELLED_STATUS:
            facts.cancelled_lessons += 1

    for lesson in period_lessons:
        scheduled_at = _as_utc(lesson.scheduled_at)
        package = lesson.package
        learner_id = package.learner_id if package else None

        if period_start <= scheduled_at <= period_end:
            apply_lesson(current, lesson)
            if scheduled_at.date() in day_facts:
                apply_lesson(day_facts[scheduled_at.date()], lesson)
            apply_lesson(weekday_facts[scheduled_at.weekday()], lesson)
            if learner_id is not None:
                apply_lesson(learner_facts[learner_id], lesson)
        elif previous_period_start <= scheduled_at <= previous_period_end:
            apply_lesson(previous, lesson)

    for payment in payments:
        paid_at = _as_utc(payment.paid_at)
        if period_start <= paid_at <= period_end:
            current.cash_revenue += Decimal(payment.amount)
            day_facts.setdefault(paid_at.date(), PeriodFacts()).cash_revenue += Decimal(payment.amount)
            learner_facts[payment.learner_id].cash_revenue += Decimal(payment.amount)
        elif previous_period_start <= paid_at <= previous_period_end:
            previous.cash_revenue += Decimal(payment.amount)

    reminder_day_counts = {
        day: {"scheduled": 0, "delivered": 0, "failed": 0}
        for day in _period_dates(period_start, period_end)
    }
    delivered_reminders = 0
    failed_reminders = 0
    scheduled_reminders = 0
    failed_learner_ids: set[int] = set()
    for reminder in reminders:
        status = reminder.status or "unknown"
        day = _as_utc(reminder.scheduled_for).date()
        if status in DELIVERED_REMINDER_STATUSES:
            delivered_reminders += 1
            reminder_day_counts.setdefault(day, {"scheduled": 0, "delivered": 0, "failed": 0})["delivered"] += 1
        elif status in FAILED_REMINDER_STATUSES:
            failed_reminders += 1
            failed_learner_ids.add(reminder.learner_id)
            reminder_day_counts.setdefault(day, {"scheduled": 0, "delivered": 0, "failed": 0})["failed"] += 1
        elif status == "scheduled":
            scheduled_reminders += 1
            reminder_day_counts.setdefault(day, {"scheduled": 0, "delivered": 0, "failed": 0})["scheduled"] += 1

    total_decided_reminders = delivered_reminders + failed_reminders
    notification_delivery_rate = _safe_rate(delivered_reminders, total_decided_reminders)
    no_telegram_learners = [
        learner for learner in active_learners
        if learner.bot_user is None or learner.bot_user.chat_id is None
    ]

    summary = AnalyticsSummary(
        active_learners=len(active_learners),
        completed_lessons=current.completed_lessons,
        planned_lessons=current.planned_lessons,
        cancelled_lessons=current.cancelled_lessons,
        completed_hours=current.completed_hours,
        planned_hours=current.planned_hours,
        cash_revenue=current.cash_revenue,
        earned_revenue=current.earned_revenue,
        planned_revenue=current.planned_revenue,
        outstanding_revenue=total_outstanding,
        cancellation_rate=_safe_rate(
            current.cancelled_lessons,
            current.completed_lessons + current.planned_lessons + current.cancelled_lessons,
        ),
        notification_delivery_rate=notification_delivery_rate,
    )

    comparisons = {
        "completed_lessons": _comparison(current.completed_lessons, previous.completed_lessons),
        "completed_hours": _comparison(current.completed_hours, previous.completed_hours),
        "cash_revenue": _comparison(current.cash_revenue, previous.cash_revenue),
        "earned_revenue": _comparison(current.earned_revenue, previous.earned_revenue),
        "cancelled_lessons": _comparison(current.cancelled_lessons, previous.cancelled_lessons),
    }

    timeseries = [
        AnalyticsTimePoint(
            date=day,
            completed_lessons=day_facts[day].completed_lessons,
            planned_lessons=day_facts[day].planned_lessons,
            cancelled_lessons=day_facts[day].cancelled_lessons,
            completed_hours=day_facts[day].completed_hours,
            planned_hours=day_facts[day].planned_hours,
            cash_revenue=day_facts[day].cash_revenue,
            earned_revenue=day_facts[day].earned_revenue,
            reminders_scheduled=reminder_day_counts.get(day, {}).get("scheduled", 0),
            reminders_delivered=reminder_day_counts.get(day, {}).get("delivered", 0),
            reminders_failed=reminder_day_counts.get(day, {}).get("failed", 0),
        )
        for day in _period_dates(period_start, period_end)
    ]

    weekday_load = [
        AnalyticsWeekdayPoint(
            weekday=weekday,
            completed_lessons=weekday_facts[weekday].completed_lessons,
            planned_lessons=weekday_facts[weekday].planned_lessons,
            cancelled_lessons=weekday_facts[weekday].cancelled_lessons,
            completed_hours=weekday_facts[weekday].completed_hours,
            planned_hours=weekday_facts[weekday].planned_hours,
        )
        for weekday in range(7)
    ]

    future_lessons_by_learner: dict[int, list[Lesson]] = defaultdict(list)
    for lesson in all_lessons:
        if lesson.status in PLANNED_STATUSES and _as_utc(lesson.scheduled_at) >= now:
            future_lessons_by_learner[lesson.package.learner_id].append(lesson)

    learner_breakdown: list[AnalyticsLearnerBreakdown] = []
    for learner in active_learners:
        facts = learner_facts[learner.id]
        total_lessons = facts.completed_lessons + facts.planned_lessons + facts.cancelled_lessons
        cancellation_rate = _safe_rate(facts.cancelled_lessons, total_lessons)
        risk_flags: list[str] = []
        has_future_lessons = len(future_lessons_by_learner.get(learner.id, [])) > 0
        if not has_future_lessons:
            risk_flags.append("no_future_lessons")
        if cancellation_rate >= CANCELLATION_RISK_THRESHOLD and facts.cancelled_lessons > 0:
            risk_flags.append("high_cancellation_rate")
        if outstanding_by_learner.get(learner.id, Decimal("0")) > 0:
            risk_flags.append("outstanding_balance")
        if learner.bot_user is None or learner.bot_user.chat_id is None:
            risk_flags.append("no_telegram")

        learner_breakdown.append(
            AnalyticsLearnerBreakdown(
                learner_id=learner.id,
                learner_name=learner.display_name,
                completed_lessons=facts.completed_lessons,
                planned_lessons=facts.planned_lessons,
                cancelled_lessons=facts.cancelled_lessons,
                completed_hours=facts.completed_hours,
                planned_hours=facts.planned_hours,
                cash_revenue=facts.cash_revenue,
                earned_revenue=facts.earned_revenue,
                planned_revenue=facts.planned_revenue,
                outstanding_revenue=outstanding_by_learner.get(learner.id, Decimal("0")),
                cancellation_rate=cancellation_rate,
                has_future_lessons=has_future_lessons,
                risk_flags=risk_flags,
            )
        )

    learner_breakdown.sort(
        key=lambda item: (
            len(item.risk_flags),
            float(item.outstanding_revenue),
            item.cancelled_lessons,
            item.completed_lessons,
        ),
        reverse=True,
    )

    package_breakdown: list[AnalyticsPackageBreakdown] = []
    for package in packages:
        if package.learner_id not in active_learner_ids:
            continue
        package_lessons = sorted(package.lessons, key=lambda lesson: lesson.scheduled_at)
        total_lessons = package.total_lessons or len(package_lessons)
        completed_lessons = sum(1 for lesson in package_lessons if lesson.status == COMPLETED_STATUS)
        cancelled_lessons = sum(1 for lesson in package_lessons if lesson.status == CANCELLED_STATUS)
        future_lessons = [
            lesson for lesson in package_lessons
            if lesson.status in PLANNED_STATUSES and _as_utc(lesson.scheduled_at) >= now
        ]
        remaining_lessons = max(0, total_lessons - completed_lessons - cancelled_lessons)
        next_lesson = future_lessons[0] if future_lessons else None
        last_lesson = package_lessons[-1] if package_lessons else None
        last_future_lesson = future_lessons[-1] if future_lessons else None
        ends_soon = (
            package.status == "active"
            and last_future_lesson is not None
            and _as_utc(last_future_lesson.scheduled_at) <= ending_soon_cutoff
        )
        risk_flags: list[str] = []
        if package.status == "active" and not future_lessons:
            risk_flags.append("no_future_lessons")
        if ends_soon:
            risk_flags.append("ending_soon")
        if package.payment_status in {"unpaid", "partial"}:
            risk_flags.append("payment_open")

        package_breakdown.append(
            AnalyticsPackageBreakdown(
                package_id=package.id,
                package_title=package.title,
                learner_id=package.learner_id,
                learner_name=package.learner.display_name if package.learner else "Unknown",
                status=package.status,
                total_lessons=total_lessons,
                completed_lessons=completed_lessons,
                cancelled_lessons=cancelled_lessons,
                remaining_lessons=remaining_lessons,
                progress_percent=round(((completed_lessons + cancelled_lessons) / total_lessons) * 100, 1) if total_lessons else 0,
                next_lesson_at=next_lesson.scheduled_at if next_lesson else None,
                last_lesson_at=last_lesson.scheduled_at if last_lesson else None,
                ends_soon=ends_soon,
                risk_flags=risk_flags,
            )
        )

    package_breakdown.sort(
        key=lambda item: (len(item.risk_flags), item.ends_soon, item.remaining_lessons * -1),
        reverse=True,
    )

    notifications = AnalyticsNotifications(
        total_scheduled=scheduled_reminders,
        total_delivered=delivered_reminders,
        total_failed=failed_reminders,
        delivery_rate=notification_delivery_rate,
        failed_learners_count=len(failed_learner_ids),
        no_telegram_learners_count=len(no_telegram_learners),
    )

    insights = _build_insights(
        summary=summary,
        learners=learner_breakdown,
        packages=package_breakdown,
        notifications=notifications,
    )

    return AnalyticsOverviewResponse(
        period_start=period_start,
        period_end=period_end,
        previous_period_start=previous_period_start,
        previous_period_end=previous_period_end,
        summary=summary,
        comparisons=comparisons,
        timeseries=timeseries,
        weekday_load=weekday_load,
        learners=learner_breakdown,
        packages=package_breakdown,
        notifications=notifications,
        insights=insights,
    )


def _build_insights(
    *,
    summary: AnalyticsSummary,
    learners: list[AnalyticsLearnerBreakdown],
    packages: list[AnalyticsPackageBreakdown],
    notifications: AnalyticsNotifications,
) -> list[AnalyticsInsight]:
    insights: list[AnalyticsInsight] = []

    no_future_learners = [learner for learner in learners if "no_future_lessons" in learner.risk_flags]
    if no_future_learners:
        insights.append(
            AnalyticsInsight(
                code="no_future_learners",
                category="learner",
                severity="warning",
                title="Ученики без будущих уроков",
                detail=f"{len(no_future_learners)} активных учеников не имеют будущих занятий.",
                action_label="Открыть учеников",
                target_path="/learners",
                metric_value=len(no_future_learners),
            )
        )

    high_cancel_learners = [learner for learner in learners if "high_cancellation_rate" in learner.risk_flags]
    if high_cancel_learners:
        insights.append(
            AnalyticsInsight(
                code="high_cancellation_rate",
                category="workload",
                severity="warning",
                title="Высокая доля отмен",
                detail=f"{len(high_cancel_learners)} учеников имеют долю отмен 20% или выше за период.",
                action_label="Проверить учеников",
                target_path="/learners",
                metric_value=len(high_cancel_learners),
            )
        )

    ending_packages = [package for package in packages if package.ends_soon]
    if ending_packages:
        insights.append(
            AnalyticsInsight(
                code="ending_packages",
                category="package",
                severity="warning",
                title="Пакеты заканчиваются в ближайшие 3 дня",
                detail=f"{len(ending_packages)} активных пакетов скоро дойдут до последнего урока.",
                action_label="Открыть пакеты",
                target_path="/packages",
                metric_value=len(ending_packages),
            )
        )

    debt_learners = [learner for learner in learners if learner.outstanding_revenue > 0]
    if debt_learners:
        insights.append(
            AnalyticsInsight(
                code="outstanding_balance",
                category="finance",
                severity="critical",
                title="Есть задолженность",
                detail=f"{len(debt_learners)} учеников имеют открытый баланс.",
                action_label="Открыть финансы",
                target_path="/finance/dashboard",
                metric_value=len(debt_learners),
            )
        )

    if notifications.total_failed > 0:
        insights.append(
            AnalyticsInsight(
                code="notification_failures",
                category="notifications",
                severity="critical",
                title="Ошибки уведомлений",
                detail=f"{notifications.total_failed} уведомлений завершились ошибкой за выбранный период.",
                action_label="Открыть уведомления",
                target_path="/notifications",
                metric_value=notifications.total_failed,
            )
        )

    if notifications.no_telegram_learners_count > 0:
        insights.append(
            AnalyticsInsight(
                code="no_telegram_learners",
                category="notifications",
                severity="info",
                title="Не все ученики подключены к Telegram",
                detail=f"{notifications.no_telegram_learners_count} активных учеников не имеют Telegram-связки.",
                action_label="Открыть учеников",
                target_path="/learners",
                metric_value=notifications.no_telegram_learners_count,
            )
        )

    if not insights:
        insights.append(
            AnalyticsInsight(
                code="no_critical_issues",
                category="workload",
                severity="info",
                title="Критичных отклонений нет",
                detail="За выбранный период нет заметных рисков по расписанию, оплатам или уведомлениям.",
            )
        )

    return insights
