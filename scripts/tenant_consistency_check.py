#!/usr/bin/env python3
"""
Tenant consistency checker for SaaS multi-tenancy.
Validates data integrity and tenant isolation.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from database.models import (
    Tenant, User, Learner, LessonPackage, Lesson, 
    ReminderRule, ReminderInstance, Application
)


async def check_tenant_consistency(database_url: str):
    """Check tenant data consistency and isolation."""
    engine = create_async_engine(database_url)
    
    async with AsyncSession(engine) as session:
        print("🔍 Checking tenant consistency...")
        
        # Check 1: Orphaned records (records with non-existent tenant_id)
        print("\n1. Checking for orphaned records...")
        
        models_to_check = [
            (User, "users"),
            (Learner, "learners"), 
            (LessonPackage, "lesson_packages"),
            (Lesson, "lessons"),
            (ReminderRule, "reminder_rules"),
            (ReminderInstance, "reminder_instances"),
            (Application, "applications"),
        ]
        
        for model, table_name in models_to_check:
            if hasattr(model, 'tenant_id'):
                # Count records with non-null tenant_id that don't have corresponding tenant
                orphaned_query = (
                    select(func.count())
                    .select_from(model)
                    .outerjoin(Tenant, model.tenant_id == Tenant.id)
                    .where(
                        and_(
                            model.tenant_id.is_not(None),
                            Tenant.id.is_(None)
                        )
                    )
                )
                orphaned_count = (await session.execute(orphaned_query)).scalar_one()
                
                if orphaned_count > 0:
                    print(f"  ❌ {table_name}: {orphaned_count} orphaned records")
                else:
                    print(f"  ✅ {table_name}: No orphaned records")
        
        # Check 2: Super-admin users should have tenant_id = NULL
        print("\n2. Checking super-admin tenant assignments...")
        
        admin_with_tenant_query = select(func.count()).select_from(User).where(
            and_(User.role == 'admin', User.tenant_id.is_not(None))
        )
        admin_with_tenant_count = (await session.execute(admin_with_tenant_query)).scalar_one()
        
        if admin_with_tenant_count > 0:
            print(f"  ❌ {admin_with_tenant_count} admin users have tenant_id (should be NULL)")
        else:
            print("  ✅ All admin users have NULL tenant_id")
        
        # Check 3: Regular users should have valid tenant_id
        print("\n3. Checking regular user tenant assignments...")
        
        regular_without_tenant_query = select(func.count()).select_from(User).where(
            and_(User.role != 'admin', User.tenant_id.is_(None))
        )
        regular_without_tenant_count = (await session.execute(regular_without_tenant_query)).scalar_one()
        
        if regular_without_tenant_count > 0:
            print(f"  ❌ {regular_without_tenant_count} regular users have NULL tenant_id")
        else:
            print("  ✅ All regular users have valid tenant_id")
        
        # Check 4: Inactive tenants
        print("\n4. Checking inactive tenants...")
        
        inactive_tenants_query = select(Tenant).where(Tenant.is_active == False)
        inactive_tenants = (await session.execute(inactive_tenants_query)).scalars().all()
        
        for tenant in inactive_tenants:
            # Count active data in inactive tenant
            learner_count = (await session.execute(
                select(func.count()).select_from(Learner).where(Learner.tenant_id == tenant.id)
            )).scalar_one()
            
            if learner_count > 0:
                print(f"  ⚠️  Inactive tenant '{tenant.name}' has {learner_count} learners")
            else:
                print(f"  ✅ Inactive tenant '{tenant.name}' has no active data")
        
        # Check 5: Cross-tenant data relationships
        print("\n5. Checking cross-tenant relationships...")
        
        # Check if lesson packages reference learners from different tenants
        cross_tenant_packages_query = (
            select(func.count())
            .select_from(LessonPackage)
            .join(Learner, LessonPackage.learner_id == Learner.id)
            .where(LessonPackage.tenant_id != Learner.tenant_id)
        )
        cross_tenant_packages = (await session.execute(cross_tenant_packages_query)).scalar_one()
        
        if cross_tenant_packages > 0:
            print(f"  ❌ {cross_tenant_packages} lesson packages reference learners from different tenants")
        else:
            print("  ✅ All lesson packages reference learners from same tenant")
        
        print("\n🎉 Tenant consistency check completed!")
    
    await engine.dispose()


async def main():
    """Main entry point."""
    import os
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    
    try:
        await check_tenant_consistency(database_url)
    except Exception as e:
        print(f"❌ Error during consistency check: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())