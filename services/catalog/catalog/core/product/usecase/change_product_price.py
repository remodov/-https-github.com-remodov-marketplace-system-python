import uuid
from dataclasses import dataclass
from decimal import Decimal

from ...errors import invalid
from ...security.principal import Principal
from ..aggregate.product import Product
from ..port.out import (
    ACTION_PRODUCT_PRICE_CHANGED,
    AuditEntry,
    AuditLogger,
    Clock,
    IdGenerator,
    ProductRepository,
    UnitOfWork,
)
from .ownership import require_ownership


@dataclass(frozen=True)
class ChangeProductPrice:
    product_id: uuid.UUID
    requester: Principal
    new_price: Decimal


class ChangeProductPriceHandler:
    def __init__(
        self,
        products: ProductRepository,
        audit: AuditLogger,
        clock: Clock,
        ids: IdGenerator,
        uow: UnitOfWork,
    ) -> None:
        self.products = products
        self.audit = audit
        self.clock = clock
        self.ids = ids
        self.uow = uow

    async def handle(self, cmd: ChangeProductPrice) -> Product:
        if cmd.new_price <= 0:
            raise invalid("INVALID_PRICE", f"Цена должна быть больше нуля, а не {cmd.new_price}")
        async with self.uow.begin():
            product = await self.products.by_id_for_update(cmd.product_id)
            require_ownership(product, cmd.requester)
            previous = product.price
            product.change_price(cmd.new_price, self.clock.now())
            await self.products.update(product)
            if cmd.requester.is_admin:
                await self.audit.record(
                    AuditEntry(
                        id=self.ids.new_id(),
                        actor_id=cmd.requester.sub,
                        action=ACTION_PRODUCT_PRICE_CHANGED,
                        product_id=product.id,
                        occurred_at=self.clock.now(),
                        metadata={
                            "from": str(previous),
                            "to": str(product.price),
                            "ownerSellerId": str(product.seller_id),
                        },
                    )
                )
            return product
