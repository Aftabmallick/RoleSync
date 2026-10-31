import contextlib
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, Uuid, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.config import settings

logger = logging.getLogger("rolesync.database")

# Common portable types supporting both PostgreSQL (JSONB, native UUID) and SQLite
PG_UUID = UUID(as_uuid=True).with_variant(Uuid(as_uuid=True), "sqlite")
PG_JSONB = JSONB().with_variant(JSON, "sqlite")

primary_url = settings.get_database_url()
is_primary_sqlite = primary_url.startswith("sqlite")

# Create primary engine
if is_primary_sqlite:
    _engine = create_async_engine(primary_url, echo=False)
else:
    _engine = create_async_engine(
        primary_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )

_fallback_engine = None
_active_engine = _engine
_is_using_fallback = is_primary_sqlite
_tested_connection = False


class Base(DeclarativeBase):
    pass


async def get_active_engine():
    global _active_engine, _fallback_engine, _is_using_fallback, _tested_connection
    if _is_using_fallback or _tested_connection:
        return _active_engine

    try:
        # Quick pre-flight probe
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        _tested_connection = True
        return _engine
    except Exception as exc:
        logger.info(f"PostgreSQL unreachable ({type(exc).__name__}). Using persistent local SQLite database.")
        if _fallback_engine is None:
            _fallback_engine = create_async_engine("sqlite+aiosqlite:///./rolesync_dev.db", echo=False)
            async with _fallback_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        _active_engine = _fallback_engine
        _is_using_fallback = True
        _tested_connection = True
        return _active_engine


async def init_db() -> None:
    """Creates database tables if they do not already exist on active engine."""
    eng = await get_active_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async session with auto-commit/rollback."""
    eng = await get_active_engine()
    session_factory = async_sessionmaker(
        bind=eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Alias for general un-isolated session."""
    async for s in get_db():
        yield s


@contextlib.asynccontextmanager
async def get_tenant_session(user_id: str) -> AsyncGenerator[AsyncSession, None]:
    """
    Safely scopes the PostgreSQL tenant ID to an explicit transaction.
    Guarantees isolation across pooled connections and enforces Row-Level Security (RLS).
    """
    eng = await get_active_engine()
    session_factory = async_sessionmaker(
        bind=eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    async with session_factory() as session:
        async with session.begin():
            if not _is_using_fallback:
                await session.execute(
                    text("SET LOCAL app.current_user_id = :uid"),
                    {"uid": str(user_id)}
                )
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                if not _is_using_fallback:
                    try:
                        await session.execute(text("RESET app.current_user_id"))
                    except Exception:
                        pass
