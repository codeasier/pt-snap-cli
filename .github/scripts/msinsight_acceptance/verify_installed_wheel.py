#!/usr/bin/env python3
"""New helper, syntax checked only. Run using the intended installed venv Python.
Compares all pt_snap_cli/ wheel members with that interpreter's installed package.
No pickle execution. Does not authenticate a wheel's origin or dependency safety.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actual = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    if actual != args.expected_sha256:
        parser.error("Wheel SHA256 mismatch")
    if args.output.exists():
        parser.error("Select a fresh output filename")
    spec = importlib.util.find_spec("pt_snap_cli")
    if not spec or not spec.origin:
        parser.error("No installed pt_snap_cli package in this interpreter")
    root = Path(spec.origin).resolve().parent
    if not root.is_relative_to(Path(sys.prefix).resolve()):
        parser.error("Package is outside the current interpreter prefix")
    if "site-packages" not in root.parts and "dist-packages" not in root.parts:
        parser.error("Package is not in a regular installed package directory")
    checked, mismatches = [], []
    with zipfile.ZipFile(args.wheel) as wheel:
        for entry in wheel.infolist():
            if entry.is_dir() or not entry.filename.startswith("pt_snap_cli/"):
                continue
            relative = Path(entry.filename).relative_to("pt_snap_cli")
            if ".." in relative.parts:
                parser.error("Invalid wheel member path")
            installed = root / relative
            expected = hashlib.sha256(wheel.read(entry)).hexdigest()
            matches = (
                installed.is_file()
                and hashlib.sha256(installed.read_bytes()).hexdigest() == expected
            )
            checked.append(str(relative))
            if not matches:
                mismatches.append(str(relative))
    if not checked:
        parser.error("No package members found")
    with args.output.open("x") as out:
        json.dump(
            {
                "wheel_sha256": actual,
                "package_member_count": len(checked),
                "members": checked,
                "mismatches": mismatches,
            },
            out,
            indent=2,
        )
        out.write("\n")
    if mismatches:
        raise SystemExit("Installed package differs from wheel")
    print("Verified", len(checked), "installed package members")


if __name__ == "__main__":
    main()
