from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .order import Item, Money


@runtime_checkable
class Event(Protocol):
    @property
    def event_type(self) -> str: ...

    @property
    def aggregate_id(self) -> uuid.UUID: ...

    @property
    def occurred_at(self) -> datetime: ...


@dataclass(frozen=True)
class ItemSnapshot:
    product_id: uuid.UUID
    quantity: int
    unit_price: Money


@dataclass(frozen=True)
class OrderCreated:
    order_id: uuid.UUID
    customer_id: uuid.UUID
    seller_id: uuid.UUID
    total: Money
    items: tuple[ItemSnapshot, ...]
    at: datetime

    @property
    def event_type(self) -> str:
        return "OrderCreated"

    @property
    def aggregate_id(self) -> uuid.UUID:
        return self.order_id

    @property
    def occurred_at(self) -> datetime:
        return self.at


def snapshots_of(items: Sequence[Item]) -> tuple[ItemSnapshot, ...]:
    return tuple(ItemSnapshot(item.product_id, item.quantity, item.unit_price) for item in items)
