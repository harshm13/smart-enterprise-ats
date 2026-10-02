from contextvars import ContextVar
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ── Tenant context (set per-request by TenantMiddleware) ────────────────────
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)

# ── Engine ───────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Declarative base ─────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Request-scoped DB dependency ─────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields a tenant-scoped AsyncSession.
    Sets `app.current_tenant` PostgreSQL session variable so that
    Row-Level Security policies can filter by tenant automatically.
    """
    async with AsyncSessionLocal() as session:
        tenant_id = current_tenant_id.get()
        if tenant_id:
            await session.execute(
                # Use text() to safely set the custom GUC variable
                __import__("sqlalchemy").text(
                    "SET LOCAL app.current_tenant = :tid"
                ),
                {"tid": tenant_id},
            )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Schema initialisation (dev / test only) ──────────────────────────────────
async def init_db() -> None:
    """Create all tables. In production, use Alembic migrations instead."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
