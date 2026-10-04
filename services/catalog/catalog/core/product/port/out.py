import uuid
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from ..aggregate.product import Product, Status


class SortField(StrEnum):
    CREATED_AT_DESC = "createdAt,desc"
    CREATED_AT_ASC = "createdAt,asc"
    PRICE_ASC = "price,asc"
    PRICE_DESC = "price,desc"
    TITLE_ASC = "title,asc"


@dataclass(frozen=True)
class ListFilter:
    status: Status | None = None
    page: int = 1
    size: int = 20
    sort: SortField = SortField.CREATED_AT_DESC


@dataclass(frozen=True)
class ProductPage:
    items: list[Product]
    page: int
    size: int
    total: int


@runtime_checkable
class ProductRepository(Protocol):
    async def by_id(self, product_id: uuid.UUID) -> Product: ...
    async def by_id_for_update(self, product_id: uuid.UUID) -> Product: ...
    async def insert(self, product: Product) -> None: ...
    async def update(self, product: Product) -> None: ...
    async def list_by_seller(self, seller_id: uuid.UUID, list_filter: ListFilter) -> ProductPage: ...


ACTION_PRODUCT_PUBLISHED = "PRODUCT_PUBLISHED"
ACTION_PRODUCT_HIDDEN = "PRODUCT_HIDDEN"
ACTION_PRODUCT_PRICE_CHANGED = "PRODUCT_PRICE_CHANGED"


@dataclass(frozen=True)
class AuditEntry:
    id: uuid.UUID
    actor_id: uuid.UUID
    action: str
    product_id: uuid.UUID
    occurred_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class AuditLogger(Protocol):
    async def record(self, entry: AuditEntry) -> None: ...


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class IdGenerator(Protocol):
    def new_id(self) -> uuid.UUID: ...


@runtime_checkable
class UnitOfWork(Protocol):
    def begin(self) -> AbstractAsyncContextManager[None]: ...


@dataclass(frozen=True)
class PresignedUpload:
    key: str
    url: str
    expires_at: datetime


@runtime_checkable
class ImageStorage(Protocol):
    def presign_upload(self, key: str, content_type: str) -> PresignedUpload: ...
