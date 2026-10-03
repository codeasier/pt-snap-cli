"""High-level API for PyTorch memory snapshot analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from pt_snap_cli.config import Config
from pt_snap_cli.core import (
    CapabilityService,
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusFileInvalidError,
    FocusNotConfiguredError,
    FocusService,
    ImportMetadataService,
    OverviewService,
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
    callstack_layout: str | None = None
    callstack_layout_error: str | None = None


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
        # SnapshotAnalyzer instances reuse a single
        # SQLite connection and skip schema validation on every query.
        # Explicit ``is not None`` because an empty cache is falsy via
        # ``__len__`` and would be silently replaced otherwise.
        self._context_cache = context_cache if context_cache is not None else ContextCache()
        self._owns_context_cache: bool = context_cache is None
        self._closed: bool = False
        self._query_service = QueryService(self._focus_service, context_cache=self._context_cache)
        self._metadata_service = ImportMetadataService()
        self._capability_service = CapabilityService(
            query_service=self._query_service,
        )
        self._overview_service = OverviewService(
            self._focus_service,
            metadata_service=self._metadata_service,
            context_cache=self._context_cache,
        )

    def close(self) -> None:
        """End this analyzer's lifetime, closing only its internally owned cache.

        Safe to call repeatedly. An injected cache remains the caller's
        responsibility and can still be used by other analyzers.
        """
        if self._closed:
            return
        self._closed = True
        self._query_service.close()
        if self._owns_context_cache:
            self._context_cache.close()

    def __enter__(self) -> SnapshotAnalyzer:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SnapshotAnalyzer is closed.")

    @property
    def context_cache(self) -> ContextCache:
        """Return the :class:`ContextCache` this analyzer uses."""
        return self._context_cache

    def invalidate_context_cache(self, db_path: Path | str | None = None) -> None:
        """Drop cached contexts, including from an explicitly shared cache.

        This cleanup operation remains available after close(). While open,
        the analyzer can create fresh contexts on its next query or overview.
        """
        self._context_cache.invalidate(db_path)

    def get_focus(self) -> FocusState:
        self._ensure_open()
        state = self._focus_service.get_focus(
            explicit_db_path=self._db_path,
            explicit_device_id=self._device_id,
        )
        return FocusState(
            db_path=str(state.db_path) if state.db_path is not None else None,
            device_id=self._device_id if self._device_id is not None else state.device_id,
            source=state.source,
            available_devices=state.available_devices,
            callstack_layout=state.callstack_layout,
            callstack_layout_error=state.callstack_layout_error,
        )

    def set_focus(self, db_path: str | None = None, device_id: int | None = None) -> FocusState:
        self._ensure_open()
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
        self._ensure_open()
        return [
            {
                "name": template.name,
                "description": template.description,
                "category": template.category,
            }
            for template in self._query_service.list_templates(category)
        ]

    def get_template_info(self, name: str) -> dict[str, Any] | None:
        self._ensure_open()
        try:
            info = self._query_service.get_template_info(name)
        except TemplateNotFoundError:
            return None

        return self._query_service.template_info_to_dict(info)

    def execute_query(
        self,
        template: str,
        params: dict[str, Any] | None = None,
        device_id: int | None = None,
        max_rows: int | None = None,
        *,
        exact_total: bool = False,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        self._ensure_open()
        try:
            result = self._query_service.execute_query(
                template=template,
                params=params,
                db_path=self._db_path,
                device_id=device_id if device_id is not None else self._device_id,
                max_rows=max_rows,
                exact_total=exact_total,
                timeout_s=timeout_s,
            )
        except FocusNotConfiguredError as exc:
            raise RuntimeError("No database configured. Call set_focus() first.") from exc
        return {
            "total": result.total,
            "returned": result.returned,
            "device_id": result.device_id,
            "rows": result.rows,
            "template": result.template,
            "semantics_version": result.semantics_version,
            "has_more": result.has_more,
            "truncated": result.truncated,
            "total_is_exact": result.total_is_exact,
            "timeout_s": result.timeout_s,
        }

    def list_capabilities(self) -> dict[str, Any]:
        self._ensure_open()
        return self._capability_service.catalog_to_dict(self._capability_service.catalog())

    def get_database_overview(self, db_path: str | None = None) -> dict[str, Any]:
        self._ensure_open()
        resolved_path = db_path if db_path is not None else self._db_path
        try:
            overview = self._overview_service.inspect(resolved_path)
        except FocusNotConfiguredError as exc:
            raise RuntimeError("No database configured. Call set_focus() first.") from exc
        except FocusFileInvalidError as exc:
            raise ValueError(str(exc)) from exc
        except DatabaseMissingError as exc:
            raise FileNotFoundError(str(exc)) from exc
        except DatabaseSchemaError as exc:
            raise ValueError(str(exc)) from exc
        return self._overview_service.overview_to_dict(overview)

    def get_database_metadata(self, db_path: str | None = None) -> dict[str, Any]:
        self._ensure_open()
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
