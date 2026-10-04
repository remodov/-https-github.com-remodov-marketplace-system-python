import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from notification.database import make_engine, make_session_factory, run_migrations
from notification.inbox import Processor

NOW = datetime(2026, 4, 28, 11, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


@pytest.fixture(scope="session")
async def engine():
    engine = make_engine(
        os.environ.get(
            "TEST_DATABASE_URL", "postgresql+asyncpg://catalog:catalog@localhost:5470/notifications_test"
        )
    )
    await run_migrations(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def processor(engine: AsyncEngine) -> Processor:
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE notifications, processed_events"))
    return Processor(make_session_factory(engine), FixedClock())


async def processed_count(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text("SELECT count(*) FROM processed_events")) or 0)


def order_created(customer: uuid.UUID, seller: uuid.UUID) -> bytes:
    return (
        f'{{"orderId":"{uuid.uuid4()}","customerId":"{customer}","sellerId":"{seller}",'
        '"occurredAt":"2026-04-28T11:00:00Z","totalAmount":"4981.00","currency":"RUB","itemsCount":1}'
    ).encode()
