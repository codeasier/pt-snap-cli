from __future__ import annotations

from pathlib import Path

import pytest

from pt_snap_cli.core.errors import (
    InvalidSkillTargetError,
    SkillCatalogError,
    SkillInstallError,
    SkillNotFoundError,
)
from pt_snap_cli.core.skill_service import (
    SkillService,
    default_catalog_dir,
    human_skill_summary,
    skill_dir_digest,
)


def _write_skill(root: Path, name: str, description: str, body: str = "body\n") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{body}",
        encoding="utf-8",
    )
    return skill_dir


@pytest.fixture
def catalog(tmp_path: Path) -> Path:
    root = tmp_path / "catalog"
    _write_skill(root, "pt-snap-demo", "Demo skill")
    _write_skill(root, "pt-snap-other", "Other skill")
    return root


@pytest.fixture
def service(catalog: Path, tmp_path: Path) -> SkillService:
    return SkillService(
        catalog_dir=catalog,
        home=tmp_path / "home",
        cwd=tmp_path / "project",
        environ={},
    )


def test_list_skills_marks_missing_then_installed(service: SkillService, tmp_path: Path) -> None:
    listings = {
        item.name: item for item in service.list_skills(hosts=("claude",), scopes=("user",))
    }
    assert listings["pt-snap-demo"].status == "missing"
    assert listings["pt-snap-demo"].locations[0].path == (
        tmp_path / "home" / ".claude" / "skills" / "pt-snap-demo"
    )

    service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    listings = {
        item.name: item for item in service.list_skills(hosts=("claude",), scopes=("user",))
    }
    assert listings["pt-snap-demo"].status == "installed"
    assert listings["pt-snap-other"].status == "missing"


def test_install_all_default_hosts_and_detect_outdated(
    service: SkillService, tmp_path: Path
) -> None:
    report = service.install_skills(scope="user")
    actions = {(item.name, item.host, item.action) for item in report.results}
    assert actions == {
        ("pt-snap-demo", "agents", "installed"),
        ("pt-snap-demo", "claude", "installed"),
        ("pt-snap-other", "agents", "installed"),
        ("pt-snap-other", "claude", "installed"),
    }
    assert (tmp_path / "home" / ".agents" / "skills" / "pt-snap-demo" / "SKILL.md").is_file()

    dest = tmp_path / "home" / ".claude" / "skills" / "pt-snap-demo" / "SKILL.md"
    dest.write_text(dest.read_text(encoding="utf-8") + "local change\n", encoding="utf-8")
    listings = {
        item.name: item for item in service.list_skills(hosts=("claude",), scopes=("user",))
    }
    assert listings["pt-snap-demo"].status == "outdated"

    with pytest.raises(SkillInstallError, match="--force"):
        service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user")

    updated = service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user", force=True)
    assert updated.results[0].action == "updated"
    listings = {
        item.name: item for item in service.list_skills(hosts=("claude",), scopes=("user",))
    }
    assert listings["pt-snap-demo"].status == "installed"


def test_project_scope_and_unknown_inputs(service: SkillService, tmp_path: Path) -> None:
    report = service.install_skills(["pt-snap-demo"], hosts=("codex",), scope="project")
    dest = tmp_path / "project" / ".codex" / "skills" / "pt-snap-demo"
    assert dest.joinpath("SKILL.md").is_file()
    assert report.results[0].scope == "project"

    again = service.install_skills(["pt-snap-demo"], hosts=("codex",), scope="project")
    assert again.results[0].action == "already_installed"

    with pytest.raises(SkillNotFoundError, match="pt-snap-missing"):
        service.install_skills(["pt-snap-missing"], hosts=("claude",))
    with pytest.raises(InvalidSkillTargetError, match="windsurf"):
        service.install_skills(["pt-snap-demo"], hosts=("windsurf",))
    with pytest.raises(InvalidSkillTargetError, match="global"):
        service.install_skills(["pt-snap-demo"], scope="global")


