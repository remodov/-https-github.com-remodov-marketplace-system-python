from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....core.product.port.out import AuditEntry
from .tables import catalog_audit_log
from .unit_of_work import session_in_scope


class SqlAlchemyAuditLogger:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def record(self, entry: AuditEntry) -> None:
        async with session_in_scope(self.sessions) as session:
            await session.execute(
                insert(catalog_audit_log).values(
                    id=entry.id,
                    actor_id=entry.actor_id,
                    action=entry.action,
                    product_id=entry.product_id,
                    occurred_at=entry.occurred_at,
                    metadata=dict(entry.metadata),
                )
            )
