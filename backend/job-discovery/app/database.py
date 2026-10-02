"""
SQLAlchemy async engine & session factory.
"""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _connect_args(url: str) -> dict:
    """
    Le « Transaction pooler » de Supabase (port 6543) rend la connexion au
    pool après chaque transaction : une requête préparée par asyncpg n'existe
    plus à la suivante. On désactive alors le cache, et chaque requête porte
    un nom unique. Le « Session pooler » (port 5432) n'a pas ce problème.
    """
    if ":6543/" in url:
        return {
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        }
    return {}


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    connect_args=_connect_args(settings.database_url),
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
