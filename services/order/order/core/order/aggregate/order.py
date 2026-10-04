import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from ...errors import AppError, conflict, invalid
from .events import (
    Event,
    OrderCancelled,
    OrderConfirmed,
    OrderCreated,
    OrderDelivered,
    OrderEvent,
    OrderExpired,
    OrderPaid,
    OrderShipped,
    snapshots_of,
)

CURRENCY = "RUB"
MAX_QUANTITY = 999
KOPECK = Decimal("0.01")
MIN_CONFIRM_AMOUNT = Decimal(100)
MAX_CANCELLATION_COMMENT = 500


class Status(StrEnum):
    DRAFT = "DRAFT"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    DISPUTE = "DISPUTE"
    REFUNDED = "REFUNDED"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    @classmethod
    def rub(cls, amount: Decimal) -> "Money":
        return cls(amount.quantize(KOPECK, rounding=ROUND_HALF_UP), CURRENCY)

    def add(self, other: "Money") -> "Money":
        return Money(self.amount + other.amount, self.currency)

    def times(self, count: int) -> "Money":
        return Money(self.amount * count, self.currency)


ZERO_RUB = Money.rub(Decimal(0))


@dataclass(frozen=True)
class Address:
    country: str
    city: str
    street: str
    postal_code: str
    pickup_point: str = ""


@dataclass(frozen=True)
class CancellationReason:
    code: str
    comment: str = ""

    @classmethod
    def create(cls, code: str, comment: str) -> "CancellationReason":
        code = code.strip().upper()
        if not code:
            raise invalid("VALIDATION_ERROR", "Нужен код причины отмены")
        if len(comment) > MAX_CANCELLATION_COMMENT:
            raise invalid(
                "VALIDATION_ERROR", f"Комментарий к отмене не длиннее {MAX_CANCELLATION_COMMENT} символов"
            )
        return cls(code, comment)


@dataclass(frozen=True)
class LifecycleState:
    payment_id: uuid.UUID | None = None
    paid_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    closed_at: datetime | None = None


class Item:
    def __init__(
        self,
        id: uuid.UUID,
        product_id: uuid.UUID,
        seller_id: uuid.UUID,
        quantity: int,
        unit_price: Money,
    ) -> None:
        self._id = id
        self._product_id = product_id
        self._seller_id = seller_id
        self._quantity = quantity
        self._unit_price = unit_price

    @classmethod
    def create(
        cls,
        id: uuid.UUID,
        product_id: uuid.UUID,
        seller_id: uuid.UUID,
        quantity: int,
        unit_price: Money,
    ) -> "Item":
        if quantity < 1 or quantity > MAX_QUANTITY:
            raise invalid("VALIDATION_ERROR", f"Количество должно быть от 1 до {MAX_QUANTITY}")
        if unit_price.amount < 0 or unit_price.currency != CURRENCY:
            raise invalid("INVALID_PRICE", "Цена позиции должна быть неотрицательной в рублях")
        return cls(id, product_id, seller_id, quantity, Money.rub(unit_price.amount))

    @classmethod
    def restore(
        cls,
        id: uuid.UUID,
        product_id: uuid.UUID,
        seller_id: uuid.UUID,
        quantity: int,
        unit_price: Money,
    ) -> "Item":
        return cls(id, product_id, seller_id, quantity, unit_price)

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def product_id(self) -> uuid.UUID:
        return self._product_id

    @property
    def seller_id(self) -> uuid.UUID:
        return self._seller_id

    @property
    def quantity(self) -> int:
        return self._quantity

    @property
    def unit_price(self) -> Money:
        return self._unit_price

    @property
    def line_total(self) -> Money:
        return self._unit_price.times(self._quantity)


