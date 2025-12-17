"""Service for managing learner schedules.

This module contains business logic for working with learner schedules -
weekly recurring rules that define when a learner typically has lessons.

Key components:
    - get_learner_schedule: Get schedule for a learner
    - update_learner_schedule: Replace entire schedule
    - add_schedule_slots: Add slots for multiple days
    - delete_schedule_slot: Remove a single slot
    - generate_lesson_dates: Generate lesson dates from schedule

Business logic:
    - All operations respect tenant isolation
    - Schedules are stored in lesson_package_templates table with learner_id
    - Schedule data is stored as JSON in default_config column
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database.models import LessonPackageTemplate, Learner


# Type definitions
ScheduleSlot = dict  # {"day": int, "time": str, "duration": int}
ScheduleData = dict  # {"slots": list[ScheduleSlot], "timezone": str}


async def get_learner_schedule(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    learner_id: int,
) -> ScheduleData:
    """Get schedule for a learner.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        learner_id: ID of the learner
        
    Returns:
        Schedule data with slots and timezone
    """
    stmt = select(LessonPackageTemplate).where(
        LessonPackageTemplate.tenant_id == current_tenant.tenant_id,
        LessonPackageTemplate.learner_id == learner_id,
    )
    result = await session.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template or not template.default_config:
        return {"slots": [], "timezone": "Europe/Moscow"}
    
    config = template.default_config
    schedule = config.get("schedule", {})
    return {
        "slots": schedule.get("slots", []),
        "timezone": schedule.get("timezone", template.default_timezone or "Europe/Moscow"),
    }


async def update_learner_schedule(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    learner_id: int,
    slots: list[ScheduleSlot],
    timezone: str = "Europe/Moscow",
) -> ScheduleData:
    """Replace entire schedule for a learner.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        learner_id: ID of the learner
        slots: New list of schedule slots
        timezone: Timezone for the schedule
        
    Returns:
        Updated schedule data
    """
    # Sort slots by day and time for consistent ordering
    sorted_slots = sorted(slots, key=lambda s: (s["day"], s["time"]))
    
    stmt = select(LessonPackageTemplate).where(
        LessonPackageTemplate.tenant_id == current_tenant.tenant_id,
        LessonPackageTemplate.learner_id == learner_id,
    )
    result = await session.execute(stmt)
    template = result.scalar_one_or_none()
    
    schedule_data = {"slots": sorted_slots, "timezone": timezone}
    
    if template:
        # Update existing
        template.default_config = {"schedule": schedule_data}
        template.default_timezone = timezone
    else:
        # Create new
        template = LessonPackageTemplate(
            tenant_id=current_tenant.tenant_id,
            learner_id=learner_id,
            name=f"schedule_{learner_id}",
            default_timezone=timezone,
            default_config={"schedule": schedule_data},
        )
        session.add(template)
    
    await session.flush()
    return schedule_data


async def add_schedule_slots(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    learner_id: int,
    days: list[int],
    time_str: str,
    duration: int,
) -> ScheduleData:
    """Add slots for multiple days with the same time.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        learner_id: ID of the learner
        days: List of days (0=Monday, 6=Sunday)
        time_str: Start time in HH:MM format
        duration: Duration in minutes
        
    Returns:
        Updated schedule data
    """
    current = await get_learner_schedule(session, current_tenant, learner_id)
    slots = current["slots"]
    timezone = current["timezone"]
    
    # Add new slots for each day
    for day in days:
        new_slot = {"day": day, "time": time_str, "duration": duration}
        # Check if slot already exists
        exists = any(
            s["day"] == day and s["time"] == time_str
            for s in slots
        )
        if not exists:
            slots.append(new_slot)
    
    return await update_learner_schedule(
        session, current_tenant, learner_id, slots, timezone
    )


async def delete_schedule_slot(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    learner_id: int,
    slot_index: int,
) -> ScheduleData:
    """Delete a single slot by index.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        learner_id: ID of the learner
        slot_index: Index of slot to delete
        
    Returns:
        Updated schedule data
        
    Raises:
        ValueError: If slot index is out of range
    """
    current = await get_learner_schedule(session, current_tenant, learner_id)
    slots = current["slots"]
    timezone = current["timezone"]
    
    if slot_index < 0 or slot_index >= len(slots):
        raise ValueError(f"Invalid slot index: {slot_index}")
    
    slots.pop(slot_index)
    
    return await update_learner_schedule(
        session, current_tenant, learner_id, slots, timezone
    )


def generate_lesson_dates(
    slots: list[ScheduleSlot],
    start_date: date,
    lesson_count: int,
) -> list[dict]:
    """Generate lesson dates based on schedule.
    
    Args:
        slots: Schedule slots
        start_date: First possible lesson date
        lesson_count: Number of lessons to generate
        
    Returns:
        List of dicts with datetime and duration for each lesson
    """
    if not slots or lesson_count <= 0:
        return []
    
    dates = []
    current_date = start_date
    max_iterations = lesson_count * 30  # Safety limit
    iterations = 0
    
    while len(dates) < lesson_count and iterations < max_iterations:
        weekday = current_date.weekday()  # 0 = Monday
        
        # Find slots for this weekday, sorted by time
        day_slots = sorted(
            [s for s in slots if s["day"] == weekday],
            key=lambda s: s["time"]
        )
        
        for slot in day_slots:
            if len(dates) >= lesson_count:
                break
            
            hour, minute = map(int, slot["time"].split(":"))
            lesson_time = datetime.combine(
                current_date,
                time(hour=hour, minute=minute)
            )
            
            # Only add if on or after start_date
            if lesson_time.date() >= start_date:
                dates.append({
                    "datetime": lesson_time.isoformat(),
                    "duration": slot["duration"],
                })
        
        current_date += timedelta(days=1)
        iterations += 1
    
    return dates
