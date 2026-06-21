from __future__ import annotations

import logging
import os
import pickle
import sqlite3
from pathlib import Path

from pt_snap_cli.core.errors import ImportExecutionError, ImportToolMissingError
from pt_snap_cli.vendor.memsnapdump.tools.adaptors.snapshot2db import run_dump_to_db

logger = logging.getLogger(__name__)


class SnapshotImportBackend:
    """Stable adapter over the vendored snapshot-to-database implementation."""

    def dump_to_db(
        self,
        snapshot_file: Path,
        output_dir: Path,
        device: int | None = None,
    ) -> Path:
        # Single source of truth for the .db path: must match the expression
        # used inside the vendored run_dump_to_db closure (snapshot_file.name + ".db").
        db_path = output_dir / f"{snapshot_file.name}.db"

        self._ensure_fresh_db(db_path)

        try:
            ok = run_dump_to_db(
                snapshot_file=str(snapshot_file),
                dump_dir=str(output_dir),
                device=device,
            )
        except ImportError as exc:
            # The vendored closure was not importable at runtime — this is a
            # packaging problem, not a user-facing data error.
            raise ImportToolMissingError(
                "Vendored snapshot import backend is unavailable. Reinstall pt-snap-cli; "
                "the package may be incomplete."
            ) from exc
        except (OSError, sqlite3.DatabaseError, pickle.UnpicklingError, ValueError) as exc:
            # Narrow, observable failure modes: filesystem, sqlite, pickle parse,
            # or vendor validation (e.g. "device not found"). Other exception
            # types (MemoryError, KeyboardInterrupt, ...) are intentionally left
            # to propagate untouched so the original traceback is preserved.
            raise ImportExecutionError(f"Vendored snapshot import backend failed: {exc}") from exc

        if not ok:
            raise ImportExecutionError("Vendored snapshot import backend reported failure.")
        if not db_path.is_file():
            raise ImportExecutionError(f"Expected database not produced: {db_path}")

        return db_path

    @staticmethod
    def _ensure_fresh_db(db_path: Path) -> None:
        """Remove an existing target .db before delegating to the vendor.

        The vendored SnapshotDb opens its database in ``auto_create=True`` mode
        and silently ``DROP TABLE``s any pre-existing tables for the old device
        schema on ``__init__``. That means re-running ``pt-snap import`` against
        a populated .db would destroy user data without warning. We delete the
        target file here (with a log message) so the behavior is explicit and
        logged, while keeping the vendored closure unchanged.
        """
        if db_path.exists() and db_path.is_file():
            logger.warning(
                "Overwriting existing database at %s (pt-snap import always regenerates the target).",
                db_path,
            )
            os.remove(db_path)
