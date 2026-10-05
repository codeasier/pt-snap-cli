"""Shared pre-open dataset checks. No repair, migration, WAL changes or SQLite opens."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import DatabaseSchemaError


def require_readonly_member(root: Path, member: Path, *, immutable: bool = False) -> None:
    parts = member.relative_to(root).parts
    for index in range(1, len(parts) + 1):
        if root.joinpath(*parts[:index]).is_symlink():
            raise DatabaseSchemaError(f"Dataset member must not use symlink paths: {member}")
    if member.resolve() != member or not member.is_file():
        raise DatabaseSchemaError(f"Dataset member is missing or not a canonical file: {member}")
    for suffix in ("-wal", "-journal", "-shm"):
        sidecar = Path(str(member) + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            raise DatabaseSchemaError(f"Dataset member has a live SQLite sidecar: {member}")
    with member.open("rb") as source:
        header = source.read(20)
    # Only finalized compatibility datasets use immutable transport. Native
    # datasets retain their non-WAL contract; no writer repair/checkpoint occurs.
    if not immutable and header[:16] == b"SQLite format 3\x00" and 2 in header[18:20]:
        raise DatabaseSchemaError(f"Dataset member uses persistent WAL mode: {member}")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