def test_upgrade_updates_outdated_and_skips_missing(service: SkillService) -> None:
    service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    dest = service.skill_destination("claude", "user", "pt-snap-demo") / "SKILL.md"
    dest.write_text(dest.read_text(encoding="utf-8") + "local change\n", encoding="utf-8")

    report = service.upgrade_skills(hosts=("claude",), scope="user")
    actions = {item.name: item.action for item in report.results}
    assert actions["pt-snap-demo"] == "updated"
    assert actions["pt-snap-other"] == "not_installed"

    current = service.upgrade_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    assert current.results[0].action == "already_installed"
    listings = {
        item.name: item for item in service.list_skills(hosts=("claude",), scopes=("user",))
    }
    assert listings["pt-snap-demo"].status == "installed"


def test_uninstall_removes_installed_skill(service: SkillService) -> None:
    service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    dest = service.skill_destination("claude", "user", "pt-snap-demo")
    assert dest.joinpath("SKILL.md").is_file()

    report = service.uninstall_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    assert report.results[0].action == "uninstalled"
    assert not dest.exists()

    again = service.uninstall_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    assert again.results[0].action == "not_installed"


def test_all_locations_uninstall_removes_every_listed_copy(
    service: SkillService,
) -> None:
    service.install_skills(["pt-snap-demo"], hosts=("cursor",), scope="user")
    service.install_skills(["pt-snap-demo"], hosts=("agents", "claude"), scope="project")
    cursor = service.skill_destination("cursor", "user", "pt-snap-demo")
    agents_project = service.skill_destination("agents", "project", "pt-snap-demo")
    claude_project = service.skill_destination("claude", "project", "pt-snap-demo")

    report = service.uninstall_skills(["pt-snap-demo"], all_locations=True)
    actions = {(item.host, item.scope, item.action) for item in report.results}
    assert actions == {
        ("cursor", "user", "uninstalled"),
        ("agents", "project", "uninstalled"),
        ("claude", "project", "uninstalled"),
    }
    assert not cursor.exists()
    assert not agents_project.exists()
    assert not claude_project.exists()


def test_all_locations_uninstall_reports_default_not_installed(
    service: SkillService,
) -> None:
    report = service.uninstall_skills(["pt-snap-demo"], all_locations=True)
    actions = {(item.host, item.scope, item.action) for item in report.results}
    assert actions == {
        ("agents", "user", "not_installed"),
        ("claude", "user", "not_installed"),
    }


def test_default_python_uninstall_stays_on_install_destinations(
    service: SkillService,
) -> None:
    service.install_skills(["pt-snap-demo"], hosts=("cursor",), scope="user")
    service.install_skills(["pt-snap-demo"], hosts=("agents",), scope="project")

    report = service.uninstall_skills(["pt-snap-demo"])
    actions = {(item.host, item.scope, item.action) for item in report.results}
    assert actions == {
        ("agents", "user", "not_installed"),
        ("claude", "user", "not_installed"),
    }
    assert (
        service.skill_destination("cursor", "user", "pt-snap-demo").joinpath("SKILL.md").is_file()
    )
    assert (
        service.skill_destination("agents", "project", "pt-snap-demo")
        .joinpath("SKILL.md")
        .is_file()
    )


def test_all_locations_uninstall_rejects_target_or_dir(
    service: SkillService, tmp_path: Path
) -> None:
    with pytest.raises(InvalidSkillTargetError, match="--target or --dir"):
        service.uninstall_skills(["pt-snap-demo"], hosts=("claude",), all_locations=True)
    with pytest.raises(InvalidSkillTargetError, match="--target or --dir"):
        service.uninstall_skills(["pt-snap-demo"], dest_dir=tmp_path / "skills", all_locations=True)


def test_all_locations_uninstall_refuses_before_mutating_conflict(
    service: SkillService,
) -> None:
    service.install_skills(["pt-snap-demo"], hosts=("cursor",), scope="user")
    dest = service.skill_destination("claude", "project", "pt-snap-demo")
    dest.mkdir(parents=True)
    notes = dest / "notes.txt"
    notes.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(SkillInstallError, match="Refusing to delete"):
        service.uninstall_skills(["pt-snap-demo"], all_locations=True)
    assert (
        service.skill_destination("cursor", "user", "pt-snap-demo").joinpath("SKILL.md").is_file()
    )
    assert notes.is_file()


def test_human_skill_summary_keeps_first_sentence() -> None:
    text = (
        "Collect a snapshot by dumping a `.pkl` file. Not for diagnosing an "
        "existing SnapshotDB and not for importing pickle."
    )
    assert human_skill_summary(text) == "Collect a snapshot by dumping a `.pkl` file."


