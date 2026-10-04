import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

TOPIC = "marketplace.payments.v1"

HEADER_EVENT_ID = "event-id"
HEADER_EVENT_TYPE = "event-type"
HEADER_EVENT_VERSION = "event-version"
HEADER_AGGREGATE_TYPE = "aggregate-type"
HEADER_AGGREGATE_ID = "aggregate-id"
HEADER_OCCURRED_AT = "occurred-at"

EVENT_PAYMENT_COMPLETED = "PaymentCompleted"
EVENT_PAYMENT_FAILED = "PaymentFailed"

DECIMAL_STRING = r"^-?\d+(\.\d+)?$"


class PaymentEventBase(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True, strict=True
    )

    payment_id: uuid.UUID
    order_id: uuid.UUID
    occurred_at: datetime

    def encode(self) -> bytes:
        return self.model_dump_json(by_alias=True, exclude_none=True).encode()


class PaymentCompletedPayload(PaymentEventBase):
    amount: str = Field(pattern=DECIMAL_STRING)
    currency: str = Field(min_length=3, max_length=3)


class PaymentFailedPayload(PaymentEventBase):
    reason: str
