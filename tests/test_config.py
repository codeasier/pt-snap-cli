"""Tests for configuration management."""

import json
from pathlib import Path

from pt_snap_cli.config import Config


class TestConfig:
    """Test configuration management."""

    def test_config_init_empty(self, tmp_path: Path) -> None:
        """Test config initialization with no config file."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config = Config()
            assert not config.config_file.exists()
            assert config.current_db_path is None
            assert config.show() == {}
        finally:
            Path.home = original_home

    def test_config_set_db_path(self, tmp_path: Path) -> None:
        """Test setting database path."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config = Config()
            db_path = tmp_path / "test.db"
            db_path.touch()
            
            config.current_db_path = db_path
            
            assert config.config_file.exists()
            assert config.current_db_path == db_path.resolve()
            
            # Verify persisted to file
            config_data = json.loads(config.config_file.read_text())
            assert config_data["current_db_path"] == str(db_path.resolve())
        finally:
            Path.home = original_home

    def test_config_clear_db_path(self, tmp_path: Path) -> None:
        """Test clearing database path."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config = Config()
            db_path = tmp_path / "test.db"
            db_path.touch()
            
            config.current_db_path = db_path
            config.clear_current_db_path()
            
            assert config.current_db_path is None
            config_data = json.loads(config.config_file.read_text())
            assert "current_db_path" not in config_data
        finally:
            Path.home = original_home

    def test_config_get_set(self, tmp_path: Path) -> None:
        """Test generic get/set methods."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config = Config()
            
            config.set("test_key", "test_value")
            assert config.get("test_key") == "test_value"
            assert config.get("nonexistent", "default") == "default"
        finally:
            Path.home = original_home

    def test_config_clear_all(self, tmp_path: Path) -> None:
        """Test clearing all configuration."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config = Config()
            config.set("key1", "value1")
            config.set("key2", "value2")
            
            config.clear()
            
            assert config.show() == {}
            assert config.current_db_path is None
        finally:
            Path.home = original_home

    def test_config_validate_db_path_exists(self, tmp_path: Path) -> None:
        """Test validate_db_path when file exists."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config = Config()
            db_path = tmp_path / "test.db"
            db_path.touch()
            config.current_db_path = db_path
            
            assert config.validate_db_path() is True
            assert config.current_db_path is not None
        finally:
            Path.home = original_home

    def test_config_validate_db_path_not_exists(self, tmp_path: Path) -> None:
        """Test validate_db_path when file doesn't exist."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config = Config()
            db_path = tmp_path / "test.db"
            config.current_db_path = db_path
            
            assert config.validate_db_path() is False
            assert config.current_db_path is None  # Should be cleared
        finally:
            Path.home = original_home

    def test_config_load_from_file(self, tmp_path: Path) -> None:
        """Test loading config from existing file."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config_dir = tmp_path / ".config" / "pt-snap-cli"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "config.json"
            
            db_path = tmp_path / "existing.db"
            db_path.touch()
            config_file.write_text(json.dumps({
                "current_db_path": str(db_path),
                "other_key": "other_value"
            }))
            
            config = Config()
            assert config.current_db_path == db_path.resolve()
            assert config.get("other_key") == "other_value"
        finally:
            Path.home = original_home

    def test_config_load_invalid_json(self, tmp_path: Path) -> None:
        """Test loading config from invalid JSON file."""
        # Monkey-patch Path.home to use tmp_path
        original_home = Path.home
        Path.home = lambda: tmp_path
        try:
            config_dir = tmp_path / ".config" / "pt-snap-cli"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "config.json"
            config_file.write_text("invalid json {")
            
            config = Config()
            assert config.show() == {}
        finally:
            Path.home = original_home
