"""Shell completion functions for CLI options."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pt_snap_cli.config import CURRENT_DB_KEY, Config


def complete_template_names() -> list[str]:
    """Return all registered query template names for shell completion."""
    from pt_snap_cli.query.registry import list_queries

    return sorted(list_queries())


def complete_categories() -> list[str]:
    """Return valid category names for shell completion."""
    return ["basic", "statistical", "business"]


def _resolve_db_for_completion() -> Path | None:
    """Resolve the database path using the same priority as the CLI.

    Priority: env var > project context > global config.
    """
    env_path = os.environ.get("PT_SNAP_DB_PATH")
    if env_path:
        return Path(env_path).expanduser()

    project_context = Config.find_project_context_path()
    if project_context:
        try:
            with open(project_context) as f:
                data = json.load(f)
            db_path = data.get(CURRENT_DB_KEY)
            if db_path:
                return Path(db_path).expanduser()
        except (json.JSONDecodeError, OSError):
            pass

    global_path = Config().current_db_path
    return global_path


def complete_device_ids() -> list[str]:
    """Return device IDs from the resolved database for shell completion."""
    import sqlite3

    db_path = _resolve_db_for_completion()
    if db_path is None or not db_path.exists():
        return []

    try:
        uri = f"file:{db_path}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'trace_entry_%'"
            )
            device_ids = []
            for row in cursor.fetchall():
                table_name = row[0]
                device_id = table_name.split("_")[-1]
                device_ids.append(device_id)
            return sorted(device_ids, key=int)
    except Exception:
        return []
