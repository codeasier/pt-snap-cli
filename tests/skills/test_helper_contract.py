from pathlib import Path

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
