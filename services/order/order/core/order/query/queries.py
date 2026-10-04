import uuid
from dataclasses import dataclass

from ...errors import not_found
from ...security.principal import Principal
from ..aggregate.order import Order
from ..port.out import OrderRepository


@dataclass(frozen=True)
class GetOrder:
    order_id: uuid.UUID
    requester: Principal


class QueryHandler:
    def __init__(self, orders: OrderRepository) -> None:
        self.orders = orders

    async def get_order(self, query: GetOrder) -> Order:
        order = await self.orders.by_id(query.order_id)
        if not order.owned_by(query.requester.sub) and not query.requester.is_admin:
            raise not_found("ORDER_NOT_FOUND", "Заказ не найден")
        return order
