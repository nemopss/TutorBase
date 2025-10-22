"""Query profiling utilities for development and debugging.

This module provides tools for analyzing database query performance,
including EXPLAIN ANALYZE output and slow query logging.

Key components:
    - explain_query: Run EXPLAIN ANALYZE on a query
    - log_slow_queries: Middleware to log queries exceeding threshold
    - QueryProfiler: Context manager for profiling query blocks

Usage:
    # In development mode
    if config.DEV_MODE:
        await explain_query(session, stmt)
    
    # Profile a block of queries
    async with QueryProfiler(session, "create_package"):
        # ... database operations
        pass

Note:
    Query profiling should only be enabled in development mode
    to avoid performance overhead in production.
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from config import config

logger = logging.getLogger(__name__)


async def explain_query(session: AsyncSession, stmt: Select, analyze: bool = True) -> str:
    """Run EXPLAIN (ANALYZE) on a query and return the plan.
    
    Executes EXPLAIN or EXPLAIN ANALYZE on the given query to show
    the query execution plan. Useful for identifying performance issues
    like missing indexes, sequential scans, or inefficient joins.
    
    Args:
        session: Async database session
        stmt: SQLAlchemy select statement to analyze
        analyze: If True, run EXPLAIN ANALYZE (executes query), otherwise just EXPLAIN
        
    Returns:
        Query execution plan as formatted string
        
    Example:
        >>> stmt = select(Lesson).where(Lesson.tenant_id == 1)
        >>> plan = await explain_query(session, stmt)
        >>> print(plan)
        Seq Scan on lessons  (cost=0.00..35.50 rows=10 width=100)
          Filter: (tenant_id = 1)
    """
    if not config.DEV_MODE:
        logger.warning("explain_query called in non-dev mode, skipping")
        return "Query profiling disabled in production"
    
    # Compile the statement to SQL
    compiled = stmt.compile(compile_kwargs={"literal_binds": True})
    sql = str(compiled)
    
    # Build EXPLAIN query
    explain_prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
    explain_sql = f"{explain_prefix} {sql}"
    
    try:
        result = await session.execute(text(explain_sql))
        rows = result.fetchall()
        
        # Format output
        plan_lines = [row[0] for row in rows]
        plan = "\n".join(plan_lines)
        
        logger.debug(f"Query plan:\n{plan}")
        return plan
        
    except Exception as e:
        logger.error(f"Failed to explain query: {e}")
        return f"Error: {e}"


class QueryProfiler:
    """Context manager for profiling database query blocks.
    
    Measures execution time and optionally logs slow queries.
    Useful for identifying performance bottlenecks in service methods.
    
    Attributes:
        session: Database session to profile
        operation_name: Name of operation being profiled
        threshold_ms: Log warning if execution exceeds this (milliseconds)
        start_time: Operation start timestamp
        
    Example:
        async with QueryProfiler(session, "create_package", threshold_ms=100):
            package = await crud.create_lesson_package(...)
            await crud.create_lessons(...)
        # Logs: "create_package completed in 45.2ms"
    """
    
    def __init__(
        self,
        session: AsyncSession,
        operation_name: str,
        threshold_ms: float = 100.0,
    ):
        """Initialize query profiler.
        
        Args:
            session: Async database session
            operation_name: Name for logging (e.g., "create_package")
            threshold_ms: Warn if operation exceeds this duration
        """
        self.session = session
        self.operation_name = operation_name
        self.threshold_ms = threshold_ms
        self.start_time: float = 0.0
    
    async def __aenter__(self) -> 'QueryProfiler':
        """Start profiling."""
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Stop profiling and log results."""
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        if exc_type is not None:
            logger.error(
                f"{self.operation_name} failed after {duration_ms:.1f}ms: {exc_val}"
            )
            return False
        
        if duration_ms > self.threshold_ms:
            logger.warning(
                f"{self.operation_name} completed in {duration_ms:.1f}ms "
                f"(threshold: {self.threshold_ms}ms)"
            )
        else:
            logger.debug(f"{self.operation_name} completed in {duration_ms:.1f}ms")
        
        return False


@asynccontextmanager
async def profile_queries(
    session: AsyncSession,
    operation_name: str,
    threshold_ms: float = 100.0,
) -> AsyncGenerator[QueryProfiler, None]:
    """Async context manager for profiling queries.
    
    Convenience wrapper around QueryProfiler class.
    
    Args:
        session: Async database session
        operation_name: Name for logging
        threshold_ms: Warn if operation exceeds this duration
        
    Yields:
        QueryProfiler instance
        
    Example:
        async with profile_queries(session, "fetch_lessons", threshold_ms=50):
            lessons = await crud.fetch_lessons_for_package(...)
    """
    profiler = QueryProfiler(session, operation_name, threshold_ms)
    async with profiler:
        yield profiler


def log_query_stats(query_count: int, duration_ms: float, operation: str) -> None:
    """Log query statistics for an operation.
    
    Helper function to log query count and duration.
    Useful for tracking N+1 query problems.
    
    Args:
        query_count: Number of queries executed
        duration_ms: Total duration in milliseconds
        operation: Operation name for logging
        
    Example:
        >>> log_query_stats(15, 234.5, "list_packages")
        WARNING - list_packages executed 15 queries in 234.5ms (avg: 15.6ms/query)
    """
    if query_count == 0:
        return
    
    avg_ms = duration_ms / query_count
    
    if query_count > 10:
        logger.warning(
            f"{operation} executed {query_count} queries in {duration_ms:.1f}ms "
            f"(avg: {avg_ms:.1f}ms/query) - possible N+1 problem"
        )
    elif duration_ms > 100:
        logger.warning(
            f"{operation} executed {query_count} queries in {duration_ms:.1f}ms "
            f"(avg: {avg_ms:.1f}ms/query)"
        )
    else:
        logger.debug(
            f"{operation} executed {query_count} queries in {duration_ms:.1f}ms "
            f"(avg: {avg_ms:.1f}ms/query)"
        )


__all__ = [
    'explain_query',
    'QueryProfiler',
    'profile_queries',
    'log_query_stats',
]