class Order:
    def __init__(
        self,
        id: uuid.UUID,
        customer_id: uuid.UUID,
        seller_id: uuid.UUID,
        status: Status,
        items: Sequence[Item],
        shipping_fee: Money,
        address: Address,
        created_at: datetime,
        updated_at: datetime,
        lifecycle: LifecycleState,
    ) -> None:
        self._id = id
        self._customer_id = customer_id
        self._seller_id = seller_id
        self._status = status
        self._items = list(items)
        self._shipping_fee = shipping_fee
        self._address = address
        self._created_at = created_at
        self._updated_at = updated_at
        self._lifecycle = lifecycle
        self._events: list[Event] = []

    @classmethod
    def create(
        cls,
        id: uuid.UUID,
        customer_id: uuid.UUID,
        items: Sequence[Item],
        address: Address,
        now: datetime,
    ) -> "Order":
        if not items:
            raise invalid("EMPTY_ORDER", "В заказе нет ни одной позиции")
        seller_id = items[0].seller_id
        seen: set[uuid.UUID] = set()
        for item in items:
            if item.seller_id != seller_id:
                raise invalid(
                    "MULTI_SELLER_NOT_SUPPORTED", "В одном заказе могут быть товары только одного продавца"
                )
            if item.product_id in seen:
                raise invalid("VALIDATION_ERROR", f"Товар {item.product_id} повторяется в позициях заказа")
            seen.add(item.product_id)
        order = cls(
            id, customer_id, seller_id, Status.DRAFT, items, ZERO_RUB, address, now, now, LifecycleState()
        )
        order._register(OrderCreated, now, total=order.total, items=snapshots_of(items))
        return order

    @classmethod
    def restore(
        cls,
        id: uuid.UUID,
        customer_id: uuid.UUID,
        seller_id: uuid.UUID,
        status: Status,
        items: Sequence[Item],
        shipping_fee: Money,
        address: Address,
        created_at: datetime,
        updated_at: datetime,
        lifecycle: LifecycleState,
    ) -> "Order":
        return cls(
            id,
            customer_id,
            seller_id,
            status,
            items,
            shipping_fee,
            address,
            created_at,
            updated_at,
            lifecycle,
        )

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def customer_id(self) -> uuid.UUID:
        return self._customer_id

    @property
    def seller_id(self) -> uuid.UUID:
        return self._seller_id

    @property
    def status(self) -> Status:
        return self._status

    @property
    def items(self) -> list[Item]:
        return list(self._items)

    @property
    def shipping_fee(self) -> Money:
        return self._shipping_fee

    @property
    def shipping_address(self) -> Address:
        return self._address

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def lifecycle(self) -> LifecycleState:
        return self._lifecycle

    @property
    def total(self) -> Money:
        total = ZERO_RUB
        for item in self._items:
            total = total.add(item.line_total)
        return total.add(self._shipping_fee)

    def owned_by(self, customer_id: uuid.UUID) -> bool:
        return self._customer_id == customer_id

    def sold_by(self, seller_id: uuid.UUID) -> bool:
        return self._seller_id == seller_id

    def confirm(self, now: datetime) -> None:
        self._require(Status.DRAFT, "подтвердить")
        if not self._items:
            raise invalid("EMPTY_ORDER", "В заказе нет ни одной позиции")
        total = self.total
        if total.amount < MIN_CONFIRM_AMOUNT:
            raise invalid(
                "ORDER_BELOW_MINIMUM",
                f"Сумма заказа {total.amount:.2f} меньше минимальной {MIN_CONFIRM_AMOUNT:.2f}",
            )
        self._move_to(Status.PENDING_PAYMENT, now)
        self._register(OrderConfirmed, now, total=total)

    def mark_paid(self, payment_id: uuid.UUID, now: datetime) -> None:
        self._require(Status.PENDING_PAYMENT, "оплатить")
        self._move_to(Status.PAID, now)
        self._lifecycle = replace(self._lifecycle, payment_id=payment_id, paid_at=now)
        self._register(OrderPaid, now, payment_id=payment_id, total=self.total)

    def cancel(self, reason: CancellationReason, now: datetime) -> None:
        if self._status not in (Status.DRAFT, Status.PENDING_PAYMENT):
            raise self._invalid_state("отменить без возврата")
        previous = self._status
        self._close(Status.CANCELLED, now)
        self._register(OrderCancelled, now, previous_status=previous, reason=reason, refund_id=None)

    def cancel_after_payment(self, reason: CancellationReason, refund_id: uuid.UUID, now: datetime) -> None:
        self._require(Status.PAID, "отменить с возвратом")
        previous = self._status
        self._close(Status.CANCELLED, now)
        self._register(OrderCancelled, now, previous_status=previous, reason=reason, refund_id=refund_id)

    def expire(self, now: datetime) -> None:
        self._require(Status.PENDING_PAYMENT, "закрыть по таймауту")
        self._close(Status.EXPIRED, now)
        self._register(OrderExpired, now)

    def mark_shipped(self, tracking_number: str, now: datetime) -> None:
        if not tracking_number.strip():
            raise invalid("VALIDATION_ERROR", "Нужен трек-номер отправления")
        self._require(Status.PAID, "передать в доставку")
        self._move_to(Status.SHIPPED, now)
        self._lifecycle = replace(self._lifecycle, shipped_at=now)
        self._register(OrderShipped, now, tracking_number=tracking_number)

    def confirm_delivery(self, now: datetime) -> None:
        self._require(Status.SHIPPED, "подтвердить получение")
        self._move_to(Status.DELIVERED, now)
        self._lifecycle = replace(self._lifecycle, delivered_at=now)
        self._register(OrderDelivered, now)

    def pull_events(self) -> list[Event]:
        events, self._events = self._events, []
        return events

    def _require(self, expected: Status, action: str) -> None:
        if self._status is not expected:
            raise self._invalid_state(action)

    def _invalid_state(self, action: str) -> AppError:
        return conflict("ORDER_INVALID_STATE", f"Заказ в статусе {self._status} нельзя {action}")

    def _move_to(self, next_status: Status, now: datetime) -> None:
        self._status = next_status
        self._updated_at = now

    def _close(self, next_status: Status, now: datetime) -> None:
        self._move_to(next_status, now)
        self._lifecycle = replace(self._lifecycle, closed_at=now)

    def _register(self, event_class: type[OrderEvent], now: datetime, **fields) -> None:
        self._events.append(
            event_class(
                order_id=self._id, customer_id=self._customer_id, seller_id=self._seller_id, at=now, **fields
            )
        )
