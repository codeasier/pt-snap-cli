"""High-level API for PyTorch memory snapshot analysis.

This module provides a programmatic interface that both the CLI
and the MCP server can use. It has no MCP dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pt_snap_cli.config import Config
from pt_snap_cli.context import Context
from pt_snap_cli.query.executor import QueryExecutor
from pt_snap_cli.query.registry import (
    get_template_info as _get_template_info,
)
from pt_snap_cli.query.registry import (
    list_by_category_with_details,
    list_queries_with_details,
)


@dataclass
class FocusState:
    """Current focus state of the analyzer."""

    db_path: str | None
    device_id: int | None
    source: str
    available_devices: list[int]


class SnapshotAnalyzer:
    """Programmatic API for analyzing PyTorch memory snapshots."""

    def __init__(
        self,
        db_path: Path | None = None,
        device_id: int | None = None,
    ) -> None:
        self._config = Config()
        self._db_path = db_path
        self._device_id = device_id
        self._context: Context | None = None
        self._executor: QueryExecutor | None = None

    def _ensure_context(self) -> tuple[Context, QueryExecutor]:
        """Resolve focus and create context/executor if needed."""
        if self._context is not None and self._executor is not None:
            return self._context, self._executor

        resolved = self._config.resolve_focus(self._db_path, explicit_device_id=self._device_id)
        if resolved.db_path is None:
            raise RuntimeError("No database configured. Call set_focus() first.")
        self._context = Context(resolved.db_path)
        self._executor = QueryExecutor(self._context)
        return self._context, self._executor

    def get_focus(self) -> FocusState:
        """Get current focus state."""
        resolved = self._config.resolve_focus(self._db_path, explicit_device_id=self._device_id)
        devices: list[int] = []
        if resolved.db_path and resolved.db_path.exists():
            try:
                ctx = Context(resolved.db_path)
                devices = ctx.device_ids
            except Exception:
                pass
        return FocusState(
            db_path=str(resolved.db_path) if resolved.db_path else None,
            device_id=resolved.device_id,
            source=resolved.source,
            available_devices=devices,
        )

    def set_focus(self, db_path: str | None = None, device_id: int | None = None) -> FocusState:
        """Set focus to a new database/device."""
        if db_path:
            self._db_path = Path(db_path)
            # Validate immediately
            Context(self._db_path)
        if device_id is not None:
            self._device_id = device_id
        # Reset cached context so next _ensure_context re-resolves
        self._context = None
        self._executor = None
        return self.get_focus()

    def list_templates(self, category: str | None = None) -> list[dict]:
        """List available query templates."""
        if category:
            return list_by_category_with_details(category)
        return list_queries_with_details()

    def get_template_info(self, name: str) -> dict | None:
        """Get detailed template information."""
        return _get_template_info(name)

    def execute_query(
        self,
        template: str,
        params: dict[str, Any] | None = None,
        device_id: int | None = None,
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Execute a query template. Returns {total, returned, device_id, rows}."""
        ctx, executor = self._ensure_context()
        target_device = device_id or self._device_id
        if target_device is None and ctx.device_ids:
            target_device = ctx.device_ids[0]

        rows = executor.execute_template(template, params or {}, device_id=target_device)
        total = len(rows)
        if max_rows is not None and max_rows > 0:
            rows = rows[:max_rows]

        return {
            "total": total,
            "returned": len(rows),
            "device_id": target_device,
            "rows": rows,
        }
