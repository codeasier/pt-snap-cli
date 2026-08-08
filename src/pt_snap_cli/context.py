"""Database context management for PyTorch memory snapshots."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote


class DatabaseNotFoundError(FileNotFoundError):
    """Raised when database file does not exist."""

    pass


class SchemaVersionError(ValueError):
    """Raised when database schema is invalid or incompatible."""

    pass


class Context:
    """Database context manager for PyTorch memory snapshot analysis.

    Manages SQLite database connections in read-only mode with schema validation.

    By default the underlying SQLite connection is opened and closed for every
    ``connect()`` context. Pass ``persistent=True`` to keep the connection
    alive across calls so that long-lived owners (e.g. a ``ContextCache``
    shared by an MCP server) can avoid the per-query open/close cost.
    Persistent contexts still close their connection when ``close()`` is
    invoked explicitly.
    """

    def __init__(
        self,
        db_path: str | Path,
        devices: list[int] | None = None,
        *,
        persistent: bool = False,
    ):
        """Initialize context with database path.

        Args:
            db_path: Path to the SQLite database file.
            devices: Optional list of device IDs to filter.
            persistent: When True, the connection stays open after each
                ``connect()`` call so it can be reused. The caller is
                responsible for invoking ``close()`` to release it.

        Raises:
            DatabaseNotFoundError: If database file does not exist.
            SchemaVersionError: If database schema is invalid.
        """
        self.db_path = Path(db_path)
        self._devices = devices
        self._persistent = persistent
        self._conn: sqlite3.Connection | None = None
        self._connect_depth = 0
        self._device_ids: list[int] | None = None

        if not self.db_path.exists():
            raise DatabaseNotFoundError(f"Database not found: {self.db_path}")

        self._validate_schema()

    def _validate_schema(self) -> None:
        """Validate database has required schema (dictionary table)."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary'"
            )
            if not cursor.fetchone():
                raise SchemaVersionError(
                    "Invalid database schema: 'dictionary' table not found. "
                    "This may not be a valid PyTorch memory snapshot database."
                )

    @property
    def device_ids(self) -> list[int]:
        """Get list of device IDs available in the database."""
        if self._device_ids is None:
            self._device_ids = self._discover_device_ids()
        return self._device_ids

    def discover_devices(self) -> list[int]:
        """Discover device IDs available in the database.

        Method-style alias of the ``device_ids`` property, exposed for
        callers (e.g. import service) that prefer an explicit method.
        """
        return self.device_ids

    def _discover_device_ids(self) -> list[int]:
        """Discover device IDs from database table names."""
        device_ids = set()
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'trace_entry_%'"
            )
            for row in cursor.fetchall():
                table_name = row[0]
                device_id = int(table_name.split("_")[-1])
                if self._devices is None or device_id in self._devices:
                    device_ids.add(device_id)
        return sorted(device_ids)

    def cursor(self) -> sqlite3.Cursor:
        """Get a database cursor.

        Returns:
            SQLite cursor for database operations.

        Raises:
            RuntimeError: If database is not connected.
        """
        if self._conn is None:
            raise RuntimeError("Database not connected. Use connect() context manager.")
        return self._conn.cursor()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connection.

        Opens database in read-only mode for safe analysis. When the
        context was constructed with ``persistent=True`` the underlying
        SQLite connection remains open after the context exits and is
        reused by subsequent ``connect()`` calls until ``close()`` is
        invoked explicitly.

        Yields:
            SQLite connection object.
        """
        if self._conn is None:
            # Keep the colon in Windows drive prefixes while encoding SQLite URI metacharacters.
            encoded_path = quote(self.db_path.as_posix(), safe="/:")
            uri = f"file:{encoded_path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row

        self._connect_depth += 1
        try:
            yield self._conn
        finally:
            if self._connect_depth > 0:
                self._connect_depth -= 1
            if not self._persistent and self._connect_depth == 0:
                self.close()

    def close(self) -> None:
        """Close the database connection.

        Safe to call multiple times and on already-closed contexts.
        """
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._connect_depth = 0
