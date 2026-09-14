from __future__ import annotations

from pathlib import Path

from pt_snap_cli.core.skill_service import list_catalog_skills

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_SKILLS = REPO_ROOT / "skills"
BUNDLED_SKILLS = REPO_ROOT / "src" / "pt_snap_cli" / "bundled_skills"


def _skill_file_map(skill_dir: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        files[path.relative_to(skill_dir).as_posix()] = path.read_bytes()
    return files


def test_bundled_skills_match_repo_catalog() -> None:
    repo = {spec.name: spec for spec in list_catalog_skills(REPO_SKILLS)}
    bundled = {spec.name: spec for spec in list_catalog_skills(BUNDLED_SKILLS)}
    assert set(repo) == set(bundled)
    for name, spec in repo.items():
        assert _skill_file_map(spec.source_dir) == _skill_file_map(bundled[name].source_dir)


def test_package_data_includes_bundled_skill_tree() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"bundled_skills/**/*"' in text
    assert '"bundled_skills/*/SKILL.md"' not in text
