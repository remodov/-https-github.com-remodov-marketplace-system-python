import asyncio
import logging
from contextlib import suppress

from ..port.out import Clock, EventOutbox, ExternalEventPublisher, UnitOfWork

log = logging.getLogger("order.outbox")


class PublishFailed(Exception):
    pass


class OutboxRelay:
    def __init__(
        self,
        outbox: EventOutbox,
        publisher: ExternalEventPublisher,
        clock: Clock,
        uow: UnitOfWork,
        batch_size: int,
    ) -> None:
        self.outbox = outbox
        self.publisher = publisher
        self.clock = clock
        self.uow = uow
        self.batch_size = batch_size
        self.stopping = asyncio.Event()

    # TODO шаг 10: в одной единице работы (uow.begin) взять пачку unpublished, опубликовать
    # каждую через publisher и пометить mark_published временем clock; отказ брокера завернуть
    # в PublishFailed, тогда транзакция откатится и строки останутся. Вернуть число отправленных.
    async def once(self) -> int:
        return 0

    async def run(self, every: float, batch_timeout: float) -> None:
        while not self.stopping.is_set():
            await self.tick(batch_timeout)
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stopping.wait(), every)

    def stop(self) -> None:
        self.stopping.set()

    async def tick(self, batch_timeout: float) -> None:
        try:
            async with asyncio.timeout(batch_timeout):
                published = await self.once()
        except Exception as error:
            log.warning("outbox relay: пачка не отправлена, повторим на следующем круге: %s", error)
            return
        if published:
            log.info("outbox relay: события отправлены: %d", published)
