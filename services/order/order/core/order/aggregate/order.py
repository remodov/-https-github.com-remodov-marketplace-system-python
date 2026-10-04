import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from ...errors import invalid

CURRENCY = "RUB"
MAX_QUANTITY = 999
KOPECK = Decimal("0.01")


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
        return cls(id, customer_id, seller_id, Status.DRAFT, items, ZERO_RUB, address, now, now)

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
    ) -> "Order":
        return cls(id, customer_id, seller_id, status, items, shipping_fee, address, created_at, updated_at)

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
    def total(self) -> Money:
        total = ZERO_RUB
        for item in self._items:
            total = total.add(item.line_total)
        return total.add(self._shipping_fee)

    def owned_by(self, customer_id: uuid.UUID) -> bool:
        return self._customer_id == customer_id
