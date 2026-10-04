import uuid

from fastapi import APIRouter, Depends, Response

from ....core.order.query.queries import GetOrder, QueryHandler
from ....core.order.usecase.create_order import CreateOrder, CreateOrderHandler, OrderLine
from ....core.security.principal import Principal, Role
from .auth import Authenticator, optional_principal, require_roles
from .schemas import CreateOrderRequest, OrderResponse, address_of, response_of


def order_router(auth: Authenticator, create: CreateOrderHandler, queries: QueryHandler) -> APIRouter:
    router = APIRouter(prefix="/api/v1/orders", tags=["orders"])
    customer_or_admin = require_roles(optional_principal(auth), Role.CUSTOMER, Role.ADMIN)

    @router.post("", status_code=201)
    async def create_order(
        body: CreateOrderRequest,
        response: Response,
        principal: Principal = Depends(customer_or_admin),
    ) -> OrderResponse:
        order = await create.handle(
            CreateOrder(
                customer=principal,
                lines=[
                    OrderLine(product_id=item.product_id, seller_id=item.seller_id, quantity=item.quantity)
                    for item in body.items
                ],
                shipping_address=address_of(body.shipping_address),
            )
        )
        response.headers["Location"] = f"/api/v1/orders/{order.id}"
        return response_of(order)

    @router.get("/{order_id}")
    async def get_order(
        order_id: uuid.UUID,
        principal: Principal = Depends(customer_or_admin),
    ) -> OrderResponse:
        order = await queries.get_order(GetOrder(order_id=order_id, requester=principal))
        return response_of(order)

    return router
