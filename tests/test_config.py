"""Tests for configuration management."""

import json
from pathlib import Path

import pytest

from pt_snap_cli.config import ENV_DB_PATH, Config, ContextResolutionError


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


class TestDbContextResolver:
    """Test database context resolution."""

    @pytest.fixture(autouse=True)
    def mock_home_and_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Keep resolver tests isolated from the real user environment."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv(ENV_DB_PATH, raising=False)

    def test_write_and_resolve_project_context(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test writing and resolving project context."""
        monkeypatch.chdir(tmp_path)
        db_path = tmp_path / "test.db"
        db_path.touch()
        config = Config()

        context_file = config.write_project_db_path(db_path)
        resolved = config.resolve_db_context()

        assert context_file == tmp_path / ".pt-snap" / "context.json"
        assert resolved.db_path == db_path.resolve()
        assert resolved.source == "project"
        assert resolved.context_file == context_file

    def test_resolve_project_context_from_child_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test resolving project context by walking up parent directories."""
        project = tmp_path / "project"
        child = project / "nested" / "child"
        child.mkdir(parents=True)
        db_path = tmp_path / "test.db"
        db_path.touch()
        config = Config()
        config.write_project_db_path(db_path, base_dir=project)
        monkeypatch.chdir(child)

        resolved = config.resolve_db_context()

        assert resolved.db_path == db_path.resolve()
        assert resolved.source == "project"

    def test_resolve_priority_explicit_env_project_global(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test database context priority order."""
        monkeypatch.chdir(tmp_path)
        explicit_db = tmp_path / "explicit.db"
        env_db = tmp_path / "env.db"
        project_db = tmp_path / "project.db"
        global_db = tmp_path / "global.db"
        for db_path in (explicit_db, env_db, project_db, global_db):
            db_path.touch()

        config = Config()
        config.current_db_path = global_db
        config.write_project_db_path(project_db)
        monkeypatch.setenv(ENV_DB_PATH, str(env_db))

        explicit = config.resolve_db_context(explicit_db)
        env = config.resolve_db_context()
        monkeypatch.delenv(ENV_DB_PATH)
        project = config.resolve_db_context()
        (tmp_path / ".pt-snap" / "context.json").unlink()
        global_context = config.resolve_db_context()

        assert explicit.db_path == explicit_db
        assert explicit.source == "explicit"
        assert env.db_path == env_db
        assert env.source == "env"
        assert project.db_path == project_db.resolve()
        assert project.source == "project"
        assert global_context.db_path == global_db.resolve()
        assert global_context.source == "global"

    def test_project_context_is_cwd_scoped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test different working directories can use different contexts."""
        project_a = tmp_path / "project-a"
        project_b = tmp_path / "project-b"
        project_a.mkdir()
        project_b.mkdir()
        db_a = tmp_path / "a.db"
        db_b = tmp_path / "b.db"
        db_a.touch()
        db_b.touch()
        config = Config()
        config.write_project_db_path(db_a, base_dir=project_a)
        config.write_project_db_path(db_b, base_dir=project_b)

        monkeypatch.chdir(project_a)
        resolved_a = config.resolve_db_context()
        monkeypatch.chdir(project_b)
        resolved_b = config.resolve_db_context()

        assert resolved_a.db_path == db_a.resolve()
        assert resolved_b.db_path == db_b.resolve()

    def test_invalid_project_context_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test invalid project context JSON fails clearly."""
        monkeypatch.chdir(tmp_path)
        context_dir = tmp_path / ".pt-snap"
        context_dir.mkdir()
        (context_dir / "context.json").write_text("not-json")

        with pytest.raises(ContextResolutionError, match="Invalid project context file"):
            Config().resolve_db_context()

    def test_project_context_missing_db_key(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test project context without current_db_path fails clearly."""
        monkeypatch.chdir(tmp_path)
        context_dir = tmp_path / ".pt-snap"
        context_dir.mkdir()
        (context_dir / "context.json").write_text(json.dumps({"other": "value"}))

        with pytest.raises(ContextResolutionError, match="current_db_path"):
            Config().resolve_db_context()
