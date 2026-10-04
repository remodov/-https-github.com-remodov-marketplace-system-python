import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from ...errors import invalid, not_found
from ...security.principal import Principal
from ..aggregate.order import Address, Item, Order
from ..port.out import CatalogGateway, Clock, IdempotencyKeys, IdGenerator, OrderRepository, UnitOfWork


@dataclass(frozen=True)
class OrderLine:
    product_id: uuid.UUID
    seller_id: uuid.UUID
    quantity: int


@dataclass(frozen=True)
class CreateOrder:
    customer: Principal
    lines: Sequence[OrderLine]
    shipping_address: Address
    idempotency_key: str
    request_hash: str


@dataclass(frozen=True)
class CreateOrderResult:
    order: Order
    created: bool


class CreateOrderHandler:
    def __init__(
        self,
        orders: OrderRepository,
        catalog: CatalogGateway,
        keys: IdempotencyKeys,
        clock: Clock,
        ids: IdGenerator,
        uow: UnitOfWork,
    ) -> None:
        self.orders = orders
        self.catalog = catalog
        self.keys = keys
        self.clock = clock
        self.ids = ids
        self.uow = uow

    # TODO шаг 9: до работы спросить у keys прежний заказ по ключу и хешу (конфликт
    # хеша уходит наружу как есть), после сборки заказа записать его и занять ключ в
    # одной единице работы; если ключ занять не удалось, вернуть чужой заказ с created=False.
    async def handle(self, cmd: CreateOrder) -> CreateOrderResult:
        if not cmd.lines:
            raise invalid("EMPTY_ORDER", "В заказе нет ни одной позиции")
        require_single_seller(cmd.lines)
        order = await self.build(cmd)
        async with self.uow.begin():
            await self.orders.insert(order)
        return CreateOrderResult(order, created=True)

    async def build(self, cmd: CreateOrder) -> Order:
        prices = await self.catalog.prices(product_ids_of(cmd.lines))
        items = []
        for line in cmd.lines:
            price = prices.get(line.product_id)
            if price is None:
                raise not_found("PRODUCT_NOT_FOUND", f"Товар {line.product_id} не найден в каталоге")
            items.append(
                Item.create(self.ids.new_id(), line.product_id, line.seller_id, line.quantity, price)
            )
        return Order.create(
            self.ids.new_id(), cmd.customer.sub, items, cmd.shipping_address, self.clock.now()
        )


def require_single_seller(lines: Sequence[OrderLine]) -> None:
    for line in lines[1:]:
        if line.seller_id != lines[0].seller_id:
            raise invalid(
                "MULTI_SELLER_NOT_SUPPORTED", "В одном заказе могут быть товары только одного продавца"
            )


def product_ids_of(lines: Sequence[OrderLine]) -> list[uuid.UUID]:
    return list(dict.fromkeys(line.product_id for line in lines))
