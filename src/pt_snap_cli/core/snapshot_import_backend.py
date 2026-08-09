from __future__ import annotations

import os
import pickle
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
            backup_fd: int | None = None
            try:
                if had_destination and post_publish is not None:
                    backup_fd, backup_name = tempfile.mkstemp(
                        dir=output_dir,
                        prefix=f".{db_path.name}.",
                        suffix=".rollback",
                    )
                    backup_path = Path(backup_name)
                    try:
                        try:
                            source_mode = db_path.stat().st_mode & 0o777
                        except OSError:
                            source_mode = 0o600
                        with open(db_path, "rb") as src:
                            while True:
                                chunk = src.read(1024 * 1024)
                                if not chunk:
                                    break
                                os.write(backup_fd, chunk)
                        os.fchmod(backup_fd, source_mode or 0o600)
                    except BaseException:
                        try:
                            os.close(backup_fd)
                        except OSError:
                            pass
                        backup_path.unlink(missing_ok=True)
                        backup_path = None
                        backup_fd = None
                        raise
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
                    if backup_fd is not None and backup_path is not None:
                        # Restore by writing through the secure fd; never go
                        # through the path name, which a concurrent attacker
                        # may have replaced with a symlink.
                        os.lseek(backup_fd, 0, os.SEEK_SET)
                        with open(db_path, "wb") as dst:
                            while True:
                                chunk = os.read(backup_fd, 1024 * 1024)
                                if not chunk:
                                    break
                                dst.write(chunk)
                        os.close(backup_fd)
                        backup_fd = None
                        backup_path.unlink(missing_ok=True)
                        backup_path = None
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

            if backup_fd is not None:
                try:
                    os.close(backup_fd)
                except OSError:
                    pass
                backup_fd = None
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
