import uuid
from collections.abc import Callable
from decimal import Decimal

from ..cache import Cache
from .model import Product
from .repository import UnitOfWork


class ProductService:
    def __init__(self, uow: Callable[[], UnitOfWork], cache: Cache) -> None:
        self.uow = uow
        self.cache = cache

    async def search(self, query: str) -> list[Product]:
        part = query.strip()
        async with self.uow() as store:
            return await store.all() if part == "" else await store.by_title(part)

    # TODO шаг 2: сценарий чтения cheaper_than

    async def by_id(self, product_id: uuid.UUID) -> Product:
        async with self.uow() as store:
            return await store.by_id(product_id)

    async def create(self, title: str, price: Decimal, stock: int) -> Product:
        product = Product.create(title, price, stock)
        async with self.uow() as store:
            await store.add(product)
        return product

    async def reserve(self, product_id: uuid.UUID, quantity: int) -> Product:
        async with self.uow() as store:
            product = await store.by_id(product_id)
            product.reserve(quantity)
            await store.save(product)
        return product