def test_custom_dir_install_list_upgrade_and_uninstall(
    service: SkillService, tmp_path: Path
) -> None:
    dest_dir = tmp_path / "other-agent" / "skills"
    report = service.install_skills(["pt-snap-demo"], dest_dir=dest_dir)
    skill_dir = dest_dir / "pt-snap-demo"
    assert report.results[0].host == "custom"
    assert report.results[0].path == skill_dir
    assert skill_dir.joinpath("SKILL.md").is_file()

    listings = {item.name: item for item in service.list_skills(dest_dir=dest_dir)}
    assert listings["pt-snap-demo"].status == "installed"
    assert listings["pt-snap-demo"].locations[0].host == "custom"
    assert listings["pt-snap-other"].status == "missing"

    skill_dir.joinpath("SKILL.md").write_text(
        skill_dir.joinpath("SKILL.md").read_text(encoding="utf-8") + "local change\n",
        encoding="utf-8",
    )
    upgraded = service.upgrade_skills(["pt-snap-demo"], dest_dir=dest_dir)
    assert upgraded.results[0].action == "updated"

    removed = service.uninstall_skills(["pt-snap-demo"], dest_dir=dest_dir)
    assert removed.results[0].action == "uninstalled"
    assert not skill_dir.exists()


def test_custom_dir_rejects_host_and_scope_filters(service: SkillService, tmp_path: Path) -> None:
    dest_dir = tmp_path / "skills"
    with pytest.raises(InvalidSkillTargetError, match="--target"):
        service.install_skills(["pt-snap-demo"], hosts=("claude",), dest_dir=dest_dir)
    with pytest.raises(InvalidSkillTargetError, match="--project"):
        service.install_skills(["pt-snap-demo"], scope="project", dest_dir=dest_dir)
    with pytest.raises(InvalidSkillTargetError, match="--target"):
        service.list_skills(hosts=("claude",), dest_dir=dest_dir)


def test_custom_dir_rejects_file_path(service: SkillService, tmp_path: Path) -> None:
    dest_file = tmp_path / "not-a-dir"
    dest_file.write_text("nope\n", encoding="utf-8")
    with pytest.raises(InvalidSkillTargetError, match="must be a directory"):
        service.install_skills(["pt-snap-demo"], dest_dir=dest_file)


def test_install_refuses_existing_destination_without_skill_md(
    service: SkillService,
) -> None:
    dest = service.skill_destination("claude", "user", "pt-snap-demo")
    dest.mkdir(parents=True)
    notes = dest / "notes.txt"
    notes.write_text("keep me\n", encoding="utf-8")

    listings = {
        item.name: item for item in service.list_skills(hosts=("claude",), scopes=("user",))
    }
    assert listings["pt-snap-demo"].status == "outdated"

    with pytest.raises(SkillInstallError, match="--force"):
        service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    assert notes.is_file()

    updated = service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user", force=True)
    assert updated.results[0].action == "updated"
    assert dest.joinpath("SKILL.md").is_file()
    assert not notes.exists()


def test_upgrade_refuses_existing_destination_without_skill_md(
    service: SkillService,
) -> None:
    dest = service.skill_destination("claude", "user", "pt-snap-demo")
    dest.mkdir(parents=True)
    notes = dest / "notes.txt"
    notes.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(SkillInstallError, match="missing SKILL.md"):
        service.upgrade_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    assert notes.is_file()
    assert not dest.joinpath("SKILL.md").exists()


def test_install_refuses_before_mutating_later_host_conflict(
    service: SkillService,
) -> None:
    claude_dest = service.skill_destination("claude", "user", "pt-snap-demo")
    claude_dest.mkdir(parents=True)
    notes = claude_dest / "notes.txt"
    notes.write_text("keep me\n", encoding="utf-8")
    agents_dest = service.skill_destination("agents", "user", "pt-snap-demo")

    with pytest.raises(SkillInstallError, match="--force"):
        service.install_skills(["pt-snap-demo"], scope="user")
    assert notes.is_file()
    assert not agents_dest.exists()


