class ScreenNotAssembled(Exception):
    pass


class DownstreamError(ScreenNotAssembled):
    def __init__(self, service: str, status: int | None = None, cause: Exception | None = None) -> None:
        super().__init__(f"{service}: ответил {status}" if status is not None else f"{service}: {cause}")
        self.service = service
        self.status = status
