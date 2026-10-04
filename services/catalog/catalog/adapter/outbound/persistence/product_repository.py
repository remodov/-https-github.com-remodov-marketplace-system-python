import uuid

from sqlalchemy import Row, Select, and_, func, insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....core.errors import AppError, not_found
from ....core.product.aggregate.product import Product, Status
from ....core.product.port.out import ListFilter, ProductPage, SortField
from .tables import products
from .unit_of_work import session_in_scope

ORDER_BY = {
    SortField.CREATED_AT_DESC: (products.c.created_at.desc(), products.c.id),
    SortField.CREATED_AT_ASC: (products.c.created_at.asc(), products.c.id),
    SortField.PRICE_ASC: (products.c.price.asc(), products.c.id),
    SortField.PRICE_DESC: (products.c.price.desc(), products.c.id),
    SortField.TITLE_ASC: (products.c.title.asc(), products.c.id),
}


class SqlAlchemyProductRepository:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def by_id(self, product_id: uuid.UUID) -> Product:
        return await self._one(select(products).where(products.c.id == product_id), product_id)

    async def by_id_for_update(self, product_id: uuid.UUID) -> Product:
        return await self._one(
            select(products).where(products.c.id == product_id).with_for_update(), product_id
        )

    async def insert(self, product: Product) -> None:
        async with session_in_scope(self.sessions) as session:
            await session.execute(
                insert(products).values(
                    id=product.id,
                    title=product.title,
                    description=product.description,
                    price=product.price,
                    currency=product.currency,
                    seller_id=product.seller_id,
                    status=product.status.value,
                    created_at=product.created_at,
                    updated_at=product.updated_at,
                )
            )

    async def update(self, product: Product) -> None:
        async with session_in_scope(self.sessions) as session:
            result = await session.execute(
                update(products)
                .where(products.c.id == product.id)
                .values(
                    title=product.title,
                    description=product.description,
                    price=product.price,
                    status=product.status.value,
                    updated_at=product.updated_at,
                )
            )
        if result.rowcount == 0:
            raise product_not_found(product.id)

    async def list_by_seller(self, seller_id: uuid.UUID, list_filter: ListFilter) -> ProductPage:
        page = max(list_filter.page, 1)
        size = list_filter.size if 1 <= list_filter.size <= 100 else 20
        condition = products.c.seller_id == seller_id
        if list_filter.status is not None:
            condition = and_(condition, products.c.status == list_filter.status.value)
        async with session_in_scope(self.sessions) as session:
            total = await session.scalar(select(func.count()).select_from(products).where(condition))
            rows = await session.execute(
                select(products)
                .where(condition)
                .order_by(*ORDER_BY[list_filter.sort])
                .limit(size)
                .offset((page - 1) * size)
            )
            items = [restore(row) for row in rows]
        return ProductPage(items=items, page=page, size=size, total=int(total or 0))

    async def _one(self, statement: Select, product_id: uuid.UUID) -> Product:
        async with session_in_scope(self.sessions) as session:
            row = (await session.execute(statement)).one_or_none()
        if row is None:
            raise product_not_found(product_id)
        return restore(row)


def restore(row: Row) -> Product:
    return Product.restore(
        id=row.id,
        title=row.title,
        description=row.description or "",
        price=row.price,
        currency=row.currency,
        seller_id=row.seller_id,
        status=Status(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def product_not_found(product_id: uuid.UUID) -> AppError:
    return not_found("PRODUCT_NOT_FOUND", f"Продукт {product_id} не найден")