def test_upgrade_refuses_before_mutating_later_host_conflict(
    service: SkillService,
) -> None:
    service.install_skills(["pt-snap-demo"], hosts=("agents",), scope="user")
    agents_skill = service.skill_destination("agents", "user", "pt-snap-demo") / "SKILL.md"
    agents_skill.write_text(
        agents_skill.read_text(encoding="utf-8") + "local change\n",
        encoding="utf-8",
    )
    claude_dest = service.skill_destination("claude", "user", "pt-snap-demo")
    claude_dest.mkdir(parents=True)
    notes = claude_dest / "notes.txt"
    notes.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(SkillInstallError, match="missing SKILL.md"):
        service.upgrade_skills(["pt-snap-demo"], scope="user")
    assert "local change" in agents_skill.read_text(encoding="utf-8")
    assert notes.is_file()


def test_uninstall_refuses_existing_destination_without_skill_md(
    service: SkillService,
) -> None:
    dest = service.skill_destination("claude", "user", "pt-snap-demo")
    dest.mkdir(parents=True)
    notes = dest / "notes.txt"
    notes.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(SkillInstallError, match="Refusing to delete"):
        service.uninstall_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    assert notes.is_file()
    assert dest.is_dir()


def test_uninstall_refuses_before_mutating_later_host_conflict(
    service: SkillService,
) -> None:
    service.install_skills(["pt-snap-demo"], hosts=("agents",), scope="user")
    agents_dest = service.skill_destination("agents", "user", "pt-snap-demo")
    claude_dest = service.skill_destination("claude", "user", "pt-snap-demo")
    claude_dest.mkdir(parents=True)
    notes = claude_dest / "notes.txt"
    notes.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(SkillInstallError, match="Refusing to delete"):
        service.uninstall_skills(["pt-snap-demo"], scope="user")
    assert agents_dest.joinpath("SKILL.md").is_file()
    assert notes.is_file()


