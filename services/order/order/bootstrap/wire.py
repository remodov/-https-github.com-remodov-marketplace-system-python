from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..adapter.inbound.http.auth import Authenticator, JwtAuthenticator, LocalTokens
from ..adapter.outbound.catalog.client import CatalogClient, CatalogSettings
from ..adapter.outbound.persistence.order_repository import SqlAlchemyOrderRepository
from ..adapter.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from ..adapter.outbound.system.system import SystemClock, UuidGenerator
from ..core.order.port.out import CatalogGateway, Clock, IdGenerator
from ..core.order.query.queries import QueryHandler
from ..core.order.usecase.create_order import CreateOrderHandler
from .config import Settings


@dataclass(frozen=True)
class Deps:
    clock: Clock | None = None
    ids: IdGenerator | None = None
    authenticator: Authenticator | None = None
    catalog: CatalogGateway | None = None


@dataclass(frozen=True)
class Handlers:
    create: CreateOrderHandler
    queries: QueryHandler


# TODO шаг 8: подобрать числа - таймауты на соединение и чтение, попытки, пауза,
# порог размыкателя. Худшее время ответа = попытки x (таймаут + пауза); оно должно
# быть меньше, чем терпение браузера покупателя.
def catalog_settings(base_url: str) -> CatalogSettings:
    return CatalogSettings(
        base_url=base_url,
        connect_timeout=0,
        request_timeout=0,
        attempts=1,
        backoff=0,
        breaker_failures=0,
        breaker_open_for=0,
    )


def catalog_of(settings: Settings, deps: Deps) -> CatalogGateway:
    return deps.catalog or CatalogClient(catalog_settings(settings.catalog_url))


def wire_handlers(sessions: async_sessionmaker, catalog: CatalogGateway, deps: Deps) -> Handlers:
    clock = deps.clock or SystemClock()
    ids = deps.ids or UuidGenerator()
    orders = SqlAlchemyOrderRepository(sessions)
    uow = SqlAlchemyUnitOfWork(sessions)
    return Handlers(
        create=CreateOrderHandler(orders, catalog, clock, ids, uow),
        queries=QueryHandler(orders),
    )


def authenticator_of(settings: Settings, deps: Deps) -> Authenticator:
    if deps.authenticator is not None:
        return deps.authenticator
    if settings.auth_mode == "jwt":
        return JwtAuthenticator(settings.jwks_url, settings.jwt_issuer, settings.jwt_audience)
    return LocalTokens()
