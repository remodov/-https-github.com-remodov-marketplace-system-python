import uuid
from dataclasses import dataclass
from decimal import Decimal

from ...security.principal import Principal
from ..aggregate.product import Product
from ..port.out import AuditLogger, Clock, IdGenerator, ProductRepository, UnitOfWork


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

    # TODO шаг 7: загрузить товар под блокировкой внутри единицы работы, проверить владение,
    # сменить цену методом агрегата, сохранить, для администратора записать PRODUCT_PRICE_CHANGED в журнал.
    async def handle(self, cmd: ChangeProductPrice) -> Product:
        raise NotImplementedError("TODO шаг 7: смена цены ещё не реализована")
