<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-08 | Updated: 2026-08-24 -->

# snapshot

Parent scope: [pt_snap_cli package](../AGENTS.md)

## Purpose
`snapshot` is the first-party runtime for trusted PyTorch memory snapshot representations. It owns pickle/JSON normalization, allocator replay, SnapshotDB adaptation, and replay-safe slicing; CLI/API product contracts remain in `core/`.

## Key Files
| File | Description |
|------|-------------|
| `representation.py` | Shared pickle/JSON load, save, canonicalization, device construction, and replay entry points. |
| `PROVENANCE.md` | Append-only source mapping, license decisions, and local runtime modification history. |
| `LICENSE` | MIT terms shipped with the snapshot runtime. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `base/` | Snapshot entities, frames, blocks, segments, devices, and enum conversions. |
| `simulate/` | Allocator state, mutation, lookup, hook dispatch, and replay execution. |
| `tools/adaptors/` | Snapshot-to-database records, schemas, and replay-driven database generation. |
| `tools/slice_dump/` | Boundary-state reconstruction and per-device slice serialization. |
| `util/` | File, logging, timer, and SQLite metadata helpers retained by the runtime. |

## For AI Agents

### Working In This Directory
- Treat every pickle load as trusted-code execution; never inspect an untrusted snapshot by deserializing it.
- Keep user-facing import/split validation and publication semantics in `core/`; this subtree provides runtime mechanisms.
- Preserve representation compatibility, original event IDs across slices, and replay-valid allocator state.
- `PROVENANCE.md` is append-only. The guard compares old/new Git blobs on PRs, main pushes, and releases; runtime PRs also require the exact decision/reason labels from `.github/pull_request_template.md`.

### Testing Requirements
- Run `pytest tests/test_fixture_provenance.py` before any runtime suite that deserializes committed fixtures, then run `pytest tests/snapshot` for runtime changes.
- Run affected import/split tests under `tests/core/` and `pytest tests/test_governance.py` when runtime or provenance changes.

### Change Together
- Representation field changes require loader/serializer, replay, slice, fixture, and golden-observation review.
- Database adaptor changes require SnapshotDB schema docs and import/runtime tests.
- Slice runtime changes require `src/pt_snap_cli/core/split_service.py`, split docs, and replay/publication tests to remain aligned.

## Dependencies

### Internal
- Core import services use the snapshot import backend; `SplitService` calls representation and slicing APIs directly.
- `tests/snapshot/` owns focused representation, replay, adaptor, and slice coverage; `tests/fixtures/AGENTS.md` owns executable fixture acceptance.

### External
- Python pickle and SQLite standard-library behavior; pickle input is never sandboxed.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
