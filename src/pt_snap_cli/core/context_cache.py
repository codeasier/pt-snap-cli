"""LRU cache for read-only SQLite ``Context`` instances.

The cache exists so that long-lived owners (e.g. the MCP server, which keeps
a single :class:`SnapshotAnalyzer` alive across many tool calls) can reuse a
single :class:`pt_snap_cli.context.Context` -- and its persistent read-only
SQLite connection -- instead of paying the cost of ``dictionary`` schema
validation, device discovery, and a fresh ``sqlite3.connect`` URI handshake on
every query.

Entries are keyed by the resolved absolute path of the database file and
stamped with a file signature at the time of insertion. On lookup the cache
compares the current signature to the cached value and evicts the entry on
mismatch, so a database that is replaced on disk (for example, by
``pt-snap import``) is re-opened automatically even when the replacement has
the same mtime. Callers can also force a refresh with
:meth:`ContextCache.invalidate`.
"""

from __future__ import annotations

import sqlite3
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

from pt_snap_cli.context import Context, DatabaseNotFoundError

if TYPE_CHECKING:
    pass

FileSignature = tuple[int, int, int]


class ContextCache:
    """LRU cache of :class:`Context` instances keyed by absolute db path."""

    def __init__(self, maxsize: int = 4) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self._maxsize = maxsize
        # Insertion order doubles as LRU recency (oldest first).
        self._entries: OrderedDict[Path, tuple[Context, FileSignature]] = OrderedDict()

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, db_path: Path | str) -> Context:
        """Return a cached or freshly opened :class:`Context` for ``db_path``.

        On a hit the cached entry is promoted to most-recently-used. On a
        miss -- or when the file's signature has changed -- a new persistent
        context is created and stored, evicting the oldest entry once the
        cache is full.

        Raises:
            DatabaseNotFoundError: If ``db_path`` does not exist on disk.
        """
        key = Path(db_path).expanduser().resolve()
        if not key.exists():
            raise DatabaseNotFoundError(f"Database not found: {key}")

        # Probe metadata first so a missing/inaccessible file raises
        # consistently whether the cache is hit or missed.
        current_signature = self._file_signature(key)

        cached = self._entries.get(key)
        if cached is not None:
            ctx, cached_signature = cached
            if cached_signature == current_signature:
                self._entries.move_to_end(key)
                return ctx
            self._safe_close(ctx)
            del self._entries[key]

        ctx = Context(key, persistent=True)
        self._entries[key] = (ctx, current_signature)
        self._evict_if_needed()
        return ctx

    def invalidate(self, db_path: Path | str | None = None) -> None:
        """Drop a single cached entry or every entry when ``db_path`` is None."""
        if db_path is None:
            while self._entries:
                _, (ctx, _) = self._entries.popitem(last=False)
                self._safe_close(ctx)
            return
        key = Path(db_path).expanduser().resolve()
        cached = self._entries.pop(key, None)
        if cached is not None:
            self._safe_close(cached[0])

    def close(self) -> None:
        """Drop every cached entry and close the underlying connections."""
        self.invalidate()

    def _evict_if_needed(self) -> None:
        while len(self._entries) > self._maxsize:
            _, (ctx, _) = self._entries.popitem(last=False)
            self._safe_close(ctx)

    @staticmethod
    def _safe_close(ctx: Context) -> None:
        try:
            ctx.close()
        except sqlite3.Error:
            # Already-closed connections are fine; other sqlite errors are
            # best-effort cleanup, never worth masking the real exception.
            pass

    @staticmethod
    def _file_signature(path: Path) -> FileSignature:
        """Return metadata that changes when a database is replaced in place."""
        stat = path.stat()
        return (stat.st_mtime_ns, stat.st_ino, stat.st_size)


__all__ = ["ContextCache"]
