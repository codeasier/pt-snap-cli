from __future__ import annotations

import logging
from pathlib import Path

from pt_snap_cli.core.errors import (
    DatabaseSchemaError,
    FocusFileInvalidError,
    ImportExecutionError,
    ImportMetadataError,
    InvalidDeviceError,
    SnapshotFileInvalidError,
    SourceChangedError,
)
from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.import_metadata import ImportMetadataService
from pt_snap_cli.core.models import FocusState, ImportMetadata, ImportOptions, ImportResult
from pt_snap_cli.core.snapshot_import_backend import SnapshotImportBackend

logger = logging.getLogger(__name__)

VALID_SUFFIXES = {".pkl", ".pickle"}


class ImportService:
    """Import PyTorch snapshot pickle files through the built-in backend."""

    def __init__(
        self,
        focus_service: FocusService | None = None,
        backend: SnapshotImportBackend | None = None,
        metadata_service: ImportMetadataService | None = None,
    ) -> None:
        self._focus_service: FocusService | None = focus_service
        self._backend: SnapshotImportBackend = backend or SnapshotImportBackend()
        self._metadata_service: ImportMetadataService = metadata_service or ImportMetadataService()

    def import_snapshot(self, options: ImportOptions) -> ImportResult:
        self._validate_snapshot_file(options.snapshot_file)
        output_dir = self._resolve_output_dir(options.snapshot_file, options.output_dir)
        db_path = self._backend.target_db_path(options.snapshot_file, output_dir)

        try:
            source_sha256 = self._metadata_service.calculate_sha256(options.snapshot_file)
        except ImportMetadataError as exc:
            raise ImportExecutionError(str(exc)) from exc

        decision = self._metadata_service.evaluate_cache(
            db_path=db_path,
            source_sha256=source_sha256,
            requested_device=options.device,
            force=options.force,
        )
        if decision.reused:
            if decision.metadata is None:
                raise AssertionError("Cache hit must include import metadata")
            focus_state = self._set_focus_if_requested(db_path, options)
            return ImportResult(
                db_path=db_path,
                device_id=options.device,
                focus_state=focus_state,
                reused=True,
                metadata=decision.metadata,
                cache_miss_reason=None,
            )

        completed_metadata: ImportMetadata | None = None

        def finalize_temp_db(tmp_db_path: Path) -> None:
            nonlocal completed_metadata
            try:
                final_sha256 = self._metadata_service.calculate_sha256(options.snapshot_file)
            except ImportMetadataError as exc:
                raise ImportExecutionError(str(exc)) from exc
            if final_sha256 != source_sha256:
                raise SourceChangedError(
                    "Snapshot source changed while import was running; existing database preserved."
                )

            try:
                metadata = self._metadata_service.build_metadata(
                    source_path=options.snapshot_file,
                    source_sha256=final_sha256,
                    requested_device=options.device,
                )
                self._metadata_service.write(tmp_db_path, metadata)
                inspection = self._metadata_service.inspect(tmp_db_path)
            except (ImportMetadataError, DatabaseSchemaError) as exc:
                raise ImportExecutionError(f"Imported database metadata is invalid: {exc}") from exc

            if inspection.status != "available" or inspection.metadata != metadata:
                raise ImportExecutionError("Imported database metadata validation failed.")
            completed_metadata = metadata

        focus_state: FocusState | None = None

        def set_focus_after_publish(published_db_path: Path) -> None:
            nonlocal focus_state
            focus_state = self._set_focus_if_requested(published_db_path, options)

        db_path = self._backend.dump_to_db(
            options.snapshot_file,
            output_dir,
            options.device,
            finalize_temp_db=finalize_temp_db,
            post_publish=set_focus_after_publish if options.set_focus else None,
        )
        if completed_metadata is None:
            raise ImportExecutionError("Imported database metadata was not produced.")

        return ImportResult(
            db_path=db_path,
            device_id=options.device,
            focus_state=focus_state,
            reused=False,
            metadata=completed_metadata,
            cache_miss_reason=decision.reason,
        )

    def _set_focus_if_requested(
        self,
        db_path: Path,
        options: ImportOptions,
    ) -> FocusState | None:
        if not options.set_focus:
            return None
        if self._focus_service is None:
            self._focus_service = FocusService()
        try:
            return self._focus_service.set_project_focus(
                db_path=db_path,
                device_id=options.device,
            )
        except (FocusFileInvalidError, DatabaseSchemaError, InvalidDeviceError, OSError) as exc:
            raise ImportExecutionError(
                f"Imported database cannot be registered as focus: {exc}"
            ) from exc

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
