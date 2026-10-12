#!/usr/bin/env python3
"""New readonly helper; only syntax/synthetic tests performed, not a rerun of acceptance.
Use after writers have stopped; immutable SQLite assumes no pending WAL.
Never prints source call stacks; JSON stores only table hashes/counts, not rows.
"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for b in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def inventory(root):
    result = {}
    for p in sorted(root.rglob("*")):
        if p.name.endswith(("-wal", "-shm", "-journal")):
            raise ValueError("Stop writers and resolve WAL/SHM/journal sidecars before inspection")
        if p.is_symlink():
            raise ValueError("Refusing symlink in evidence directory")
        if p.is_file():
            result[str(p.relative_to(root))] = {
                "sha256": digest(p),
                "bytes": p.stat().st_size,
            }
    return result


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def logical(path):
    for ending in ("-wal", "-shm", "-journal"):
        if Path(str(path) + ending).exists() or Path(str(path) + ending).is_symlink():
            raise ValueError("Stop writers and resolve WAL/journal before immutable inspection")
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        result = {}
        for table, schema in db.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"
        ):
            cols = [r[1] for r in db.execute("PRAGMA table_info(" + quote(table) + ")")]
            query = "SELECT * FROM " + quote(table) + " ORDER BY " + ",".join(map(quote, cols))
            h = hashlib.sha256()
            count = 0
            for row in db.execute(query):
                # Typed canonical encoding also supports BLOB without exposing its contents.
                encoded = [(type(x).__name__, x.hex() if isinstance(x, bytes) else x) for x in row]
                h.update(
                    json.dumps(encoded, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
                )
                count += 1
            result[table] = {
                "schema": schema,
                "rows": count,
                "logical_sha256": h.hexdigest(),
            }
        return result


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--artifact", type=Path, required=True)
    a.add_argument("--compare", type=Path)
    a.add_argument(
        "--mode",
        choices=("exact", "logical"),
        help="Required with --compare: exact byte-for-byte copy gate; logical post-GUI cache gate",
    )
    a.add_argument("--output", type=Path, required=True)
    args = a.parse_args()
    if bool(args.compare) != bool(args.mode):
        a.error("--compare and --mode must be supplied together")
    if args.output.exists() or args.output.is_symlink():
        a.error("Select a fresh output filename")
    roots = [args.artifact] + ([args.compare] if args.compare else [])
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            a.error("Artifact must be an existing nonsymlink directory")
        if args.output.resolve().is_relative_to(root.resolve()):
            a.error("Write the report outside the artifact")
    result = {
        "helper_schema_version": 2,
        "mode": args.mode or "inventory",
        "inventory": inventory(args.artifact),
    }
    if args.compare:
        before = result["inventory"]
        after = inventory(args.compare)
        result["comparison_inventory"] = after
        result["identical_file_set"] = set(before) == set(after)
        result["changed_files"] = sorted(
            k for k in set(before) & set(after) if before[k] != after[k]
        )
        result["missing_files"] = sorted(set(before) - set(after))
        result["added_files"] = sorted(set(after) - set(before))
        result["exact_copy"] = before == after
        if args.mode == "exact":
            result["passed"] = result["exact_copy"]
        else:
            # Only shard DB bytes may change. Manifest and all other files must stay exact.
            db_members = {
                str(x.relative_to(args.artifact)) for x in args.artifact.glob("device_*/*.db")
            }
            result["unchanged_non_database_files"] = all(
                before[k] == after.get(k) for k in before if k not in db_members
            )
            result["manifest_unchanged"] = "manifest.json" in before and before[
                "manifest.json"
            ] == after.get("manifest.json")
            result["members"] = []
            allowed_added_tables = {"memory_allocation_cache_v1_0"}
            for member in sorted(db_members):
                if member not in after:
                    continue
                db, other = args.artifact / member, args.compare / member
                old, new = logical(db), logical(other)
                added = {k: v for k, v in new.items() if k not in old}
                result["members"].append(
                    {
                        "member": member,
                        "base_tables_unchanged": all(new.get(k) == v for k, v in old.items()),
                        "added_tables": added,
                        "only_known_derived_tables_added": set(added) <= allowed_added_tables,
                        "bytes_changed": digest(db) != digest(other),
                    }
                )
            result["all_base_tables_unchanged"] = (
                bool(db_members)
                and len(result["members"]) == len(db_members)
                and all(m["base_tables_unchanged"] for m in result["members"])
            )
            result["only_known_derived_tables_added"] = all(
                m["only_known_derived_tables_added"] for m in result["members"]
            )
            result["passed"] = (
                result["identical_file_set"]
                and result["unchanged_non_database_files"]
                and result["manifest_unchanged"]
                and result["all_base_tables_unchanged"]
                and result["only_known_derived_tables_added"]
            )
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, ensure_ascii=False)
        out.write("\n")
    if args.compare and not result["passed"]:
        raise SystemExit("Comparison failed in " + args.mode + " mode; report saved")


if __name__ == "__main__":
    main()
