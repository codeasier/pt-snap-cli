from pathlib import Path

import pytest
from typer.main import get_command

from pt_snap_cli.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "pt-snap-helper" / "SKILL.md"
AGENTS_PATH = REPO_ROOT / "skills" / "AGENTS.md"

ROUTED_SKILLS = (
    "pt-snap-setup",
    "pt-snap-ascend-npu-collect",
    "pt-snap-memory-leak",
    "pt-snap-memory-peak-breakdown",
    "pt-snap-memory-fragmentation",
)

JSON_COMMANDS = (
    ("metadata",),
    ("report", "peak-memory"),
    ("skill", "list"),
    ("skill", "install"),
    ("skill", "upgrade"),
    ("skill", "uninstall"),
    ("query",),
    ("focus",),
    ("import",),
    ("split",),
    ("config",),
    ("capabilities",),
    ("overview",),
)


def _skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _command_has_option(*path: str, option: str) -> bool:
    command = get_command(app)
    for name in path:
        command = command.commands[name]
    return any(option in param.opts for param in command.params)


def test_helper_skill_frontmatter_and_index() -> None:
    skill = _skill()
    agents = AGENTS_PATH.read_text(encoding="utf-8")

    assert skill.startswith("---\nname: pt-snap-helper\n")
    assert "read-only navigator" in skill
    assert "pt-snap-helper/SKILL.md" in agents
    assert "Routes by user goal and input type" in agents


def test_helper_skill_checks_availability_and_restart() -> None:
    skill = _skill()

    assert "pt-snap skill list --json" in skill
    assert "pt-snap skill install pt-snap-helper --json" in skill
    assert "pt-snap skill upgrade pt-snap-helper --json" in skill
    assert "Do not run install or upgrade from this skill." in skill
    assert (
        "Restart the agent after install, upgrade, or uninstall so the skill "
        "change takes effect."
    ) in skill


def test_helper_skill_uses_current_json_capability() -> None:
    skill = _skill()

    assert "Prefer `--json` where supported" in skill
    assert "pt-snap capabilities --json" in skill
    assert "pt-snap overview '<db_path>' --json" in skill
    assert "pt-snap metadata '<db_path>' --json" in skill
    assert "pt-snap report peak-memory '<db_path>' --device <device_id> --json" in skill
    assert "pt-snap query --list --json" in skill
    assert "pt-snap query --template-info <name> --json" in skill
    assert "has_more" in skill
    assert "truncated" in skill
    assert "pt-snap focus --json" in skill
    assert "pt-snap config --json" in skill
    assert "pt-snap import <snapshot.pkl> --json" in skill
    assert "There is no global `--json` flag" in skill
    assert "Do not invent a global `--json` flag on `pt-snap`." not in skill
    for path in JSON_COMMANDS:
        assert _command_has_option(*path, option="--json")
    assert not _command_has_option(option="--json")


def test_helper_skill_routes_by_goal_and_input_type() -> None:
    skill = _skill()

    assert "## Routing matrix" in skill
    assert "Existing SnapshotDB" in skill
    assert "overview first, then diagnose" in skill
    assert "Only pickle" in skill
    assert "`pt-snap` missing" in skill
    assert "Need Ascend NPU capture" in skill
    for name in ROUTED_SKILLS:
        assert f"`{name}`" in skill
    assert "CSV, SVG, and other visualization files are not SnapshotDB input" in skill


@pytest.mark.parametrize(
    ("goal", "missing_cli_route"),
    [
        ("Install or verify the CLI", "`pt-snap-setup`"),
        ("Collect an Ascend NPU pickle", "`pt-snap-ascend-npu-collect`"),
        ("Leak / live allocations at end of trace", "`pt-snap-setup` first"),
        ("What was live at a peak event", "`pt-snap-setup` first"),
        ("Allocator gaps / reserved-pool pressure", "`pt-snap-setup` first"),
    ],
)
def test_helper_missing_cli_matrix_routes_by_goal(goal: str, missing_cli_route: str) -> None:
    matrix = _skill().split("## Routing matrix", 1)[1].split("Exact next-skill names:", 1)[0]
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in matrix.splitlines()
        if line.startswith("|")
    ]
    missing_cli_column = rows[0].index("`pt-snap` missing")
    row = next(row for row in rows[2:] if row[0] == goal)
    assert row[missing_cli_column] == missing_cli_route


def test_helper_missing_cli_preserves_unchecked_status_and_collection_priority() -> None:
    prerequisite = " ".join(
        _skill()
        .split("## Prerequisite: check skill availability", 1)[1]
        .split("### Interpret availability", 1)[0]
        .split()
    )
    assert "report catalog/directory status as `unchecked`" in prerequisite
    assert "For Ascend NPU capture, choose `pt-snap-ascend-npu-collect` first" in prerequisite
    assert "For existing SnapshotDB analysis or CLI installation/verification" in prerequisite
    assert "hand off to `pt-snap-setup`" in prerequisite


def test_helper_collection_handoff_requires_host_loading_and_handles_failure() -> None:
    collection = " ".join(
        _skill().split("### Need Ascend NPU collection", 1)[1].split("## Boundaries", 1)[0].split()
    )
    assert "already loaded by the host or the host's supported loader succeeds" in collection
    assert "Missing `pt-snap` does not block collection" in collection
    assert "If loading fails or no loader is available, pause the collection handoff" in collection
    assert "configure the known skill directory for host discovery and restart" in collection
    assert "Source readability is not host-loading evidence" in collection
    assert "Do not install packages or skills implicitly" in collection
    assert "TorchNPU/environment verification remains owned by the collection skill" in collection


def test_helper_capture_then_analysis_keeps_separate_stage_decisions() -> None:
    missing_cli = " ".join(
        _skill().split("### `pt-snap` missing", 1)[1].split("## Boundaries", 1)[0].split()
    )
    assert "For capture followed by analysis, route collection first" in missing_cli
    assert "After capture, route to setup if the CLI is still missing" in missing_cli
    assert "trusted import remains an independent decision" in missing_cli
    assert "only after a SnapshotDB exists" in missing_cli
    assert "For pickle-only analysis, explain the independent trusted-input decision" in missing_cli


def test_helper_skill_keeps_pickle_import_and_focus_as_handoffs() -> None:
    skill = _skill()

    assert "import is an independent trusted-input decision" in skill
    assert "Do not run `pt-snap import`." in skill
    assert "Do not run `pt-snap focus` with a database path." in skill
    assert "Do not persist focus" in skill
    assert "overview first, then diagnose" in skill
    assert "This helper must not run that command or change focus." in skill
    assert "pt-snap import <snapshot.pkl> --json" in skill
    assert "That command currently has no `--json` option." not in skill
    assert "Do not run `pt-snap skill install`" in skill


def test_helper_skill_recovers_missing_focus_with_sibling_candidates() -> None:
    skill = _skill()
    normalized = " ".join(skill.split())

    assert "#### Missing focus target with sibling candidates" in skill
    assert "enter this recovery branch" in skill.casefold()
    assert (
        "A displayed path or exit code 0 from `pt-snap focus` does not mean " "the target is usable"
    ) in normalized
    assert "Do not auto-select by name, size, or mtime." in skill
    assert "Even a single candidate requires an explicit user choice." in normalized
    assert "Before the user confirms a path, do not run diagnostic queries" in skill
    assert "the next inspect step is" in skill
    assert "`pt-snap metadata '<db_path>' --json`, not `pt-snap query`" in skill
    assert "Do not inherit the focused device from the missing target" in normalized
    assert "This helper must not run metadata, query, import, or persist focus." in normalized
