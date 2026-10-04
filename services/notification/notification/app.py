import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from .config import Settings
from .consumer import Consumer
from .database import DatabasePinger, make_engine, make_session_factory, run_migrations
from .httpapi import health_router, install_handlers, notification_router
from .inbox import Processor

log = logging.getLogger("notification")

CONSUMER_STOP_TIMEOUT_SECONDS = 15.0


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)
    processor = Processor(make_session_factory(engine), SystemClock())
    consumer = Consumer(settings.kafka_brokers, settings.kafka_group, settings.kafka_topic, processor)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_migrations(engine)
        consuming = asyncio.create_task(consume_quietly(consumer), name="kafka-consumer")
        log.info(
            "сервис уведомлений готов, порт %s, kafka %s, группа %s",
            settings.http_port,
            settings.kafka_brokers,
            settings.kafka_group,
        )
        yield
        consuming.cancel()
        async with asyncio.timeout(CONSUMER_STOP_TIMEOUT_SECONDS):
            await asyncio.gather(consuming, return_exceptions=True)
        await engine.dispose()

    app = FastAPI(title="Уведомления", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    install_handlers(app)
    app.include_router(health_router(DatabasePinger(engine)))
    app.include_router(notification_router(processor, settings.admin_token))
    return app


async def consume_quietly(consumer: Consumer) -> None:
    try:
        await consumer.run()
    except Exception:
        log.exception("консьюмер остановлен")
