from __future__ import annotations

import copy
import os
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pt_snap_cli.config import Config, FocusResolutionError
from pt_snap_cli.context import Context, DatabaseNotFoundError, SchemaVersionError
from pt_snap_cli.core.dataset_resolver import DatasetResolver, ResolvedDataset
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
        callstack_layout: str | None = None
        callstack_layout_error: str | None = None

        if resolved.db_path is not None and resolved.db_path.exists():
            try:
                dataset = DatasetResolver().inspect(resolved.db_path)
                ctx = dataset if dataset is not None else Context(resolved.db_path)
                available_devices = ctx.device_ids
                callstack_layout = ctx.callstack_layout
                callstack_layout_error = ctx.callstack_layout_error
            except (DatabaseNotFoundError, SchemaVersionError):
                available_devices = []

        return FocusState(
            db_path=resolved.db_path,
            device_id=resolved.device_id,
            available_devices=available_devices,
            source=resolved.source,
            focus_file=resolved.focus_file,
            callstack_layout=callstack_layout,
            callstack_layout_error=callstack_layout_error,
        )

    @staticmethod
    def _safe_focus_path(path: Path) -> None:
        if path.resolve() != path or path.is_symlink() or (path.exists() and not path.is_file()):
            raise OSError(f"Unsafe project focus path: {path}")

    @staticmethod
    def _checkpoint_file(path: Path, content: bytes, mode: int) -> tuple[Path, tuple[int, int]]:
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=".focus.pt-snap-", suffix=".recovery")
        backup = Path(name)
        identity = os.fstat(fd)
        try:
            remaining = memoryview(content)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("Could not write focus recovery checkpoint")
                remaining = remaining[written:]
            os.fchmod(fd, mode)
            os.fsync(fd)
            FocusService._verify_checkpoint(backup, (identity.st_dev, identity.st_ino))
        except BaseException:
            try:
                FocusService._verify_checkpoint(backup, (identity.st_dev, identity.st_ino))
                backup.unlink()
            except OSError:
                pass
            raise
        finally:
            os.close(fd)
        return backup, (identity.st_dev, identity.st_ino)

    @staticmethod
    def _verify_checkpoint(path: Path, identity: tuple[int, int]) -> None:
        FocusService._safe_focus_path(path)
        info = path.lstat()
        if (info.st_dev, info.st_ino) != identity:
            raise OSError(f"Focus recovery checkpoint substituted: {path}")

    @staticmethod
    def _restore_project_focus(
        path: Path, backup: Path, identity: tuple[int, int], expected_bytes: bytes
    ) -> None:
        FocusService._safe_focus_path(path)
        FocusService._verify_checkpoint(backup, identity)
        if backup.read_bytes() != expected_bytes:
            raise OSError("Focus recovery checkpoint content changed; preserve evidence")
        os.replace(backup, path)

    @contextmanager
    def project_focus_transaction(self) -> Iterator[None]:
        """Import-only compensation, including writes that mutate and THEN raise.

        Store old bytes verbatim, not normalized JSON. An I/O/alias failure during
        compensation preserves the checkpoint and reports its recovery location.
        This is not a concurrency lock or an arbitrary-crash atomicity promise.
        """
        from .errors import ImportExecutionError

        path = self._config.project_focus_path()
        self._safe_focus_path(path)
        old = path.read_bytes() if path.exists() else None
        state = copy.deepcopy(self._config._config)
        backup: Path | None = None
        identity: tuple[int, int] | None = None
        path.parent.mkdir(parents=True, exist_ok=True)
        backup, identity = self._checkpoint_file(
            path,
            old if old is not None else b"",
            path.stat().st_mode & 0o777 if old is not None else 0o600,
        )
        preserve = False
        try:
            yield
        except BaseException as focus_error:
            self._config._config = state
            try:
                self._safe_focus_path(path)
                if old is None:
                    if path.exists():
                        # Verified exact path; never unlink a symlink target.
                        path.unlink()
                elif not path.exists() or path.read_bytes() != old:
                    assert backup is not None and identity is not None
                    try:
                        self._restore_project_focus(path, backup, identity, old)
                    except BaseException:
                        # A rename may have restored the exact bytes BEFORE an
                        # injected/late I/O exception. Verify the actual outcome.
                        self._safe_focus_path(path)
                        if not path.exists() or path.read_bytes() != old:
                            raise
                    self._safe_focus_path(path)
                    if not path.exists() or path.read_bytes() != old:
                        raise OSError(
                            "Project focus was not restored exactly; preserve recovery evidence"
                        )
                    if not backup.exists():
                        backup = None
            except BaseException as rollback_error:
                preserve = True
                raise ImportExecutionError(
                    f"Focus update failed and focus rollback also failed: {rollback_error}. "
                    f"Recovery focus checkpoint: {backup}; prior focus existed: {old is not None}."
                ) from focus_error
            raise
        finally:
            if backup is not None and identity is not None and not preserve:
                # Failure to clean a committed checkpoint is safer than masking
                # the real transaction outcome or deleting a substituted path.
                try:
                    self._verify_checkpoint(backup, identity)
                    backup.unlink()
                except OSError:
                    pass

    def set_project_focus(
        self,
        db_path: Path | str,
        device_id: int | None = None,
        base_dir: Path | None = None,
    ) -> FocusState:
        db_path = Path(db_path).expanduser().absolute()
        ctx = self._validated_context(db_path)
        db_path = db_path.resolve()
        self._validate_device(ctx, device_id)
        self._config.write_project_focus(db_path, base_dir=base_dir, device_id=device_id)
        return FocusState(
            db_path=db_path,
            device_id=device_id,
            available_devices=ctx.device_ids,
            source="project",
            focus_file=self._config.project_focus_path(base_dir),
            callstack_layout=ctx.callstack_layout,
            callstack_layout_error=ctx.callstack_layout_error,
        )

    def set_global_focus(self, db_path: Path | str, device_id: int | None = None) -> FocusState:
        db_path = Path(db_path).expanduser().absolute()
        ctx = self._validated_context(db_path)
        db_path = db_path.resolve()
        self._validate_device(ctx, device_id)
        self._config.write_global_focus(db_path, device_id=device_id)
        return FocusState(
            db_path=db_path,
            device_id=device_id,
            available_devices=ctx.device_ids,
            source="global",
            focus_file=self._config.config_file,
            callstack_layout=ctx.callstack_layout,
            callstack_layout_error=ctx.callstack_layout_error,
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
                callstack_layout=ctx.callstack_layout,
                callstack_layout_error=ctx.callstack_layout_error,
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
            callstack_layout=ctx.callstack_layout,
            callstack_layout_error=ctx.callstack_layout_error,
        )

    def clear_global_focus(self) -> None:
        self._config.clear()

    def show_global_config(self) -> dict[str, Any]:
        return self._config.show()

    def get_global_config_path(self) -> Path:
        return self._config.config_file

    def validate_session_db(
        self,
        db_path: Path | str,
        device_id: int | None = None,
    ) -> FocusState:
        db_path = Path(db_path).expanduser().absolute()
        ctx = self._validated_context(db_path)
        db_path = db_path.resolve()
        self._validate_device(ctx, device_id)
        return FocusState(
            db_path=db_path,
            device_id=device_id,
            available_devices=ctx.device_ids,
            source="explicit",
            focus_file=None,
            callstack_layout=ctx.callstack_layout,
            callstack_layout_error=ctx.callstack_layout_error,
        )

    def _validated_context(self, db_path: Path) -> Context | ResolvedDataset:
        dataset = DatasetResolver().inspect(db_path)
        if dataset is not None:
            return dataset
        try:
            return Context(db_path)
        except DatabaseNotFoundError as exc:
            raise DatabaseMissingError(str(exc)) from exc
        except (SchemaVersionError, sqlite3.DatabaseError) as exc:
            raise DatabaseSchemaError(str(exc)) from exc

    def _validate_device(self, ctx: Context | ResolvedDataset, device_id: int | None) -> None:
        if device_id is None:
            return
        if device_id not in ctx.device_ids:
            raise InvalidDeviceError(f"Device {device_id} not found. Available: {ctx.device_ids}")
