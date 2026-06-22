from __future__ import annotations

import os
import pickle
import sqlite3
import tempfile
from pathlib import Path

from pt_snap_cli.core.errors import ImportExecutionError, ImportToolMissingError


class SnapshotImportBackend:
    """Stable adapter over the vendored snapshot-to-database implementation."""

    def dump_to_db(
        self,
        snapshot_file: Path,
        output_dir: Path,
        device: int | None = None,
    ) -> Path:
        db_path = output_dir / f"{snapshot_file.name}.db"
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dump_to_db = self._load_run_dump_to_db()

        with tempfile.TemporaryDirectory(dir=output_dir) as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            tmp_db_path = tmp_dir / db_path.name
            try:
                ok = run_dump_to_db(
                    snapshot_file=str(snapshot_file),
                    dump_dir=str(tmp_dir),
                    device=device,
                )
            except (OSError, sqlite3.DatabaseError, pickle.UnpicklingError, ValueError) as exc:
                raise ImportExecutionError(
                    f"Vendored snapshot import backend failed: {exc}"
                ) from exc

            if not ok:
                raise ImportExecutionError("Vendored snapshot import backend reported failure.")
            if not tmp_db_path.is_file():
                raise ImportExecutionError(f"Expected database not produced: {tmp_db_path}")

            try:
                os.replace(tmp_db_path, db_path)
            except OSError as exc:
                raise ImportExecutionError(
                    f"Vendored snapshot import backend failed: {exc}"
                ) from exc

        return db_path

    @staticmethod
    def _load_run_dump_to_db():
        try:
            from pt_snap_cli.vendor.memsnapdump.tools.adaptors.snapshot2db import run_dump_to_db
        except ImportError as exc:
            raise ImportToolMissingError(
                "Vendored snapshot import backend is unavailable. Reinstall pt-snap-cli; "
                "the package may be incomplete."
            ) from exc
        return run_dump_to_db
