from __future__ import annotations

import hashlib
import re
from pathlib import Path

FIXTURE_DIR = Path("tests/fixtures/snapshots")
MANIFEST = FIXTURE_DIR / "SHA256SUMS"
PROVENANCE = FIXTURE_DIR / "PROVENANCE.md"
PICKLE_SUFFIXES = {".pkl", ".pickle"}
LFS_POINTER = re.compile(
    rb"version https://git-lfs.github.com/spec/v1\n"
    rb"oid sha256:(?P<digest>[0-9a-f]{64})\n"
    rb"size (?P<size>\d+)\n?\Z"
)
EXPECTED_SIZES = {
    "snapshot_1768383987920985470.pkl": 573970,
    "snapshot_expandable.pkl": 581140,
    "snapshot_import_131k_sanitized.pickle": 43140853,
    "snapshot_import_628k_sanitized.pickle": 175057085,
    "snapshot_with_empty_cache_expandable.pkl": 614145,
    "snapshot_with_empty_cache.pkl": 617060,
    "snapshot_with_multi_devices.pkl": 1355829,
}


class FixtureProvenanceError(RuntimeError):
    pass


def load_manifest() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in MANIFEST.read_text().splitlines():
        digest, filename = line.split("  ", 1)
        if filename in entries:
            raise FixtureProvenanceError(f"Duplicate fixture manifest entry: {filename}")
        entries[filename] = digest
    return entries


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fixture:
        for chunk in iter(lambda: fixture.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_snapshot_fixtures() -> None:
    expected = load_manifest()
    fixtures = {
        path.name: path for path in FIXTURE_DIR.iterdir() if path.suffix.lower() in PICKLE_SUFFIXES
    }
    if set(fixtures) != set(expected) or set(fixtures) != set(EXPECTED_SIZES):
        raise FixtureProvenanceError("Executable fixture set does not match the reviewed manifest")

    for filename, path in fixtures.items():
        pointer = LFS_POINTER.fullmatch(path.read_bytes()) if path.stat().st_size < 1024 else None
        actual_digest = pointer.group("digest").decode() if pointer else _sha256(path)
        actual_size = int(pointer.group("size")) if pointer else path.stat().st_size
        if actual_digest != expected[filename]:
            raise FixtureProvenanceError(f"Fixture checksum mismatch: {filename}")
        if actual_size != EXPECTED_SIZES[filename]:
            raise FixtureProvenanceError(f"Fixture size mismatch: {filename}")