def test_publish_restores_previous_copy_when_replace_fails(
    service: SkillService, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user")
    dest = service.skill_destination("claude", "user", "pt-snap-demo")
    skill_md = dest / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + "local change\n", encoding="utf-8")
    original_replace = Path.replace

    def fake_replace(self: Path, target: Path, /) -> Path:
        if ".pt-snap-staging" in self.name:
            raise OSError("replace failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fake_replace)
    with pytest.raises(SkillInstallError, match="Failed to install skill"):
        service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user", force=True)
    assert "local change" in skill_md.read_text(encoding="utf-8")
    leftovers = [path.name for path in dest.parent.iterdir() if "pt-snap-staging" in path.name]
    assert leftovers == []


def test_publish_translates_parent_mkdir_oserror(service: SkillService, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").write_text("not a directory\n", encoding="utf-8")
    with pytest.raises(SkillInstallError, match="Failed to install skill"):
        service.install_skills(["pt-snap-demo"], hosts=("claude",), scope="user")


def test_catalog_translates_unreadable_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = tmp_path / "catalog"
    _write_skill(catalog, "pt-snap-demo", "Demo")
    original_iterdir = Path.iterdir

    def fake_iterdir(self: Path):
        if self == catalog:
            raise PermissionError("denied")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    service = SkillService(
        catalog_dir=catalog,
        home=tmp_path / "home",
        cwd=tmp_path / "project",
        environ={},
    )
    with pytest.raises(SkillCatalogError, match="Failed to read skill catalog"):
        service.list_catalog()


def test_digest_translates_unreadable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = _write_skill(tmp_path / "catalog", "pt-snap-demo", "Demo")
    skill_md = skill_dir / "SKILL.md"
    original_read_bytes = Path.read_bytes

    def fake_read_bytes(self: Path) -> bytes:
        if self == skill_md:
            raise PermissionError("denied")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)
    with pytest.raises(SkillCatalogError, match="Failed to read skill file"):
        skill_dir_digest(skill_dir)


def test_agents_shared_roots(service: SkillService, tmp_path: Path) -> None:
    report = service.install_skills(["pt-snap-demo"], hosts=("agents",), scope="user")
    assert report.results[0].path == tmp_path / "home" / ".agents" / "skills" / "pt-snap-demo"
    project = service.install_skills(["pt-snap-demo"], hosts=("agents",), scope="project")
    assert project.results[0].path == tmp_path / "project" / ".agents" / "skills" / "pt-snap-demo"


def test_claude_config_dir_overrides_user_root(catalog: Path, tmp_path: Path) -> None:
    config = tmp_path / "claude-config"
    service = SkillService(
        catalog_dir=catalog,
        home=tmp_path / "home",
        cwd=tmp_path / "project",
        environ={"CLAUDE_CONFIG_DIR": str(config)},
    )
    assert service.skill_destination("claude", "user", "pt-snap-demo") == (
        config / "skills" / "pt-snap-demo"
    )
    assert service.skill_destination("claude", "project", "pt-snap-demo") == (
        tmp_path / "project" / ".claude" / "skills" / "pt-snap-demo"
    )
    assert service.skill_destination("cursor", "user", "pt-snap-demo") == (
        tmp_path / "home" / ".cursor" / "skills" / "pt-snap-demo"
    )
    assert service.skill_destination("agents", "user", "pt-snap-demo") == (
        tmp_path / "home" / ".agents" / "skills" / "pt-snap-demo"
    )


def test_codex_home_overrides_user_root(catalog: Path, tmp_path: Path) -> None:
    config = tmp_path / "codex-home"
    service = SkillService(
        catalog_dir=catalog,
        home=tmp_path / "home",
        cwd=tmp_path / "project",
        environ={"CODEX_HOME": str(config)},
    )
    assert service.skill_destination("codex", "user", "pt-snap-demo") == (
        config / "skills" / "pt-snap-demo"
    )
    assert service.skill_destination("codex", "project", "pt-snap-demo") == (
        tmp_path / "project" / ".codex" / "skills" / "pt-snap-demo"
    )
    assert service.skill_destination("agents", "user", "pt-snap-demo") == (
        tmp_path / "home" / ".agents" / "skills" / "pt-snap-demo"
    )


def test_default_catalog_includes_repo_skills() -> None:
    catalog = default_catalog_dir(environ={})
    names = {spec.name for spec in SkillService(catalog_dir=catalog).list_catalog()}
    assert names == {
        "pt-snap-ascend-npu-collect",
        "pt-snap-helper",
        "pt-snap-memory-fragmentation",
        "pt-snap-memory-leak",
        "pt-snap-memory-peak-breakdown",
        "pt-snap-setup",
    }
    assert (catalog / "pt-snap-helper" / "SKILL.md").is_file()
    assert (catalog / "pt-snap-setup" / "SKILL.md").is_file()


def test_catalog_rejects_traversal_frontmatter_name(tmp_path: Path) -> None:
    skill_dir = tmp_path / "catalog" / "bad-skill"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: ../../evil\ndescription: Traversal\n---\n\n# bad\n",
        encoding="utf-8",
    )
    service = SkillService(
        catalog_dir=tmp_path / "catalog",
        home=tmp_path / "home",
        cwd=tmp_path / "project",
        environ={},
    )
    with pytest.raises(SkillCatalogError, match="not a valid skill directory name"):
        service.list_catalog()


def test_catalog_rejects_malformed_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "catalog" / "broken-skill"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: [\n---\n\n# broken\n",
        encoding="utf-8",
    )
    service = SkillService(
        catalog_dir=tmp_path / "catalog",
        home=tmp_path / "home",
        cwd=tmp_path / "project",
        environ={},
    )
    with pytest.raises(SkillCatalogError, match="Invalid SKILL.md frontmatter"):
        service.list_catalog()


def test_injected_environ_selects_catalog_and_ignores_process_env(
    catalog: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    poison = tmp_path / "poison-catalog"
    _write_skill(poison, "poison-skill", "Poison")
    monkeypatch.setenv("PT_SNAP_SKILLS_DIR", str(poison))

    ignored = SkillService(
        home=tmp_path / "home",
        cwd=tmp_path / "project",
        environ={},
    )
    ignored_names = {spec.name for spec in ignored.list_catalog()}
    assert "poison-skill" not in ignored_names
    assert "pt-snap-setup" in ignored_names

    selected = SkillService(
        home=tmp_path / "home",
        cwd=tmp_path / "project",
        environ={"PT_SNAP_SKILLS_DIR": str(catalog)},
    )
    selected_names = {spec.name for spec in selected.list_catalog()}
    assert selected_names == {"pt-snap-demo", "pt-snap-other"}
