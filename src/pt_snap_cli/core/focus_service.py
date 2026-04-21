from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pt_snap_cli.config import Config, FocusResolutionError
from pt_snap_cli.context import Context, DatabaseNotFoundError, SchemaVersionError
from pt_snap_cli.core.errors import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusFileInvalidError,
    FocusNotConfiguredError,
    InvalidDeviceError,
)
from pt_snap_cli.core.models import FocusState, ResolvedFocus


class FocusService:
    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config()

    def resolve_focus(
        self,
        explicit_db_path: Path | str | None = None,
        explicit_device_id: int | None = None,
        start_dir: Path | None = None,
    ) -> ResolvedFocus:
        try:
            resolved = self._config.resolve_focus(
                explicit_db_path=explicit_db_path,
                explicit_device_id=explicit_device_id,
                start_dir=start_dir,
            )
        except FocusResolutionError as exc:
            raise FocusFileInvalidError(str(exc)) from exc

        return ResolvedFocus(
            db_path=resolved.db_path,
            device_id=resolved.device_id,
            source=resolved.source,
            focus_file=resolved.focus_file,
        )

    def get_focus(
        self,
        start_dir: Path | None = None,
        explicit_db_path: Path | str | None = None,
        explicit_device_id: int | None = None,
    ) -> FocusState:
        resolved = self.resolve_focus(explicit_db_path, explicit_device_id, start_dir)
        available_devices: list[int] = []

        if resolved.db_path is not None and resolved.db_path.exists():
            try:
                available_devices = Context(resolved.db_path).device_ids
            except (DatabaseNotFoundError, SchemaVersionError):
                available_devices = []

        return FocusState(
            db_path=resolved.db_path,
            device_id=resolved.device_id,
            available_devices=available_devices,
            source=resolved.source,
            focus_file=resolved.focus_file,
        )

    def set_project_focus(
        self,
        db_path: Path | str,
        device_id: int | None = None,
        base_dir: Path | None = None,
    ) -> FocusState:
        db_path = Path(db_path).expanduser().resolve()
        ctx = self._validated_context(db_path)
        self._validate_device(ctx, device_id)
        self._config.write_project_focus(db_path, base_dir=base_dir, device_id=device_id)
        return FocusState(
            db_path=db_path,
            device_id=device_id,
            available_devices=ctx.device_ids,
            source="project",
            focus_file=self._config.project_focus_path(base_dir),
        )

    def set_global_focus(self, db_path: Path | str, device_id: int | None = None) -> FocusState:
        db_path = Path(db_path).expanduser().resolve()
        ctx = self._validated_context(db_path)
        self._validate_device(ctx, device_id)
        self._config.current_db_path = db_path
        self._config.current_device_id = device_id
        return FocusState(
            db_path=db_path,
            device_id=device_id,
            available_devices=ctx.device_ids,
            source="global",
            focus_file=self._config.config_file,
        )

    def set_device(
        self,
        device_id: int,
        start_dir: Path | None = None,
        scope: str = "resolved",
    ) -> FocusState:
        resolved = self.resolve_focus(start_dir=start_dir)
        if resolved.db_path is None:
            raise FocusNotConfiguredError("No database set. Use 'pt-snap focus <db_path>' first.")

        ctx = self._validated_context(resolved.db_path)
        self._validate_device(ctx, device_id)

        if scope == "global" or (scope == "resolved" and resolved.source == "global"):
            self._config.current_device_id = device_id
            return FocusState(
                db_path=resolved.db_path,
                device_id=device_id,
                available_devices=ctx.device_ids,
                source="global",
                focus_file=self._config.config_file,
            )

        focus_file = self._config.write_project_focus(
            resolved.db_path,
            base_dir=start_dir,
            device_id=device_id,
        )
        return FocusState(
            db_path=resolved.db_path,
            device_id=device_id,
            available_devices=ctx.device_ids,
            source="project",
            focus_file=focus_file,
        )

    def clear_global_focus(self) -> None:
        self._config.clear()

    def show_global_config(self) -> dict[str, Any]:
        return self._config.show()

    def get_global_config_path(self) -> Path:
        return self._config.config_file

    def validate_session_db(self, db_path: Path | str) -> FocusState:
        db_path = Path(db_path).expanduser().resolve()
        ctx = self._validated_context(db_path)
        return FocusState(
            db_path=db_path,
            device_id=None,
            available_devices=ctx.device_ids,
            source="explicit",
            focus_file=None,
        )

    def _validated_context(self, db_path: Path) -> Context:
        try:
            return Context(db_path)
        except DatabaseNotFoundError as exc:
            raise DatabaseMissingError(str(exc)) from exc
        except (SchemaVersionError, sqlite3.DatabaseError) as exc:
            raise DatabaseSchemaError(str(exc)) from exc

    def _validate_device(self, ctx: Context, device_id: int | None) -> None:
        if device_id is None:
            return
        if device_id not in ctx.device_ids:
            raise InvalidDeviceError(f"Device {device_id} not found. Available: {ctx.device_ids}")
