from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

current_session: ContextVar[AsyncSession | None] = ContextVar("catalog_current_session", default=None)


@asynccontextmanager
async def session_in_scope(sessions: async_sessionmaker) -> AsyncIterator[AsyncSession]:
    bound = current_session.get()
    if bound is not None:
        yield bound
        return
    async with sessions() as session, session.begin():
        yield session


class SqlAlchemyUnitOfWork:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[None]:
        if current_session.get() is not None:
            yield
            return
        async with self.sessions() as session, session.begin():
            token = current_session.set(session)
            try:
                yield
            finally:
                current_session.reset(token)
