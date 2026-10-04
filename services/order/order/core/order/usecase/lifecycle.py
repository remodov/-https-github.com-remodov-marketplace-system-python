import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ...errors import AppError, not_found
from ...security.principal import Principal
from ..aggregate.order import CancellationReason, Order, Status
from ..port.out import Clock, EventOutbox, OrderRepository, PaymentGateway, ProcessedEvents, UnitOfWork


@dataclass(frozen=True)
class ConfirmOrder:
    order_id: uuid.UUID
    requester: Principal


@dataclass(frozen=True)
class PayOrder:
    order_id: uuid.UUID
    payment_id: uuid.UUID


@dataclass(frozen=True)
class CancelOrder:
    order_id: uuid.UUID
    requester: Principal
    reason: CancellationReason


@dataclass(frozen=True)
class ExpireOrder:
    order_id: uuid.UUID


@dataclass(frozen=True)
class MarkShipped:
    order_id: uuid.UUID
    seller: Principal
    tracking_number: str


@dataclass(frozen=True)
class ConfirmDelivery:
    order_id: uuid.UUID
    requester: Principal


class Unchanged(Exception):
    pass


Transition = Callable[[Order], Awaitable[None]]


class LifecycleHandler:
    def __init__(
        self,
        orders: OrderRepository,
        outbox: EventOutbox,
        payment: PaymentGateway,
        processed: ProcessedEvents,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self.orders = orders
        self.outbox = outbox
        self.payment = payment
        self.processed = processed
        self.clock = clock
        self.uow = uow

    async def confirm(self, cmd: ConfirmOrder) -> Order:
        async def apply(order: Order) -> None:
            require_visible(order, cmd.requester)
            order.confirm(self.clock.now())

        return await self._transition(cmd.order_id, apply)

    async def pay(self, cmd: PayOrder) -> Order:
        async def apply(order: Order) -> None:
            if order.status is Status.PAID and order.lifecycle.payment_id == cmd.payment_id:
                raise Unchanged
            order.mark_paid(cmd.payment_id, self.clock.now())

        return await self._transition(cmd.order_id, apply)

    async def pay_from_event(self, event_id: uuid.UUID, event_type: str, cmd: PayOrder) -> bool:
        async with self.uow.begin():
            fresh = await self.processed.mark_processed(event_id, event_type, self.clock.now())
            if not fresh:
                return False
            await self.pay(cmd)
            return True

    async def cancel(self, cmd: CancelOrder) -> Order:
        async def apply(order: Order) -> None:
            require_visible(order, cmd.requester)
            now = self.clock.now()
            if order.status is not Status.PAID:
                order.cancel(cmd.reason, now)
                return
            refund_id = await self.payment.request_refund(
                order.id, order.lifecycle.payment_id, order.total, f"refund-{order.id}"
            )
            order.cancel_after_payment(cmd.reason, refund_id, now)

        return await self._transition(cmd.order_id, apply)

    async def expire(self, cmd: ExpireOrder) -> Order:
        async def apply(order: Order) -> None:
            if order.status is not Status.PENDING_PAYMENT:
                raise Unchanged
            order.expire(self.clock.now())

        return await self._transition(cmd.order_id, apply)

    async def ship(self, cmd: MarkShipped) -> Order:
        async def apply(order: Order) -> None:
            if not order.sold_by(cmd.seller.sub) and not cmd.seller.is_admin:
                raise order_not_found()
            order.mark_shipped(cmd.tracking_number, self.clock.now())

        return await self._transition(cmd.order_id, apply)

    async def deliver(self, cmd: ConfirmDelivery) -> Order:
        async def apply(order: Order) -> None:
            require_visible(order, cmd.requester)
            order.confirm_delivery(self.clock.now())

        return await self._transition(cmd.order_id, apply)

    async def _transition(self, order_id: uuid.UUID, apply: Transition) -> Order:
        async with self.uow.begin():
            order = await self.orders.by_id_for_update(order_id)
            try:
                await apply(order)
            except Unchanged:
                return order
            await self.orders.update(order)
            await self.outbox.append(order.pull_events())
            return order


def require_visible(order: Order, principal: Principal) -> None:
    if not order.owned_by(principal.sub) and not principal.is_admin:
        raise order_not_found()


def order_not_found() -> AppError:
    return not_found("ORDER_NOT_FOUND", "Заказ не найден")
