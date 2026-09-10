from __future__ import annotations

from pathlib import Path

SKILL_PATH = Path("skills/pt-snap-ascend-npu-collect/SKILL.md")
AGENTS_PATH = Path("skills/AGENTS.md")


def _skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalized_skill() -> str:
    return " ".join(_skill().split())


def test_skill_frontmatter_and_agent_routing() -> None:
    skill = _skill()
    agents = AGENTS_PATH.read_text(encoding="utf-8")

    assert skill.startswith("---\nname: pt-snap-ascend-npu-collect\n")
    assert "Collect Ascend NPU (torch_npu) PyTorch memory snapshots" in skill
    assert "This is a collection skill, not\nan analysis skill." in skill
    assert "Not for diagnosing an existing SnapshotDB" in skill
    assert "pt-snap-ascend-npu-collect/SKILL.md" in agents
    assert "Collect Ascend NPU pickles" in agents
    assert "Collection skills guide capture configuration" in agents


def test_skill_preserves_active_interpreter_and_refuses_installs() -> None:
    skill = _skill()
    normalized = _normalized_skill()

    assert '"<python_candidate>" -c "import sys; print(sys.executable)"' in skill
    assert "Preserve this path exactly as `<python_executable>`" in skill
    assert "Do not assume Conda" in normalized
    assert "Do not install `torch_npu`" in skill
    assert "Do not install packages or switch Python environments." in skill


def test_skill_verifies_torch_npu_collection_apis() -> None:
    skill = _skill()

    assert "from torch_npu.npu import memory" in skill
    assert "hasattr(memory, '_record_memory_history')" in skill
    assert "hasattr(memory, '_snapshot')" in skill
    assert "hasattr(memory, '_dump_snapshot')" in skill
    assert "_record_memory_history(" in skill
    assert "_dump_snapshot(" in skill
    assert "enabled=None" in skill


def test_skill_routes_frameworks_without_inventing_vllm_flags() -> None:
    skill = _skill()

    for route in (
        "`native-api`",
        "`mindspeed-mm`",
        "`verl`",
        "`mindspeed-core`",
        "`oom-env`",
    ):
        assert route in skill

    assert '"memory_profile"' in skill or "`memory_profile`" in skill
    assert "global_profiler.tool=torch_memory" in skill
    assert "--record-memory-history" in skill
    assert "Do not invent a vllm-ascend snapshot flag." in skill
    assert "Never invent a vllm-ascend snapshot integration." in skill
    assert "MindSpeed-RL inherits the verl profiler" in skill


def test_skill_documents_oom_env_and_version_floor() -> None:
    skill = _skill()

    assert "OOM_SNAPSHOT_ENABLE" in skill
    assert "OOM_SNAPSHOT_PATH" in skill
    assert "TASK_QUEUE_ENABLE" in skill
    assert "TorchNPU `>= 6.0.0`" in skill
    assert "HDK `>= 25.5.0`" in skill
    assert "CANN `>= 8.5.0`" in skill
    assert "CSV is not importable" in skill or "CSV is not SnapshotDB input" in skill


def test_skill_keeps_pickle_import_and_diagnosis_out_of_scope() -> None:
    skill = _skill()
    normalized = _normalized_skill()

    assert "Never open, import, inspect, or deserialize pickle input." in skill
    assert "Never run `pt-snap import`" in skill
    assert "Never persist focus" in normalized
    assert "Never start leak, peak, fragmentation, or OOM-root-cause analysis." in skill
    assert "A collected pickle is not a SnapshotDB." in skill
    assert "readiness.json" not in skill
    assert "pt-snap import <" not in skill
    assert "pt-snap query" not in skill
    assert "pt-snap report" not in skill


def test_skill_hands_off_to_existing_analysis_skills() -> None:
    skill = _skill()

    assert "`pt-snap-memory-leak`" in skill
    assert "`pt-snap-memory-peak-breakdown`" in skill
    assert "`pt-snap-memory-fragmentation`" in skill
    assert "`pt-snap-setup`" in skill
    assert "import is a separate trusted-input decision" in skill


def test_skill_uses_conservative_result_categories() -> None:
    skill = _skill()

    for category in (
        "native-api-plan",
        "framework-config-plan",
        "oom-env-plan",
        "unsupported-framework",
        "collection-complete",
        "blocked",
    ):
        assert f"`{category}`" in skill

    assert "Never recommend unbounded `max_entries` unless the user asked for it." in skill
    assert "transfer_to_npu" in skill
    assert "does not make the pickle CUDA-shaped" in skill


def test_skill_output_contract_covers_scope_artifacts_and_unknowns() -> None:
    skill = _skill()

    for section in (
        "`Collection scope`",
        "`Environment`",
        "`Route`",
        "`Version limits`",
        "`Artifacts`",
        "`Compatibility notes`",
        "`Handoff`",
        "`Unknowns`",
    ):
        assert section in skill
