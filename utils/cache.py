"""
Redis caching infrastructure for TutorBase.

Provides decorators and utilities for caching function results in Redis
with automatic fallback to database when Redis is unavailable.
"""

import json
import logging
from dataclasses import is_dataclass, asdict
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
from hashlib import md5

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Global cache client instance
cache_client: Optional[redis.Redis] = None

T = TypeVar("T")


async def init_cache(redis_url: str, max_connections: int = 50) -> None:
    """
    Initialize Redis cache client with connection pooling.

    Args:
        redis_url: Redis connection URL (e.g., redis://redis:6379/0)
        max_connections: Maximum number of connections in the pool (default: 50)

    Raises:
        redis.RedisError: If connection fails
    """
    global cache_client
    try:
        cache_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            max_connections=max_connections,
            health_check_interval=30,  # Check connection health every 30s
        )
        # Test connection
        await cache_client.ping()
        logger.info(f"Redis cache initialized successfully: {redis_url} (max_connections={max_connections})")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis cache: {e}. Caching will be disabled.")
        cache_client = None


async def close_cache() -> None:
    """Close Redis cache client connection."""
    global cache_client
    if cache_client:
        await cache_client.close()
        cache_client = None
        logger.info("Redis cache connection closed")


def _build_cache_key(key_prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Build a unique cache key from function name and arguments.

    Args:
        key_prefix: Prefix for the cache key (e.g., "templates", "tenants")
        func_name: Name of the cached function
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Cache key string
    """
    # Extract tenant_id for multi-tenancy isolation
    tenant_id = None
    
    # Filter out session and other non-serializable objects
    filtered_args = []
    for arg in args:
        if hasattr(arg, "__class__"):
            class_name = arg.__class__.__name__
            if class_name == "AsyncSession":
                continue
            elif class_name == "CurrentTenant":
                # Extract tenant_id from CurrentTenant for cache isolation
                tenant_id = getattr(arg, "tenant_id", None)
                continue
        filtered_args.append(str(arg))

    filtered_kwargs = {}
    for k, v in kwargs.items():
        if k == "session":
            continue
        if hasattr(v, "__class__"):
            class_name = v.__class__.__name__
            if class_name == "AsyncSession":
                continue
            elif class_name == "CurrentTenant":
                tenant_id = getattr(v, "tenant_id", None)
                continue
        filtered_kwargs[k] = str(v)

    # Create hash of arguments for consistent key length
    cache_data = {"args": filtered_args, "kwargs": filtered_kwargs}
    if tenant_id is not None:
        cache_data["tenant_id"] = tenant_id
    
    args_str = json.dumps(cache_data, sort_keys=True)
    args_hash = md5(args_str.encode()).hexdigest()[:16]

    return f"{key_prefix}:{func_name}:{args_hash}"


def cached(ttl: int = 300, key_prefix: str = "") -> Callable:
    """
    Decorator for caching function results in Redis.

    Automatically falls back to executing the function if Redis is unavailable.
    Cache keys are built from function name and arguments, including tenant_id
    for multi-tenancy isolation.

    IMPORTANT: Cached values are deserialized as dictionaries/primitives, not
    as the original object types. If you need typed objects, convert them after
    retrieval or use DTOs/Pydantic models that can be reconstructed from dicts.

    Args:
        ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        key_prefix: Prefix for cache keys (e.g., "templates", "tenants")

    Returns:
        Decorated function

    Example:
        @cached(ttl=300, key_prefix="templates")
        async def get_template(session: AsyncSession, template_id: int):
            return await crud.get_template(session, template_id)
    
    Note:
        - Session objects are automatically filtered from cache keys
        - CurrentTenant.tenant_id is included in cache key for isolation
        - Cache misses and errors automatically fall back to function execution
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # If Redis is not available, execute function directly
            if not cache_client:
                logger.debug(f"Cache unavailable, executing {func.__name__} directly")
                return await func(*args, **kwargs)

            # Build cache key
            cache_key = _build_cache_key(key_prefix, func.__name__, args, kwargs)

            try:
                # Try to get from cache
                cached_value = await cache_client.get(cache_key)
                if cached_value:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return json.loads(cached_value)

                logger.debug(f"Cache MISS: {cache_key}")

            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")
                # Fall through to execute function

            # Execute function
            result = await func(*args, **kwargs)

            # Try to cache result
            try:
                # Convert result to JSON-serializable format
                if hasattr(result, "dict"):
                    # Pydantic model
                    cache_value = result.dict()
                elif is_dataclass(result):
                    # Dataclass (including slots=True)
                    cache_value = asdict(result)
                elif hasattr(result, "__dict__"):
                    # SQLAlchemy model
                    cache_value = {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
                elif isinstance(result, (list, tuple)):
                    # List of models
                    cache_value = [
                        item.dict() if hasattr(item, "dict") else
                        asdict(item) if is_dataclass(item) else
                        {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
                        if hasattr(item, "__dict__") else item
                        for item in result
                    ]
                else:
                    cache_value = result

                await cache_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(cache_value, default=str),
                )
                logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")

            except Exception as e:
                logger.warning(f"Cache write error for {cache_key}: {e}")
                # Don't fail if caching fails

            return result

        return wrapper

    return decorator


async def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache entries matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "templates:*", "tenants:*:123")

    Returns:
        Number of keys deleted

    Example:
        # Invalidate all template caches
        await invalidate_cache("templates:*")

        # Invalidate specific template
        await invalidate_cache(f"templates:*:{template_id}")
    """
    if not cache_client:
        logger.debug(f"Cache unavailable, skipping invalidation for pattern: {pattern}")
        return 0

    try:
        keys = []
        async for key in cache_client.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            deleted = await cache_client.delete(*keys)
            logger.info(f"Cache invalidated: {deleted} keys matching '{pattern}'")
            return deleted

        logger.debug(f"No cache keys found matching pattern: {pattern}")
        return 0

    except Exception as e:
        logger.error(f"Cache invalidation error for pattern '{pattern}': {e}")
        return 0


async def get_cache_stats() -> dict[str, Any]:
    """
    Get cache statistics from Redis.

    Returns:
        Dictionary with cache stats (keys, memory, hits, misses, etc.)
    """
    if not cache_client:
        return {"available": False, "error": "Cache client not initialized"}

    try:
        info = await cache_client.info("stats")
        keyspace = await cache_client.info("keyspace")

        return {
            "available": True,
            "total_keys": keyspace.get("db0", {}).get("keys", 0),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": (
                info.get("keyspace_hits", 0) / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
                if info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0) > 0
                else 0
            ),
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {"available": False, "error": str(e)}
