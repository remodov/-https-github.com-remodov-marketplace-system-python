import asyncio
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel

from .downstream import DownstreamClient
from .errors import DownstreamError, ScreenNotAssembled

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

        # TODO шаг 13: собрать экран.
        # Заказ уже прочитан: из него известны товары (order.items) и идентификатор платежа
        # (order.payment_id). Осталось добрать карточки товаров (self.catalog, модель ProductCard)
        # и статус платежа (self._payment_status). Эти походы независимы, экран не обязан
        # ждать их по очереди.
        raise ScreenNotAssembled(f"шаг 13: экран заказа {order.id} ещё не собирается")

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
