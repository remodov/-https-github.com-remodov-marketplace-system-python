import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from .model import Payment, Status
from .repository import Database, find_by_id, insert, lock_by_id, update_status

KOPECK = Decimal("0.01")


class Clock(Protocol):
    def now(self) -> datetime: ...


class Service:
    def __init__(self, database: Database, clock: Clock) -> None:
        self.database = database
        self.clock = clock

    # TODO шаг 11: заказ платят один раз - повторная авторизация того же заказа
    # возвращает уже созданный платёж, а не списывает деньги второй раз.
    async def authorize(self, order_id: uuid.UUID, amount: Decimal, currency: str) -> Payment:
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
        async with self.database.connection() as connection, connection.transaction():
            await insert(connection, payment)
        return payment

    async def capture(self, payment_id: uuid.UUID) -> Payment:
        return await self._move_to(payment_id, Status.CAPTURED)

    # TODO шаг 11: повторный возврат это не второй возврат и не ошибка - сага может
    # дойти до компенсации дважды, ответ тот же, деньги возвращаются один раз.
    async def refund(self, payment_id: uuid.UUID) -> Payment:
        return await self._move_to(payment_id, Status.REFUNDED)

    async def by_id(self, payment_id: uuid.UUID) -> Payment:
        async with self.database.connection() as connection:
            return await find_by_id(connection, payment_id)

    async def _move_to(self, payment_id: uuid.UUID, next_status: Status) -> Payment:
        async with self.database.connection() as connection, connection.transaction():
            current = await lock_by_id(connection, payment_id)
            moved = current.move_to(next_status, self.clock.now())
            await update_status(connection, moved)
            return moved
