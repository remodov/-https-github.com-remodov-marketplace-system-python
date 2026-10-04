import uuid
from collections.abc import Sequence

from sqlalchemy import Row, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....core.errors import not_found
from ....core.order.aggregate.order import Address, Item, Money, Order, Status
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
        async with session_in_scope(self.sessions) as session:
            row = (await session.execute(select(orders).where(orders.c.id == order_id))).one_or_none()
            if row is None:
                raise not_found("ORDER_NOT_FOUND", "Заказ не найден")
            item_rows = (
                await session.execute(
                    select(order_items).where(order_items.c.order_id == order_id).order_by(order_items.c.id)
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
    )
