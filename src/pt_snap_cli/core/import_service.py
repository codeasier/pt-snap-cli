from __future__ import annotations

import logging
from pathlib import Path

from pt_snap_cli.core.errors import (
    DatabaseSchemaError,
    FocusFileInvalidError,
    ImportExecutionError,
    SnapshotFileInvalidError,
)
from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.models import ImportOptions, ImportResult
from pt_snap_cli.core.snapshot_import_backend import SnapshotImportBackend

logger = logging.getLogger(__name__)

VALID_SUFFIXES = {".pkl", ".pickle"}


class ImportService:
    """Import PyTorch snapshot pickle files through the vendored backend."""

    def __init__(
        self,
        focus_service: FocusService | None = None,
        backend: SnapshotImportBackend | None = None,
    ) -> None:
        self._focus_service = focus_service
        self._backend = backend or SnapshotImportBackend()

    def import_snapshot(self, options: ImportOptions) -> ImportResult:
        self._validate_snapshot_file(options.snapshot_file)
        output_dir = self._resolve_output_dir(options.snapshot_file, options.output_dir)
        db_path = self._backend.dump_to_db(options.snapshot_file, output_dir, options.device)

        focus_state = None
        if options.set_focus:
            if self._focus_service is None:
                self._focus_service = FocusService()
            try:
                focus_state = self._focus_service.set_project_focus(
                    db_path=db_path,
                    device_id=options.device,
                    base_dir=output_dir,
                )
            except (FocusFileInvalidError, DatabaseSchemaError) as exc:
                # Focus write happens after the .db is on disk; if the new
                # database fails validation (e.g. vendor produced a non-pt-snap
                # schema), report it as an import execution failure rather than
                # leaking the underlying domain error through the import API.
                raise ImportExecutionError(
                    f"Imported database cannot be registered as focus: {exc}"
                ) from exc

        return ImportResult(db_path=db_path, device_id=options.device, focus_state=focus_state)

    @staticmethod
    def _validate_snapshot_file(path: Path) -> None:
        if not path.exists():
            raise SnapshotFileInvalidError(f"Snapshot file does not exist: {path}")
        if not path.is_file():
            raise SnapshotFileInvalidError(f"Snapshot path is not a file: {path}")
        if path.suffix.lower() not in VALID_SUFFIXES:
            raise SnapshotFileInvalidError(
                f"Snapshot suffix must be .pkl or .pickle, got {path.suffix!r}"
            )

    @staticmethod
    def _resolve_output_dir(snapshot_file: Path, output_dir: Path | None) -> Path:
        return output_dir.resolve() if output_dir is not None else snapshot_file.resolve().parent
