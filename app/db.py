from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.db_seed import ensure_bootstrap_seed
from app.models import Base  # registers User, UserGrant, SitePin on metadata

engine = create_async_engine(
    settings.database_url,
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def _ensure_database_exists() -> None:
    url = make_url(settings.database_url)
    db_name = url.database
    if not db_name:
        return

    admin_engine = create_async_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        echo=False,
    )
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if not exists:
                quoted = db_name.replace('"', '""')
                await conn.execute(text(f'CREATE DATABASE "{quoted}"'))
    finally:
        await admin_engine.dispose()


async def init_db_schema() -> None:
    await _ensure_database_exists()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_bootstrap_data()


async def ensure_bootstrap_data() -> None:
    async with async_session_factory() as session:
        await ensure_bootstrap_seed(session)
        await session.commit()
