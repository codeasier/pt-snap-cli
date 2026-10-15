"""Shared read-only transport checks; never checkpoint or repair source databases."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import DatabaseSchemaError
from .validation_budget import ValidationBudget, check_budget


def require_readonly_member(root: Path, member: Path, *, immutable: bool = False) -> None:
    parts = member.relative_to(root).parts
    for index in range(1, len(parts) + 1):
        if root.joinpath(*parts[:index]).is_symlink():
            raise DatabaseSchemaError(f"Dataset member must not use symlink paths: {member}")
    if member.resolve() != member or not member.is_file():
        raise DatabaseSchemaError(f"Dataset member is missing or not a canonical file: {member}")
    with member.open("rb") as source:
        header = source.read(20)
    wal = Path(str(member) + "-wal")
    for suffix in ("-wal", "-journal", "-shm"):
        sidecar = Path(str(member) + suffix)
        if sidecar.is_symlink():
            raise DatabaseSchemaError(f"Dataset member has an aliased SQLite sidecar: {member}")
        if sidecar.exists():
            if not immutable or suffix == "-journal" or header[18:20] != b"\x02\x02":
                raise DatabaseSchemaError(f"Dataset member has a live SQLite sidecar: {member}")
            if not sidecar.is_file() or not wal.is_file():
                raise DatabaseSchemaError(f"Invalid SQLite WAL transport: {member}")
            with wal.open("rb") as source:
                magic = source.read(4)
            if magic not in (b"", b"\x37\x7f\x06\x82", b"\x37\x7f\x06\x83"):
                raise DatabaseSchemaError(f"Invalid SQLite WAL header: {member}")
    # The immutable flag identifies finalized compatibility members here. The
    # connection helper still disables immutable transport when WAL is present.
    # Native datasets retain their non-WAL contract; no repair/checkpoint occurs.
    if not immutable and header[:16] == b"SQLite format 3\x00" and 2 in header[18:20]:
        raise DatabaseSchemaError(f"Dataset member uses persistent WAL mode: {member}")


def member_is_immutable(member: Path, compatibility: bool = True) -> bool:
    """Never bypass SQLite's WAL/locking protocol for a live compatible member."""
    return compatibility and not any(
        Path(str(member) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")
    )


def readonly_member_uri(member: Path, compatibility: bool = True) -> str:
    return (
        member.as_uri()
        + "?mode=ro"
        + ("&immutable=1" if member_is_immutable(member, compatibility) else "")
    )


def hash_file(path: Path, *, budget: ValidationBudget | None = None) -> str:
    check_budget(budget)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            check_budget(budget)
            digest.update(chunk)
    check_budget(budget)
    return digest.hexdigest()
