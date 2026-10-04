import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from ...security.principal import Principal
from ..aggregate.product import Product
from ..port.out import (
    ACTION_PRODUCT_HIDDEN,
    ACTION_PRODUCT_PUBLISHED,
    AuditEntry,
    AuditLogger,
    Clock,
    IdGenerator,
    ProductRepository,
    UnitOfWork,
)
from .ownership import require_ownership


@dataclass(frozen=True)
class PublishProduct:
    product_id: uuid.UUID
    requester: Principal


@dataclass(frozen=True)
class HideProduct:
    product_id: uuid.UUID
    requester: Principal


class ChangeStatusHandler:
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

    async def publish(self, cmd: PublishProduct) -> Product:
        return await self._transition(
            cmd.product_id, cmd.requester, ACTION_PRODUCT_PUBLISHED, Product.publish
        )

    async def hide(self, cmd: HideProduct) -> Product:
        return await self._transition(cmd.product_id, cmd.requester, ACTION_PRODUCT_HIDDEN, Product.hide)

    async def _transition(
        self,
        product_id: uuid.UUID,
        requester: Principal,
        action: str,
        move: Callable[[Product, datetime], None],
    ) -> Product:
        async with self.uow.begin():
            product = await self.products.by_id_for_update(product_id)
            require_ownership(product, requester)
            previous = product.status
            move(product, self.clock.now())
            await self.products.update(product)
            if requester.is_admin:
                await self.audit.record(
                    AuditEntry(
                        id=self.ids.new_id(),
                        actor_id=requester.sub,
                        action=action,
                        product_id=product.id,
                        occurred_at=self.clock.now(),
                        metadata={
                            "from": previous.value,
                            "to": product.status.value,
                            "ownerSellerId": str(product.seller_id),
                        },
                    )
                )
            return product
