from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import config

engine = create_async_engine(f"sqlite+aiosqlite:///{config.DB_PATH}")
async_session = async_sessionmaker(engine, expire_on_commit=False)
