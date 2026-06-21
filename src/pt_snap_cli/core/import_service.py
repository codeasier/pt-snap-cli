from __future__ import annotations

import pickle
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pt_snap_cli.core.errors import ImportToolMissingError, SnapshotFileInvalidError
from pt_snap_cli.core.models import ImportOptions, ImportResult
from pt_snap_cli.core.snapshot_import_backend import SnapshotImportBackend

if TYPE_CHECKING:
    from pt_snap_cli.core.focus_service import FocusService

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
        self._backend_available = True
        self._run_dump_to_db: Callable[[Path, Path, int | None], Path] | None = (
            self._backend.dump_to_db
        )

    def import_snapshot(self, options: ImportOptions) -> ImportResult:
        self._validate_snapshot_file(options.snapshot_file)
        output_dir = self._resolve_output_dir(options.snapshot_file, options.output_dir)
        db_path = self._invoke_backend(options.snapshot_file, output_dir, options.device)

        focus_state = None
        if options.set_focus:
            if self._focus_service is None:
                from pt_snap_cli.core.focus_service import FocusService

                self._focus_service = FocusService()
            focus_state = self._focus_service.set_project_focus(
                db_path=db_path,
                device_id=options.device,
                base_dir=output_dir,
            )

        return ImportResult(db_path=db_path, device_id=options.device, focus_state=focus_state)

    def _ensure_backend_available(self) -> None:
        if not self._backend_available or self._run_dump_to_db is None:
            raise ImportToolMissingError(
                "Vendored snapshot import backend is unavailable. Reinstall pt-snap-cli; "
                "the package may be incomplete."
            )

    def _invoke_backend(
        self,
        snapshot_file: Path,
        output_dir: Path,
        device: int | None,
    ) -> Path:
        self._ensure_backend_available()
        assert self._run_dump_to_db is not None
        return self._run_dump_to_db(snapshot_file, output_dir, device)

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
        try:
            with path.open("rb") as file:
                obj = pickle.load(file)
        except Exception as exc:
            raise SnapshotFileInvalidError(f"Cannot unpickle snapshot file: {exc}") from exc
        if not isinstance(obj, dict):
            raise SnapshotFileInvalidError(
                f"Snapshot top-level must be a dict, got {type(obj).__name__}"
            )

    @staticmethod
    def _resolve_output_dir(snapshot_file: Path, output_dir: Path | None) -> Path:
        return output_dir.resolve() if output_dir is not None else snapshot_file.resolve().parent
