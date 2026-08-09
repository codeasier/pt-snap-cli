"""Focus management for pt-snap-cli."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENV_DB_PATH = "PT_SNAP_DB_PATH"
PROJECT_FOCUS_DIR = ".pt-snap"
PROJECT_FOCUS_FILE = "focus.json"
DB_PATH_KEY = "db_path"
DEVICE_ID_KEY = "device_id"


class FocusResolutionError(ValueError):
    """Raised when a configured focus cannot be read."""

    pass


@dataclass(frozen=True)
class ResolvedFocus:
    """Resolved focus (database + optional device) with its source."""

    db_path: Path | None
    source: str
    focus_file: Path | None = None
    device_id: int | None = None

    @property
    def is_configured(self) -> bool:
        """Return whether a database path was resolved."""
        return self.db_path is not None


class Config:
    """Configuration manager for pt-snap-cli.

    Manages user configuration including current database path and device ID.
    Configuration is stored in ~/.config/pt-snap-cli/config.json
    """

    def __init__(self) -> None:
        """Initialize configuration manager."""
        self.config_dir = Path.home() / ".config" / "pt-snap-cli"
        self.config_file = self.config_dir / "config.json"
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    self._config = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._config = {}
        else:
            self._config = {}

    @staticmethod
    def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
        """Publish JSON without truncating an existing file on failure."""
        try:
            mode = path.stat().st_mode & 0o777
        except FileNotFoundError:
            mode = 0o600
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp_path, mode)
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

    def _save(self, updated: dict[str, Any]) -> None:
        """Persist and then commit an updated in-memory configuration."""
        self._write_json_atomic(self.config_file, updated)
        self._config = updated

    @property
    def current_db_path(self) -> Path | None:
        """Get current database path from configuration."""
        db_path = self._config.get(DB_PATH_KEY)
        if db_path:
            return Path(db_path).expanduser()
        return None

    @current_db_path.setter
    def current_db_path(self, db_path: Path | str) -> None:
        """Set current database path in configuration."""
        updated = self._config.copy()
        updated[DB_PATH_KEY] = str(Path(db_path).expanduser().resolve())
        self._save(updated)

    def clear_current_db_path(self) -> None:
        """Clear current database path from configuration."""
        updated = self._config.copy()
        updated.pop(DB_PATH_KEY, None)
        self._save(updated)

    @property
    def current_device_id(self) -> int | None:
        """Get current device ID from configuration."""
        return self._config.get(DEVICE_ID_KEY)

    @current_device_id.setter
    def current_device_id(self, device_id: int | None) -> None:
        """Set current device ID in configuration."""
        updated = self._config.copy()
        if device_id is not None:
            updated[DEVICE_ID_KEY] = device_id
        else:
            updated.pop(DEVICE_ID_KEY, None)
        self._save(updated)

    def validate_db_path(self) -> bool:
        """Validate that the current database path exists."""
        db_path = self.current_db_path
        if db_path and db_path.exists():
            return True
        if db_path:
            self.clear_current_db_path()
        return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        updated = self._config.copy()
        updated[key] = value
        self._save(updated)

    def clear(self) -> None:
        """Clear all configuration."""
        self._save({})

    def show(self) -> dict[str, Any]:
        """Show current configuration."""
        return self._config.copy()

    @staticmethod
    def project_focus_path(base_dir: Path | None = None) -> Path:
        """Return the project focus file path to write in a directory."""
        root = (base_dir or Path.cwd()).resolve()
        return root / PROJECT_FOCUS_DIR / PROJECT_FOCUS_FILE

    @staticmethod
    def find_project_focus_path(start_dir: Path | None = None) -> Path | None:
        """Find the nearest project focus file from a directory upward."""
        current = (start_dir or Path.cwd()).resolve()
        if current.is_file():
            current = current.parent

        for directory in (current, *current.parents):
            focus_file = directory / PROJECT_FOCUS_DIR / PROJECT_FOCUS_FILE
            if focus_file.exists():
                return focus_file
        return None

    def write_project_focus(
        self, db_path: Path | str, base_dir: Path | None = None, device_id: int | None = None
    ) -> Path:
        """Write a project-scoped focus file with db_path and optional device_id."""
        focus_file = self.project_focus_path(base_dir)
        focus_file.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {DB_PATH_KEY: str(Path(db_path).expanduser().resolve())}
        if device_id is not None:
            data[DEVICE_ID_KEY] = device_id
        self._write_json_atomic(focus_file, data)
        return focus_file

    def write_global_focus(self, db_path: Path | str, device_id: int | None = None) -> Path:
        """Write the database and optional device as one global config update."""
        updated = self._config.copy()
        updated[DB_PATH_KEY] = str(Path(db_path).expanduser().resolve())
        if device_id is None:
            updated.pop(DEVICE_ID_KEY, None)
        else:
            updated[DEVICE_ID_KEY] = device_id
        self._save(updated)
        return self.config_file

    def get_project_focus(
        self, start_dir: Path | None = None
    ) -> tuple[Path, Path, int | None] | None:
        """Return the nearest project focus data: (db_path, focus_file, device_id)."""
        focus_file = self.find_project_focus_path(start_dir)
        if focus_file is None:
            return None

        try:
            with open(focus_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise FocusResolutionError(f"Invalid project focus file: {focus_file}") from exc

        db_path = data.get(DB_PATH_KEY) or data.get("current_db_path")
        if not db_path:
            raise FocusResolutionError(f"Project focus file has no {DB_PATH_KEY!r}: {focus_file}")
        device_id = data.get(DEVICE_ID_KEY)
        return Path(db_path).expanduser(), focus_file, device_id

    def resolve_focus(
        self,
        explicit_db_path: Path | str | None = None,
        explicit_device_id: int | None = None,
        start_dir: Path | None = None,
    ) -> ResolvedFocus:
        """Resolve focus (db_path + device_id) using explicit, env, project, then global."""
        if explicit_db_path is not None:
            return ResolvedFocus(
                Path(explicit_db_path).expanduser(), "explicit", None, explicit_device_id
            )

        env_db_path = os.environ.get(ENV_DB_PATH)
        if env_db_path:
            return ResolvedFocus(Path(env_db_path).expanduser(), "env", None, None)

        project_focus = self.get_project_focus(start_dir)
        if project_focus is not None:
            db_path, focus_file, device_id = project_focus
            return ResolvedFocus(db_path, "project", focus_file, device_id)

        global_db_path = self.current_db_path
        if global_db_path is not None:
            global_device_id = self.current_device_id
            return ResolvedFocus(global_db_path, "global", self.config_file, global_device_id)

        return ResolvedFocus(None, "none", None, None)
