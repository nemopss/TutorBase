from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import config

DATABASE_URL = config.build_async_database_url()

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)
