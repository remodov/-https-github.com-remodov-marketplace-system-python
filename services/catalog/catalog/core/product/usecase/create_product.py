from dataclasses import dataclass
from decimal import Decimal

from ...security.principal import Principal
from ..aggregate.product import Product
from ..port.out import Clock, IdGenerator, ProductRepository


@dataclass(frozen=True)
class CreateProduct:
    seller: Principal
    title: str
    description: str
    price: Decimal
    currency: str


class CreateProductHandler:
    def __init__(self, products: ProductRepository, clock: Clock, ids: IdGenerator) -> None:
        self.products = products
        self.clock = clock
        self.ids = ids

    async def handle(self, cmd: CreateProduct) -> Product:
        product = Product.create(
            self.ids.new_id(),
            cmd.seller.sub,
            cmd.title,
            cmd.description,
            cmd.price,
            cmd.currency,
            self.clock.now(),
        )
        await self.products.insert(product)
        return product
