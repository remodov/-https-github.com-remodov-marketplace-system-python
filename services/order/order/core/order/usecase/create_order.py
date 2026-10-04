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


class KeyTakenByOther(Exception):
    pass


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

    async def handle(self, cmd: CreateOrder) -> CreateOrderResult:
        if not cmd.lines:
            raise invalid("EMPTY_ORDER", "В заказе нет ни одной позиции")
        require_single_seller(cmd.lines)
        existing = await self.keys.find(cmd.idempotency_key, cmd.request_hash)
        if existing is not None:
            return await self.replay(existing)
        order = await self.build(cmd)
        try:
            async with self.uow.begin():
                await self.orders.insert(order)
                claimed = await self.keys.claim(
                    cmd.idempotency_key, cmd.request_hash, order.id, order.created_at
                )
                if not claimed:
                    raise KeyTakenByOther
        except KeyTakenByOther:
            winner = await self.keys.find(cmd.idempotency_key, cmd.request_hash)
            if winner is None:
                raise
            return await self.replay(winner)
        return CreateOrderResult(order, created=True)

    async def replay(self, order_id: uuid.UUID) -> CreateOrderResult:
        return CreateOrderResult(await self.orders.by_id(order_id), created=False)

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
