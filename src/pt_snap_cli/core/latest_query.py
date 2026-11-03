"""Latest-request-wins coordination without sharing SQLite connections."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Event, Lock

from .errors import QueryCancelledError


class LatestQuery:
    def __init__(self) -> None:
        self._state = Lock()
        self._work = Lock()
        self._active: Event | None = None

    def cancel(self) -> None:
        with self._state:
            if self._active is not None:
                self._active.set()

    @contextmanager
    def run(
        self, remaining: Callable[[], float | None] | None = None
    ) -> Iterator[Callable[[], bool]]:
        token = Event()
        with self._state:
            if self._active is not None:
                self._active.set()
            self._active = token
        try:
            # The old task must unwind and close its own SQLite handles first.
            while True:
                self._check(token)
                left = remaining() if remaining is not None else None
                if self._work.acquire(timeout=min(left, 0.05) if left is not None else 0.05):
                    break
            try:
                self._check(token)
                if remaining is not None:
                    remaining()
                yield token.is_set
                self._check(token)
            finally:
                self._work.release()
        finally:
            with self._state:
                if self._active is token:
                    self._active = None

    @staticmethod
    def _check(token: Event) -> None:
        if token.is_set():
            raise QueryCancelledError("Frame tree query cancelled by a newer request or reset.")
