"""Database context management for PyTorch memory snapshots."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import quote

CallstackLayout = Literal["v1", "v2"]
_METADATA_TABLE = "pt_snap_metadata"


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
        self._callstack_layout: CallstackLayout | None = None

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
            self._callstack_layout = self._detect_callstack_layout(conn)

    @property
    def callstack_layout(self) -> CallstackLayout | None:
        """Return the detected callstack schema, or None when it is unrecognized.

        ``v1`` is inline ``callstack`` text on each ``trace_entry_<device>``
        table. ``v2`` stores ``callstackId`` and a shared ``callstack`` table.
        Detection is read-only and cached on this context; it is not written
        to focus files. Conflicting or damaged layouts raise
        :class:`SchemaVersionError` during construction.
        """
        return self._callstack_layout

    def _detect_callstack_layout(self, conn: sqlite3.Connection) -> CallstackLayout | None:
        """Identify v1/v2 callstack layout from table columns and metadata."""
        cursor = conn.cursor()
        layouts: dict[int, CallstackLayout] = {}
        unrecognized: list[int] = []
        for device_id, table_name in _trace_entry_tables(cursor):
            columns = _table_columns(cursor, table_name)
            has_id = "callstackid" in columns
            has_text = "callstack" in columns
            if has_id and has_text:
                raise SchemaVersionError(
                    "Incompatible callstack layout: "
                    f"'{table_name}' has both callstack and callstackId columns."
                )
            if has_id:
                layouts[device_id] = "v2"
            elif has_text:
                layouts[device_id] = "v1"
            else:
                unrecognized.append(device_id)

        if layouts and unrecognized:
            raise SchemaVersionError(
                "Incompatible callstack layout: some devices have a recognized "
                "callstack schema but others do not "
                f"(unrecognized devices: {unrecognized})."
            )

        distinct = set(layouts.values())
        if len(distinct) > 1:
            raise SchemaVersionError(
                "Incompatible callstack layout: devices disagree "
                f"({', '.join(sorted(distinct))})."
            )

        layout = next(iter(distinct), None)
        has_callstack_table = _has_table(cursor, "callstack")
        if layout == "v1" and has_callstack_table:
            raise SchemaVersionError(
                "Incompatible callstack layout: inline callstack text coexists "
                "with a shared callstack table."
            )
        if layout == "v2":
            if not has_callstack_table:
                raise SchemaVersionError(
                    "Incompatible callstack layout: callstackId is present but "
                    "the shared callstack table is missing."
                )
            callstack_columns = _table_columns(cursor, "callstack")
            if not {"id", "callstack"}.issubset(callstack_columns):
                raise SchemaVersionError(
                    "Incompatible callstack layout: shared callstack table is "
                    "missing id or callstack columns."
                )

        metadata_version = _import_format_version(cursor)
        if metadata_version in (1, 2) and layout is not None:
            expected: CallstackLayout = "v1" if metadata_version == 1 else "v2"
            if layout != expected:
                raise SchemaVersionError(
                    "Incompatible callstack layout: "
                    f"pt_snap_metadata.import_format_version is {metadata_version} "
                    f"but the database structure is {layout}."
                )

        return layout

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


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _has_table(cursor: sqlite3.Cursor, name: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cursor.fetchone() is not None


def _table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({_quote_ident(table_name)})")
    return {str(row[1]).lower() for row in cursor.fetchall()}


def _trace_entry_tables(cursor: sqlite3.Cursor) -> list[tuple[int, str]]:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'trace_entry_%'"
    )
    tables: list[tuple[int, str]] = []
    for row in cursor.fetchall():
        table_name = row[0]
        suffix = table_name.rsplit("_", 1)[-1]
        try:
            tables.append((int(suffix), table_name))
        except ValueError:
            continue
    return tables


def _import_format_version(cursor: sqlite3.Cursor) -> int | None:
    if not _has_table(cursor, _METADATA_TABLE):
        return None
    columns = _table_columns(cursor, _METADATA_TABLE)
    if "import_format_version" not in columns:
        return None
    try:
        rows = cursor.execute(f"SELECT import_format_version FROM {_METADATA_TABLE}").fetchall()
    except sqlite3.DatabaseError:
        return None
    if len(rows) != 1:
        return None
    try:
        return int(rows[0][0])
    except (TypeError, ValueError):
        return None
