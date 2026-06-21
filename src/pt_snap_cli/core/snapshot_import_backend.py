from __future__ import annotations

from pathlib import Path

from pt_snap_cli.core.errors import ImportExecutionError, ImportToolMissingError
from pt_snap_cli.vendor.memsnapdump.tools.adaptors.snapshot2db import run_dump_to_db


class SnapshotImportBackend:
    """Stable adapter over the vendored snapshot-to-database implementation."""

    def dump_to_db(
        self,
        snapshot_file: Path,
        output_dir: Path,
        device: int | None = None,
    ) -> Path:
        db_path = output_dir / f"{snapshot_file.name}.db"

        try:
            ok = run_dump_to_db(
                snapshot_file=str(snapshot_file),
                dump_dir=str(output_dir),
                device=device,
            )
        except ImportError as exc:
            raise ImportToolMissingError(
                "Vendored snapshot import backend is unavailable. Reinstall pt-snap-cli; "
                "the package may be incomplete."
            ) from exc
        except Exception as exc:
            raise ImportExecutionError(f"Vendored snapshot import backend failed: {exc}") from exc

        if not ok:
            raise ImportExecutionError("Vendored snapshot import backend reported failure.")
        if not db_path.is_file():
            raise ImportExecutionError(f"Expected database not produced: {db_path}")

        return db_path
