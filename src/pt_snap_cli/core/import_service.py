from __future__ import annotations

import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pt_snap_cli.core.errors import (
    ImportExecutionError,
    ImportToolMissingError,
    SnapshotFileInvalidError,
)
from pt_snap_cli.core.models import ImportOptions, ImportResult

if TYPE_CHECKING:
    from pt_snap_cli.core.focus_service import FocusService

VALID_SUFFIXES = {".pkl", ".pickle"}

try:
    from memsnapdump.tools.adaptors.snapshot2db import (  # pyright: ignore[reportMissingImports]
        run_dump_to_db as _upstream_run_dump_to_db,
    )
except ImportError:
    _upstream_run_dump_to_db: Any = None


class ImportService:
    """Import PyTorch snapshot pickle files through the source-integrated MemSnapDump API.

    The upstream tool is imported lazily at module load so this package can still be
    imported without the optional dependency. All upstream execution goes through a
    single private call point for testability. There is intentionally no subprocess
    fallback because this PR integrates against MemSnapDump source directly, not a
    published PyPI command contract.
    """

    def __init__(self, focus_service: FocusService | None = None) -> None:
        self._focus_service = focus_service

    def import_snapshot(self, options: ImportOptions) -> ImportResult:
        self._validate_snapshot_file(options.snapshot_file)
        output_dir = self._resolve_output_dir(options.snapshot_file, options.output_dir)

        if _upstream_run_dump_to_db is None:
            raise ImportToolMissingError(
                "memsnapdump package is required; install with pip install -e .[memsnapdump] "
                "(or pip install /tmp/MemSnapDump)"
            )

        try:
            self._run_dump_to_db(
                snapshot_file=str(options.snapshot_file),
                dump_dir=str(output_dir),
                device=options.device,
            )
        except TypeError as exc:
            # Monkeypatched / misconfigured call point -> treat as missing tool.
            if "NoneType" in str(exc) and "not callable" in str(exc):
                raise ImportToolMissingError(
                    "memsnapdump call point is unavailable; install with "
                    "pip install -e .[memsnapdump]"
                ) from exc
            raise ImportExecutionError(f"memsnapdump run_dump_to_db failed: {exc}") from exc
        except Exception as exc:
            raise ImportExecutionError(f"memsnapdump run_dump_to_db failed: {exc}") from exc

        db_path = output_dir / (options.snapshot_file.name + ".db")
        if not db_path.is_file():
            raise ImportExecutionError(f"Expected database not produced: {db_path}")

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

    def _run_dump_to_db(
        self,
        snapshot_file: str,
        dump_dir: str,
        device: int | None,
    ) -> bool:
        kwargs: dict[str, Any] = {"snapshot_file": snapshot_file, "dump_dir": dump_dir}
        if device is not None:
            kwargs["device"] = device
        assert _upstream_run_dump_to_db is not None  # checked by import_snapshot
        return _upstream_run_dump_to_db(**kwargs)

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
