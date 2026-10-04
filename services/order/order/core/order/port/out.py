import uuid
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol, runtime_checkable

from ..aggregate.order import Money, Order


@runtime_checkable
class OrderRepository(Protocol):
    async def insert(self, order: Order) -> None: ...
    async def by_id(self, order_id: uuid.UUID) -> Order: ...


@runtime_checkable
class CatalogGateway(Protocol):
    async def prices(self, product_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Money]: ...


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class IdGenerator(Protocol):
    def new_id(self) -> uuid.UUID: ...


@runtime_checkable
class UnitOfWork(Protocol):
    def begin(self) -> AbstractAsyncContextManager[None]: ...
