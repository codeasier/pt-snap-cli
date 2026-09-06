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
    ImportMetadataService,
    QueryService,
    TemplateNotFoundError,
)
from pt_snap_cli.core.context_cache import ContextCache


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
        *,
        context_cache: ContextCache | None = None,
    ) -> None:
        self._config = Config()
        self._db_path = db_path
        self._device_id = device_id
        self._focus_service = FocusService(self._config)
        # Share one context cache across the analyzer so that long-lived
        # analyzers (e.g. the MCP server singleton) reuse a single
        # SQLite connection and skip schema validation on every query.
        # Explicit ``is not None`` because an empty cache is falsy via
        # ``__len__`` and would be silently replaced otherwise.
        self._context_cache = context_cache if context_cache is not None else ContextCache()
        self._query_service = QueryService(self._focus_service, context_cache=self._context_cache)
        self._metadata_service = ImportMetadataService()

    @property
    def context_cache(self) -> ContextCache:
        """Return the :class:`ContextCache` this analyzer uses."""
        return self._context_cache

    def invalidate_context_cache(self, db_path: Path | str | None = None) -> None:
        """Drop a cached context (or every cached context when ``db_path`` is None)."""
        self._context_cache.invalidate(db_path)

    def get_focus(self) -> FocusState:
        state = self._focus_service.get_focus(
            explicit_db_path=self._db_path,
            explicit_device_id=self._device_id,
        )
        return FocusState(
            db_path=str(state.db_path) if state.db_path is not None else None,
            device_id=self._device_id if self._device_id is not None else state.device_id,
            source=state.source,
            available_devices=state.available_devices,
        )

    def set_focus(self, db_path: str | None = None, device_id: int | None = None) -> FocusState:
        if db_path is None and device_id is None:
            return self.get_focus()
        candidate_db = Path(db_path) if db_path is not None else self._db_path
        candidate_device = (
            device_id if db_path is not None or device_id is not None else self._device_id
        )
        if candidate_db is None and candidate_device is not None:
            resolved = self._focus_service.resolve_focus()
            if resolved.db_path is None:
                raise RuntimeError("No database configured. Set db_path before selecting a device.")
            candidate_db = resolved.db_path

        if candidate_db is not None:
            try:
                self._focus_service.validate_session_db(candidate_db, candidate_device)
            except DatabaseMissingError as exc:
                raise FileNotFoundError(str(exc)) from exc
            except DatabaseSchemaError as exc:
                raise ValueError(str(exc)) from exc

        if db_path is not None:
            self._db_path = Path(db_path)
            self._device_id = device_id
        elif device_id is not None:
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
        except TemplateNotFoundError:
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
                    "choices": param.choices,
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

    def get_database_metadata(self, db_path: str | None = None) -> dict[str, Any]:
        resolved = self._focus_service.resolve_focus(
            explicit_db_path=db_path if db_path is not None else self._db_path,
            explicit_device_id=self._device_id,
        )
        if resolved.db_path is None:
            raise RuntimeError("No database configured. Call set_focus() first.")
        try:
            inspection = self._metadata_service.inspect(resolved.db_path)
        except DatabaseMissingError as exc:
            raise FileNotFoundError(str(exc)) from exc
        except DatabaseSchemaError as exc:
            raise ValueError(str(exc)) from exc
        return self._metadata_service.inspection_to_dict(inspection)
