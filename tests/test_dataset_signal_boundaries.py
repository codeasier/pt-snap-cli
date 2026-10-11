"""Characterize current CLI signal boundaries; no SIGTERM/SIGKILL cleanup promise."""

import json
import multiprocessing
import os
import signal
from pathlib import Path

import pytest

from tests.core.dataset_lifecycle_fixtures import build
from tests.dataset_concurrency_support import ISOLATED_ENV, WAIT_SECONDS, cli_at_scratch_stage
from tests.test_dataset_focus import hashes

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Requires actual POSIX signal semantics")


@pytest.mark.parametrize("action", ["complete", "SIGINT", "SIGTERM", "SIGKILL"])
def test_cli_scratch_signal_boundary(tmp_path, monkeypatch, action):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ISOLATED_ENV:
        monkeypatch.delenv(name, raising=False)
    _, root, _, _, _ = build(tmp_path, 7)
    before = hashes(root)
    scratch_parent = tmp_path / "scratch"
    scratch_parent.mkdir()
    stdout, stderr = tmp_path / "stdout", tmp_path / "stderr"
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=cli_at_scratch_stage,
        args=(root, scratch_parent, child, stdout, stderr),
    )
    process.start()
    child.close()
    try:
        assert parent.poll(WAIT_SECONDS), "CLI did not reach a completed scratch insert"
        stage = parent.recv()
        derived = Path(stage["database"])
        assert stage["pid"] == process.pid
        assert stage["inserted_rows"] > 0 and derived.stat().st_size > 0
        assert derived.parent.parent == scratch_parent
        assert process.is_alive()
        assert hashes(root) == before
        if action == "complete":
            parent.send("continue")
        else:
            os.kill(process.pid, getattr(signal, action))
        process.join(WAIT_SECONDS)
        assert not process.is_alive(), "CLI did not exit after release/signal"
        if action == "complete":
            assert process.exitcode == 0
            assert json.loads(stdout.read_text())["returned"] == 5
            assert stderr.read_text() == ""
            assert not list(scratch_parent.iterdir())
        elif action == "SIGINT":
            assert process.exitcode in (1, 130)
            assert stdout.read_text() == ""
            assert json.loads(stderr.read_text())["error"]["message"] == "Aborted!"
            assert not list(scratch_parent.iterdir())
        else:
            # Existing Python/OS behavior terminates before finally/TemporaryDirectory
            # cleanup. Residue is deliberately observed, not deleted as evidence.
            assert process.exitcode == -getattr(signal, action)
            assert stdout.read_text() == stderr.read_text() == ""
            assert derived.is_file()
            assert list(scratch_parent.iterdir()) == [derived.parent]
        assert hashes(root) == before
    finally:
        parent.close()
        if process.is_alive():
            process.kill()
            process.join(WAIT_SECONDS)
        process.close()
