import time
from collections.abc import Callable


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int,
        open_for: float,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.open_for = open_for
        self.now = now
        self.failures_in_a_row = 0
        self.opened_at: float | None = None
        self.probe_in_flight = False

    def allows_call(self) -> bool:
        if self.opened_at is None:
            return True
        if self.now() - self.opened_at < self.open_for or self.probe_in_flight:
            return False
        self.probe_in_flight = True
        return True

    def succeeded(self) -> None:
        self.probe_in_flight = False
        self.failures_in_a_row = 0
        self.opened_at = None

    def failed(self) -> None:
        self.probe_in_flight = False
        self.failures_in_a_row += 1
        if self.opened_at is not None or self.failures_in_a_row >= self.failure_threshold:
            self.opened_at = self.now()
