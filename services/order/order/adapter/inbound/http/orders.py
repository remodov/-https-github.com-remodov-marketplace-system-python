import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import StringConstraints

from ....core.order.aggregate.order import CancellationReason
from ....core.order.query.queries import GetOrder, QueryHandler
from ....core.order.usecase.create_order import CreateOrder, CreateOrderHandler, OrderLine
from ....core.order.usecase.lifecycle import (
    CancelOrder,
    ConfirmDelivery,
    ConfirmOrder,
    LifecycleHandler,
    MarkShipped,
    PayOrder,
)
from ....core.security.principal import Principal, Role
from .auth import Authenticator, optional_principal, require_roles
from .schemas import (
    CancelOrderRequest,
    CreateOrderRequest,
    OrderResponse,
    PayOrderRequest,
    ShipOrderRequest,
    address_of,
    response_of,
)

IdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    Header(alias="Idempotency-Key"),
]


def order_router(
    auth: Authenticator, create: CreateOrderHandler, lifecycle: LifecycleHandler, queries: QueryHandler
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/orders", tags=["orders"])
    principal_of = optional_principal(auth)
    customer_or_admin = require_roles(principal_of, Role.CUSTOMER, Role.ADMIN)
    seller_or_admin = require_roles(principal_of, Role.SELLER, Role.ADMIN)
    admin_only = require_roles(principal_of, Role.ADMIN)

    @router.post("", status_code=201)
    async def create_order(
        body: CreateOrderRequest,
        idempotency_key: IdempotencyKey,
        response: Response,
        principal: Principal = Depends(customer_or_admin),
    ) -> OrderResponse:
        result = await create.handle(
            CreateOrder(
                customer=principal,
                lines=[
                    OrderLine(product_id=item.product_id, seller_id=item.seller_id, quantity=item.quantity)
                    for item in body.items
                ],
                shipping_address=address_of(body.shipping_address),
                idempotency_key=idempotency_key,
                request_hash=request_hash(body),
            )
        )
        if not result.created:
            response.status_code = 200
            return response_of(result.order)
        response.headers["Location"] = f"/api/v1/orders/{result.order.id}"
        return response_of(result.order)

    @router.get("/{order_id}")
    async def get_order(
        order_id: uuid.UUID,
        principal: Principal = Depends(customer_or_admin),
    ) -> OrderResponse:
        order = await queries.get_order(GetOrder(order_id=order_id, requester=principal))
        return response_of(order)

    @router.post("/{order_id}/confirm")
    async def confirm_order(
        order_id: uuid.UUID,
        principal: Principal = Depends(customer_or_admin),
    ) -> OrderResponse:
        return response_of(await lifecycle.confirm(ConfirmOrder(order_id=order_id, requester=principal)))

    @router.post("/{order_id}/cancel")
    async def cancel_order(
        order_id: uuid.UUID,
        body: CancelOrderRequest,
        principal: Principal = Depends(customer_or_admin),
    ) -> OrderResponse:
        reason = CancellationReason.create(body.reason_code, body.comment)
        return response_of(
            await lifecycle.cancel(CancelOrder(order_id=order_id, requester=principal, reason=reason))
        )

    @router.post("/{order_id}/ship")
    async def ship_order(
        order_id: uuid.UUID,
        body: ShipOrderRequest,
        principal: Principal = Depends(seller_or_admin),
    ) -> OrderResponse:
        return response_of(
            await lifecycle.ship(
                MarkShipped(order_id=order_id, seller=principal, tracking_number=body.tracking_number)
            )
        )

    @router.post("/{order_id}/deliver")
    async def confirm_delivery(
        order_id: uuid.UUID,
        principal: Principal = Depends(customer_or_admin),
    ) -> OrderResponse:
        return response_of(await lifecycle.deliver(ConfirmDelivery(order_id=order_id, requester=principal)))

    @router.post("/{order_id}/pay")
    async def pay_order(
        order_id: uuid.UUID,
        body: PayOrderRequest,
        principal: Principal = Depends(admin_only),
    ) -> OrderResponse:
        return response_of(await lifecycle.pay(PayOrder(order_id=order_id, payment_id=body.payment_id)))

    return router


def request_hash(body: CreateOrderRequest) -> str:
    return hashlib.sha256(body.model_dump_json(by_alias=True).encode()).hexdigest()
