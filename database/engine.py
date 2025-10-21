"""Database engine and session configuration.

This module sets up the SQLAlchemy async engine and session factory
for database connections throughout the application.

Module-level variables:
    DATABASE_URL: Async database connection URL from config
    engine: SQLAlchemy async engine with connection pooling
    async_session: Session factory for creating database sessions

Configuration:
    - pool_pre_ping: Enables connection health checks before use
    - expire_on_commit: Disabled to allow access to objects after commit
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import config

# Build async database URL from configuration
DATABASE_URL = config.build_async_database_url()

# Create async engine with connection pooling and health checks
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)

# Create session factory with expire_on_commit disabled
# This allows accessing object attributes after commit without refetching
async_session = async_sessionmaker(engine, expire_on_commit=False)
