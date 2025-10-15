import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services import template_service
from services.exceptions import NotFoundError
from tests import factories


@pytest.mark.asyncio
async def test_create_and_get_template(db_session: AsyncSession):
    dto = await template_service.create_template(
        db_session,
        name="Premium Course",
        description="Eight lessons intensive",
        lesson_count=8,
        duration_days=30,
        default_config={"weekly_schedule": [{"day": 1, "time": "09:00"}]},
    )

    assert dto.name == "Premium Course"
    assert dto.lesson_count == 8

    fetched = await template_service.get_template(db_session, dto.id)
    assert fetched.id == dto.id
    assert fetched.default_config["weekly_schedule"][0]["day"] == 1


@pytest.mark.asyncio
async def test_list_templates(db_session: AsyncSession):
    await factories.create_template(db_session, name="Template One")
    await factories.create_template(db_session, name="Template Two")
    await db_session.flush()

    templates = await template_service.list_templates(db_session)
    names = {tpl.name for tpl in templates}
    assert {"Template One", "Template Two"} <= names


@pytest.mark.asyncio
async def test_update_template(db_session: AsyncSession):
    template = await factories.create_template(db_session, name="Initial", lesson_count=4)
    await db_session.flush()

    dto = await template_service.update_template(
        db_session,
        template.id,
        name="Updated",
        lesson_count=5,
        default_config={"weekly_schedule": [{"day": 3, "time": "15:00"}]},
    )

    assert dto.name == "Updated"
    assert dto.lesson_count == 5
    assert dto.default_config["weekly_schedule"][0]["day"] == 3


@pytest.mark.asyncio
async def test_update_template_missing_raises(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await template_service.update_template(db_session, 999, name="X")


@pytest.mark.asyncio
async def test_duplicate_template(db_session: AsyncSession):
    template = await factories.create_template(db_session, name="Original", lesson_count=3)
    await db_session.flush()

    duplicate = await template_service.duplicate_template(db_session, template.id)
    assert duplicate.name.startswith("Original")
    assert duplicate.lesson_count == template.lesson_count


@pytest.mark.asyncio
async def test_duplicate_template_missing_raises(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await template_service.duplicate_template(db_session, 999)


@pytest.mark.asyncio
async def test_delete_template(db_session: AsyncSession):
    template = await factories.create_template(db_session, name="Disposable")
    await db_session.flush()
    await template_service.delete_template(db_session, template.id)
    await db_session.flush()

    with pytest.raises(NotFoundError):
        await template_service.get_template(db_session, template.id)


@pytest.mark.asyncio
async def test_get_template_missing_raises(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await template_service.get_template(db_session, 999)