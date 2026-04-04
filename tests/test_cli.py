"""Tests for CLI."""

from pathlib import Path

from typer.testing import CliRunner

from pt_snap_analyzer.cli import app

runner = CliRunner()


class TestCLI:
    """Test CLI commands."""

    def test_version_flag(self) -> None:
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "pt-snap-analyzer version" in result.stdout

    def test_help_flag(self) -> None:
        """Test --help flag."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "PyTorch Memory Snapshot Analysis Tool" in result.stdout

    def test_use_database_not_found(self, tmp_path: Path) -> None:
        """Test 'use' command with non-existent database."""
        non_existent = tmp_path / "not_found.db"
        result = runner.invoke(app, ["use", str(non_existent)])
        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_use_database_success(self, tmp_path: Path) -> None:
        """Test 'use' command with valid database."""
        import sqlite3

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE dictionary (
                `table` TEXT,
                `column` TEXT,
                `key` TEXT,
                `value` TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE trace_entry_0 (
                id INTEGER PRIMARY KEY
            )
        """)
        conn.commit()
        conn.close()

        result = runner.invoke(app, ["use", str(db_path)])
        assert result.exit_code == 0
        assert "Using database" in result.stdout
