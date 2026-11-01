"""Fail closed when a critical module loses measured line/branch coverage."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from coverage import Coverage, CoverageData
from coverage.exceptions import CoverageException

# These are independent floors, not an average that another module can offset.
# Keep the original three floors unchanged when extending the risk inventory.
CRITICAL_FLOORS = {
    "src/pt_snap_cli/core/snapshot_import_backend.py": 90,
    "src/pt_snap_cli/snapshot/simulate/simulated_caching_allocator.py": 88,
    "src/pt_snap_cli/snapshot/simulate/snapshot_mutator.py": 84,
    "src/pt_snap_cli/core/import_metadata_contract.py": 100,
    "src/pt_snap_cli/core/import_metadata.py": 90,
    "src/pt_snap_cli/core/split_service.py": 90,
    "src/pt_snap_cli/core/focus_service.py": 90,
    "src/pt_snap_cli/core/skill_service.py": 90,
    "src/pt_snap_cli/core/snapshot_cache.py": 90,
    "src/pt_snap_cli/snapshot/representation.py": 95,
}


class CoverageGuardError(ValueError):
    """Coverage evidence is absent, invalid, or below an independent floor."""


def check_coverage(root: Path) -> None:
    root = root.resolve()
    if not callable(getattr(CoverageData, "close", None)):
        raise CoverageGuardError("Critical coverage requires coverage>=7.10.3; install .[dev]")
    data_file = root / ".coverage"
    if not data_file.is_file():
        raise CoverageGuardError(f"Missing coverage data: {data_file}")
    data: CoverageData | None = None
    try:
        coverage = Coverage(data_file=str(data_file), config_file=str(root / "pyproject.toml"))
        # Own the data before load(): a corrupt SQLite file can fail inside
        # coverage.py's connection __enter__, before its normal cleanup runs.
        data = coverage.get_data()
        coverage.load()
        if not data.has_arcs():
            raise CoverageGuardError("Critical coverage requires branch data, not line-only data")
        measured = {Path(name).resolve() for name in data.measured_files()}
        failures = []
        for relative, floor in CRITICAL_FLOORS.items():
            source = root / relative
            if not source.is_file():
                failures.append(f"{relative}: missing critical source file")
                continue
            if source not in measured:
                failures.append(f"{relative}: missing measured coverage data")
                continue
            if not coverage.analysis2(str(source))[1]:
                failures.append(f"{relative}: no executable statements")
                continue
            # report() returns the unrounded line+branch percentage. Never compare
            # the rounded terminal percentage, which could hide a regression.
            percent = coverage.report(
                morfs=[str(source)],
                file=io.StringIO(),
                ignore_errors=False,
                skip_empty=False,
                skip_covered=False,
            )
            print(f"{relative}: {percent:.4f}% (required {floor}%)")
            if percent < floor:
                failures.append(f"{relative}: {percent:.4f}% is below {floor}%")
        if failures:
            raise CoverageGuardError("\n".join(failures))
    except (CoverageException, OSError) as error:
        raise CoverageGuardError(f"Cannot validate critical coverage: {error}") from error
    finally:
        if data is not None:
            data.close()


def main() -> int:
    try:
        check_coverage(Path(__file__).resolve().parents[2])
    except CoverageGuardError as error:
        print(f"Critical coverage gate failed:\n{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
