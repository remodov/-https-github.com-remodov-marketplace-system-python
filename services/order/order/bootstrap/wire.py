from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..adapter.inbound.http.auth import Authenticator, JwtAuthenticator, LocalTokens
from ..adapter.outbound.catalog.client import CatalogClient, CatalogSettings
from ..adapter.outbound.kafka.publisher import KafkaPublisher
from ..adapter.outbound.persistence.idempotency_repository import SqlAlchemyIdempotencyKeys
from ..adapter.outbound.persistence.order_repository import SqlAlchemyOrderRepository
from ..adapter.outbound.persistence.outbox_repository import SqlAlchemyOutbox
from ..adapter.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from ..adapter.outbound.system.log_publisher import LogPublisher
from ..adapter.outbound.system.system import SystemClock, UuidGenerator
from ..core.order.port.out import CatalogGateway, Clock, ExternalEventPublisher, IdGenerator
from ..core.order.query.queries import QueryHandler
from ..core.order.usecase.create_order import CreateOrderHandler
from ..core.order.usecase.relay_outbox import OutboxRelay
from .config import Settings

OUTBOX_BATCH_SIZE = 100
OUTBOX_BATCH_TIMEOUT_SECONDS = 10.0
OUTBOX_RELAY_STOP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class Deps:
    clock: Clock | None = None
    ids: IdGenerator | None = None
    authenticator: Authenticator | None = None
    catalog: CatalogGateway | None = None
    publisher: ExternalEventPublisher | None = None


@dataclass(frozen=True)
class Handlers:
    create: CreateOrderHandler
    queries: QueryHandler
    relay: OutboxRelay


def catalog_settings(base_url: str) -> CatalogSettings:
    return CatalogSettings(
        base_url=base_url,
        connect_timeout=0.5,
        request_timeout=1.0,
        attempts=2,
        backoff=0.05,
        breaker_failures=5,
        breaker_open_for=60.0,
    )


def catalog_of(settings: Settings, deps: Deps) -> CatalogGateway:
    return deps.catalog or CatalogClient(catalog_settings(settings.catalog_url))


def publisher_of(settings: Settings, deps: Deps) -> ExternalEventPublisher:
    if deps.publisher is not None:
        return deps.publisher
    if settings.event_publisher == "kafka":
        return KafkaPublisher(settings.kafka_brokers, settings.kafka_topic)
    return LogPublisher()


def wire_handlers(
    sessions: async_sessionmaker, catalog: CatalogGateway, publisher: ExternalEventPublisher, deps: Deps
) -> Handlers:
    clock = deps.clock or SystemClock()
    ids = deps.ids or UuidGenerator()
    orders = SqlAlchemyOrderRepository(sessions)
    keys = SqlAlchemyIdempotencyKeys(sessions)
    outbox = SqlAlchemyOutbox(sessions, ids)
    uow = SqlAlchemyUnitOfWork(sessions)
    return Handlers(
        create=CreateOrderHandler(orders, catalog, keys, outbox, clock, ids, uow),
        queries=QueryHandler(orders),
        relay=OutboxRelay(outbox, publisher, clock, uow, OUTBOX_BATCH_SIZE),
    )


def authenticator_of(settings: Settings, deps: Deps) -> Authenticator:
    if deps.authenticator is not None:
        return deps.authenticator
    if settings.auth_mode == "jwt":
        return JwtAuthenticator(settings.jwks_url, settings.jwt_issuer, settings.jwt_audience)
    return LocalTokens()
