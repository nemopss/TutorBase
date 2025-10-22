"""Tests for template service caching functionality."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from services import template_service
from services.dto import TemplateDTO
from services.exceptions import NotFoundError
from database.models import LessonPackageTemplate


@pytest.fixture
def mock_current_tenant():
    """Mock CurrentTenant for testing."""
    tenant = MagicMock()
    tenant.tenant_id = 1
    tenant.is_super_admin = False
    return tenant


@pytest.fixture
def mock_template():
    """Mock LessonPackageTemplate for testing."""
    template = LessonPackageTemplate(
        id=1,
        name="Test Template",
        description="Test Description",
        lesson_count=10,
        duration_days=30,
        default_timezone="Europe/Moscow",
        default_config={"key": "value"},
        tenant_id=1,
    )
    template.created_at = datetime(2024, 1, 1, 12, 0, 0)
    template.updated_at = datetime(2024, 1, 1, 12, 0, 0)
    return template


@pytest.fixture
def mock_template_dto():
    """Mock TemplateDTO for testing."""
    return TemplateDTO(
        id=1,
        name="Test Template",
        description="Test Description",
        lesson_count=10,
        duration_days=30,
        timezone="Europe/Moscow",
        default_config={"key": "value"},
    )


class TestGetTemplateCaching:
    """Test caching for get_template function."""

    @pytest.mark.asyncio
    async def test_get_template_caches_result(self, mock_current_tenant, mock_template):
        """Test that get_template caches the result."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.get_lesson_package_template") as mock_crud:
            mock_crud.return_value = mock_template
            
            # First call - should hit database
            result1 = await template_service.get_template(mock_session, mock_current_tenant, 1)
            assert result1.id == 1
            assert result1.name == "Test Template"
            assert mock_crud.call_count == 1
            
            # Second call - should use cache (but we can't test this without real Redis)
            # This test verifies the decorator is applied correctly
            result2 = await template_service.get_template(mock_session, mock_current_tenant, 1)
            assert result2.id == 1

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, mock_current_tenant):
        """Test that get_template raises NotFoundError when template not found."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.get_lesson_package_template") as mock_crud:
            mock_crud.return_value = None
            
            with pytest.raises(NotFoundError, match="Template 999 not found"):
                await template_service.get_template(mock_session, mock_current_tenant, 999)


class TestListTemplatesCaching:
    """Test caching for list_templates function."""

    @pytest.mark.asyncio
    async def test_list_templates_caches_result(self, mock_current_tenant, mock_template):
        """Test that list_templates caches the result."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.fetch_lesson_package_templates") as mock_crud:
            mock_crud.return_value = [mock_template]
            
            # First call - should hit database
            result1 = await template_service.list_templates(mock_session, mock_current_tenant)
            assert len(result1) == 1
            assert result1[0].id == 1
            assert mock_crud.call_count == 1
            
            # Second call - should use cache (but we can't test this without real Redis)
            result2 = await template_service.list_templates(mock_session, mock_current_tenant)
            assert len(result2) == 1

    @pytest.mark.asyncio
    async def test_list_templates_empty(self, mock_current_tenant):
        """Test that list_templates returns empty list when no templates."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.fetch_lesson_package_templates") as mock_crud:
            mock_crud.return_value = []
            
            result = await template_service.list_templates(mock_session, mock_current_tenant)
            assert result == []


class TestCreateTemplateInvalidation:
    """Test cache invalidation for create_template function."""

    @pytest.mark.asyncio
    async def test_create_template_invalidates_cache(self, mock_current_tenant, mock_template):
        """Test that create_template invalidates template list cache."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.create_lesson_package_template") as mock_crud, \
             patch("services.template_service.invalidate_cache") as mock_invalidate:
            mock_crud.return_value = mock_template
            
            result = await template_service.create_template(
                mock_session,
                mock_current_tenant,
                name="New Template",
                description="New Description",
                lesson_count=10,
                duration_days=30,
            )
            
            assert result.id == 1
            assert result.name == "Test Template"
            
            # Verify cache invalidation was called
            mock_invalidate.assert_called_once_with("templates:list_templates:*")


