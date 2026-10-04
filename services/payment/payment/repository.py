import uuid
from pathlib import Path

import asyncpg

from .model import Payment, PaymentNotFound, Status

SCHEMA = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")

SELECT_PAYMENT = "SELECT id, order_id, amount, currency, status, created_at, updated_at FROM payments"


class DatabaseNotStarted(Exception):
    pass


class Database:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=10)
        await self.pool.execute(SCHEMA)

    async def aclose(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def started(self) -> asyncpg.Pool:
        if self.pool is None:
            raise DatabaseNotStarted("пул asyncpg не запущен: нужен start() в lifespan")
        return self.pool

    def connection(self):
        return self.started().acquire()

    async def ping(self) -> None:
        await self.started().fetchval("SELECT 1")


async def find_by_id(connection: asyncpg.Connection, payment_id: uuid.UUID) -> Payment:
    return payment_of(await connection.fetchrow(f"{SELECT_PAYMENT} WHERE id = $1", payment_id), payment_id)


async def lock_by_id(connection: asyncpg.Connection, payment_id: uuid.UUID) -> Payment:
    row = await connection.fetchrow(f"{SELECT_PAYMENT} WHERE id = $1 FOR UPDATE", payment_id)
    return payment_of(row, payment_id)


async def find_by_order_id(connection: asyncpg.Connection, order_id: uuid.UUID) -> Payment | None:
    row = await connection.fetchrow(f"{SELECT_PAYMENT} WHERE order_id = $1", order_id)
    return None if row is None else restore(row)


async def insert(connection: asyncpg.Connection, payment: Payment) -> None:
    await connection.execute(
        """
        INSERT INTO payments (id, order_id, amount, currency, status, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        payment.id,
        payment.order_id,
        payment.amount,
        payment.currency,
        payment.status.value,
        payment.created_at,
        payment.updated_at,
    )


async def update_status(connection: asyncpg.Connection, payment: Payment) -> None:
    await connection.execute(
        "UPDATE payments SET status = $2, updated_at = $3 WHERE id = $1",
        payment.id,
        payment.status.value,
        payment.updated_at,
    )


def payment_of(row: asyncpg.Record | None, payment_id: uuid.UUID) -> Payment:
    if row is None:
        raise PaymentNotFound(payment_id)
    return restore(row)


def restore(row: asyncpg.Record) -> Payment:
    return Payment(
        id=row["id"],
        order_id=row["order_id"],
        amount=row["amount"],
        currency=row["currency"],
        status=Status(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
