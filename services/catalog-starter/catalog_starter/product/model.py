import uuid
from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .errors import OutOfStockError, invalid


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    _id: Mapped[uuid.UUID] = mapped_column("id", primary_key=True)
    _title: Mapped[str] = mapped_column("title", String(255), nullable=False)
    _price: Mapped[Decimal] = mapped_column("price", Numeric(12, 2), nullable=False)
    _stock: Mapped[int] = mapped_column("stock", Integer, nullable=False)
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
    def version(self) -> int:
        return self._version

    def reserve(self, quantity: int) -> None:
        if quantity <= 0:
            raise invalid("количество должно быть больше нуля")
        if quantity > self._stock:
            raise OutOfStockError(self._id, quantity, self._stock)
        self._stock -= quantity
