"""Configuration management for pt-snap-cli."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENV_DB_PATH = "PT_SNAP_DB_PATH"
PROJECT_CONTEXT_DIR = ".pt-snap"
PROJECT_CONTEXT_FILE = "context.json"
CURRENT_DB_KEY = "current_db_path"


class ContextResolutionError(ValueError):
    """Raised when a configured database context cannot be read."""

    pass


@dataclass(frozen=True)
class ResolvedDbContext:
    """Resolved database context with its source."""

    db_path: Path | None
    source: str
    context_file: Path | None = None

    @property
    def is_configured(self) -> bool:
        """Return whether a database path was resolved."""
        return self.db_path is not None


class Config:
    """Configuration manager for pt-snap-cli.

    Manages user configuration including current database path.
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

    def _save(self) -> None:
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self._config, f, indent=2)

    @property
    def current_db_path(self) -> Path | None:
        """Get current database path from configuration."""
        db_path = self._config.get(CURRENT_DB_KEY)
        if db_path:
            return Path(db_path).expanduser()
        return None

    @current_db_path.setter
    def current_db_path(self, db_path: Path | str) -> None:
        """Set current database path in configuration."""
        self._config[CURRENT_DB_KEY] = str(Path(db_path).expanduser().resolve())
        self._save()

    def clear_current_db_path(self) -> None:
        """Clear current database path from configuration."""
        self._config.pop(CURRENT_DB_KEY, None)
        self._save()

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
        self._config[key] = value
        self._save()

    def clear(self) -> None:
        """Clear all configuration."""
        self._config = {}
        self._save()

    def show(self) -> dict[str, Any]:
        """Show current configuration."""
        return self._config.copy()

    @staticmethod
    def project_context_path(base_dir: Path | None = None) -> Path:
        """Return the project context file path to write in a directory."""
        root = (base_dir or Path.cwd()).resolve()
        return root / PROJECT_CONTEXT_DIR / PROJECT_CONTEXT_FILE

    @staticmethod
    def find_project_context_path(start_dir: Path | None = None) -> Path | None:
        """Find the nearest project context file from a directory upward."""
        current = (start_dir or Path.cwd()).resolve()
        if current.is_file():
            current = current.parent

        for directory in (current, *current.parents):
            context_file = directory / PROJECT_CONTEXT_DIR / PROJECT_CONTEXT_FILE
            if context_file.exists():
                return context_file
        return None

    def write_project_db_path(self, db_path: Path | str, base_dir: Path | None = None) -> Path:
        """Write a project-scoped database path and return the context file."""
        context_file = self.project_context_path(base_dir)
        context_file.parent.mkdir(parents=True, exist_ok=True)
        data = {CURRENT_DB_KEY: str(Path(db_path).expanduser().resolve())}
        with open(context_file, "w") as f:
            json.dump(data, f, indent=2)
        return context_file

    def get_project_db_path(self, start_dir: Path | None = None) -> tuple[Path, Path] | None:
        """Return the nearest project database path and its context file."""
        context_file = self.find_project_context_path(start_dir)
        if context_file is None:
            return None

        try:
            with open(context_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise ContextResolutionError(
                f"Invalid project context file: {context_file}"
            ) from exc

        db_path = data.get(CURRENT_DB_KEY)
        if not db_path:
            raise ContextResolutionError(
                f"Project context file has no {CURRENT_DB_KEY!r}: {context_file}"
            )
        return Path(db_path).expanduser(), context_file

    def resolve_db_context(
        self,
        explicit_db_path: Path | str | None = None,
        start_dir: Path | None = None,
    ) -> ResolvedDbContext:
        """Resolve database path using explicit, env, project, then global config."""
        if explicit_db_path is not None:
            return ResolvedDbContext(Path(explicit_db_path).expanduser(), "explicit")

        env_db_path = os.environ.get(ENV_DB_PATH)
        if env_db_path:
            return ResolvedDbContext(Path(env_db_path).expanduser(), "env")

        project_db = self.get_project_db_path(start_dir)
        if project_db is not None:
            db_path, context_file = project_db
            return ResolvedDbContext(db_path, "project", context_file)

        global_db_path = self.current_db_path
        if global_db_path is not None:
            return ResolvedDbContext(global_db_path, "global", self.config_file)

        return ResolvedDbContext(None, "none")
