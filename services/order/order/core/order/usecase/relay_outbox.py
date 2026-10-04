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

    async def once(self) -> int:
        published = 0
        async with self.uow.begin():
            for message in await self.outbox.unpublished(self.batch_size):
                try:
                    await self.publisher.publish(message)
                except Exception as error:
                    raise PublishFailed(f"публикация {message.event_type} {message.id}: {error}") from error
                await self.outbox.mark_published(message.id, self.clock.now())
                published += 1
        return published

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
