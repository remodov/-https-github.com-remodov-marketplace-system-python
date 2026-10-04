import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from .model import Payment, Status
from .repository import Database, find_by_id, find_by_order_id, insert, lock_by_id, update_status

KOPECK = Decimal("0.01")


class Clock(Protocol):
    def now(self) -> datetime: ...


class Service:
    def __init__(self, database: Database, clock: Clock) -> None:
        self.database = database
        self.clock = clock

    async def authorize(self, order_id: uuid.UUID, amount: Decimal, currency: str) -> Payment:
        async with self.database.connection() as connection, connection.transaction():
            existing = await find_by_order_id(connection, order_id)
            if existing is not None:
                return existing
            now = self.clock.now()
            payment = Payment(
                id=uuid.uuid4(),
                order_id=order_id,
                amount=amount.quantize(KOPECK, rounding=ROUND_HALF_UP),
                currency=currency,
                status=Status.AUTHORIZED,
                created_at=now,
                updated_at=now,
            )
            await insert(connection, payment)
            return payment

    async def capture(self, payment_id: uuid.UUID) -> Payment:
        return await self._move_to(payment_id, Status.CAPTURED)

    async def refund(self, payment_id: uuid.UUID) -> Payment:
        async with self.database.connection() as connection, connection.transaction():
            current = await lock_by_id(connection, payment_id)
            if current.status is Status.REFUNDED:
                return current
            moved = current.move_to(Status.REFUNDED, self.clock.now())
            await update_status(connection, moved)
            return moved

    async def by_id(self, payment_id: uuid.UUID) -> Payment:
        async with self.database.connection() as connection:
            return await find_by_id(connection, payment_id)

    async def _move_to(self, payment_id: uuid.UUID, next_status: Status) -> Payment:
        async with self.database.connection() as connection, connection.transaction():
            current = await lock_by_id(connection, payment_id)
            moved = current.move_to(next_status, self.clock.now())
            await update_status(connection, moved)
            return moved
