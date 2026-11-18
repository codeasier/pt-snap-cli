"""Disposable, content-addressed validation receipts for repeated imports.

Receipts live outside datasets. They never substitute file timestamps for byte
hashes, and are only consulted inside an import operation. Bump VERSION whenever
the validation semantics change, independently of the package version.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

VERSION = 1
_ENABLED: ContextVar[bool] = ContextVar("import_validation_receipts", default=False)


@contextmanager
def import_receipts() -> Iterator[None]:
    token = _ENABLED.set(True)
    try:
        yield
    finally:
        _ENABLED.reset(token)


def _path(root: Path, scope: str) -> Path | None:
    if not receipts_enabled():
        return None
    key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    try:
        return (
            Path.home()
            / ".cache"
            / "pt-snap-cli"
            / f"validation-v{VERSION}"
            / f"{key}-{scope}.json"
        )
    except (OSError, RuntimeError):
        return None


def import_validation_active() -> bool:
    """Import admission policy is independent of receipt/cache configuration."""
    return _ENABLED.get()


def receipts_enabled() -> bool:
    return _ENABLED.get() and os.environ.get("PT_SNAP_DATASET_CACHE") is None


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_receipt(root: Path, scope: str, fingerprint: str) -> dict[str, object] | None:
    path = _path(root, scope)
    if path is None:
        return None
    try:
        if path.is_symlink() or path.stat().st_size > 4096:
            return None
        envelope = json.loads(path.read_bytes())
        data = envelope["data"]
        if (
            envelope["sha256"] != hashlib.sha256(_encoded(data)).hexdigest()
            or data["fingerprint"] != fingerprint
            or not isinstance(data["payload"], dict)
        ):
            return None
        return data["payload"]
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return None


def save_receipt(root: Path, scope: str, fingerprint: str, payload: dict[str, object]) -> None:
    path = _path(root, scope)
    if path is None:
        return
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"fingerprint": fingerprint, "payload": payload}
        raw = _encoded({"data": data, "sha256": hashlib.sha256(_encoded(data)).hexdigest()})
        # One bounded record per dataset/scope, atomically replaced on change.
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(raw)
        os.replace(temporary, path)
    except OSError:
        # Read-only homes, full disks and stale receipts affect speed, not validity.
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
