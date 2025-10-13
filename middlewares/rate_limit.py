"""Rate limiting middleware to prevent spam."""
import logging
from typing import Any, Awaitable, Callable, Dict
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message
from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import config


logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting middleware using Redis.
    
    Limits users to a certain number of messages per time window.
    """
    
    def __init__(
        self,
        redis_url: str = None,
        max_requests: int = 20,
        window_seconds: int = 60,
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis_url: Redis connection URL
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.redis_url = redis_url or config.REDIS_URL
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis: Redis | None = None
        
    async def _get_redis(self) -> Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process update with rate limiting."""
        # Only rate limit messages
        if not isinstance(event, Update) or not event.message:
            return await handler(event, data)
            
        message: Message = event.message
        user_id = message.from_user.id if message.from_user else None
        
        if not user_id:
            return await handler(event, data)
        
        try:
            redis = await self._get_redis()
            key = f"rate_limit:{user_id}"
            
            # Get current count
            count = await redis.get(key)
            
            if count is None:
                # First request in window
                await redis.setex(key, self.window_seconds, 1)
                return await handler(event, data)
            
            current_count = int(count)
            
            if current_count >= self.max_requests:
                # Rate limit exceeded
                logger.warning(
                    f"Rate limit exceeded for user {user_id}: {current_count}/{self.max_requests} in {self.window_seconds}s"
                )
                await message.answer(
                    "⚠️ Вы отправляете слишком много сообщений. Пожалуйста, подождите немного."
                )
                return  # Don't process the update
            
            # Increment counter
            await redis.incr(key)
            return await handler(event, data)
            
        except RedisError as exc:
            # If Redis fails, allow request (fail open)
            logger.error(f"Redis error in rate limiter: {exc}")
            return await handler(event, data)
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
