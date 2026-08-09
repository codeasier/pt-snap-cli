from tests._fixture_provenance import (
    PROVENANCE,
    load_manifest,
    verify_snapshot_fixtures,
)


def test_executable_snapshot_fixtures_match_reviewed_manifest() -> None:
    verify_snapshot_fixtures()


def test_fixture_provenance_covers_every_manifest_object() -> None:
    text = PROVENANCE.read_text()
    for filename, digest in load_manifest().items():
        assert filename in text
        assert digest in text
