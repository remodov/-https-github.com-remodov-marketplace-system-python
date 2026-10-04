from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..adapter.inbound.http.auth import Authenticator, JwtAuthenticator, LocalTokens
from ..adapter.outbound.persistence.audit_repository import SqlAlchemyAuditLogger
from ..adapter.outbound.persistence.product_repository import SqlAlchemyProductRepository
from ..adapter.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from ..adapter.outbound.storage.s3_image_storage import S3ImageStorage, StorageSettings
from ..adapter.outbound.system.system import SystemClock, UuidGenerator
from ..core.product.port.out import Clock, IdGenerator, ImageStorage
from ..core.product.query.queries import QueryHandler
from ..core.product.usecase.change_product_price import ChangeProductPriceHandler
from ..core.product.usecase.change_status import ChangeStatusHandler
from ..core.product.usecase.create_product import CreateProductHandler
from ..core.product.usecase.request_image_upload import RequestImageUploadHandler
from .config import Settings


@dataclass(frozen=True)
class Deps:
    clock: Clock | None = None
    ids: IdGenerator | None = None
    authenticator: Authenticator | None = None
    images: ImageStorage | None = None


@dataclass(frozen=True)
class Handlers:
    create: CreateProductHandler
    price: ChangeProductPriceHandler
    transitions: ChangeStatusHandler
    queries: QueryHandler
    uploads: RequestImageUploadHandler


def wire_handlers(sessions: async_sessionmaker, settings: Settings, deps: Deps) -> Handlers:
    clock = deps.clock or SystemClock()
    ids = deps.ids or UuidGenerator()
    images = deps.images or S3ImageStorage(storage_settings_of(settings), clock)
    products = SqlAlchemyProductRepository(sessions)
    audit = SqlAlchemyAuditLogger(sessions)
    uow = SqlAlchemyUnitOfWork(sessions)
    return Handlers(
        create=CreateProductHandler(products, clock, ids),
        price=ChangeProductPriceHandler(products, audit, clock, ids, uow),
        transitions=ChangeStatusHandler(products, audit, clock, ids, uow),
        queries=QueryHandler(products),
        uploads=RequestImageUploadHandler(products, images, ids),
    )


def storage_settings_of(settings: Settings) -> StorageSettings:
    return StorageSettings(
        endpoint=settings.s3_endpoint,
        region=settings.s3_region,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        upload_ttl_seconds=settings.image_upload_url_ttl_seconds,
    )


def authenticator_of(settings: Settings, deps: Deps) -> Authenticator:
    if deps.authenticator is not None:
        return deps.authenticator
    if settings.auth_mode == "jwt":
        return JwtAuthenticator(settings.jwks_url, settings.jwt_issuer, settings.jwt_audience)
    return LocalTokens()
