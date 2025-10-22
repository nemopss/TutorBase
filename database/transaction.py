"""Transaction management utilities for service layer.

This module provides decorators and context managers for handling database
transactions with automatic commit/rollback and retry logic for deadlocks.

Key components:
    - @transactional: Decorator for service methods requiring transactions
    - TransactionContext: Context manager for nested transaction handling
    - retry logic: Automatic retry with exponential backoff for deadlocks

Usage:
    @transactional(max_retries=3, backoff_factor=0.5)
    async def create_package(session: AsyncSession, ...):
        # All operations in one transaction
        # Auto-commit on success, rollback on error
        pass

Design principles:
    - Service methods should be decorated with @transactional
    - CRUD methods should NOT manage transactions (let service layer handle it)
    - Deadlocks are retried automatically with exponential backoff
    - All other exceptions trigger immediate rollback and re-raise
"""
import asyncio
import logging
from functools import wraps
from typing import TypeVar, Callable, Any, ParamSpec

from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


def _is_deadlock_error(error: Exception) -> bool:
    """Check if exception is a deadlock error.
    
    Detects deadlock errors from both PostgreSQL and SQLite.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is a deadlock
    """
    error_msg = str(error).lower()
    return any(keyword in error_msg for keyword in [
        'deadlock',
        'lock timeout',
        'database is locked',
        'could not serialize',
    ])


def _extract_session(args: tuple, kwargs: dict) -> AsyncSession | None:
    """Extract AsyncSession from function arguments.
    
    Looks for session in both positional and keyword arguments.
    Assumes session is either first positional arg or 'session' kwarg.
    
    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        AsyncSession if found, None otherwise
    """
    # Check kwargs first
    session = kwargs.get('session')
    if isinstance(session, AsyncSession):
        return session
    
    # Check first positional arg
    if args and isinstance(args[0], AsyncSession):
        return args[0]
    
    return None


def transactional(
    max_retries: int = 3,
    backoff_factor: float = 0.5,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for transactional service methods.
    
    Automatically commits transaction on success, rolls back on error,
    and retries on deadlock with exponential backoff.
    
    Transaction lifecycle:
        1. Execute decorated function
        2. On success: commit transaction
        3. On deadlock: rollback, wait, retry (up to max_retries)
        4. On other error: rollback, re-raise immediately
    
    Args:
        max_retries: Maximum number of retry attempts for deadlocks (default: 3)
        backoff_factor: Base delay for exponential backoff in seconds (default: 0.5)
        
    Returns:
        Decorated function with transaction management
        
    Raises:
        ValueError: If session not found in function arguments
        Exception: Re-raises any exception after rollback
        
    Example:
        @transactional(max_retries=3, backoff_factor=0.5)
        async def create_package(
            session: AsyncSession,
            current_tenant: CurrentTenant,
            ...
        ) -> PackageDTO:
            # All operations in one transaction
            package = await crud.create_package(...)
            await crud.create_lessons(...)
            # Auto-commit on success
            return package
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Extract session from arguments
            session = _extract_session(args, kwargs)
            if session is None:
                raise ValueError(
                    f"@transactional decorator requires AsyncSession as first argument "
                    f"or 'session' keyword argument in {func.__name__}"
                )
            
            last_error: Exception | None = None
            
            # Retry loop for deadlocks
            for attempt in range(max_retries):
                try:
                    # Execute the decorated function
                    result = await func(*args, **kwargs)
                    
                    # Commit transaction on success
                    await session.commit()
                    
                    # Log retry success if this wasn't first attempt
                    if attempt > 0:
                        logger.info(
                            f"Transaction succeeded after {attempt + 1} attempts in {func.__name__}"
                        )
                    
                    return result
                    
                except (OperationalError, DBAPIError) as e:
                    # Rollback transaction
                    await session.rollback()
                    last_error = e
                    
                    # Check if it's a deadlock error
                    if _is_deadlock_error(e):
                        if attempt < max_retries - 1:
                            # Calculate exponential backoff delay
                            delay = backoff_factor * (2 ** attempt)
                            logger.warning(
                                f"Deadlock detected in {func.__name__}, "
                                f"retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(
                                f"Deadlock in {func.__name__} failed after {max_retries} attempts"
                            )
                    else:
                        # Not a deadlock, don't retry
                        logger.error(f"Database error in {func.__name__}: {e}")
                    
                    raise
                    
                except Exception as e:
                    # Rollback on any other exception
                    await session.rollback()
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                    raise
            
            # Should never reach here, but just in case
            if last_error:
                raise last_error
            raise RuntimeError(f"Transaction failed in {func.__name__} with no error captured")
        
        return wrapper
    return decorator


class TransactionContext:
    """Context manager for explicit transaction handling.
    
    Provides fine-grained control over transaction boundaries when
    decorator approach is not suitable. Useful for complex workflows
    with conditional commits or nested transactions.
    
    Usage:
        async with TransactionContext(session) as tx:
            await crud.create_package(...)
            if condition:
                await tx.commit()
            else:
                await tx.rollback()
    
    Note:
        Prefer @transactional decorator for most use cases.
        Use this only when you need explicit control.
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize transaction context.
        
        Args:
            session: AsyncSession to manage
        """
        self.session = session
        self._committed = False
        self._rolled_back = False
    
    async def __aenter__(self) -> 'TransactionContext':
        """Enter transaction context.
        
        Returns:
            Self for use in with statement
        """
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit transaction context with automatic rollback on exception.
        
        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
            
        Returns:
            False to propagate exceptions
        """
        if exc_type is not None:
            # Exception occurred, rollback if not already done
            if not self._rolled_back and not self._committed:
                await self.session.rollback()
                logger.error(f"Transaction rolled back due to {exc_type.__name__}: {exc_val}")
            return False
        
        # No exception, commit if not already done
        if not self._committed and not self._rolled_back:
            await self.session.commit()
        
        return False
    
    async def commit(self) -> None:
        """Explicitly commit transaction.
        
        Raises:
            RuntimeError: If already committed or rolled back
        """
        if self._committed:
            raise RuntimeError("Transaction already committed")
        if self._rolled_back:
            raise RuntimeError("Cannot commit after rollback")
        
        await self.session.commit()
        self._committed = True
    
    async def rollback(self) -> None:
        """Explicitly rollback transaction.
        
        Raises:
            RuntimeError: If already committed or rolled back
        """
        if self._committed:
            raise RuntimeError("Cannot rollback after commit")
        if self._rolled_back:
            raise RuntimeError("Transaction already rolled back")
        
        await self.session.rollback()
        self._rolled_back = True


__all__ = [
    'transactional',
    'TransactionContext',
]
