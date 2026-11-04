"""First-use docs and recovery examples, using synthetic inputs only."""

import json
import re
import shlex
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from typer.testing import CliRunner

from pt_snap_cli.cli import app

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "zh")
SKILLS = (
    "pt-snap-helper",
    "pt-snap-memory-leak",
    "pt-snap-memory-peak-breakdown",
    "pt-snap-memory-fragmentation",
)
DOCS = (
    "README.md",
    "README_zh.md",
    "docs/README.md",
    *(f"docs/{lang}/{topic}.md" for lang in LANGUAGES for topic in ("quickstart", "skills")),
    *(f"skills/{skill}/SKILL.md" for skill in SKILLS),
    *(f"skills/{skill}/references/output-recovery.md" for skill in SKILLS),
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _blocks(text: str, language: str) -> list[str]:
    return re.findall(rf"```{language}\n(.*?)```", text, re.S)


def _anchors(text: str) -> set[str]:
    # GitHub heading anchors retain Unicode letters but drop punctuation.
    headings = re.findall(r"^#{1,6} (.+)$", text, re.M)
    return {
        re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-") for heading in headings
    } | set(re.findall(r'<a\s+(?:id|name)="([^"]+)"', text))


@pytest.mark.parametrize("path", DOCS)
def test_onboarding_local_links_and_heading_anchors(path: str) -> None:
    for target in re.findall(r"\[[^\]\n]+\]\(([^\s)]+)\)", _read(path)):
        parts = urlsplit(target)
        if parts.scheme or parts.netloc:
            continue
        destination = (ROOT / path).parent / unquote(parts.path) if parts.path else ROOT / path
        assert destination.exists(), (path, target)
        if parts.fragment and destination.suffix == ".md":
            assert unquote(parts.fragment) in _anchors(destination.read_text(encoding="utf-8")), (
                path,
                target,
            )


@pytest.mark.parametrize("language", LANGUAGES)
def test_first_report_precedes_advanced_formats_with_nearby_state_boundaries(language: str) -> None:
    text = _read(f"docs/{language}/quickstart.md")
    report = text.index("pt-snap report peak-memory snapshot.pkl.db")
    advanced = text.index("## Advanced Input Options" if language == "en" else "## 高级输入选项")
    assert report < advanced
    before_report = text[:report]
    for term in (
        "Python 3.10",
        "TorchNPU",
        "torch_cuda_memory.html",
        "pt-snap-ascend-npu-collect/SKILL.md",
        "manifest.json",
        ".pt-snap/focus.json",
        "--no-focus",
        "--output-dir",
        "import_metadata.status",
        "metadata_missing",
        "1048576 bytes",
        "allocated",
        "active",
        "reserved",
    ):
        assert term in before_report
    assert "included_bytes" in text and "--limit 20" in text
    assert "no-replace" in before_report and "--force" in before_report


def test_bilingual_quickstart_commands_and_example_are_identical() -> None:
    texts = [_read(f"docs/{language}/quickstart.md") for language in LANGUAGES]
    assert _blocks(texts[0], "bash") == _blocks(texts[1], "bash")
    assert _blocks(texts[0], "json") == _blocks(texts[1], "json")
    for path in ("README.md", "README_zh.md"):
        text = _read(path)
        assert "AGENTS.md#development-and-checks" in text
        assert "basedpyright" in text
    assert "python -m basedpyright" in _read("AGENTS.md")


@pytest.mark.parametrize("language", LANGUAGES)
def test_agent_normal_install_precedes_exception_navigation(language: str) -> None:
    text = _read(f"docs/{language}/skills.md")
    install = text.index("pt-snap skill install\n")
    verify = text.index("pt-snap skill list --json")
    custom = text.index("## Destinations" if language == "en" else "## 安装位置")
    absent = text.index("## Collection when" if language == "en" else "## CLI 缺失")
    assert install < verify < custom < absent
    for term in ("pt-snap-helper", "installed", "100–700", "output-recovery.md"):
        assert term in text


@pytest.fixture
def example_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    path = tmp_path / "snapshot.pkl.db"
    mib = 1048576
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript("""
            CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT);
            CREATE TABLE trace_entry_0 (
                id INTEGER PRIMARY KEY, action INTEGER, address INTEGER, size INTEGER,
                stream INTEGER, allocated INTEGER, active INTEGER, reserved INTEGER,
                callstack TEXT
            );
            CREATE TABLE block_0 (
                id INTEGER PRIMARY KEY, address INTEGER, size INTEGER,
                requestedSize INTEGER, state INTEGER, allocEventId INTEGER, freeEventId INTEGER
            );
            """)
        # Allocate 2+6 MiB, request a deferred 2 MiB free, then allocate another
        # 2 MiB. Earliest allocated/reserved peaks differ from the active peak.
        conn.executemany(
            "INSERT INTO trace_entry_0 VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)",
            [
                (9, 0, 100, 2 * mib, 2 * mib, 2 * mib, 8 * mib, "first"),
                (10, 0, 200, 6 * mib, 8 * mib, 8 * mib, 16 * mib, "second"),
                (11, 1, 100, 2 * mib, 6 * mib, 8 * mib, 16 * mib, "free"),
                (12, 0, 300, 2 * mib, 8 * mib, 10 * mib, 16 * mib, "third"),
            ],
        )
        conn.executemany(
            "INSERT INTO block_0 VALUES (?, ?, ?, ?, ?, ?, -1)",
            [
                (1, 100, 2 * mib, 2 * mib, 0, 9),
                (2, 200, 6 * mib, 6 * mib, 1, 10),
                (3, 300, 2 * mib, 2 * mib, 1, 12),
            ],
        )
    return path


@pytest.mark.parametrize("language", LANGUAGES)
def test_documented_read_only_path_reaches_report(example_db: Path, language: str) -> None:
    text = _read(f"docs/{language}/quickstart.md")
    commands = [
        shlex.split(line)[1:]
        for block in _blocks(text, "bash")
        for line in block.strip().splitlines()
        if line.startswith(
            ("pt-snap overview ", "pt-snap query ", "pt-snap report peak-memory snapshot")
        )
    ]
    before = example_db.read_bytes()
    results = [CliRunner().invoke(app, command) for command in commands]
    assert len(results) == 3
    assert all(result.exit_code == 0 for result in results), [result.output for result in results]
    overview = json.loads(results[0].stdout)
    assert overview["import_metadata"]["status"] == "unavailable"
    assert overview["import_metadata"]["reason"] == "metadata_missing"
    expected_peak = json.loads(_blocks(text, "json")[0])
    assert json.loads(results[1].stdout)["rows"] == [expected_peak]
    assert "Peak memory report" in results[2].stdout
    assert "Event ID: 12" in results[2].stdout
    assert "Active memory by callstack:" in results[2].stdout
    assert "100.0000%" in results[2].stdout
    assert example_db.read_bytes() == before
    assert not (example_db.parent / ".pt-snap").exists()


@pytest.mark.parametrize("skill", SKILLS)
def test_recovery_reference_is_packaged_identically_and_preserves_complete_json(skill: str) -> None:
    relative = f"{skill}/references/output-recovery.md"
    assert _read(f"skills/{relative}") == _read(f"src/pt_snap_cli/bundled_skills/{relative}")
    assert "references/output-recovery.md" in _read(f"skills/{skill}/SKILL.md")
    recovery = _read(f"skills/{relative}")
    for requirement in (
        "stdout and stderr separately",
        "no gaps or overlaps",
        "overview.import_metadata.status",
        "stop diagnosis",
        "Do not write scratch/report files",
    ):
        assert requirement in recovery


@pytest.mark.parametrize("outcome", ("complete", "truncated", "failed"))
def test_documented_in_memory_recovery_does_not_hide_failure_or_drop_fields(
    outcome: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _blocks(_read("skills/pt-snap-helper/references/output-recovery.md"), "python")[0]
    payload = {
        "ok": True,
        "cli_version": "test",
        "templates": [{"name": "memory_peak", "output_schema": [{"units": "bytes"}]}],
        "skills": [],
        "unknown_future_field": {"preserve": "完整"},
    }
    stdout = json.dumps(payload, indent=2)
    if outcome == "truncated":
        stdout = stdout[:-4]
    stderr = "probe failed" if outcome == "failed" else ""
    calls = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 2 if outcome == "failed" else 0, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", run)
    if outcome == "complete":
        exec(code, {})
        captured = capsys.readouterr()
        assert json.loads(captured.out) == payload
        assert len(captured.out) < len(stdout)
    elif outcome == "truncated":
        with pytest.raises(json.JSONDecodeError):
            exec(code, {})
        assert capsys.readouterr().out == ""
    else:
        with pytest.raises(SystemExit) as error:
            exec(code, {})
        assert error.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == "" and captured.err == stderr
    assert calls == [
        (
            ["pt-snap", "capabilities", "--json"],
            {"capture_output": True, "text": True, "check": False},
        )
    ]
