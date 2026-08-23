import re
from pathlib import Path

SKILL_PATH = Path("skills/pt-snap-memory-fragmentation/SKILL.md")
TEMPLATE_ROOT = Path("src/pt_snap_cli/query/templates")
CLI_PATH = Path("src/pt_snap_cli/cli.py")


def test_memory_fragmentation_skill_uses_current_pt_snap_surfaces() -> None:
    skill = SKILL_PATH.read_text()
    cli = CLI_PATH.read_text()
    templates = {
        "memory_peak": TEMPLATE_ROOT / "statistical/memory_peak.yaml",
        "allocator_gap": TEMPLATE_ROOT / "statistical/allocator_gap.yaml",
        "allocation": TEMPLATE_ROOT / "basic/allocation.yaml",
        "event": TEMPLATE_ROOT / "basic/event.yaml",
        "active_memory_callstack_at_event": (
            TEMPLATE_ROOT / "business/active_memory_callstack_at_event.yaml"
        ),
    }

    assert "name: pt-snap-memory-fragmentation" in skill
    assert "`pt-snap-setup`" in skill
    assert "readiness.json" not in skill
    assert 'pt-snap metadata "<db_path>" --json' in skill
    assert "pt-snap report peak-memory" in skill
    for command in ('@app.command("focus")', '@app.command("metadata")', '@app.command("query")'):
        assert command in cli
    assert '@report_app.command("peak-memory")' in cli

    for template, path in templates.items():
        assert path.is_file()
        assert f"  {template}:" in path.read_text()
        assert f"--template-info {template}" in skill
        assert f"--template-use {template}" in skill


def test_memory_fragmentation_skill_uses_paginated_runtime_evidence() -> None:
    skill = SKILL_PATH.read_text()

    allocation_command = (
        '--template-use allocation --params \'{"min_id":0,"order_by":"id",'
        '"order_dir":"ASC","limit":<page_size>,"offset":<offset>}\''
    )
    assert allocation_command in skill

    for action in range(4):
        event_params = (
            f'--template-use event --params \'{{"min_id":0,"action":{action},'
            '"order_by":"id","order_dir":"ASC","limit":<page_size>,'
            '"offset":<offset>}\''
        )
        assert event_params in skill

    assert "`0=segment_map` and `1=segment_unmap`" in skill
    assert "`2=segment_alloc` and `3=segment_free`" in skill
    assert "negative IDs are synthetic reconstruction events" in skill
    assert "Event size sums are operation volume, not retained bytes or" in skill


def test_memory_fragmentation_skill_limits_raw_sql_to_read_only_aggregates() -> None:
    skill = SKILL_PATH.read_text()
    raw_sql = skill.split('sqlite3 -readonly "<db_path>" "', maxsplit=1)[1].split(
        "\n```", maxsplit=1
    )[0]

    assert 'sqlite3 -readonly "<db_path>"' in skill
    assert "non-negative decimal integer matching" in skill
    assert "before interpolating it into a table name" in skill
    assert "WHERE id >= 0 AND action IN (0, 1, 2, 3)" in skill
    assert "only for segment operation" in skill
    assert "counts/sizes or maximum observed gaps" in skill
    assert "No writable SQL is" in skill
    assert "Do not replace a missing required template with raw SQL." in skill
    for statement in (
        "alter",
        "attach",
        "create",
        "delete",
        "detach",
        "drop",
        "insert",
        "reindex",
        "replace",
        "update",
        "vacuum",
    ):
        assert re.search(rf"\b{statement}\b", raw_sql, re.IGNORECASE) is None


def test_memory_fragmentation_skill_preserves_snapshotdb_boundaries() -> None:
    skill = SKILL_PATH.read_text()

    for guardrail in (
        "Do not run `pt-snap focus <database_path>`",
        "Do not run `pt-snap import`",
        "Never import or deserialize pickle input.",
        "Never write reports, exports, scratch databases, focus files, or readiness",
        "pass both the",
        "database and device explicitly to every diagnostic query",
        "Event IDs are ordering markers, not timestamps.",
    ):
        assert guardrail in skill


def test_memory_fragmentation_skill_prevents_fragmentation_overclaims() -> None:
    skill = SKILL_PATH.read_text()

    for limitation in (
        "free-region topology",
        "size-bin history",
        "largest contiguous free region",
        "`reserved - active` is not pure",
        "fragmentation, and no definitive fragmentation ratio",
        "no definitive fragmentation ratio or OOM root cause",
        "not attribute reserved bytes, cached bytes",
        "Do not use `callstack_analysis` as segment-source attribution.",
        "Its query has no",
        "action filter, so it mixes event types",
    ):
        assert limitation in skill

    for classification in (
        "allocator/cache pressure",
        "segment retention/churn",
        "fragmentation-consistent pressure",
        "normal allocator behavior",
        "inconclusive",
    ):
        assert f"`{classification}`" in skill

    for section in (
        "`Scope`",
        "`Evidence`",
        "`Inference`",
        "`Unknowns`",
        "`Classifications and confidence`",
        "`Validation experiments`",
    ):
        assert section in skill
