import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer
from pydantic.alias_generators import to_camel

from ....core.order.aggregate.order import MAX_QUANTITY, Address, Item, Order, Status

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True)


class AddressRequest(ApiModel):
    country: str = ""
    city: NonBlank
    street: NonBlank
    postal_code: str = ""
    pickup_point: str = ""


class OrderItemRequest(ApiModel):
    product_id: uuid.UUID
    seller_id: uuid.UUID
    quantity: int = Field(ge=1, le=MAX_QUANTITY)


class CreateOrderRequest(ApiModel):
    items: list[OrderItemRequest] = Field(min_length=1)
    shipping_address: AddressRequest


class CancelOrderRequest(ApiModel):
    reason_code: str
    comment: str = ""


class ShipOrderRequest(ApiModel):
    tracking_number: str


class PayOrderRequest(ApiModel):
    payment_id: uuid.UUID


class AddressResponse(ApiModel):
    country: str
    city: str
    street: str
    postal_code: str
    pickup_point: str


class OrderItemResponse(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    seller_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal

    @field_serializer("unit_price", "line_total")
    def money_as_number(self, value: Decimal) -> float:
        return float(value)


class OrderResponse(ApiModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    seller_id: uuid.UUID
    status: Status
    items: list[OrderItemResponse]
    shipping_fee: Decimal
    total: Decimal
    currency: str
    shipping_address: AddressResponse
    payment_id: uuid.UUID | None
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("shipping_fee", "total")
    def money_as_number(self, value: Decimal) -> float:
        return float(value)


def address_of(body: AddressRequest) -> Address:
    return Address(
        country=body.country,
        city=body.city,
        street=body.street,
        postal_code=body.postal_code,
        pickup_point=body.pickup_point,
    )


def item_response_of(item: Item) -> OrderItemResponse:
    return OrderItemResponse(
        id=item.id,
        product_id=item.product_id,
        seller_id=item.seller_id,
        quantity=item.quantity,
        unit_price=item.unit_price.amount,
        line_total=item.line_total.amount,
    )


def response_of(order: Order) -> OrderResponse:
    address = order.shipping_address
    total = order.total
    state = order.lifecycle
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        seller_id=order.seller_id,
        status=order.status,
        items=[item_response_of(item) for item in order.items],
        shipping_fee=order.shipping_fee.amount,
        total=total.amount,
        currency=total.currency,
        shipping_address=AddressResponse(
            country=address.country,
            city=address.city,
            street=address.street,
            postal_code=address.postal_code,
            pickup_point=address.pickup_point,
        ),
        payment_id=state.payment_id,
        paid_at=state.paid_at,
        shipped_at=state.shipped_at,
        delivered_at=state.delivered_at,
        closed_at=state.closed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )
