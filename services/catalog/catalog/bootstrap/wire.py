from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..adapter.inbound.http.auth import Authenticator, JwtAuthenticator, LocalTokens
from ..adapter.outbound.persistence.audit_repository import SqlAlchemyAuditLogger
from ..adapter.outbound.persistence.product_repository import SqlAlchemyProductRepository
from ..adapter.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from ..adapter.outbound.system.system import SystemClock, UuidGenerator
from ..core.product.port.out import Clock, IdGenerator
from ..core.product.query.queries import QueryHandler
from ..core.product.usecase.change_product_price import ChangeProductPriceHandler
from ..core.product.usecase.change_status import ChangeStatusHandler
from ..core.product.usecase.create_product import CreateProductHandler
from .config import Settings


@dataclass(frozen=True)
class Deps:
    clock: Clock | None = None
    ids: IdGenerator | None = None
    authenticator: Authenticator | None = None


@dataclass(frozen=True)
class Handlers:
    create: CreateProductHandler
    price: ChangeProductPriceHandler
    transitions: ChangeStatusHandler
    queries: QueryHandler


def wire_handlers(sessions: async_sessionmaker, deps: Deps) -> Handlers:
    clock = deps.clock or SystemClock()
    ids = deps.ids or UuidGenerator()
    products = SqlAlchemyProductRepository(sessions)
    audit = SqlAlchemyAuditLogger(sessions)
    uow = SqlAlchemyUnitOfWork(sessions)
    return Handlers(
        create=CreateProductHandler(products, clock, ids),
        price=ChangeProductPriceHandler(products, audit, clock, ids, uow),
        transitions=ChangeStatusHandler(products, audit, clock, ids, uow),
        queries=QueryHandler(products),
    )


def authenticator_of(settings: Settings, deps: Deps) -> Authenticator:
    if deps.authenticator is not None:
        return deps.authenticator
    if settings.auth_mode == "jwt":
        return JwtAuthenticator(settings.jwks_url, settings.jwt_issuer, settings.jwt_audience)
    return LocalTokens()
