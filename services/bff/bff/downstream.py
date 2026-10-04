from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .errors import DownstreamError

TIMEOUT_SECONDS = 2.0

Reply = TypeVar("Reply", bound=BaseModel)


class DownstreamClient:
    def __init__(self, name: str, base_url: str) -> None:
        self.name = name
        self.http = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(TIMEOUT_SECONDS))

    async def get(self, path: str, authorization: str, reply: type[Reply]) -> Reply:
        headers = {"Authorization": authorization} if authorization else {}
        try:
            response = await self.http.get(path, headers=headers)
        except httpx.HTTPError as error:
            raise DownstreamError(self.name, cause=error) from error
        if response.status_code != 200:
            raise DownstreamError(self.name, status=response.status_code)
        try:
            return reply.model_validate_json(response.content)
        except ValidationError as error:
            raise DownstreamError(self.name, cause=error) from error

    async def aclose(self) -> None:
        await self.http.aclose()
