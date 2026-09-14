from __future__ import annotations

from pathlib import Path

from pt_snap_cli.core.skill_service import list_catalog_skills

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_SKILLS = REPO_ROOT / "skills"
BUNDLED_SKILLS = REPO_ROOT / "src" / "pt_snap_cli" / "bundled_skills"


def test_bundled_skills_match_repo_catalog() -> None:
    repo = {spec.name: spec for spec in list_catalog_skills(REPO_SKILLS)}
    bundled = {spec.name: spec for spec in list_catalog_skills(BUNDLED_SKILLS)}
    assert set(repo) == set(bundled)
    for name, spec in repo.items():
        repo_text = (spec.source_dir / "SKILL.md").read_text(encoding="utf-8")
        bundled_text = (bundled[name].source_dir / "SKILL.md").read_text(encoding="utf-8")
        assert bundled_text == repo_text
