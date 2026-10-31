"""Async SQLAlchemy engine, session factory, and FastAPI dependency."""

from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

def _normalise_async_url(url: str) -> str:
    """Accept deployment-style URLs while keeping SQLAlchemy async drivers explicit."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url.removeprefix("sqlite://")
    return url


_db_url = _normalise_async_url(settings.effective_database_url)
_is_sqlite = _db_url.startswith("sqlite")
_engine_kwargs: dict[str, object] = {"echo": False, "pool_pre_ping": not _is_sqlite}
if not _is_sqlite:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10
else:
    _engine_kwargs["connect_args"] = {"timeout": 30, "check_same_thread": False}

engine = create_async_engine(_db_url, **_engine_kwargs)


if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        """SQLite does not enable FK enforcement by default."""
        cursor_factory = getattr(dbapi_connection, "cursor", None)
        if not callable(cursor_factory):
            raise TypeError("SQLite DB-API connection does not expose cursor()")
        cursor = cursor_factory()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping_database() -> None:
    """Raise the underlying database exception when readiness is required."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
