import logging
import uuid
from collections.abc import Callable
from decimal import Decimal

from ..cache import Cache
from .card import Card, card_of
from .model import Product
from .repository import UnitOfWork

log = logging.getLogger("catalog.cache")


def card_key(product_id: uuid.UUID) -> str:
    return f"product-card:{product_id}"


class ProductService:
    def __init__(self, uow: Callable[[], UnitOfWork], cache: Cache) -> None:
        self.uow = uow
        self.cache = cache

    async def search(self, query: str) -> list[Product]:
        part = query.strip()
        async with self.uow() as store:
            return await store.all() if part == "" else await store.by_title(part)

    async def cheaper_than(self, max_price: Decimal) -> list[Product]:
        async with self.uow() as store:
            return await store.cheaper(max_price)

    async def by_id(self, product_id: uuid.UUID) -> Product:
        async with self.uow() as store:
            return await store.by_id(product_id)

    # TODO шаг 6: карточка из кэша, сброс записи при любом изменении товара
    async def card(self, product_id: uuid.UUID) -> Card:
        return card_of(await self.by_id(product_id))

    async def create(self, title: str, price: Decimal, stock: int) -> Product:
        product = Product.create(title, price, stock)
        async with self.uow() as store:
            await store.add(product)
        return product

    async def change_price(self, product_id: uuid.UUID, new_price: Decimal) -> Product:
        return await self._change(product_id, lambda p: p.change_price(new_price))

    async def apply_discount(self, product_id: uuid.UUID, percent: int) -> Product:
        return await self._change(product_id, lambda p: p.apply_discount(percent))

    async def change_stock(self, product_id: uuid.UUID, delta: int) -> Product:
        return await self._change(product_id, lambda p: p.change_stock(delta))

    async def _change(self, product_id: uuid.UUID, command: Callable[[Product], None]) -> Product:
        async with self.uow() as store:
            product = await store.by_id(product_id)
            command(product)
            await store.save(product)
        return product

    async def reserve(self, product_id: uuid.UUID, quantity: int) -> Product:
        async with self.uow() as store:
            product = await store.by_id_for_update(product_id)
            product.reserve(quantity)
            await store.save(product)
        return product
