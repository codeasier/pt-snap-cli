"""Versioned logical attestation for finalized, caller-owned compatibility members.

This is an integrity baseline, not authentication of an untrusted manifest. It
covers every original schema object and table. Only a new, ordinary allocation
cache table for the member's own device can be ignored during comparison.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import struct
from contextlib import closing
from pathlib import Path

CONTENT_VERSION = 1


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _row_bytes(*values: object) -> bytes:
    """Injective storage-class encoding; length framing retains empty/NULL/rows."""
    result = bytearray()
    for value in values:
        if value is None:
            tag, payload = b"n", b""
        elif type(value) is int:
            tag, payload = b"i", str(value).encode("ascii")
        elif type(value) is float:
            tag, payload = b"f", struct.pack(">d", value)
        elif isinstance(value, str):
            tag, payload = b"t", value.encode("utf-8")
        elif isinstance(value, bytes):
            tag, payload = b"b", value
        else:
            raise ValueError("Unsupported SQLite storage class")
        result.extend(tag + len(payload).to_bytes(8, "big") + payload)
    return bytes(result)


def _schema(conn: sqlite3.Connection) -> list[list[str | None]]:
    # rootpage is physical allocation, not semantic schema. Include internal
    # tables and indexes (whose SQL can be NULL), views and triggers in baseline.
    return [
        list(row)
        for row in conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name COLLATE BINARY"
        )
    ]


def _table_content(conn: sqlite3.Connection, name: str) -> dict[str, object]:
    # SQLite sorts canonical BLOB row encodings, not collated/coerced SQL values.
    # Stream the sorted result, preserving duplicate multiplicity. No whole-table
    # Python materialization, executable dump, or modification of the member.
    columns = [row[1] for row in conn.execute(f"PRAGMA table_xinfo({_quote(name)})")]
    arguments = ",".join(_quote(column) for column in columns)
    digest = hashlib.sha256(b"pt-snap-member-table-v1\0")
    count = 0
    for (encoded,) in conn.execute(
        f"SELECT pt_snap_row({arguments}) AS encoded FROM {_quote(name)} ORDER BY encoded"
    ):
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def member_content(path: Path) -> dict[str, object]:
    """Caller must preflight and bracket finalized members with file guards."""
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.create_function("pt_snap_row", -1, _row_bytes, deterministic=True)
        schema = _schema(conn)
        tables = {}
        for kind, name, _, sql in schema:
            if kind == "table":
                if not isinstance(name, str) or (
                    sql and re.match(r"CREATE\s+VIRTUAL\s+TABLE\s", sql, re.IGNORECASE)
                ):
                    raise ValueError("Unsupported virtual table in compatible content proof")
                tables[name] = _table_content(conn, name)
        return {"schema": schema, "tables": tables}


def validate_member_content(proof: object) -> None:
    """Fail closed for malformed evidence even on the byte-identical fast path."""
    if not isinstance(proof, dict) or set(proof) != {"schema", "tables"}:
        raise ValueError("Malformed compatible base-content proof")
    schema, tables = proof["schema"], proof["tables"]
    if not isinstance(schema, list) or not isinstance(tables, dict):
        raise ValueError("Malformed compatible base-content proof")
    names = set()
    table_names = set()
    for item in schema:
        if (
            not isinstance(item, list)
            or len(item) != 4
            or item[0] not in ("table", "index", "view", "trigger")
            or not all(isinstance(value, str) and value for value in item[:3])
            or (item[3] is not None and not isinstance(item[3], str))
            or (item[0], item[1]) in names
        ):
            raise ValueError("Malformed compatible base schema proof")
        names.add((item[0], item[1]))
        if item[0] == "table":
            table_names.add(item[1])
    if set(tables) != table_names or not table_names:
        raise ValueError("Incomplete compatible base table proof")
    for entry in tables.values():
        if (
            not isinstance(entry, dict)
            or set(entry) != {"rows", "sha256"}
            or type(entry["rows"]) is not int
            or entry["rows"] < 0
            or not isinstance(entry["sha256"], str)
            or re.fullmatch("[0-9a-f]{64}", entry["sha256"]) is None
        ):
            raise ValueError("Malformed compatible base table proof")


def compare_member_content(path: Path, proof: object, device: int) -> None:
    validate_member_content(proof)
    assert isinstance(proof, dict)
    expected_schema = proof["schema"]
    assert isinstance(expected_schema, list)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.create_function("pt_snap_row", -1, _row_bytes, deterministic=True)
        schema = _schema(conn)
        added = [item for item in schema if item not in expected_schema]
        allowed = f"memory_allocation_cache_v1_{device}"
        if added:
            if (
                len(added) != 1
                or added[0][:3] != ["table", allowed, allowed]
                or not isinstance(added[0][3], str)
                or not re.match(r"CREATE\s+TABLE\s", added[0][3], re.IGNORECASE)
                or any(item[1] == allowed for item in expected_schema)
            ):
                raise ValueError("Unrecognized derived schema in compatible member")
            schema.remove(added[0])
        if schema != expected_schema:
            raise ValueError("Compatible base schema or data changed")
        # Validate schema before scanning rows; never scan the newly permitted
        # derived table or unknown objects. Every original table remains covered.
        tables = {
            item[1]: _table_content(conn, item[1])
            for item in schema
            if item[0] == "table" and isinstance(item[1], str)
        }
        if tables != proof["tables"]:
            raise ValueError("Compatible base schema or data changed")
