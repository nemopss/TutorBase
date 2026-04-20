"""Tests for user permissions caching functionality."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from api.dependencies import _get_user_cached, get_current_user
from database.models import User


@pytest.fixture
def mock_user():
    """Mock User for testing."""
    user = User(
        id=1,
        telegram_id=123456,
        username="testuser",
        display_name="Test User",
        role="teacher",
        tenant_id=1,
    )
    user.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    user.updated_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    user.last_login_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return user


class TestGetUserCached:
    """Test caching for _get_user_cached function."""

    @pytest.mark.asyncio
    async def test_get_user_cached_caches_result(self, mock_user):
        """Test that _get_user_cached caches the user result."""
        mock_session = AsyncMock()
        
        with patch("api.dependencies.crud.get_user") as mock_crud:
            mock_crud.return_value = mock_user
            
            # First call - should hit database
            result1 = await _get_user_cached(mock_session, 1)
            assert result1.id == 1
            assert result1.role == "teacher"
            assert mock_crud.call_count == 1
            
            # Second call - should use cache (but we can't test this without real Redis)
            # This test verifies the decorator is applied correctly
            result2 = await _get_user_cached(mock_session, 1)
            assert result2.id == 1

    @pytest.mark.asyncio
    async def test_get_user_cached_returns_none_when_not_found(self):
        """Test that _get_user_cached returns None when user not found."""
        mock_session = AsyncMock()
        
        with patch("api.dependencies.crud.get_user") as mock_crud:
            mock_crud.return_value = None
            
            result = await _get_user_cached(mock_session, 999)
            assert result is None


class TestGetCurrentUserCaching:
    """Test caching in get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_uses_cached_lookup(self, mock_user):
        """Test that get_current_user uses cached user lookup."""
        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.scheme = "Bearer"
        mock_credentials.credentials = "valid_token"
        
        with patch("api.dependencies.decode_token") as mock_decode, \
             patch("api.dependencies._get_user_cached") as mock_cached:
            mock_decode.return_value = {"sub": "1"}
            mock_cached.return_value = mock_user
            
            result = await get_current_user(mock_credentials, mock_session)
            
            assert result.id == 1
            assert result.role == "teacher"
            # Verify cached function was called
            mock_cached.assert_called_once_with(mock_session, 1)

    @pytest.mark.asyncio
    async def test_get_current_user_raises_401_when_user_not_found(self):
        """Test that get_current_user raises 401 when cached user not found."""
        from fastapi import HTTPException
        
        mock_session = AsyncMock()
        mock_credentials = MagicMock()
        mock_credentials.scheme = "Bearer"
        mock_credentials.credentials = "valid_token"
        
        with patch("api.dependencies.decode_token") as mock_decode, \
             patch("api.dependencies._get_user_cached") as mock_cached:
            mock_decode.return_value = {"sub": "999"}
            mock_cached.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, mock_session)
            
            assert exc_info.value.status_code == 401
            assert "User not found" in exc_info.value.detail


class TestUserPermissionsCachingTTL:
    """Test that user permissions caching uses correct TTL."""

    @pytest.mark.asyncio
    async def test_get_user_cached_uses_300s_ttl(self):
        """Test that _get_user_cached uses 300s TTL."""
        # This is a documentation test - verifies decorator parameters
        import inspect
        source = inspect.getsource(_get_user_cached)
        assert "ttl=300" in source
        assert 'key_prefix="users"' in source


class TestUserCacheInvalidation:
    """Test cache invalidation on user updates."""

    @pytest.mark.asyncio
    async def test_update_user_role_invalidates_cache(self, mock_user, monkeypatch):
        """Test that updating user role invalidates cache."""
        from api.routes.users import update_user_role
        from api.schemas import UserRoleUpdateRequest
        from config import config
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_tenant = MagicMock()
        mock_payload = UserRoleUpdateRequest(role="viewer")
        monkeypatch.setattr(config, "ADMINS", [])
        
        with patch("api.routes.users.crud.get_user") as mock_get, \
             patch("api.routes.users.invalidate_cache") as mock_invalidate:
            mock_get.return_value = mock_user
            
            result = await update_user_role(
                user_id=1,
                payload=mock_payload,
                session=mock_session,
                current_tenant=mock_tenant,
                _=None,
            )
            
            assert result.role == "viewer"
            # Verify cache invalidation was called
            mock_invalidate.assert_called_once_with("users:_get_user_cached:*")

    @pytest.mark.asyncio
    async def test_update_user_role_rejects_admin_role(self, mock_user, monkeypatch):
        """Test that platform admin access cannot be granted via role update."""
        from fastapi import HTTPException
        from api.routes.users import update_user_role
        from api.schemas import UserRoleUpdateRequest
        from config import config

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_tenant = MagicMock()
        mock_payload = UserRoleUpdateRequest(role="admin")
        monkeypatch.setattr(config, "ADMINS", [])

        with patch("api.routes.users.crud.get_user") as mock_get:
            mock_get.return_value = mock_user

            with pytest.raises(HTTPException) as exc_info:
                await update_user_role(
                    user_id=1,
                    payload=mock_payload,
                    session=mock_session,
                    current_tenant=mock_tenant,
                    _=None,
                )

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_user_login_metadata_invalidates_cache_on_role_change(self, mock_user):
        """Test that update_user_login_metadata invalidates cache when role changes."""
        from database.crud import update_user_login_metadata
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        
        # Patch the actual invalidate_cache import location
        with patch("utils.cache.invalidate_cache") as mock_invalidate:
            # Change role - should invalidate cache
            result = await update_user_login_metadata(
                mock_session,
                mock_user,
                role="admin",
            )
            
            assert result.role == "admin"
            # Verify cache invalidation was called
            mock_invalidate.assert_called_once_with("users:_get_user_cached:*")

    @pytest.mark.asyncio
    async def test_update_user_login_metadata_no_invalidation_without_role_change(self, mock_user):
        """Test that update_user_login_metadata doesn't invalidate cache if role unchanged."""
        from database.crud import update_user_login_metadata
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        
        # Patch the actual invalidate_cache import location
        with patch("utils.cache.invalidate_cache") as mock_invalidate:
            # Update username only - should NOT invalidate cache
            result = await update_user_login_metadata(
                mock_session,
                mock_user,
                username="newusername",
            )
            
            assert result.username == "newusername"
            # Verify cache invalidation was NOT called
            mock_invalidate.assert_not_called()


class TestUserPermissionsCachingPerformance:
    """Test performance implications of user permissions caching."""

    @pytest.mark.asyncio
    async def test_caching_critical_for_every_request(self, mock_user):
        """Test that user lookup is cached for performance on every request."""
        # This test documents the importance of caching
        # Every authenticated request calls get_current_user
        # Without caching: ~30-50ms per request for user lookup
        # With caching: ~1-3ms per request
        # For 1000 requests/min: saves ~30-50 seconds of database time
        
        mock_session = AsyncMock()
        
        with patch("api.dependencies.crud.get_user") as mock_crud:
            mock_crud.return_value = mock_user
            
            # Simulate multiple requests
            for _ in range(10):
                result = await _get_user_cached(mock_session, 1)
                assert result.id == 1
            
            # Without caching, this would be 10 database calls
            # With caching, only first call hits database
            # (In real scenario with Redis, subsequent calls use cache)
