import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from ...errors import AppError, conflict, invalid


class Status(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    HIDDEN = "HIDDEN"


SUPPORTED_CURRENCY = "RUB"
KOPECK = Decimal("0.01")


class Product:
    def __init__(
        self,
        id: uuid.UUID,
        title: str,
        description: str,
        price: Decimal,
        currency: str,
        seller_id: uuid.UUID,
        status: Status,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        self._id = id
        self._title = title
        self._description = description
        self._price = price
        self._currency = currency
        self._seller_id = seller_id
        self._status = status
        self._created_at = created_at
        self._updated_at = updated_at

    @classmethod
    def create(
        cls,
        id: uuid.UUID,
        seller_id: uuid.UUID,
        title: str,
        description: str,
        price: Decimal,
        currency: str,
        now: datetime,
    ) -> "Product":
        title = title.strip()
        if not title:
            raise invalid("VALIDATION_ERROR", "Название не может быть пустым")
        if price <= 0:
            raise invalid("INVALID_PRICE", "Цена должна быть больше нуля")
        if currency != SUPPORTED_CURRENCY:
            raise invalid("INVALID_CURRENCY", "Поддерживается только валюта RUB")
        return cls(
            id, title, description.strip(), to_kopecks(price), currency, seller_id, Status.DRAFT, now, now
        )

    @classmethod
    def restore(
        cls,
        id: uuid.UUID,
        title: str,
        description: str,
        price: Decimal,
        currency: str,
        seller_id: uuid.UUID,
        status: Status,
        created_at: datetime,
        updated_at: datetime,
    ) -> "Product":
        return cls(id, title, description, price, currency, seller_id, status, created_at, updated_at)

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def price(self) -> Decimal:
        return self._price

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def seller_id(self) -> uuid.UUID:
        return self._seller_id

    @property
    def status(self) -> Status:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    def owned_by(self, seller_id: uuid.UUID) -> bool:
        return self._seller_id == seller_id

    # TODO шаг 7: правило BR-P01 - цена больше нуля, округление до копеек, обновить updated_at.
    def change_price(self, new_price: Decimal, now: datetime) -> None:
        raise invalid("INVALID_PRICE", "TODO шаг 7: правило смены цены ещё не реализовано")

    def publish(self, now: datetime) -> None:
        if self._status not in (Status.DRAFT, Status.HIDDEN):
            raise transition_error(self._status, Status.PUBLISHED)
        self._status = Status.PUBLISHED
        self._updated_at = now

    def hide(self, now: datetime) -> None:
        if self._status is not Status.PUBLISHED:
            raise transition_error(self._status, Status.HIDDEN)
        self._status = Status.HIDDEN
        self._updated_at = now


def to_kopecks(price: Decimal) -> Decimal:
    return price.quantize(KOPECK, rounding=ROUND_HALF_UP)


def transition_error(from_status: Status, to_status: Status) -> AppError:
    return conflict("INVALID_STATE_TRANSITION", f"Переход {from_status} -> {to_status} не разрешён")
