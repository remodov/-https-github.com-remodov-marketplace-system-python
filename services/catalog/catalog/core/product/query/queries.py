import uuid
from dataclasses import dataclass, field

from ...errors import not_found
from ...security.principal import Principal
from ..aggregate.product import Product, Status
from ..port.out import ListFilter, ProductPage, ProductRepository


@dataclass(frozen=True)
class GetProduct:
    product_id: uuid.UUID
    requester: Principal | None = None


@dataclass(frozen=True)
class ListMyProducts:
    seller: uuid.UUID
    list_filter: ListFilter = field(default_factory=ListFilter)


@dataclass(frozen=True)
class ListPublished:
    list_filter: ListFilter = field(default_factory=ListFilter)


class QueryHandler:
    def __init__(self, products: ProductRepository) -> None:
        self.products = products

    async def get_product(self, query: GetProduct) -> Product:
        product = await self.products.by_id(query.product_id)
        if product.status is Status.PUBLISHED:
            return product
        if query.requester is not None and (
            query.requester.is_admin or product.owned_by(query.requester.sub)
        ):
            return product
        raise not_found("PRODUCT_NOT_FOUND", "Продукт не найден")

    async def list_my_products(self, query: ListMyProducts) -> ProductPage:
        return await self.products.list_by_seller(query.seller, query.list_filter)

    async def list_published(self, query: ListPublished) -> ProductPage:
        return await self.products.list_published(query.list_filter)
