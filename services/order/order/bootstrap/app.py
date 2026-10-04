import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..adapter.inbound.http.health import health_router
from ..adapter.inbound.http.orders import order_router
from ..adapter.inbound.http.problem import install_handlers
from ..adapter.outbound.catalog.client import CatalogClient
from ..adapter.outbound.kafka.publisher import KafkaPublisher
from ..adapter.outbound.persistence.engine import (
    DatabasePinger,
    make_engine,
    make_session_factory,
    run_migrations,
)
from ..core.order.usecase.relay_outbox import OutboxRelay
from .config import Settings
from .wire import (
    OUTBOX_BATCH_TIMEOUT_SECONDS,
    OUTBOX_RELAY_STOP_TIMEOUT_SECONDS,
    Deps,
    authenticator_of,
    catalog_of,
    publisher_of,
    wire_handlers,
)

log = logging.getLogger("order")


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    settings = settings or Settings()
    deps = deps or Deps()
    engine = make_engine(settings.database_url)
    catalog = catalog_of(settings, deps)
    publisher = publisher_of(settings, deps)
    handlers = wire_handlers(make_session_factory(engine), catalog, publisher, deps)
    auth = authenticator_of(settings, deps)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_migrations(engine)
        if isinstance(publisher, KafkaPublisher):
            await publisher.start()
        relay_task = start_relay(handlers.relay, settings) if settings.outbox_relay_enabled else None
        log.info(
            "сервис заказов готов, порт %s, каталог %s, аутентификация %s, издатель %s",
            settings.http_port,
            settings.catalog_url,
            settings.auth_mode,
            settings.event_publisher,
        )
        yield
        if relay_task is not None:
            await stop_relay(handlers.relay, relay_task)
        await engine.dispose()
        if isinstance(publisher, KafkaPublisher):
            await publisher.aclose()
        if isinstance(catalog, CatalogClient):
            await catalog.aclose()

    app = FastAPI(title="Заказы", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.relay = handlers.relay
    install_handlers(app)
    app.include_router(health_router(DatabasePinger(engine)))
    app.include_router(order_router(auth, handlers.create, handlers.queries))
    return app


def start_relay(relay: OutboxRelay, settings: Settings) -> asyncio.Task:
    return asyncio.create_task(
        relay.run(settings.outbox_relay_interval_seconds, OUTBOX_BATCH_TIMEOUT_SECONDS), name="outbox-relay"
    )


async def stop_relay(relay: OutboxRelay, relay_task: asyncio.Task) -> None:
    relay.stop()
    await asyncio.wait_for(relay_task, OUTBOX_RELAY_STOP_TIMEOUT_SECONDS)
