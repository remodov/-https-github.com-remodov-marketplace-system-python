import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI

from ..adapter.inbound.http.health import health_router
from ..adapter.inbound.http.orders import order_router
from ..adapter.inbound.http.problem import install_handlers
from ..adapter.inbound.kafka.payment_consumer import PaymentConsumer
from ..adapter.outbound.catalog.client import CatalogClient
from ..adapter.outbound.kafka.publisher import KafkaPublisher
from ..adapter.outbound.payment.client import PaymentClient
from ..adapter.outbound.persistence.engine import (
    DatabasePinger,
    make_engine,
    make_session_factory,
    run_migrations,
)
from ..core.order.usecase.expire_unpaid import ExpireUnpaid
from ..core.order.usecase.relay_outbox import OutboxRelay
from .config import Settings
from .wire import (
    BACKGROUND_STOP_TIMEOUT_SECONDS,
    OUTBOX_BATCH_TIMEOUT_SECONDS,
    OUTBOX_RELAY_STOP_TIMEOUT_SECONDS,
    Deps,
    authenticator_of,
    catalog_of,
    payment_consumer_of,
    payment_of,
    publisher_of,
    wire_handlers,
)

log = logging.getLogger("order")


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    settings = settings or Settings()
    deps = deps or Deps()
    engine = make_engine(settings.database_url)
    catalog = catalog_of(settings, deps)
    payment = payment_of(settings, deps)
    publisher = publisher_of(settings, deps)
    handlers = wire_handlers(
        make_session_factory(engine),
        catalog,
        payment,
        publisher,
        deps,
        timedelta(seconds=settings.expire_unpaid_after_seconds),
    )
    auth = authenticator_of(settings, deps)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_migrations(engine)
        if isinstance(publisher, KafkaPublisher):
            await publisher.start()
        relay_task = start_relay(handlers.relay, settings) if settings.outbox_relay_enabled else None
        expire_task = start_expirer(handlers.expirer, settings) if settings.expire_unpaid_enabled else None
        consumer_task = (
            start_payment_consumer(payment_consumer_of(settings, handlers.lifecycle))
            if settings.payment_consumer_enabled
            else None
        )
        log.info(
            "сервис заказов готов, порт %s, каталог %s, платежи %s, аутентификация %s, издатель %s",
            settings.http_port,
            settings.catalog_url,
            settings.payment_url,
            settings.auth_mode,
            settings.event_publisher,
        )
        yield
        if consumer_task is not None:
            await stop_payment_consumer(consumer_task)
        if expire_task is not None:
            await stop_expirer(handlers.expirer, expire_task)
        if relay_task is not None:
            await stop_relay(handlers.relay, relay_task)
        await engine.dispose()
        if isinstance(publisher, KafkaPublisher):
            await publisher.aclose()
        if isinstance(catalog, CatalogClient):
            await catalog.aclose()
        if isinstance(payment, PaymentClient):
            await payment.aclose()

    app = FastAPI(title="Заказы", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.relay = handlers.relay
    app.state.lifecycle = handlers.lifecycle
    app.state.expirer = handlers.expirer
    install_handlers(app)
    app.include_router(health_router(DatabasePinger(engine)))
    app.include_router(order_router(auth, handlers.create, handlers.lifecycle, handlers.queries))
    return app


def start_relay(relay: OutboxRelay, settings: Settings) -> asyncio.Task:
    return asyncio.create_task(
        relay.run(settings.outbox_relay_interval_seconds, OUTBOX_BATCH_TIMEOUT_SECONDS), name="outbox-relay"
    )


async def stop_relay(relay: OutboxRelay, relay_task: asyncio.Task) -> None:
    relay.stop()
    await asyncio.wait_for(relay_task, OUTBOX_RELAY_STOP_TIMEOUT_SECONDS)


def start_expirer(expirer: ExpireUnpaid, settings: Settings) -> asyncio.Task:
    return asyncio.create_task(expirer.run(settings.expire_interval_seconds), name="expire-unpaid")


async def stop_expirer(expirer: ExpireUnpaid, expire_task: asyncio.Task) -> None:
    expirer.stop()
    await asyncio.wait_for(expire_task, BACKGROUND_STOP_TIMEOUT_SECONDS)


def start_payment_consumer(consumer: PaymentConsumer) -> asyncio.Task:
    return asyncio.create_task(consume_quietly(consumer), name="payment-consumer")


async def stop_payment_consumer(consumer_task: asyncio.Task) -> None:
    consumer_task.cancel()
    async with asyncio.timeout(BACKGROUND_STOP_TIMEOUT_SECONDS):
        await asyncio.gather(consumer_task, return_exceptions=True)


async def consume_quietly(consumer: PaymentConsumer) -> None:
    try:
        await consumer.run()
    except Exception:
        log.exception("потребитель событий платежа остановлен")
