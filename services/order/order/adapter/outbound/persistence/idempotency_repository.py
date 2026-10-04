import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker


class SqlAlchemyIdempotencyKeys:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    # TODO шаг 9: прочитать строку по ключу через session_in_scope; строки нет - None,
    # хеш другой - конфликт IDEMPOTENCY_KEY_CONFLICT, хеш тот же - id прежнего заказа.
    async def find(self, key: str, request_hash: str) -> uuid.UUID | None:
        return None

    # TODO шаг 9: занять ключ одной вставкой с ON CONFLICT DO NOTHING и сказать, удалось ли.
    async def claim(self, key: str, request_hash: str, order_id: uuid.UUID, now: datetime) -> bool:
        return True
