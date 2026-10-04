import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from .tables import processed_events
from .unit_of_work import session_in_scope


class SqlAlchemyProcessedEvents:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def mark_processed(self, event_id: uuid.UUID, event_type: str, now: datetime) -> bool:
        async with session_in_scope(self.sessions) as session:
            result = await session.execute(
                insert(processed_events)
                .values(event_id=event_id, event_type=event_type, processed_at=now)
                .on_conflict_do_nothing(index_elements=[processed_events.c.event_id])
            )
        return result.rowcount == 1
