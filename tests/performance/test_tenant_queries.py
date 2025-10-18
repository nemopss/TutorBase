"""
Performance tests for multi-tenant queries.
Verifies that tenant-filtered queries use indexes and perform efficiently.
"""
import time
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from tests import factories


@pytest.mark.asyncio
async def test_learner_query_uses_tenant_index(db_session: AsyncSession, current_tenant: CurrentTenant):
    """
    Test that learner queries use the composite (tenant_id, display_name) index.
    Uses EXPLAIN to verify index usage.
    """
    # Create some test data
    for i in range(10):
        await factories.create_learner(
            db_session,
            display_name=f"Learner {i}",
            tenant_id=current_tenant.tenant_id
        )
    await db_session.commit()
    
    # Get the SQL query that would be executed
    # We'll use EXPLAIN to check if indexes are used (PostgreSQL syntax)
    query = text("""
        EXPLAIN (FORMAT TEXT)
        SELECT * FROM learners 
        WHERE tenant_id = :tenant_id 
        ORDER BY display_name
    """)
    
    result = await db_session.execute(query, {"tenant_id": current_tenant.tenant_id})
    explain_output = result.fetchall()
    
    # Convert to string for easier checking
    explain_str = str(explain_output).lower()
    
    # Verify that an index is being used (not a full table scan)
    # PostgreSQL EXPLAIN output should mention "index" for index scans
    # We're looking for "index scan" or "bitmap index scan"
    assert "index" in explain_str, \
        f"Query should use index, but EXPLAIN shows: {explain_output}"


@pytest.mark.asyncio
async def test_lesson_query_uses_tenant_index(db_session: AsyncSession, current_tenant: CurrentTenant):
    """
    Test that lesson queries use the composite (tenant_id, scheduled_at) index.
    """
    # Create test data
    learner = await factories.create_learner(db_session, tenant_id=current_tenant.tenant_id)
    package = await factories.create_package(db_session, learner=learner)
    
    for i in range(10):
        await factories.create_lesson(db_session, package=package)
    await db_session.commit()
    
    # Check EXPLAIN for lessons query (PostgreSQL syntax)
    query = text("""
        EXPLAIN (FORMAT TEXT)
        SELECT * FROM lessons 
        WHERE tenant_id = :tenant_id 
        ORDER BY scheduled_at
    """)
    
    result = await db_session.execute(query, {"tenant_id": current_tenant.tenant_id})
    explain_output = result.fetchall()
    explain_str = str(explain_output).lower()
    
    assert "index" in explain_str, \
        f"Query should use index, but EXPLAIN shows: {explain_output}"


@pytest.mark.asyncio
async def test_query_performance_with_large_dataset(db_session: AsyncSession, current_tenant: CurrentTenant):
    """
    Test query performance with a larger dataset.
    Queries should complete in under 100ms even with 100+ records.
    """
    # Create 100 learners
    for i in range(100):
        await factories.create_learner(
            db_session,
            display_name=f"Learner {i:03d}",
            tenant_id=current_tenant.tenant_id
        )
    await db_session.commit()
    
    # Measure query time
    start_time = time.time()
    learners, total = await crud.fetch_learners_paginated(
        db_session,
        current_tenant,
        limit=50,
        offset=0
    )
    query_time = time.time() - start_time
    
    # Verify results
    assert total == 100
    assert len(learners) == 50
    
    # Performance assertion: should complete in under 100ms
    assert query_time < 0.1, f"Query took {query_time:.3f}s, expected < 0.1s"


@pytest.mark.asyncio
async def test_pagination_performance(db_session: AsyncSession, current_tenant: CurrentTenant):
    """
    Test that pagination with tenant filter performs efficiently.
    """
    # Create test data
    learner = await factories.create_learner(db_session, tenant_id=current_tenant.tenant_id)
    package = await factories.create_package(db_session, learner=learner)
    
    # Create 200 lessons
    for i in range(200):
        await factories.create_lesson(db_session, package=package)
    await db_session.commit()
    
    # Test pagination performance
    start_time = time.time()
    lessons, total = await crud.list_all_lessons(
        db_session,
        current_tenant,
        limit=50,
        offset=100
    )
    query_time = time.time() - start_time
    
    # Verify results
    assert total == 200
    assert len(lessons) == 50
    
    # Performance assertion
    assert query_time < 0.1, f"Paginated query took {query_time:.3f}s, expected < 0.1s"