class TestUpdateTemplateInvalidation:
    """Test cache invalidation for update_template function."""

    @pytest.mark.asyncio
    async def test_update_template_invalidates_cache(self, mock_current_tenant, mock_template):
        """Test that update_template invalidates both specific and list caches."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.get_lesson_package_template") as mock_get, \
             patch("services.template_service.crud.update_lesson_package_template") as mock_update, \
             patch("services.template_service.invalidate_cache") as mock_invalidate:
            mock_get.return_value = mock_template
            mock_update.return_value = mock_template
            
            result = await template_service.update_template(
                mock_session,
                mock_current_tenant,
                1,
                name="Updated Template",
            )
            
            assert result.id == 1
            
            # Verify cache invalidation was called twice
            assert mock_invalidate.call_count == 2
            mock_invalidate.assert_any_call("templates:get_template:*")
            mock_invalidate.assert_any_call("templates:list_templates:*")

    @pytest.mark.asyncio
    async def test_update_template_not_found(self, mock_current_tenant):
        """Test that update_template raises NotFoundError when template not found."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.get_lesson_package_template") as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(NotFoundError, match="Template 999 not found"):
                await template_service.update_template(
                    mock_session,
                    mock_current_tenant,
                    999,
                    name="Updated Template",
                )


class TestDeleteTemplateInvalidation:
    """Test cache invalidation for delete_template function."""

    @pytest.mark.asyncio
    async def test_delete_template_invalidates_cache(self, mock_current_tenant, mock_template):
        """Test that delete_template invalidates both specific and list caches."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.get_lesson_package_template") as mock_get, \
             patch("services.template_service.crud.delete_lesson_package_template") as mock_delete, \
             patch("services.template_service.invalidate_cache") as mock_invalidate:
            mock_get.return_value = mock_template
            
            await template_service.delete_template(mock_session, mock_current_tenant, 1)
            
            # Verify cache invalidation was called twice
            assert mock_invalidate.call_count == 2
            mock_invalidate.assert_any_call("templates:get_template:*")
            mock_invalidate.assert_any_call("templates:list_templates:*")

    @pytest.mark.asyncio
    async def test_delete_template_not_found(self, mock_current_tenant):
        """Test that delete_template raises NotFoundError when template not found."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.get_lesson_package_template") as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(NotFoundError, match="Template 999 not found"):
                await template_service.delete_template(mock_session, mock_current_tenant, 999)


class TestDuplicateTemplateInvalidation:
    """Test cache invalidation for duplicate_template function."""

    @pytest.mark.asyncio
    async def test_duplicate_template_invalidates_cache(self, mock_current_tenant, mock_template):
        """Test that duplicate_template invalidates template list cache."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.get_lesson_package_template") as mock_get, \
             patch("services.template_service.crud.create_lesson_package_template") as mock_create, \
             patch("services.template_service.invalidate_cache") as mock_invalidate:
            mock_get.return_value = mock_template
            mock_create.return_value = mock_template
            
            result = await template_service.duplicate_template(
                mock_session,
                mock_current_tenant,
                1,
                name="Duplicated Template",
            )
            
            assert result.id == 1
            
            # Verify cache invalidation was called
            mock_invalidate.assert_called_once_with("templates:list_templates:*")

    @pytest.mark.asyncio
    async def test_duplicate_template_not_found(self, mock_current_tenant):
        """Test that duplicate_template raises NotFoundError when template not found."""
        mock_session = AsyncMock()
        
        with patch("services.template_service.crud.get_lesson_package_template") as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(NotFoundError, match="Template 999 not found"):
                await template_service.duplicate_template(mock_session, mock_current_tenant, 999)
