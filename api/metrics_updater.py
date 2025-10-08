"""Background task to update Prometheus gauge metrics."""
import asyncio
import logging
from contextlib import asynccontextmanager

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import LessonPackage, Lesson, Learner
from database.db import async_session_maker

logger = logging.getLogger(__name__)


async def update_gauge_metrics():
    """Update gauge metrics from database."""
    try:
        from api.prometheus_metrics import (
            active_packages_gauge,
            scheduled_lessons_gauge,
            learners_gauge
        )
    except ImportError:
        logger.warning("Prometheus metrics not available")
        return

    try:
        async with async_session_maker() as session:
            # Count active packages
            active_packages_result = await session.execute(
                select(func.count()).select_from(LessonPackage).where(LessonPackage.status == 'active')
            )
            active_packages = active_packages_result.scalar_one()
            active_packages_gauge.set(active_packages)

            # Count scheduled lessons
            scheduled_lessons_result = await session.execute(
                select(func.count()).select_from(Lesson).where(Lesson.status == 'scheduled')
            )
            scheduled_lessons = scheduled_lessons_result.scalar_one()
            scheduled_lessons_gauge.set(scheduled_lessons)

            # Count total learners
            learners_result = await session.execute(
                select(func.count()).select_from(Learner)
            )
            learners = learners_result.scalar_one()
            learners_gauge.set(learners)

            logger.debug(
                f"Updated metrics: active_packages={active_packages}, "
                f"scheduled_lessons={scheduled_lessons}, learners={learners}"
            )
    except Exception as e:
        logger.error(f"Error updating gauge metrics: {e}", exc_info=True)


async def metrics_updater_task():
    """Background task that periodically updates gauge metrics."""
    logger.info("Starting metrics updater task")
    while True:
        try:
            await update_gauge_metrics()
            await asyncio.sleep(30)  # Update every 30 seconds
        except asyncio.CancelledError:
            logger.info("Metrics updater task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in metrics updater task: {e}", exc_info=True)
            await asyncio.sleep(60)  # Wait longer on error


@asynccontextmanager
async def lifespan_with_metrics(app):
    """FastAPI lifespan context manager with metrics updater."""
    # Startup
    task = asyncio.create_task(metrics_updater_task())
    logger.info("Metrics updater started")
    
    yield
    
    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Metrics updater stopped")
