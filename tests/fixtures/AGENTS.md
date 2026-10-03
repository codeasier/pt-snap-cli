# Executable Fixture Acceptance

Parent scope: [test contracts](../AGENTS.md).

Snapshot pickle files are executable inputs with a separate review lifecycle.
Being tracked by Git is not evidence that a new or modified object is trusted.

## Evidence Owners

| Record | Responsibility |
| --- | --- |
| `snapshots/PROVENANCE.md` | Source, rights/privacy review, sanitization evidence/limits, purpose, introduction decision, sizes and hashes |
| `snapshots/SHA256SUMS` | Machine-readable accepted object names and SHA-256 digests |
| `tests/_fixture_provenance.py` | Reviewed size table, exact manifest/set check, byte or LFS pointer validation without deserialization |
| `tests/test_fixture_provenance.py` | Regression coverage for the acceptance gate |

Before adding/replacing a pickle, complete provenance and non-executing static
opcode review and obtain explicit maintainer approval. Update the evidence,
manifest and expected sizes together. Historical exceptions apply only to the
objects named by their recorded decision, not replacements.

## Verification and LFS

Run `pytest tests/test_fixture_provenance.py` from the repository root before
import, split, runtime or benchmark code loads committed snapshots.
`tests/conftest.py` also enforces the gate before collection, including unexpected
pickles ignored by Git. Keep local analysis snapshots outside `snapshots/`.

A Git LFS pointer is accepted only when its object ID and declared size match the
reviewed object. Passing this check does not hydrate the object or make the pointer
deserializable. Hydrate selected benchmark/runtime inputs before loading, then
rerun verification. Changes to LFS handling require reviewing `.gitattributes`
and `.gitignore` alongside these records.
