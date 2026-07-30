"""Baseline import performance benchmark for Issue #74.

Accepted source:
    .claude/worktrees/issue-74-import-performance/benchmarks/baseline_import.py
Accepted source SHA256:
    d229e7fdf672d86e5c4f25c0ed8cd41ef94ffe708e7998e4fdcee9cab8d4fb23

Run from the worktree root:
    PYTHONPATH=src python benchmarks/baseline_import.py
"""

from __future__ import annotations

import cProfile
import io
import json
import logging
import os
import pstats
import re
import sqlite3
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

FIXTURES = Path("tests/fixtures/snapshots")

SAMPLES = {
    "8k": FIXTURES / "snapshot_with_multi_devices.pkl",
    "131k": FIXTURES / "snapshot_16k_94layers.pickle",
    "628k": FIXTURES / "memory0.pickle",
}

DEVICE = 0


@dataclass
class RunResult:
    wall_s: float
    user_s: float
    sys_s: float
    max_rss_mb: float
    db_size_mb: float


@dataclass
class SampleReport:
    name: str
    path: Path
    formal_runs: int = 0
    runs: list[RunResult] = field(default_factory=list)

    @property
    def median_wall(self) -> float:
        return statistics.median(r.wall_s for r in self.runs)

    def format_table(self) -> str:
        lines = [
            f"### {self.name} ({self.path.name})",
            "",
            f"正式测量 {self.formal_runs} 次，另有 1 次 warmup",
            "",
            "| Run | Wall (s) | User (s) | Sys (s) | Max RSS (MB) | DB (MB) |",
            "|-----|----------|----------|---------|--------------|---------|",
        ]
        for i, r in enumerate(self.runs, 1):
            lines.append(
                f"| {i} | {r.wall_s:.3f} | {r.user_s:.3f} | {r.sys_s:.3f} "
                f"| {r.max_rss_mb:.1f} | {r.db_size_mb:.1f} |"
            )
        if self.runs:
            lines.append(f"\n**Median wall time**: {self.median_wall:.3f}s")
        return "\n".join(lines)


def _parse_time_output(stderr: str) -> dict[str, float]:
    wall_match = re.search(r"(\d+\.\d+) real", stderr)
    user_match = re.search(r"(\d+\.\d+) user", stderr)
    sys_match = re.search(r"(\d+\.\d+) sys", stderr)
    rss_match = re.search(r"(\d+)\s+maximum resident set size", stderr)

    return {
        "wall_s": float(wall_match.group(1)) if wall_match else 0.0,
        "user_s": float(user_match.group(1)) if user_match else 0.0,
        "sys_s": float(sys_match.group(1)) if sys_match else 0.0,
        "max_rss_bytes": int(rss_match.group(1)) if rss_match else 0,
    }


