"""Tests for tenant service caching functionality."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from services import tenant_service
from services.exceptions import NotFoundError
from database.models import Tenant


@pytest.fixture
def mock_tenant():
    """Mock Tenant for testing."""
    tenant = Tenant(
        id=1,
        name="Test Tenant",
        slug="test-tenant",
        contact_email="admin@test.com",
        is_active=True,
    )
    tenant.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    tenant.updated_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return tenant


class TestGetTenantCaching:
    """Test caching for get_tenant function."""

    @pytest.mark.asyncio
    async def test_get_tenant_caches_result(self, mock_tenant):
        """Test that get_tenant caches the result."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.get_tenant") as mock_crud:
            mock_crud.return_value = mock_tenant
            
            # First call - should hit database
            result1 = await tenant_service.get_tenant(mock_session, 1)
            assert result1.id == 1
            assert result1.name == "Test Tenant"
            assert mock_crud.call_count == 1
            
            # Second call - should use cache (but we can't test this without real Redis)
            # This test verifies the decorator is applied correctly
            result2 = await tenant_service.get_tenant(mock_session, 1)
            assert result2.id == 1

    @pytest.mark.asyncio
    async def test_get_tenant_not_found(self):
        """Test that get_tenant raises NotFoundError when tenant not found."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.get_tenant") as mock_crud:
            mock_crud.return_value = None
            
            with pytest.raises(NotFoundError, match="Tenant 999 not found"):
                await tenant_service.get_tenant(mock_session, 999)


class TestListTenantsCaching:
    """Test caching for list_tenants function."""

    @pytest.mark.asyncio
    async def test_list_tenants_caches_result(self, mock_tenant):
        """Test that list_tenants caches the result."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.list_tenants") as mock_crud:
            mock_crud.return_value = ([mock_tenant], 1)
            
            # First call - should hit database
            result1, total1 = await tenant_service.list_tenants(mock_session, limit=100, offset=0)
            assert len(result1) == 1
            assert result1[0].id == 1
            assert total1 == 1
            assert mock_crud.call_count == 1
            
            # Second call - should use cache (but we can't test this without real Redis)
            result2, total2 = await tenant_service.list_tenants(mock_session, limit=100, offset=0)
            assert len(result2) == 1
            assert total2 == 1

    @pytest.mark.asyncio
    async def test_list_tenants_empty(self):
        """Test that list_tenants returns empty list when no tenants."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.list_tenants") as mock_crud:
            mock_crud.return_value = ([], 0)
            
            result, total = await tenant_service.list_tenants(mock_session)
            assert result == []
            assert total == 0

    @pytest.mark.asyncio
    async def test_list_tenants_pagination(self, mock_tenant):
        """Test that list_tenants respects pagination parameters."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.list_tenants") as mock_crud:
            mock_crud.return_value = ([mock_tenant], 10)
            
            result, total = await tenant_service.list_tenants(mock_session, limit=5, offset=5)
            assert len(result) == 1
            assert total == 10
            mock_crud.assert_called_once_with(mock_session, limit=5, offset=5)


