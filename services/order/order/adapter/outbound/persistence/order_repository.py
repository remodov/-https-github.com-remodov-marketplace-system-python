import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Row, Select, insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....core.errors import not_found
from ....core.order.aggregate.order import Address, Item, LifecycleState, Money, Order, Status
from .tables import order_items, orders
from .unit_of_work import session_in_scope


class SqlAlchemyOrderRepository:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def insert(self, order: Order) -> None:
        total = order.total
        async with session_in_scope(self.sessions) as session:
            await session.execute(
                insert(orders).values(
                    id=order.id,
                    customer_id=order.customer_id,
                    seller_id=order.seller_id,
                    status=order.status.value,
                    currency=total.currency,
                    total_amount=total.amount,
                    shipping_fee=order.shipping_fee.amount,
                    shipping_address=address_row(order.shipping_address),
                    created_at=order.created_at,
                    updated_at=order.updated_at,
                )
            )
            await session.execute(
                insert(order_items),
                [
                    {
                        "id": item.id,
                        "order_id": order.id,
                        "product_id": item.product_id,
                        "seller_id": item.seller_id,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price.amount,
                    }
                    for item in order.items
                ],
            )

    async def by_id(self, order_id: uuid.UUID) -> Order:
        return await self._select_one(select(orders).where(orders.c.id == order_id))

    async def by_id_for_update(self, order_id: uuid.UUID) -> Order:
        return await self._select_one(select(orders).where(orders.c.id == order_id).with_for_update())

    async def update(self, order: Order) -> None:
        state = order.lifecycle
        async with session_in_scope(self.sessions) as session:
            await session.execute(
                update(orders)
                .where(orders.c.id == order.id)
                .values(
                    status=order.status.value,
                    updated_at=order.updated_at,
                    payment_id=state.payment_id,
                    paid_at=state.paid_at,
                    shipped_at=state.shipped_at,
                    delivered_at=state.delivered_at,
                    closed_at=state.closed_at,
                )
            )

    async def pending_payment_before(self, before: datetime, limit: int) -> list[uuid.UUID]:
        async with session_in_scope(self.sessions) as session:
            rows = (
                await session.execute(
                    select(orders.c.id)
                    .where(orders.c.status == Status.PENDING_PAYMENT.value, orders.c.updated_at < before)
                    .order_by(orders.c.updated_at)
                    .limit(limit)
                )
            ).all()
        return [row.id for row in rows]

    async def _select_one(self, statement: Select) -> Order:
        async with session_in_scope(self.sessions) as session:
            row = (await session.execute(statement)).one_or_none()
            if row is None:
                raise not_found("ORDER_NOT_FOUND", "Заказ не найден")
            item_rows = (
                await session.execute(
                    select(order_items).where(order_items.c.order_id == row.id).order_by(order_items.c.id)
                )
            ).all()
        return restore(row, item_rows)


def address_row(address: Address) -> dict[str, str]:
    return {
        "country": address.country,
        "city": address.city,
        "street": address.street,
        "postalCode": address.postal_code,
        "pickupPoint": address.pickup_point,
    }


def restore(row: Row, item_rows: Sequence[Row]) -> Order:
    stored = row.shipping_address
    return Order.restore(
        id=row.id,
        customer_id=row.customer_id,
        seller_id=row.seller_id,
        status=Status(row.status),
        items=[
            Item.restore(
                id=item.id,
                product_id=item.product_id,
                seller_id=item.seller_id,
                quantity=item.quantity,
                unit_price=Money(item.unit_price, row.currency),
            )
            for item in item_rows
        ],
        shipping_fee=Money(row.shipping_fee, row.currency),
        address=Address(
            country=stored.get("country", ""),
            city=stored.get("city", ""),
            street=stored.get("street", ""),
            postal_code=stored.get("postalCode", ""),
            pickup_point=stored.get("pickupPoint", ""),
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
        lifecycle=LifecycleState(
            payment_id=row.payment_id,
            paid_at=row.paid_at,
            shipped_at=row.shipped_at,
            delivered_at=row.delivered_at,
            closed_at=row.closed_at,
        ),
    )
