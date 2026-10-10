"""Shared deadline-aware SQLite connection ownership for lifecycle reductions."""

from __future__ import annotations

import math
import sqlite3
import time

from pt_snap_cli.core.dataset_contract import SliceRecord
from pt_snap_cli.core.dataset_files import require_readonly_member
from pt_snap_cli.core.dataset_sources import DatasetSourceResolver
from pt_snap_cli.core.errors import QueryExecutionError


class _AttachedSources:
    def __init__(
        self,
        sources: DatasetSourceResolver,
        items: list[SliceRecord] | None = None,
        *,
        database: str = ":memory:",
    ) -> None:
        self.sources = sources
        self.items = sources.device.slices if items is None else items
        remaining = sources.budget.remaining()
        self.connection = sqlite3.connect(
            database, uri=True, timeout=min(5.0, remaining) if remaining is not None else 5.0
        )
        self.connection.row_factory = sqlite3.Row

    def _configure_deadline(self):
        budget = self.sources.budget
        remaining = budget.remaining()
        deadline = budget.started + budget.timeout_s if budget.timeout_s is not None else None
        self.connection.set_progress_handler(
            (lambda: int(time.monotonic() >= deadline)) if deadline is not None else None, 1000
        )
        # SQLite's default five-second lock wait must not outlive the operation.
        wait_ms = math.ceil(1000 * min(5.0, remaining)) if remaining is not None else 5000
        self.connection.execute(f"PRAGMA busy_timeout={wait_ms}")

    def __enter__(self):
        try:
            self._configure_deadline()
            self.connection.execute("PRAGMA trusted_schema=OFF")
            for item in self.items:
                self._configure_deadline()
                path = self.sources.dataset.root / item.file
                immutable = self.sources.dataset.callstack_layout == "v1"
                require_readonly_member(self.sources.dataset.root, path, immutable=immutable)
                uri = path.as_uri() + "?mode=ro" + ("&immutable=1" if immutable else "")
                self.connection.execute(f'ATTACH DATABASE ? AS "s{item.index}"', [uri])
            self.connection.execute("PRAGMA query_only=ON")
            self.sources.budget.remaining()
            return self
        except BaseException as exc:
            self.connection.set_progress_handler(None, 0)
            self.connection.close()
            if isinstance(exc, sqlite3.Error):
                self.sources.budget.remaining()
                raise QueryExecutionError(str(exc)) from exc
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.connection.set_progress_handler(None, 0)
        self.connection.close()
        return False

    def read(self, sql: str, values: list[object] | None = None):
        budget = self.sources.budget
        cursor = self.connection.cursor()
        self.sources.query_count += 1
        try:
            self._configure_deadline()
            cursor.execute(sql, values or [])
            result = []
            while batch := cursor.fetchmany(256):
                rows = [dict(row) for row in batch]
                budget.consume(rows)
                result.extend(rows)
            budget.remaining()
            return result
        except (sqlite3.Error, OverflowError) as exc:
            budget.remaining()  # Preserve the domain timeout on interruption.
            raise QueryExecutionError(str(exc)) from exc
        finally:
            cursor.close()
            self.connection.set_progress_handler(None, 0)
