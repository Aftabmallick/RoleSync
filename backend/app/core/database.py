import contextlib
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import settings

# Initialize Async Engine with connection pooling safeguards
engine = create_async_engine(
    settings.get_database_url(),
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    pass


@contextlib.asynccontextmanager
async def get_tenant_session(user_id: str) -> AsyncGenerator[AsyncSession, None]:
    """
    Safely scopes the PostgreSQL tenant ID to an explicit transaction.
    Guarantees isolation across pooled connections and enforces Row-Level Security (RLS).
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # SET LOCAL is strictly scoped to this explicit transaction block
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
                # Defensive reset on connection pool release
                try:
                    await session.execute(text("RESET app.current_user_id"))
                except Exception:
                    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """General un-isolated session for public/unauthenticated transactions (e.g., initial user signup)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
