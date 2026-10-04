import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....core.errors import conflict
from .tables import idempotency_keys
from .unit_of_work import session_in_scope


class SqlAlchemyIdempotencyKeys:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def find(self, key: str, request_hash: str) -> uuid.UUID | None:
        async with session_in_scope(self.sessions) as session:
            row = (
                await session.execute(
                    select(idempotency_keys.c.request_hash, idempotency_keys.c.order_id).where(
                        idempotency_keys.c.idempotency_key == key
                    )
                )
            ).one_or_none()
        if row is None:
            return None
        if row.request_hash != request_hash:
            raise conflict(
                "IDEMPOTENCY_KEY_CONFLICT", "Ключ Idempotency-Key уже использован для другого запроса"
            )
        return row.order_id

    async def claim(self, key: str, request_hash: str, order_id: uuid.UUID, now: datetime) -> bool:
        async with session_in_scope(self.sessions) as session:
            result = await session.execute(
                insert(idempotency_keys)
                .values(idempotency_key=key, request_hash=request_hash, order_id=order_id, created_at=now)
                .on_conflict_do_nothing(index_elements=[idempotency_keys.c.idempotency_key])
            )
        return result.rowcount == 1