def _run_import_once(snapshot: Path, output_dir: Path, device: int) -> RunResult:
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            "/usr/bin/time",
            "-l",
            sys.executable,
            "-c",
            f"""
import logging; logging.disable(logging.CRITICAL)
from pt_snap_cli.core.import_service import ImportOptions, ImportService
from pathlib import Path
options = ImportOptions(
    snapshot_file=Path({str(snapshot)!r}),
    output_dir=Path({str(output_dir)!r}),
    device={device},
    set_focus=False,
    force=True,
)
ImportService().import_snapshot(options)
""",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}", file=sys.stderr)
        print(f"STDERR: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"import failed: {result.returncode}")

    metrics = _parse_time_output(result.stderr)

    db_files = list(output_dir.glob("*.db"))
    db_size = sum(f.stat().st_size for f in db_files) if db_files else 0

    return RunResult(
        wall_s=metrics["wall_s"],
        user_s=metrics["user_s"],
        sys_s=metrics["sys_s"],
        max_rss_mb=metrics["max_rss_bytes"] / (1024 * 1024),
        db_size_mb=db_size / (1024 * 1024),
    )


def _representative_queries(db_path: Path, device: int) -> dict:
    """Stable representative summaries (not exact query-template output).

    Event queries use ORDER BY <metric> DESC, id ASC so ties resolve
    deterministically for before/after comparison.
    """
    conn = sqlite3.connect(str(db_path))
    results: dict[str, str] = {}

    peak = conn.execute(f"""
        SELECT id, action, allocated, active, reserved
        FROM trace_entry_{device}
        ORDER BY allocated DESC, id ASC
        LIMIT 1
    """).fetchone()
    if peak:
        results["memory_peak"] = (
            f"id={peak[0]} action={peak[1]} allocated={peak[2]} "
            f"active={peak[3]} reserved={peak[4]}"
        )

    gap = conn.execute(f"""
        SELECT id, action, allocated, active, reserved,
               CAST(reserved AS INTEGER) - CAST(allocated AS INTEGER) AS gap
        FROM trace_entry_{device}
        ORDER BY gap DESC, id ASC
        LIMIT 1
    """).fetchone()
    if gap:
        results["allocator_gap"] = (
            f"id={gap[0]} action={gap[1]} allocated={gap[2]} "
            f"active={gap[3]} reserved={gap[4]} gap={gap[5]}"
        )

    block_count = conn.execute(f"""
        SELECT COUNT(*), SUM(size), MAX(size), AVG(size)
        FROM block_{device}
    """).fetchone()
    if block_count:
        results["block_summary"] = (
            f"count={block_count[0]} total_size={block_count[1]} "
            f"max_size={block_count[2]} avg_size={block_count[3]:.0f}"
        )

    conn.close()
    return results


def _correctness_summary(output_dir: Path, device: int) -> dict:
    db_files = list(output_dir.glob("*.db"))
    if not db_files:
        return {"error": "no db found"}
    db_path = db_files[0]
    conn = sqlite3.connect(str(db_path))

    quick_check = conn.execute("PRAGMA quick_check").fetchone()[0]

    trace_count = conn.execute(f"SELECT COUNT(*) FROM trace_entry_{device}").fetchone()[0]
    block_count = conn.execute(f"SELECT COUNT(*) FROM block_{device}").fetchone()[0]

    max_alloc = conn.execute(f"SELECT MAX(allocated) FROM trace_entry_{device}").fetchone()[0]
    max_active = conn.execute(f"SELECT MAX(active) FROM trace_entry_{device}").fetchone()[0]
    max_reserved = conn.execute(f"SELECT MAX(reserved) FROM trace_entry_{device}").fetchone()[0]

    conn.close()

    summary = {
        "quick_check": quick_check,
        "trace_rows": trace_count,
        "block_rows": block_count,
        "max_allocated": max_alloc,
        "max_active": max_active,
        "max_reserved": max_reserved,
        "db_file": db_path.name,
    }

    queries = _representative_queries(db_path, device)
    summary["representative_queries"] = queries

    return summary


def _profile_import(snapshot: Path, output_dir: Path, device: int, top_n: int = 20) -> str:
    from pt_snap_cli.core.import_service import ImportOptions, ImportService

    service = ImportService()
    options = ImportOptions(
        snapshot_file=snapshot,
        output_dir=output_dir,
        device=device,
        set_focus=False,
        force=True,
    )

    profiler = cProfile.Profile()
    profiler.enable()
    service.import_snapshot(options)
    profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(top_n)
    return stream.getvalue()


def main() -> None:
    import argparse

    logging.getLogger("pt_snap_cli.vendor").setLevel(logging.ERROR)

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", nargs="+", default=["131k", "628k"])
    parser.add_argument("--runs-131k", type=int, default=5)
    parser.add_argument("--runs-628k", type=int, default=3)
    parser.add_argument("--runs-8k", type=int, default=5)
    parser.add_argument("--skip-profile", action="store_true")
    parser.add_argument("--skip-correctness", action="store_true")
    args = parser.parse_args()

    run_counts = {"8k": args.runs_8k, "131k": args.runs_131k, "628k": args.runs_628k}
    reports: list[SampleReport] = []

    for name in args.samples:
        if name not in SAMPLES:
            print(f"Unknown sample: {name}", file=sys.stderr)
            continue

        snapshot = SAMPLES[name]
        if not snapshot.exists():
            print(f"Missing fixture: {snapshot}", file=sys.stderr)
            continue

        n_runs = run_counts.get(name, 3)
        report = SampleReport(name=name, path=snapshot, formal_runs=n_runs)

        print(f"\n{'='*60}")
        print(f"Sample: {name} ({snapshot.name})")
        print(f"{'='*60}")

        print("  Warmup run...")
        with tempfile.TemporaryDirectory(prefix=f"baseline_{name}_warmup_") as tmp:
            _run_import_once(snapshot, Path(tmp), DEVICE)

        for i in range(n_runs):
            with tempfile.TemporaryDirectory(prefix=f"baseline_{name}_run{i}_") as tmp:
                tmp_path = Path(tmp)
                result = _run_import_once(snapshot, tmp_path, DEVICE)
                report.runs.append(result)
                print(
                    f"  Run {i+1}/{n_runs}: wall={result.wall_s:.3f}s  "
                    f"rss={result.max_rss_mb:.1f}MB  db={result.db_size_mb:.1f}MB"
                )

                if i == 0 and not args.skip_correctness:
                    summary = _correctness_summary(tmp_path, DEVICE)
                    print(f"  Correctness: {json.dumps(summary, indent=2, default=str)}")

        if not args.skip_profile:
            print(f"\n  cProfile ({name}):")
            with tempfile.TemporaryDirectory(prefix=f"baseline_{name}_profile_") as tmp:
                profile_output = _profile_import(snapshot, Path(tmp), DEVICE)
                print(profile_output)

        reports.append(report)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for report in reports:
        print(report.format_table())
        print()


if __name__ == "__main__":
    main()
