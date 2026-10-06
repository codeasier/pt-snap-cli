"""Structural benchmark contracts, never speed assertions or fixture execution."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.dataset_import_baseline import rss_kib, source_identity


@pytest.mark.parametrize(
    "platform,raw,expected", [("darwin", 1048576, 1024), ("linux", 1024, 1024)]
)
def test_isolated_self_rss_units(platform, raw, expected):
    assert rss_kib(raw, platform) == expected


def test_source_gate_checks_exact_hash_and_size_without_pickle_load(tmp_path):
    source = tmp_path / "not-an-executable-fixture.txt"
    source.write_bytes(b"hash only")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert source_identity(source, digest)["bytes"] == 9
    with pytest.raises(ValueError, match="exact reviewed"):
        source_identity(source, "0" * 64)
    link = tmp_path / "link"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="canonical"):
        source_identity(link, digest)


def test_existing_parent_refused_before_import_and_preserved(tmp_path):
    source = tmp_path / "hash-only.txt"
    source.write_bytes(b"not pickle; must not load")
    script = Path(__file__).resolve().parents[1] / "benchmarks/dataset_import_baseline.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            str(source),
            "--sha256",
            hashlib.sha256(source.read_bytes()).hexdigest(),
            "--device",
            "0",
            "--capacity",
            "2",
            "--output",
            str(tmp_path),
            "--trusted-pickle",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "FileExistsError" in result.stderr
    assert source.read_bytes() == b"not pickle; must not load"
    assert sorted(p.name for p in tmp_path.iterdir()) == [source.name]


def test_oversized_source_rejected_before_open(tmp_path, monkeypatch):
    source = tmp_path / "large.pkl"
    source.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("oversized source opened"))
    with pytest.raises(ValueError, match="small source"):
        source_identity(source, "0" * 64)


@pytest.mark.parametrize(
    "flags", [["--mode", "single-db"], ["--mode", "single-db", "--phase", "cold"]]
)
def test_hidden_flags_require_pair_and_owner_before_pickle(tmp_path, flags):
    source = tmp_path / "inert.txt"
    source.write_bytes(b"not pickle")
    script = Path(__file__).resolve().parents[1] / "benchmarks/dataset_import_baseline.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            str(source),
            "--sha256",
            hashlib.sha256(source.read_bytes()).hexdigest(),
            "--device",
            "0",
            "--capacity",
            "2",
            "--output",
            str(tmp_path / "missing"),
            "--trusted-pickle",
            *flags,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "supplied together" in result.stderr
    assert not (tmp_path / "missing").exists()


def test_reuse_miss_refuses_rebuild_and_preserves_existing_actual_bytes(tmp_path):
    from benchmarks.dataset_import_baseline import cache_hashes

    source = tmp_path / "inert.pkl"
    source.write_bytes(b"not pickle")
    output = tmp_path / "single-db"
    output.mkdir()
    old = output / "inert.pkl.db"
    old.write_bytes(b"old invalid destination must not be replaced")
    before = old.read_bytes()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    envelope = tmp_path / "run-envelope.json"
    envelope.write_text(
        json.dumps(
            {
                "source": source_identity(source, digest),
                "device": 0,
                "capacity": 2,
                "cacheHashes": {"single-db": cache_hashes(output)},
            }
        )
    )
    script = Path(__file__).resolve().parents[1] / "benchmarks/dataset_import_baseline.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            str(source),
            "--sha256",
            digest,
            "--device",
            "0",
            "--capacity",
            "2",
            "--output",
            str(output),
            "--trusted-pickle",
            "--mode",
            "single-db",
            "--phase",
            "reuse",
            "--envelope",
            str(envelope),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "refuse deserialization" in result.stderr
    assert old.read_bytes() == before and sorted(p.name for p in output.iterdir()) == [old.name]


def test_recorded_performance_report_is_structural_not_a_speed_gate():
    from pt_snap_cli.core.dataset_support import DATASET_SUPPORT

    repository = Path(__file__).resolve().parents[1]
    raw = (repository / "docs/dataset-performance-baseline.json").read_text()
    report = json.loads(raw)
    assert "/Users/" not in raw and "/private/" not in raw
    assert report["schema_version"] == 1 and report["GUI"] == "pending/not-run"
    assert len(report["source_head"]) == 40 and len(report["benchmark_script_sha256"]) == 64
    assert {(r["mode"], r["phase"]) for r in report["records"]} == {
        (mode, phase)
        for mode in ("single-db", "pt-snap-native-v2", "compatibility-v1")
        for phase in ("cold", "reuse")
    }
    for record in report["records"]:
        assert record["exit"] == 0 and record["phase_rss"]["status"] == "unavailable"
        assert "RUSAGE_SELF" in record["rss_scope"]
        assert set(record["queries"]) == set(DATASET_SUPPORT)
        assert record["individual_shard_bytes"] and record["total_disk_bytes"] > 0
        assert all(q["status"] == "passed" for q in record["queries"].values())
        # Deliberately no timing/RSS/speedup threshold: these are observations.
