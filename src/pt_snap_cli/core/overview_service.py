from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pt_snap_cli.context import Context, DatabaseNotFoundError, SchemaVersionError
from pt_snap_cli.core.context_cache import ContextCache
from pt_snap_cli.core.errors import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusNotConfiguredError,
)
from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.import_metadata import ImportMetadataService
from pt_snap_cli.core.models import DatabaseOverview, DeviceTraceBounds


class OverviewService:
    """Read-only SnapshotDB orientation: devices, trace bounds, import metadata."""

    def __init__(
        self,
        focus_service: FocusService | None = None,
        metadata_service: ImportMetadataService | None = None,
        *,
        context_cache: ContextCache | None = None,
    ) -> None:
        self._focus_service = focus_service or FocusService()
        self._metadata_service = metadata_service or ImportMetadataService()
        self._context_cache = context_cache if context_cache is not None else ContextCache()

    def inspect(
        self,
        db_path: Path | str | None = None,
        start_dir: Path | None = None,
    ) -> DatabaseOverview:
        resolved = self._focus_service.resolve_focus(
            explicit_db_path=db_path,
            start_dir=start_dir,
        )
        if resolved.db_path is None:
            raise FocusNotConfiguredError("No database path specified and no database configured.")

        db_path = resolved.db_path.expanduser().resolve()
        ctx = self._validated_context(db_path)
        devices = [
            DeviceTraceBounds(
                device_id=device_id,
                first_event_id=first_event_id,
                last_event_id=last_event_id,
            )
            for device_id, first_event_id, last_event_id in ctx.device_trace_bounds()
        ]
        return DatabaseOverview(
            db_path=db_path,
            focus_source=resolved.source,
            devices=devices,
            metadata=self._metadata_service.inspect(db_path),
        )

    def overview_to_dict(self, overview: DatabaseOverview) -> dict[str, Any]:
        inspection = self._metadata_service.inspection_to_dict(overview.metadata)
        return {
            "db_path": str(overview.db_path),
            "focus_source": overview.focus_source,
            "devices": [
                {
                    "device_id": device.device_id,
                    "first_event_id": device.first_event_id,
                    "last_event_id": device.last_event_id,
                }
                for device in overview.devices
            ],
            "import_metadata": {
                "status": inspection["status"],
                "reason": inspection["reason"],
                "metadata": inspection["metadata"],
            },
        }

    def _validated_context(self, db_path: Path) -> Context:
        try:
            return self._context_cache.get(db_path)
        except DatabaseNotFoundError as exc:
            raise DatabaseMissingError(str(exc)) from exc
        except (SchemaVersionError, sqlite3.DatabaseError) as exc:
            raise DatabaseSchemaError(str(exc)) from exc
