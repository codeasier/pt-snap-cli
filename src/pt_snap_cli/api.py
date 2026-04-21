"""High-level API for PyTorch memory snapshot analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pt_snap_cli.config import Config
from pt_snap_cli.core import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusNotConfiguredError,
    FocusService,
    QueryService,
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
        self._focus_service = FocusService(self._config)
        self._query_service = QueryService(self._focus_service)

    def get_focus(self) -> FocusState:
        state = self._focus_service.get_focus(
            explicit_db_path=self._db_path,
            explicit_device_id=self._device_id,
        )
        return FocusState(
            db_path=str(state.db_path) if state.db_path is not None else None,
            device_id=state.device_id,
            source=state.source,
            available_devices=state.available_devices,
        )

    def set_focus(self, db_path: str | None = None, device_id: int | None = None) -> FocusState:
        if db_path is not None:
            try:
                self._focus_service.validate_session_db(db_path)
            except DatabaseMissingError as exc:
                raise FileNotFoundError(str(exc)) from exc
            except DatabaseSchemaError as exc:
                raise ValueError(str(exc)) from exc
            self._db_path = Path(db_path)
        if device_id is not None:
            self._device_id = device_id
        return self.get_focus()

    def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "name": template.name,
                "description": template.description,
                "category": template.category,
            }
            for template in self._query_service.list_templates(category)
        ]

    def get_template_info(self, name: str) -> dict[str, Any] | None:
        try:
            info = self._query_service.get_template_info(name)
        except Exception:
            return None

        return {
            "name": info.name,
            "description": info.description,
            "category": info.category,
            "devices": info.devices,
            "parameters": {
                param_name: {
                    "type": param.type,
                    "default": param.default,
                    "required": param.required,
                    "description": param.description,
                }
                for param_name, param in info.parameters.items()
            },
            "output_schema": info.output_schema,
        }

    def execute_query(
        self,
        template: str,
        params: dict[str, Any] | None = None,
        device_id: int | None = None,
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        try:
            result = self._query_service.execute_query(
                template=template,
                params=params,
                db_path=self._db_path,
                device_id=device_id if device_id is not None else self._device_id,
                max_rows=max_rows,
            )
        except FocusNotConfiguredError as exc:
            raise RuntimeError("No database configured. Call set_focus() first.") from exc
        return {
            "total": result.total,
            "returned": result.returned,
            "device_id": result.device_id,
            "rows": result.rows,
        }