@pytest.mark.asyncio
async def test_filtered_query_performance(db_session: AsyncSession, current_tenant: CurrentTenant):
    """
    Test performance of filtered queries with tenant context.
    """
    # Create test data with different statuses
    learner = await factories.create_learner(db_session, tenant_id=current_tenant.tenant_id)
    package = await factories.create_package(db_session, learner=learner)
    
    for i in range(50):
        status = "completed" if i % 2 == 0 else "scheduled"
        await factories.create_lesson(db_session, package=package, status=status)
    await db_session.commit()
    
    # Test filtered query performance
    start_time = time.time()
    lessons, total = await crud.list_all_lessons(
        db_session,
        current_tenant,
        status="completed",
        limit=100,
        offset=0
    )
    query_time = time.time() - start_time
    
    # Verify results
    assert total == 25  # Half are completed
    assert len(lessons) == 25
    assert all(lesson.status == "completed" for lesson in lessons)
    
    # Performance assertion
    assert query_time < 0.1, f"Filtered query took {query_time:.3f}s, expected < 0.1s"


@pytest.mark.asyncio
async def test_reminder_instances_query_performance(db_session: AsyncSession, current_tenant: CurrentTenant):
    """
    Test performance of reminder instance queries with composite index.
    """
    # Create test data
    learner = await factories.create_learner(db_session, tenant_id=current_tenant.tenant_id)
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)
    
    # Create 150 reminder instances
    for i in range(150):
        status = ["scheduled", "sent", "delivered"][i % 3]
        await factories.create_reminder_instance(
            db_session,
            rule=rule,
            package=package,
            learner=learner,
            status=status
        )
    await db_session.commit()
    
    # Test query performance
    start_time = time.time()
    instances, total = await crud.fetch_reminder_instances_paginated(
        db_session,
        current_tenant,
        limit=50,
        offset=0,
        status="scheduled"
    )
    query_time = time.time() - start_time
    
    # Verify results
    assert total == 50  # 1/3 are scheduled
    assert len(instances) == 50
    
    # Performance assertion
    assert query_time < 0.1, f"Reminder query took {query_time:.3f}s, expected < 0.1s"


@pytest.mark.asyncio
async def test_cross_tenant_isolation_performance(db_session: AsyncSession, tenant_1, tenant_2):
    """
    Test that tenant isolation doesn't significantly impact performance.
    Queries should be fast even when database contains data from multiple tenants.
    """
    # Create data for tenant 1
    current_tenant_1 = CurrentTenant(tenant_id=tenant_1.id, is_super_admin=False, tenant=tenant_1)
    for i in range(50):
        await factories.create_learner(
            db_session,
            display_name=f"T1 Learner {i}",
            tenant_id=tenant_1.id
        )
    
    # Create data for tenant 2
    for i in range(50):
        await factories.create_learner(
            db_session,
            display_name=f"T2 Learner {i}",
            tenant_id=tenant_2.id
        )
    await db_session.commit()
    
    # Query for tenant 1 only
    start_time = time.time()
    learners, total = await crud.fetch_learners_paginated(
        db_session,
        current_tenant_1,
        limit=50,
        offset=0
    )
    query_time = time.time() - start_time
    
    # Verify isolation
    assert total == 50
    assert all(learner.tenant_id == tenant_1.id for learner in learners)
    
    # Performance should still be good
    assert query_time < 0.1, f"Cross-tenant query took {query_time:.3f}s, expected < 0.1s"


@pytest.mark.asyncio
async def test_super_admin_global_query_performance(db_session: AsyncSession, tenant_1, tenant_2):
    """
    Test that super-admin global queries (seeing all tenants) perform well.
    """
    # Create data for multiple tenants
    created_learners = []
    for i in range(30):
        learner = await factories.create_learner(
            db_session,
            display_name=f"T1 Learner {i}",
            tenant_id=tenant_1.id
        )
        created_learners.append(learner)
    
    for i in range(30):
        learner = await factories.create_learner(
            db_session,
            display_name=f"T2 Learner {i}",
            tenant_id=tenant_2.id
        )
        created_learners.append(learner)
    
    await db_session.commit()
    
    # Super-admin global context (no tenant filter)
    super_admin_context = CurrentTenant(tenant_id=None, is_super_admin=True, tenant=None)
    
    # Query all data using the same test session
    start_time = time.time()
    learners, total = await crud.fetch_learners_paginated(
        db_session,
        super_admin_context,
        limit=100,
        offset=0
    )
    query_time = time.time() - start_time
    
    # Verify results - we created 60 learners, should see all of them
    assert total == 60, f"Expected exactly 60 learners, got {total}"
    assert len(learners) == 60, f"Expected exactly 60 learners in result, got {len(learners)}"
    
    # Verify our created learners are in the results
    learner_names = {l.display_name for l in learners}
    for created in created_learners[:5]:  # Check first 5 as sample
        assert created.display_name in learner_names, f"Created learner '{created.display_name}' not found in results"
    
    # Performance assertion
    assert query_time < 0.15, f"Global query took {query_time:.3f}s, expected < 0.15s"
