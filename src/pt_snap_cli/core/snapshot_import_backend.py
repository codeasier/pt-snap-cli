from __future__ import annotations

import os
import pickle
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from pathlib import Path

from pt_snap_cli.core.errors import ImportExecutionError, ImportToolMissingError


class SnapshotImportBackend:
    """Stable adapter over the first-party snapshot-to-database implementation."""

    def dump_to_db(
        self,
        snapshot_file: Path,
        output_dir: Path,
        device: int | None = None,
        finalize_temp_db: Callable[[Path], None] | None = None,
        post_publish: Callable[[Path], None] | None = None,
    ) -> Path:
        db_path = self.target_db_path(snapshot_file, output_dir)
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
                raise ImportExecutionError(f"Snapshot import backend failed: {exc}") from exc

            if not ok:
                raise ImportExecutionError("Snapshot import backend reported failure.")
            if not tmp_db_path.is_file():
                raise ImportExecutionError(f"Expected database not produced: {tmp_db_path}")

            if finalize_temp_db is not None:
                finalize_temp_db(tmp_db_path)

            had_destination = db_path.exists()
            backup_path: Path | None = None
            try:
                if had_destination and post_publish is not None:
                    fd, backup_name = tempfile.mkstemp(
                        dir=output_dir,
                        prefix=f".{db_path.name}.",
                        suffix=".rollback",
                    )
                    os.close(fd)
                    backup_path = Path(backup_name)
                    backup_path.unlink()
                    try:
                        os.link(db_path, backup_path)
                    except OSError:
                        shutil.copy2(db_path, backup_path)
                os.replace(tmp_db_path, db_path)
            except OSError as exc:
                if backup_path is not None:
                    try:
                        backup_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                raise ImportExecutionError(f"Snapshot import backend failed: {exc}") from exc

            try:
                if post_publish is not None:
                    post_publish(db_path)
            except BaseException as publish_exc:
                try:
                    if backup_path is not None:
                        os.replace(backup_path, db_path)
                    else:
                        db_path.unlink(missing_ok=True)
                except OSError as rollback_exc:
                    recovery = (
                        f" Recovery backup: {backup_path}."
                        if backup_path is not None and backup_path.exists()
                        else ""
                    )
                    raise ImportExecutionError(
                        "Snapshot import post-publication action failed and database rollback "
                        f"also failed: {rollback_exc}.{recovery}"
                    ) from publish_exc
                raise

            if backup_path is not None:
                try:
                    backup_path.unlink(missing_ok=True)
                except OSError:
                    # Publication and focus are committed; an orphan backup is safer
                    # than reporting a failure after the transaction succeeded.
                    pass

        return db_path

    @staticmethod
    def target_db_path(snapshot_file: Path, output_dir: Path) -> Path:
        return output_dir / f"{snapshot_file.name}.db"

    @staticmethod
    def _load_run_dump_to_db():
        try:
            from pt_snap_cli.snapshot.tools.adaptors.snapshot2db import run_dump_to_db
        except ImportError as exc:
            raise ImportToolMissingError(
                "Snapshot import backend is unavailable. Reinstall pt-snap-cli; "
                "the package may be incomplete."
            ) from exc
        return run_dump_to_db
