"""Configuration management for pt-snap-analyzer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Config:
    """Configuration manager for pt-snap-analyzer.
    
    Manages user configuration including current database path.
    Configuration is stored in ~/.config/pt-snap-analyzer/config.json
    """
    
    def __init__(self) -> None:
        """Initialize configuration manager."""
        self.config_dir = Path.home() / ".config" / "pt-snap-analyzer"
        self.config_file = self.config_dir / "config.json"
        self._config: dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError):
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
        db_path = self._config.get("current_db_path")
        if db_path:
            return Path(db_path)
        return None
    
    @current_db_path.setter
    def current_db_path(self, db_path: Path | str) -> None:
        """Set current database path in configuration."""
        self._config["current_db_path"] = str(Path(db_path).expanduser().resolve())
        self._save()
    
    def clear_current_db_path(self) -> None:
        """Clear current database path from configuration."""
        self._config.pop("current_db_path", None)
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
