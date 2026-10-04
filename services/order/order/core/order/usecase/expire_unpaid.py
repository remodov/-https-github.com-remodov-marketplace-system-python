import asyncio
import logging
from contextlib import suppress
from datetime import timedelta

from ..port.out import Clock, OrderRepository
from .lifecycle import ExpireOrder, LifecycleHandler

log = logging.getLogger("order.expire")


class ExpireUnpaid:
    def __init__(
        self,
        orders: OrderRepository,
        lifecycle: LifecycleHandler,
        clock: Clock,
        after: timedelta,
        batch_size: int,
    ) -> None:
        self.orders = orders
        self.lifecycle = lifecycle
        self.clock = clock
        self.after = after
        self.batch_size = batch_size
        self.stopping = asyncio.Event()

    async def once(self) -> int:
        expired = 0
        for order_id in await self.orders.pending_payment_before(
            self.clock.now() - self.after, self.batch_size
        ):
            try:
                await self.lifecycle.expire(ExpireOrder(order_id))
            except Exception as error:
                log.warning("заказ %s не закрыт по таймауту: %s", order_id, error)
                continue
            expired += 1
        return expired

    async def run(self, every: float) -> None:
        while not await self.stopped_within(every):
            await self.tick()

    def stop(self) -> None:
        self.stopping.set()

    async def stopped_within(self, seconds: float) -> bool:
        with suppress(TimeoutError):
            await asyncio.wait_for(self.stopping.wait(), seconds)
        return self.stopping.is_set()

    async def tick(self) -> None:
        try:
            expired = await self.once()
        except Exception as error:
            log.warning("проверка неоплаченных заказов: %s", error)
            return
        if expired:
            log.info("неоплаченные заказы закрыты по таймауту: %d", expired)
