"""Fail-closed contracts for the separate installed-HTML release runner."""

from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/run_installed_html_acceptance.py"


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("installed_html_runner", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_independent_oracle_uses_lifetime_and_ordered_caller_paths(runner, tmp_path):
    db = tmp_path / "test.db"
    with closing(sqlite3.connect(db)) as con, con:
        con.executescript("""
            CREATE TABLE block_0(size, requestedSize, allocEventId, freeEventId);
            CREATE TABLE trace_entry_0(id, callstackId);
            CREATE TABLE callstack_frame(callstackId, position, frameId);
            CREATE TABLE callstack_frame_manifest(callstackId, frameCount);
            INSERT INTO block_0 VALUES(10,8,1,5),(20,16,2,NULL),(4,4,-1,-1),(90,80,9,NULL);
            INSERT INTO trace_entry_0 VALUES(1,7),(2,8),(9,7);
            INSERT INTO callstack_frame VALUES(7,0,1),(7,1,2),(8,0,1),(8,1,3);
            INSERT INTO callstack_frame_manifest VALUES(7,2),(8,2);
        """)
    before = runner.sha(db)
    rows = runner.tree_oracle(db, 4)
    assert rows["root"]["size_bytes"] == 34
    assert rows["frame/2/1"]["self_bytes"] == 10
    assert rows["frame/3/1"]["self_bytes"] == 20
    assert rows["static"]["size_bytes"] == 4
    assert runner.tree_oracle(db, 5)["root"]["size_bytes"] == 24
    assert runner.sha(db) == before


@pytest.mark.parametrize(
    "field", ["size_bytes", "self_bytes", "block_count", "requested_bytes", "percent_of_total"]
)
def test_compare_tree_rejects_wrong_values(runner, field):
    expected = {"root": {"size_bytes": 10, "self_bytes": 0, "block_count": 1, "requested_bytes": 8}}
    nodes = {"root": {**expected["root"], "percent_of_total": 100.0}}
    runner.compare_tree(nodes, expected)
    nodes["root"][field] += 1
    with pytest.raises(runner.AcceptanceError):
        runner.compare_tree(nodes, expected)


def test_compare_tree_rejects_missing_nodes(runner):
    with pytest.raises(runner.AcceptanceError, match="identity"):
        runner.compare_tree({}, {"root": {}})


@pytest.mark.parametrize("exception", [RuntimeError, AssertionError])
def test_failure_summary_never_exposes_private_exception(
    runner, monkeypatch, tmp_path, exception, capsys
):
    output = tmp_path / "public"
    monkeypatch.setattr(
        "sys.argv",
        [
            "runner",
            "--source",
            ".",
            "--wheel",
            "x",
            "--wheelhouse",
            ".",
            "--output-dir",
            str(output),
        ],
    )

    def fail(*_args):
        raise exception("/private/person/captured_callstack.py secret-user-label")

    monkeypatch.setattr(runner, "run", fail)
    assert runner.main() == 1
    raw = (output / "summary.json").read_text()
    assert "private" not in raw and "secret-user-label" not in raw
    assert json.loads(raw)["failure_type"] == exception.__name__
    assert "secret-user-label" in (tmp_path / "public-private/failure.txt").read_text()
    captured = capsys.readouterr()
    assert "secret-user-label" not in captured.out + captured.err
    assert "/private/person" not in captured.out + captured.err


def test_workflow_is_read_only_candidate_pinned_and_artifact_allowlisted():
    workflow = (SCRIPT.parents[1] / "workflows/installed-html-acceptance.yml").read_text()
    assert "contents: read" in workflow and "write" not in workflow
    assert "ref: 07bdf660f10f03a9c13ab313fae149adf62355f8" in workflow
    assert "pull_request_target" not in workflow and "secrets." not in workflow
    assert "persist-credentials: false" in workflow
    assert "html-safe-evidence/summary.json" in workflow
    assert "*.png" not in workflow
    assert "html-safe-evidence/privacy-synthetic-initial.png" in workflow
    assert "html-safe-evidence/privacy-synthetic-empty.png" in workflow
    for real_name in ("initial.png", "search.png", "deep-focus.png", "empty.png"):
        assert "html-safe-evidence/" + real_name not in workflow
    assert "html-wheel/*.whl" in workflow


@pytest.mark.parametrize(
    "path,status", [("/favicon.ico", 204), ("/not-found", 404), ("/favicon.ico/extra", 404)]
)
def test_http_handler_only_suppresses_exact_favicon(runner, tmp_path, path, status):
    class Request:
        def __init__(self):
            self.response = bytearray()

        def makefile(self, mode, *_args):
            assert mode == "rb"
            return io.BytesIO(f"GET {path} HTTP/1.0\r\nHost: localhost\r\n\r\n".encode())

        def sendall(self, data):
            self.response.extend(data)

    request = Request()
    runner.QuietHandler(request, ("127.0.0.1", 1), None, directory=str(tmp_path))
    assert bytes(request.response).startswith(f"HTTP/1.0 {status} ".encode())
    if status == 204:
        assert bytes(request.response).endswith(b"\r\n\r\n")


@pytest.mark.parametrize("kind", [b"tEXt", b"iTXt", b"zTXt"])
def test_rejected_screenshot_never_reaches_public_artifacts(runner, tmp_path, kind):
    output = tmp_path / "public"
    output.mkdir()

    class Locator:
        def all_text_contents(self):
            return ["safe-label"]

        def count(self):
            return 1

    class Page:
        def locator(self, _selector):
            return Locator()

        def screenshot(self, **kwargs):
            assert "path" not in kwargs
            return b"\x89PNG\r\n\x1a\n" + (0).to_bytes(4, "big") + kind + b"\0" * 4

    with pytest.raises(runner.AcceptanceError, match="metadata"):
        runner.sanitized_screenshot(
            Page(), output, "rejected", {"root": {"node_id": "root", "label": "safe-label"}}
        )
    assert list(output.iterdir()) == []


def test_capture_uses_css_not_coordinate_masks(runner, tmp_path):
    output = tmp_path / "private"
    output.mkdir()

    class Locator:
        def all_text_contents(self):
            return ["synthetic-label"]

        def count(self):
            return 1

    class Page:
        def locator(self, _selector):
            return Locator()

        def screenshot(self, **kwargs):
            assert "path" not in kwargs and "mask" not in kwargs
            style = kwargs["style"]
            assert (
                style
                == "#chart text,#detail,#focus-path,#children-list,#search-results,#search{visibility:hidden!important;}"
            )
            return b"\x89PNG\r\n\x1a\n" + (0).to_bytes(4, "big") + b"IEND" + b"\0" * 4

    result = runner.sanitized_screenshot(
        Page(), output, "synthetic", {"root": {"node_id": "root", "label": "synthetic-label"}}
    )
    assert (output / "synthetic.png").exists()
    assert "runner-private" in result["privacy"]


def test_actual_browser_failure_routes_screenshots_only_to_private(runner, monkeypatch, tmp_path):
    public = tmp_path / "public"
    private = tmp_path / "private"
    public.mkdir()
    private.mkdir()
    fixture = tmp_path / "fixture"
    fixture.write_bytes(b"unit-only input; never deserialized")
    wheel = tmp_path / "wheel.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("unit.dist-info/METADATA", "Version: 1.0\n")
    db = tmp_path / "unit.db"
    with closing(sqlite3.connect(db)) as con, con:
        con.execute("CREATE TABLE trace_entry_0(id, active)")
        con.execute("INSERT INTO trace_entry_0 VALUES(1,40)")
    row = {
        "node_id": "root",
        "label": "invented",
        "depth": 0,
        "size_bytes": 40,
        "requested_bytes": 40,
        "block_count": 1,
        "self_bytes": 40,
        "percent_of_total": 100.0,
    }
    monkeypatch.setattr(runner, "verify_input", lambda *_: fixture)
    monkeypatch.setattr(
        runner,
        "tree_oracle",
        lambda *_: {
            "root": {
                k: row[k] for k in ("size_bytes", "requested_bytes", "block_count", "self_bytes")
            }
        },
    )
    monkeypatch.setattr(runner.venv.EnvBuilder, "create", lambda *_: None)

    def fake_run(argv, **_kwargs):
        if len(argv) > 1 and argv[1] == "-c":
            prefix = Path(argv[0]).parents[1]
            raw = json.dumps(
                {"origin": str(prefix / "lib/pt_snap_cli/__init__.py"), "prefix": str(prefix)}
            )
        elif "import" in argv and "--json" in argv:
            raw = json.dumps({"ok": True, "db_path": str(db)})
        elif "--format" in argv and "html" in argv:
            raw = (
                '<script id="tree-data" type="application/json">'
                + json.dumps({"nodes": [row]})
                + "</script>"
            )
        else:
            raw = ""
        return SimpleNamespace(returncode=0, stdout=raw.encode(), stderr=b"")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    observed = []

    def fail_browser(_html, _nodes, destination, _summary):
        observed.append(destination)
        raise RuntimeError("simulated browser failure")

    monkeypatch.setattr(runner, "browser_checks", fail_browser)
    args = SimpleNamespace(
        source=tmp_path, wheel=wheel, wheelhouse=tmp_path, output_dir=public, private_dir=private
    )
    with pytest.raises(RuntimeError, match="simulated"):
        runner.run(args, {"checks": [], "screenshots": []})
    assert observed == [private / "screenshots"]
    assert list(public.iterdir()) == []
