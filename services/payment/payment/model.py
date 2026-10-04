import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Status(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"

    # TODO шаг 11: перечислить разрешённые переходы; всё, чего здесь нет, запрещено,
    # конечные статусы никуда не ведут, переход в себя же не переход.
    def can_move_to(self, next_status: "Status") -> bool:
        return True


class InvalidTransition(Exception):
    def __init__(self, payment_id: uuid.UUID, current: Status, next_status: Status) -> None:
        super().__init__(f"платёж {payment_id}: переход {current} -> {next_status} запрещён")
        self.payment_id = payment_id
        self.current = current
        self.next_status = next_status


class PaymentNotFound(Exception):
    pass


@dataclass(frozen=True)
class Payment:
    id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    currency: str
    status: Status
    created_at: datetime
    updated_at: datetime

    def move_to(self, next_status: Status, now: datetime) -> "Payment":
        if not self.status.can_move_to(next_status):
            raise InvalidTransition(self.id, self.status, next_status)
        return replace(self, status=next_status, updated_at=now)
