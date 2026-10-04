from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def run_migrations(engine: AsyncEngine) -> None:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_ROOT / "migrations"))

    def upgrade(connection) -> None:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    async with engine.begin() as connection:
        await connection.run_sync(upgrade)


class DatabasePinger:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
