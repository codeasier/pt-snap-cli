from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pt_snap_cli import __version__
from pt_snap_cli.context import Context, DatabaseNotFoundError, SchemaVersionError
from pt_snap_cli.core.errors import DatabaseMissingError, DatabaseSchemaError, ImportMetadataError
from pt_snap_cli.core.models import (
    CacheDecision,
    ImportMetadata,
    MetadataInspection,
)

METADATA_TABLE = "pt_snap_metadata"
METADATA_SCHEMA_VERSION = 1
# 2: trace_entry_<device> stores `callstackId` referencing the shared `callstack`
# table instead of an inlined `callstack` text column.
IMPORT_FORMAT_VERSION = 2
IMPORTER_NAME = "pt-snap-cli"
HASH_CHUNK_SIZE = 1024 * 1024

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_COLUMNS = {
    "id",
    "metadata_schema_version",
    "import_format_version",
    "source_sha256",
    "source_size",
    "source_name",
    "requested_device",
    "importer_name",
    "importer_version",
    "completed_at",
}


class ImportMetadataService:
    def calculate_sha256(self, source_path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with source_path.open("rb") as source:
                while chunk := source.read(HASH_CHUNK_SIZE):
                    digest.update(chunk)
        except OSError as exc:
            raise ImportMetadataError(f"Cannot hash snapshot file {source_path}: {exc}") from exc
        return digest.hexdigest()

    def build_metadata(
        self,
        source_path: Path,
        source_sha256: str,
        requested_device: int | None,
    ) -> ImportMetadata:
        try:
            source_size = source_path.stat().st_size
        except OSError as exc:
            raise ImportMetadataError(f"Cannot inspect snapshot file {source_path}: {exc}") from exc

        return ImportMetadata(
            metadata_schema_version=METADATA_SCHEMA_VERSION,
            import_format_version=IMPORT_FORMAT_VERSION,
            source_sha256=source_sha256,
            source_size=source_size,
            source_name=source_path.name,
            requested_device=requested_device,
            importer_name=IMPORTER_NAME,
            importer_version=__version__,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    def inspect(self, db_path: Path | str) -> MetadataInspection:
        path = Path(db_path).expanduser().resolve()
        try:
            context = Context(path)
        except DatabaseNotFoundError as exc:
            raise DatabaseMissingError(str(exc)) from exc
        except (SchemaVersionError, sqlite3.DatabaseError) as exc:
            raise DatabaseSchemaError(str(exc)) from exc

        try:
            with context.connect() as conn:
                table = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (METADATA_TABLE,),
                ).fetchone()
                if table is None:
                    return MetadataInspection(
                        db_path=path,
                        status="unavailable",
                        reason="metadata_missing",
                    )

                columns = {
                    row["name"] for row in conn.execute(f"PRAGMA table_info({METADATA_TABLE})")
                }
                if not _REQUIRED_COLUMNS.issubset(columns):
                    return MetadataInspection(
                        db_path=path,
                        status="invalid",
                        reason="metadata_invalid",
                    )

                rows = conn.execute(f"SELECT * FROM {METADATA_TABLE}").fetchall()
        except sqlite3.DatabaseError:
            return MetadataInspection(
                db_path=path,
                status="invalid",
                reason="metadata_invalid",
            )

        if len(rows) != 1 or rows[0]["id"] != 1:
            return MetadataInspection(
                db_path=path,
                status="invalid",
                reason="metadata_invalid",
            )

        try:
            metadata = self._metadata_from_row(dict(rows[0]))
        except (KeyError, TypeError, ValueError):
            return MetadataInspection(
                db_path=path,
                status="invalid",
                reason="metadata_invalid",
            )

        if metadata.metadata_schema_version != METADATA_SCHEMA_VERSION:
            return MetadataInspection(
                db_path=path,
                status="invalid",
                metadata=metadata,
                reason="metadata_version_unsupported",
            )

        return MetadataInspection(db_path=path, status="available", metadata=metadata)

    def write(self, db_path: Path | str, metadata: ImportMetadata) -> None:
        path = Path(db_path)
        try:
            self._validate_metadata(metadata, allow_unsupported_version=False)
        except (TypeError, ValueError) as exc:
            raise ImportMetadataError(f"Cannot write invalid import metadata: {exc}") from exc
        try:
            with closing(sqlite3.connect(path)) as conn, conn:
                conn.execute(f"DROP TABLE IF EXISTS {METADATA_TABLE}")
                conn.execute(f"""
                    CREATE TABLE {METADATA_TABLE} (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        metadata_schema_version INTEGER NOT NULL,
                        import_format_version INTEGER NOT NULL,
                        source_sha256 TEXT NOT NULL,
                        source_size INTEGER NOT NULL,
                        source_name TEXT NOT NULL,
                        requested_device INTEGER,
                        importer_name TEXT NOT NULL,
                        importer_version TEXT NOT NULL,
                        completed_at TEXT NOT NULL
                    )
                """)
                conn.execute(
                    f"""
                    INSERT INTO {METADATA_TABLE} (
                        id, metadata_schema_version, import_format_version,
                        source_sha256, source_size, source_name, requested_device,
                        importer_name, importer_version, completed_at
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        metadata.metadata_schema_version,
                        metadata.import_format_version,
                        metadata.source_sha256,
                        metadata.source_size,
                        metadata.source_name,
                        metadata.requested_device,
                        metadata.importer_name,
                        metadata.importer_version,
                        metadata.completed_at,
                    ),
                )
        except sqlite3.DatabaseError as exc:
            raise ImportMetadataError(f"Cannot write import metadata to {path}: {exc}") from exc

    def evaluate_cache(
        self,
        db_path: Path | str,
        source_sha256: str,
        requested_device: int | None,
        force: bool = False,
    ) -> CacheDecision:
        path = Path(db_path)
        if not path.exists():
            return CacheDecision(reused=False, metadata=None, reason="database_missing")
        if force:
            return CacheDecision(reused=False, metadata=None, reason="forced")

        try:
            inspection = self.inspect(path)
        except (DatabaseMissingError, DatabaseSchemaError):
            return CacheDecision(reused=False, metadata=None, reason="database_invalid")

        if inspection.status != "available" or inspection.metadata is None:
            return CacheDecision(
                reused=False,
                metadata=inspection.metadata,
                reason=inspection.reason or "metadata_invalid",
            )

        metadata = inspection.metadata
        if metadata.source_sha256 != source_sha256:
            return CacheDecision(reused=False, metadata=metadata, reason="source_changed")
        if metadata.import_format_version != IMPORT_FORMAT_VERSION:
            return CacheDecision(reused=False, metadata=metadata, reason="import_format_changed")
        if metadata.requested_device != requested_device:
            return CacheDecision(reused=False, metadata=metadata, reason="device_changed")
        return CacheDecision(reused=True, metadata=metadata, reason=None)

    @staticmethod
    def inspection_to_dict(inspection: MetadataInspection) -> dict[str, Any]:
        return {
            "db_path": str(inspection.db_path),
            "status": inspection.status,
            "reason": inspection.reason,
            "metadata": asdict(inspection.metadata) if inspection.metadata is not None else None,
        }

    def _metadata_from_row(self, row: dict[str, Any]) -> ImportMetadata:
        metadata = ImportMetadata(
            metadata_schema_version=self._required_int(row["metadata_schema_version"]),
            import_format_version=self._required_int(row["import_format_version"]),
            source_sha256=self._required_str(row["source_sha256"]),
            source_size=self._required_int(row["source_size"]),
            source_name=self._required_str(row["source_name"]),
            requested_device=self._optional_int(row["requested_device"]),
            importer_name=self._required_str(row["importer_name"]),
            importer_version=self._required_str(row["importer_version"]),
            completed_at=self._required_str(row["completed_at"]),
        )
        self._validate_metadata(metadata, allow_unsupported_version=True)
        return metadata

    @staticmethod
    def _validate_metadata(
        metadata: ImportMetadata,
        *,
        allow_unsupported_version: bool,
    ) -> None:
        if (
            not allow_unsupported_version
            and metadata.metadata_schema_version != METADATA_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported metadata schema version")
        if metadata.metadata_schema_version < 1 or metadata.import_format_version < 1:
            raise ValueError("Metadata versions must be positive integers")
        if not _SHA256_RE.fullmatch(metadata.source_sha256):
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
        if metadata.source_size < 0 or not metadata.source_name:
            raise ValueError("Source metadata is invalid")
        if metadata.requested_device is not None and metadata.requested_device < 0:
            raise ValueError("requested_device must be non-negative")
        if not metadata.importer_name or not metadata.importer_version:
            raise ValueError("Importer metadata is invalid")
        parsed_time = datetime.fromisoformat(metadata.completed_at)
        if parsed_time.tzinfo is None or parsed_time.utcoffset() != timedelta(0):
            raise ValueError("completed_at must use UTC")

    @staticmethod
    def _required_int(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("Expected integer metadata value")
        return value

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        return ImportMetadataService._required_int(value)

    @staticmethod
    def _required_str(value: Any) -> str:
        if not isinstance(value, str) or not value:
            raise TypeError("Expected non-empty metadata string")
        return value
