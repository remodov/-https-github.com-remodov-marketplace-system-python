import asyncio
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel

from .downstream import DownstreamClient
from .errors import DownstreamError

PAYMENT_NONE = "NONE"


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True)


class ScreenItem(ApiModel):
    product_id: uuid.UUID
    title: str
    quantity: int
    price: Decimal

    @field_serializer("price")
    def price_as_number(self, value: Decimal) -> float:
        return float(value)


class OrderScreen(ApiModel):
    order_id: uuid.UUID
    status: str
    total: Decimal
    payment_status: str
    items: list[ScreenItem]

    @field_serializer("total")
    def total_as_number(self, value: Decimal) -> float:
        return float(value)


class OrderLine(ApiModel):
    product_id: uuid.UUID
    quantity: int


class OrderReply(ApiModel):
    id: uuid.UUID
    status: str
    total: Decimal
    payment_id: uuid.UUID | None = None
    items: list[OrderLine]


class ProductCard(ApiModel):
    title: str
    price: Decimal


class PaymentReply(ApiModel):
    status: str


class ScreenAssembler:
    def __init__(self, order: DownstreamClient, catalog: DownstreamClient, payment: DownstreamClient) -> None:
        self.order = order
        self.catalog = catalog
        self.payment = payment

    @classmethod
    def for_urls(cls, order_url: str, catalog_url: str, payment_url: str) -> "ScreenAssembler":
        return cls(
            DownstreamClient("order", order_url),
            DownstreamClient("catalog", catalog_url),
            DownstreamClient("payment", payment_url),
        )

    async def assemble(self, order_id: uuid.UUID, authorization: str) -> OrderScreen:
        order = await self.order.get(f"/api/v1/orders/{order_id}", authorization, OrderReply)

        *items, payment_status = await asyncio.gather(
            *(self._item(line, authorization) for line in order.items),
            self._payment_status(order.payment_id, authorization),
        )
        return OrderScreen(
            order_id=order.id,
            status=order.status,
            total=order.total,
            payment_status=payment_status,
            items=items,
        )

    async def _item(self, line: OrderLine, authorization: str) -> ScreenItem:
        card = await self.catalog.get(f"/api/v1/products/{line.product_id}", authorization, ProductCard)
        return ScreenItem(
            product_id=line.product_id, title=card.title, quantity=line.quantity, price=card.price
        )

    async def _payment_status(self, payment_id: uuid.UUID | None, authorization: str) -> str:
        if payment_id is None:
            return PAYMENT_NONE
        try:
            payment = await self.payment.get(f"/api/v1/payments/{payment_id}", authorization, PaymentReply)
        except DownstreamError as error:
            if error.status == 404:
                return PAYMENT_NONE
            raise
        return payment.status

    async def aclose(self) -> None:
        await asyncio.gather(self.order.aclose(), self.catalog.aclose(), self.payment.aclose())
