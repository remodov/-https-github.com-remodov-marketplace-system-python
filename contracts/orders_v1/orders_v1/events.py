import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

TOPIC = "marketplace.orders.v1"

HEADER_EVENT_ID = "event-id"
HEADER_EVENT_TYPE = "event-type"
HEADER_EVENT_VERSION = "event-version"
HEADER_AGGREGATE_TYPE = "aggregate-type"
HEADER_AGGREGATE_ID = "aggregate-id"
HEADER_OCCURRED_AT = "occurred-at"

EVENT_ORDER_CREATED = "OrderCreated"
EVENT_ORDER_CONFIRMED = "OrderConfirmed"
EVENT_ORDER_PAID = "OrderPaid"
EVENT_ORDER_SHIPPED = "OrderShipped"
EVENT_ORDER_DELIVERED = "OrderDelivered"
EVENT_ORDER_COMPLETED = "OrderCompleted"
EVENT_ORDER_EXPIRED = "OrderExpired"
EVENT_ORDER_CANCELLED = "OrderCancelled"
EVENT_DISPUTE_OPENED = "DisputeOpened"
EVENT_DISPUTE_RESOLVED = "DisputeResolved"

DECIMAL_STRING = r"^-?\d+(\.\d+)?$"


class OrderEventBase(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True, strict=True
    )

    order_id: uuid.UUID
    customer_id: uuid.UUID
    seller_id: uuid.UUID
    occurred_at: datetime

    def encode(self) -> bytes:
        return self.model_dump_json(by_alias=True, exclude_none=True).encode()


class OrderCreatedPayload(OrderEventBase):
    total_amount: str = Field(pattern=DECIMAL_STRING)
    currency: str = Field(min_length=3, max_length=3)
    items_count: int


class OrderConfirmedPayload(OrderEventBase):
    total_amount: str = Field(pattern=DECIMAL_STRING)
    currency: str = Field(min_length=3, max_length=3)


class OrderPaidPayload(OrderEventBase):
    total_amount: str = Field(pattern=DECIMAL_STRING)
    currency: str = Field(min_length=3, max_length=3)
    payment_id: uuid.UUID


class OrderCancelledPayload(OrderEventBase):
    previous_status: str
    reason: str | None = None
    refund_id: uuid.UUID | None = None


class DisputeOpenedPayload(OrderEventBase):
    reason: str


class OrderShippedPayload(OrderEventBase):
    tracking_number: str


class OrderDeliveredPayload(OrderEventBase):
    pass


class OrderExpiredPayload(OrderEventBase):
    pass
