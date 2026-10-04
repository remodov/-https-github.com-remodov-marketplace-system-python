import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .errors import ConflictError, NotFoundError
from .model import Product


class ProductStore(Protocol):
    async def all(self) -> list[Product]: ...
    async def by_title(self, part: str) -> list[Product]: ...
    # TODO шаг 2: выборка товаров не дороже max_price
    async def by_id(self, product_id: uuid.UUID) -> Product: ...
    async def by_id_for_update(self, product_id: uuid.UUID) -> Product: ...
    async def add(self, product: Product) -> None: ...
    async def save(self, product: Product) -> None: ...


class SqlAlchemyProductStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def all(self) -> list[Product]:
        rows = await self.session.scalars(select(Product).order_by(Product._title))
        return list(rows)

    async def by_title(self, part: str) -> list[Product]:
        rows = await self.session.scalars(
            select(Product).where(Product._title.ilike(f"%{part}%")).order_by(Product._title)
        )
        return list(rows)

    # TODO шаг 2: запрос с условием по цене и сортировкой на стороне базы

    async def by_id(self, product_id: uuid.UUID) -> Product:
        found = await self.session.get(Product, product_id)
        if found is None:
            raise NotFoundError(product_id)
        return found

    async def by_id_for_update(self, product_id: uuid.UUID) -> Product:
        found = await self.session.scalar(select(Product).where(Product._id == product_id).with_for_update())
        if found is None:
            raise NotFoundError(product_id)
        return found

    async def add(self, product: Product) -> None:
        self.session.add(product)
        await self.session.flush()

    async def save(self, product: Product) -> None:
        try:
            await self.session.flush()
        except StaleDataError as error:
            raise ConflictError() from error


class UnitOfWork:
    """Одна транзакция: открыл, поработал с хранилищем, закоммитил или откатил."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> ProductStore:
        self.session = self.session_factory()
        await self.session.begin()
        return self.store_of(self.session)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self.session is not None
        try:
            if exc_type is None:
                await self.session.commit()
            else:
                await self.session.rollback()
        finally:
            await self.session.close()

    def store_of(self, session: AsyncSession) -> ProductStore:
        return SqlAlchemyProductStore(session)
