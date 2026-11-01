"""Skill publication faults preserve the previous copy or explicit recovery bytes."""

from pathlib import Path

import pytest

import pt_snap_cli.core.skill_service as skill_module
from pt_snap_cli.core.errors import SkillCatalogError, SkillInstallError
from pt_snap_cli.core.skill_service import SkillService


@pytest.fixture
def skills(tmp_path):
    catalog = tmp_path / "catalog"
    source = catalog / "pt-snap-test"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: pt-snap-test\ndescription: Test skill\n---\nNew content\n", encoding="utf-8"
    )
    service = SkillService(
        catalog_dir=catalog, home=tmp_path / "home", cwd=tmp_path / "project", environ={}
    )
    return service, source, tmp_path / "installed" / "pt-snap-test"


@pytest.mark.parametrize("preexisting", [False, True])
def test_failed_staging_copy_does_not_publish_or_remove_previous_skill(
    skills, monkeypatch, preexisting
):
    service, source, dest = skills
    if preexisting:
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_bytes(b"previous skill")
    before = (source / "SKILL.md").read_bytes()

    def fail_copy(source, staging):
        staging.mkdir()
        (staging / "SKILL.md").write_bytes(b"partial copy")
        raise OSError("copy interrupted")

    monkeypatch.setattr(skill_module.shutil, "copytree", fail_copy)
    with pytest.raises(SkillInstallError, match="copy interrupted"):
        service.install_skills(dest_dir=dest.parent, force=True)
    assert (source / "SKILL.md").read_bytes() == before
    if preexisting:
        assert (dest / "SKILL.md").read_bytes() == b"previous skill"
        assert list(dest.parent.iterdir()) == [dest]
    else:
        assert not dest.exists()
        assert list(dest.parent.iterdir()) == []


def test_failed_publish_and_restore_keep_previous_backup(skills, monkeypatch):
    service, source, dest = skills
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_bytes(b"previous skill")
    replace = Path.replace

    def fail_staging_and_restore(path, target):
        if path.name.endswith((".pt-snap-staging", ".pt-snap-backup")):
            raise OSError("rename denied")
        return replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_staging_and_restore)
    with pytest.raises(SkillInstallError, match="rename denied"):
        service.install_skills(dest_dir=dest.parent, force=True)
    backups = list(dest.parent.glob("*.pt-snap-backup"))
    assert len(backups) == 1
    assert (backups[0] / "SKILL.md").read_bytes() == b"previous skill"
    assert not dest.exists()
    assert not list(dest.parent.glob("*.pt-snap-staging"))
    assert (source / "SKILL.md").is_file()


def test_backup_cleanup_failure_does_not_mask_successful_publication(skills, monkeypatch):
    service, source, dest = skills
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_bytes(b"previous skill")
    remove = skill_module._remove_path

    def fail_backup_cleanup(path):
        if path.name.endswith(".pt-snap-backup"):
            raise OSError("cleanup denied")
        remove(path)

    monkeypatch.setattr(skill_module, "_remove_path", fail_backup_cleanup)
    report = service.install_skills(dest_dir=dest.parent, force=True)
    assert report.results[0].action == "updated"
    assert (dest / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
    backups = list(dest.parent.glob("*.pt-snap-backup"))
    assert len(backups) == 1
    assert (backups[0] / "SKILL.md").read_bytes() == b"previous skill"
    assert not list(dest.parent.glob("*.pt-snap-staging"))


def test_uninstall_oserror_is_normalized_without_touching_other_paths(skills, monkeypatch):
    service, _, dest = skills
    service.install_skills(dest_dir=dest.parent)
    original = (dest / "SKILL.md").read_bytes()

    def denied(path):
        assert path == dest
        raise PermissionError("delete denied")

    monkeypatch.setattr(skill_module, "_remove_path", denied)
    with pytest.raises(SkillInstallError, match="Failed to uninstall") as caught:
        service.uninstall_skills(dest_dir=dest.parent)
    assert isinstance(caught.value.__cause__, PermissionError)
    assert (dest / "SKILL.md").read_bytes() == original
    assert list(dest.parent.iterdir()) == [dest]


def test_upgrade_current_skill_is_an_explicit_noop(skills):
    service, _, dest = skills
    service.install_skills(dest_dir=dest.parent)
    before = (dest / "SKILL.md").stat()
    report = service.upgrade_skills(dest_dir=dest.parent)
    after = (dest / "SKILL.md").stat()
    assert report.results[0].action == "already_installed"
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


def test_catalog_falls_back_to_package_and_fails_when_no_source_exists(tmp_path, monkeypatch):
    packaged = tmp_path / "bundled"
    monkeypatch.setattr(skill_module, "_discover_repo_skills_dir", lambda: None)
    monkeypatch.setattr(skill_module, "_packaged_skills_dir", lambda: packaged)
    assert skill_module.default_catalog_dir({}) == packaged
    monkeypatch.setattr(skill_module, "_packaged_skills_dir", lambda: None)
    with pytest.raises(SkillCatalogError, match="not available"):
        skill_module.default_catalog_dir({})


@pytest.mark.parametrize(
    "content", ["plain skill", "---\nname: incomplete", "---\n- list\n---\nbody"]
)
def test_legacy_frontmatter_falls_back_to_directory_name(tmp_path, content):
    catalog = tmp_path / "catalog"
    skill = catalog / "pt-snap-fallback"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(content, encoding="utf-8")
    specs = skill_module.list_catalog_skills(catalog)
    assert [(spec.name, spec.description) for spec in specs] == [("pt-snap-fallback", "")]


def test_unreadable_frontmatter_is_a_catalog_error_without_mutation(skills, monkeypatch):
    service, source, dest = skills
    read_text = Path.read_text

    def denied(path, *args, **kwargs):
        if path == source / "SKILL.md":
            raise PermissionError("read denied")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(SkillCatalogError, match="Failed to read skill file"):
        service.install_skills(dest_dir=dest.parent)
    assert not dest.parent.exists()