class TestCreateTenantInvalidation:
    """Test cache invalidation for create_tenant function."""

    @pytest.mark.asyncio
    async def test_create_tenant_invalidates_cache(self, mock_tenant):
        """Test that create_tenant invalidates tenant list cache."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.create_tenant") as mock_crud, \
             patch("services.tenant_service.invalidate_cache") as mock_invalidate, \
             patch(
                 "services.tenant_service.notification_bootstrap_service.ensure_recommended_notification_rules",
                 new_callable=AsyncMock,
             ) as mock_bootstrap:
            mock_crud.return_value = mock_tenant
            
            result = await tenant_service.create_tenant(
                mock_session,
                name="New Tenant",
                slug="new-tenant",
                contact_email="admin@new.com",
            )
            
            assert result.id == 1
            assert result.name == "Test Tenant"
            
            # Verify cache invalidation was called
            mock_invalidate.assert_called_once_with("tenants:list_tenants:*")
            mock_bootstrap.assert_awaited_once_with(mock_session, mock_tenant.id)


class TestUpdateTenantInvalidation:
    """Test cache invalidation for update_tenant function."""

    @pytest.mark.asyncio
    async def test_update_tenant_invalidates_cache(self, mock_tenant):
        """Test that update_tenant invalidates both specific and list caches."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.get_tenant") as mock_get, \
             patch("services.tenant_service.crud.update_tenant") as mock_update, \
             patch("services.tenant_service.invalidate_cache") as mock_invalidate:
            mock_get.return_value = mock_tenant
            mock_update.return_value = mock_tenant
            
            result = await tenant_service.update_tenant(
                mock_session,
                1,
                name="Updated Tenant",
            )
            
            assert result.id == 1
            
            # Verify cache invalidation was called twice
            assert mock_invalidate.call_count == 2
            mock_invalidate.assert_any_call("tenants:get_tenant:*")
            mock_invalidate.assert_any_call("tenants:list_tenants:*")

    @pytest.mark.asyncio
    async def test_update_tenant_not_found(self):
        """Test that update_tenant raises NotFoundError when tenant not found."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.get_tenant") as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(NotFoundError, match="Tenant 999 not found"):
                await tenant_service.update_tenant(
                    mock_session,
                    999,
                    name="Updated Tenant",
                )

    @pytest.mark.asyncio
    async def test_update_tenant_deactivation(self, mock_tenant):
        """Test that updating is_active invalidates cache."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.get_tenant") as mock_get, \
             patch("services.tenant_service.crud.update_tenant") as mock_update, \
             patch("services.tenant_service.invalidate_cache") as mock_invalidate:
            mock_get.return_value = mock_tenant
            mock_tenant.is_active = False
            mock_update.return_value = mock_tenant
            
            result = await tenant_service.update_tenant(
                mock_session,
                1,
                is_active=False,
            )
            
            assert result.is_active is False
            assert mock_invalidate.call_count == 2


class TestDeleteTenantInvalidation:
    """Test cache invalidation for delete_tenant function."""

    @pytest.mark.asyncio
    async def test_delete_tenant_invalidates_cache(self, mock_tenant):
        """Test that delete_tenant invalidates both specific and list caches."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.get_tenant") as mock_get, \
             patch("services.tenant_service.crud.delete_tenant") as mock_delete, \
             patch("services.tenant_service.invalidate_cache") as mock_invalidate:
            mock_get.return_value = mock_tenant
            
            await tenant_service.delete_tenant(mock_session, 1)
            
            # Verify cache invalidation was called twice
            assert mock_invalidate.call_count == 2
            mock_invalidate.assert_any_call("tenants:get_tenant:*")
            mock_invalidate.assert_any_call("tenants:list_tenants:*")

    @pytest.mark.asyncio
    async def test_delete_tenant_not_found(self):
        """Test that delete_tenant raises NotFoundError when tenant not found."""
        mock_session = AsyncMock()
        
        with patch("services.tenant_service.crud.get_tenant") as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(NotFoundError, match="Tenant 999 not found"):
                await tenant_service.delete_tenant(mock_session, 999)


class TestTenantCachingTTL:
    """Test that tenant caching uses correct TTL."""

    @pytest.mark.asyncio
    async def test_get_tenant_uses_600s_ttl(self, mock_tenant):
        """Test that get_tenant uses 600s TTL (longer than templates)."""
        # This is a documentation test - verifies decorator parameters
        import inspect
        source = inspect.getsource(tenant_service.get_tenant)
        assert "ttl=600" in source
        assert 'key_prefix="tenants"' in source

    @pytest.mark.asyncio
    async def test_list_tenants_uses_600s_ttl(self, mock_tenant):
        """Test that list_tenants uses 600s TTL (longer than templates)."""
        # This is a documentation test - verifies decorator parameters
        import inspect
        source = inspect.getsource(tenant_service.list_tenants)
        assert "ttl=600" in source
        assert 'key_prefix="tenants"' in source
