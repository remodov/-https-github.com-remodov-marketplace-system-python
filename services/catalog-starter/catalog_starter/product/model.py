import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .errors import OutOfStockError, invalid


MAX_DISCOUNT_PERCENT = 50
KOPECK = Decimal("0.01")


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    _id: Mapped[uuid.UUID] = mapped_column("id", primary_key=True)
    _title: Mapped[str] = mapped_column("title", String(255), nullable=False)
    _price: Mapped[Decimal] = mapped_column("price", Numeric(12, 2), nullable=False)
    _stock: Mapped[int] = mapped_column("stock", Integer, nullable=False)
    _reserved: Mapped[int] = mapped_column("reserved", Integer, nullable=False, default=0)
    _version: Mapped[int] = mapped_column("version", BigInteger, nullable=False, default=0)

    __mapper_args__ = {"version_id_col": _version}

    @classmethod
    def create(cls, title: str, price: Decimal, stock: int) -> "Product":
        if not title.strip():
            raise invalid("название не может быть пустым")
        if price <= 0:
            raise invalid("цена должна быть больше нуля")
        if stock < 0:
            raise invalid("остаток не может быть отрицательным")
        product = cls()
        product._id = uuid.uuid4()
        product._title = title.strip()
        product._price = price
        product._stock = stock
        product._reserved = 0
        product._version = 0
        return product

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def price(self) -> Decimal:
        return self._price

    @property
    def stock(self) -> int:
        return self._stock

    @property
    def reserved(self) -> int:
        return self._reserved

    @property
    def available(self) -> int:
        return self._stock - self._reserved

    @property
    def version(self) -> int:
        return self._version

    def change_price(self, new_price: Decimal) -> None:
        if new_price <= 0:
            raise invalid("цена должна быть больше нуля")
        self._price = new_price

    def apply_discount(self, percent: int) -> None:
        if percent < 1 or percent > MAX_DISCOUNT_PERCENT:
            raise invalid(f"скидка допустима от 1 до {MAX_DISCOUNT_PERCENT} процентов, а не {percent}")
        self._price = (self._price * (100 - percent) / 100).quantize(KOPECK, rounding=ROUND_HALF_UP)

    def change_stock(self, delta: int) -> None:
        if delta == 0:
            raise invalid("изменение остатка не может быть нулевым")
        if self._stock + delta < self._reserved:
            raise OutOfStockError(self._id, -delta, self.available)
        self._stock += delta

    def reserve(self, quantity: int) -> None:
        if quantity <= 0:
            raise invalid("количество должно быть больше нуля")
        if quantity > self.available:
            raise OutOfStockError(self._id, quantity, self.available)
        self._reserved += quantity
