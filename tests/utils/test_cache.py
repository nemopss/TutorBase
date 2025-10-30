"""Tests for Redis caching infrastructure."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from utils.cache import (
    init_cache,
    close_cache,
    cached,
    invalidate_cache,
    get_cache_stats,
    _build_cache_key,
    cache_client,
)


@pytest.fixture(autouse=True)
async def cleanup_cache():
    """Cleanup cache state before each test."""
    await close_cache()
    yield
    await close_cache()


@pytest.fixture
async def mock_redis():
    """Mock Redis client for testing."""
    with patch("utils.cache.redis") as mock_redis_module:
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.setex = AsyncMock()
        mock_client.delete = AsyncMock(return_value=0)
        mock_client.scan_iter = AsyncMock(return_value=iter([]))
        mock_client.info = AsyncMock(return_value={})
        mock_client.close = AsyncMock()
        
        mock_redis_module.from_url = AsyncMock(return_value=mock_client)
        
        yield mock_client


class TestCacheInitialization:
    """Test cache initialization and cleanup."""

    async def test_init_cache_success(self, mock_redis):
        """Test successful cache initialization."""
        await init_cache("redis://localhost:6379/0")
        
        mock_redis.ping.assert_called_once()

    async def test_init_cache_failure(self):
        """Test cache initialization failure doesn't crash."""
        with patch("utils.cache.redis.from_url", side_effect=Exception("Connection failed")):
            await init_cache("redis://invalid:6379/0")
            # Should not raise, just log warning

    async def test_close_cache(self, mock_redis):
        """Test cache connection closure."""
        await init_cache("redis://localhost:6379/0")
        await close_cache()
        
        mock_redis.close.assert_called_once()


class TestCacheKeyBuilding:
    """Test cache key generation."""

    def test_build_cache_key_simple(self):
        """Test cache key building with simple arguments."""
        key = _build_cache_key("test", "my_func", (1, 2), {"arg": "value"})
        
        assert key.startswith("test:my_func:")
        assert len(key.split(":")) == 3

    def test_build_cache_key_filters_session(self):
        """Test that session objects are filtered from cache key."""
        mock_session = MagicMock()
        mock_session.__class__.__name__ = "AsyncSession"
        
        key = _build_cache_key("test", "my_func", (mock_session, 123), {})
        
        # Should only include 123, not session
        assert "AsyncSession" not in key


class TestCachedDecorator:
    """Test @cached decorator functionality."""

    async def test_cached_decorator_cache_miss(self, mock_redis):
        """Test cached decorator on cache miss."""
        await init_cache("redis://localhost:6379/0")
        
        mock_redis.get.return_value = None
        
        @cached(ttl=300, key_prefix="test")
        async def test_func(value: int) -> int:
            return value * 2
        
        result = await test_func(5)
        
        assert result == 10
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_called_once()

    async def test_cached_decorator_cache_hit(self, mock_redis):
        """Test cached decorator on cache hit."""
        await init_cache("redis://localhost:6379/0")
        
        cached_data = json.dumps({"result": 42})
        mock_redis.get.return_value = cached_data
        
        call_count = 0
        
        @cached(ttl=300, key_prefix="test")
        async def test_func(value: int) -> dict:
            nonlocal call_count
            call_count += 1
            return {"result": value}
        
        result = await test_func(42)
        
        assert result == {"result": 42}
        assert call_count == 0  # Function not called, used cache
        mock_redis.get.assert_called_once()

    async def test_cached_decorator_no_redis(self):
        """Test cached decorator falls back when Redis unavailable."""
        # Ensure cache is closed
        await close_cache()
        
        @cached(ttl=300, key_prefix="test")
        async def test_func(value: int) -> int:
            return value * 2
        
        result = await test_func(5)
        
        assert result == 10  # Function executed directly


class TestCacheInvalidation:
    """Test cache invalidation."""

    async def test_invalidate_cache_with_matches(self):
        """Test cache invalidation with matching keys."""
        # Patch cache_client directly
        with patch("utils.cache.cache_client") as mock_client:
            # Create async iterator mock
            class AsyncIteratorMock:
                def __init__(self, items):
                    self.items = items
                    self.index = 0
                
                def __aiter__(self):
                    return self
                
                async def __anext__(self):
                    if self.index >= len(self.items):
                        raise StopAsyncIteration
                    item = self.items[self.index]
                    self.index += 1
                    return item
            
            mock_client.scan_iter.return_value = AsyncIteratorMock(["key1", "key2", "key3"])
            mock_client.delete = AsyncMock(return_value=3)
            
            deleted = await invalidate_cache("test:*")
            
            assert deleted == 3
            mock_client.delete.assert_called_once_with("key1", "key2", "key3")

    async def test_invalidate_cache_no_matches(self):
        """Test cache invalidation with no matching keys."""
        # Patch cache_client directly
        with patch("utils.cache.cache_client") as mock_client:
            # Create async iterator mock with no items
            class AsyncIteratorMock:
                def __aiter__(self):
                    return self
                
                async def __anext__(self):
                    raise StopAsyncIteration
            
            mock_client.scan_iter.return_value = AsyncIteratorMock()
            
            deleted = await invalidate_cache("test:*")
            
            assert deleted == 0

    async def test_invalidate_cache_no_redis(self):
        """Test cache invalidation when Redis unavailable."""
        # Don't initialize cache
        
        deleted = await invalidate_cache("test:*")
        
        assert deleted == 0


class TestCacheStats:
    """Test cache statistics."""

    async def test_get_cache_stats_success(self, mock_redis):
        """Test getting cache statistics."""
        await init_cache("redis://localhost:6379/0")
        
        mock_redis.info.side_effect = [
            {"keyspace_hits": 100, "keyspace_misses": 20},
            {"db0": {"keys": 50}},
        ]
        
        stats = await get_cache_stats()
        
        assert stats["available"] is True
        assert stats["total_keys"] == 50
        assert stats["hits"] == 100
        assert stats["misses"] == 20
        assert 0 <= stats["hit_rate"] <= 1

    async def test_get_cache_stats_no_redis(self):
        """Test getting cache statistics when Redis unavailable."""
        # Don't initialize cache
        
        stats = await get_cache_stats()
        
        assert stats["available"] is False
        assert "error" in stats
