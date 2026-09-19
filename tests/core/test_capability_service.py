from pathlib import Path
from unittest.mock import patch

import pytest

from pt_snap_cli.core.capability_service import CapabilityService
from pt_snap_cli.query.registry import QueryRegistry


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PT_SNAP_SKILLS_DIR", raising=False)
    with patch.object(Path, "home", return_value=tmp_path):
        QueryRegistry.reset()
        yield
        QueryRegistry.reset()


def test_catalog_includes_version_template_contracts_and_skills() -> None:
    catalog = CapabilityService().catalog()
    payload = CapabilityService().catalog_to_dict(catalog)

    assert payload["cli_version"] == catalog.cli_version
    names = {item["name"] for item in payload["templates"]}
    assert {"leak_detection", "preexisting_live", "freed_block_lifetime"} <= names
    leak = next(item for item in payload["templates"] if item["name"] == "leak_detection")
    assert leak["semantics_version"] == 1
    assert "min_size" in leak["parameters"]
    assert "device_id" not in leak["parameters"]
    skill_names = {item["name"] for item in payload["skills"]}
    assert "pt-snap-helper" in skill_names
    assert "pt-snap-memory-leak" in skill_names
