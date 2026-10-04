import json
import uuid
from dataclasses import dataclass

import httpx

from ....core.errors import AppError, conflict, unavailable
from ....core.order.aggregate.order import Money


@dataclass(frozen=True)
class PaymentSettings:
    base_url: str
    connect_timeout: float
    request_timeout: float


class UnexpectedAnswer(Exception):
    pass


class PaymentClient:
    def __init__(self, settings: PaymentSettings) -> None:
        self.settings = settings
        self.http = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=httpx.Timeout(
                connect=settings.connect_timeout,
                read=settings.request_timeout,
                write=settings.request_timeout,
                pool=settings.connect_timeout,
            ),
        )

    async def request_refund(
        self, order_id: uuid.UUID, payment_id: uuid.UUID, amount: Money, idempotency_key: str
    ) -> uuid.UUID:
        body = {"orderId": str(order_id), "amount": str(amount.amount), "currency": amount.currency}
        try:
            response = await self.http.post(
                f"/api/v1/payments/{payment_id}/refund",
                content=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key},
            )
        except httpx.TransportError as error:
            raise degraded() from error
        if response.status_code >= 500:
            raise degraded() from UnexpectedAnswer(f"платежи ответили {response.status_code}")
        if response.status_code == 404:
            raise conflict("PAYMENT_NOT_FOUND", "Платёж по заказу не найден в сервисе платежей")
        if response.status_code == 409:
            raise conflict("REFUND_REJECTED", "Сервис платежей отказал в возврате")
        if response.status_code != 200:
            raise degraded() from UnexpectedAnswer(f"платежи ответили {response.status_code}")
        try:
            refunded = response.json()
            refund_id, status = uuid.UUID(refunded["id"]), refunded["status"]
        except (ValueError, KeyError, TypeError) as error:
            raise degraded() from error
        if status != "REFUNDED":
            raise conflict("REFUND_REJECTED", f"Платёж не возвращён: статус {status}")
        return refund_id

    async def aclose(self) -> None:
        await self.http.aclose()


def degraded() -> AppError:
    return unavailable("SERVICE_DEGRADED", "Сервис платежей временно недоступен")
