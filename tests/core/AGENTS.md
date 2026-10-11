# Service Boundary Tests

Parent scope: [test contracts](../AGENTS.md).
Implementation: [core services](../../src/pt_snap_cli/core/AGENTS.md).

## Focused Test Map

| Files | Behavior under test |
| --- | --- |
| `test_focus_service.py` | Resolution, database/device validation, project/global persistence |
| `test_context_cache.py` | LRU eviction, replacement signatures, invalidation and close |
| `test_query_service.py` | Catalog/result contracts, focus/device selection, executor reuse and error normalization |
| `test_capability_service.py`, `test_overview_service.py` | Catalog and read-only device/event-bound/metadata probes |
| `test_report_service.py` | Named-query composition and report fields |
| `test_import_models.py`, `test_import_errors.py`, `test_import_metadata.py` | Import inputs, error context, metadata/cache/source identity |
| `test_import_service.py` | Staging, import reuse, source changes, publication/focus transaction |
| `test_import_backend_failures.py` | Backup short/zero writes, publication/focus/rollback faults, fd closure and recovery evidence |
| `test_split_service.py` | Strategy/device validation, formats, replay, cleanup, races and no-replace publication |
| `test_skill_service.py` | Catalog precedence, host/scope/custom destinations, status and mutation preflight |
| `test_json_codec.py` | Path/dataclass conversion and JSON envelopes |

## What to Assert

- Assert normalized service errors and stable result fields, not incidental
  lower-layer messages. Add CLI/API contract cases when a shared result changes.
- Publication fault injection must check the previous destination, focus file,
  temporary files and owned descriptors. A raised exception alone does not prove
  rollback. Rollback failure is a distinct path with recovery evidence.
- Split failure/race cases must prove no partially published directory and no
  replacement of an independently created destination.
- Skill mutation preflight must cover non-skill paths and all selected locations
  before deleting any copy; list status and host loading are separate concepts.
- Cache work also exercises `tests/test_analyzer_lifecycle.py`,
  `tests/test_snapshot_analyzer_cache.py`, and `tests/test_query_cache_perf.py`.
  Service reuse after close and analyzer terminal closure need separate cases.

Run `pytest tests/core` or the owning file from the repository root. Follow the
parent's fixture gate before import/split cases and resource ownership rules for
all cached services. Cross-runtime changes additionally use `tests/snapshot/`.

## Installed Dataset Scale Acceptance

`test_dataset_scale_workload.py` checks the test-owned allocator workload and
arithmetic oracle on 100 events. `test_dataset_scale_acceptance.py` retains the
synthetic default-budget gates and has one opt-in wheel acceptance node:
`test_installed_trusted_producer_default_export_cli_and_api`.

Set `PT_SNAP_ACCEPTANCE_WHEEL` to an absolute wheel path. The node creates a fresh
venv without system packages, installs the wheel and its dependencies, clears
source/focus/query-budget overrides, and executes its actual `pt-snap` console
script in isolated HOME/CWD. Optional `PT_SNAP_ACCEPTANCE_WHEELHOUSE` enables
fully offline dependency installation with `--no-index --find-links`.
`PT_SNAP_ACCEPTANCE_EVIDENCE_DIR` preserves subprocess commands, exit codes,
timings, stdout/stderr, versions, wheel/source/member hashes, and acceptance JSON.
The same acceptance is stored in the JUnit `dataset_acceptance` property (use
`-o junit_family=xunit1`). Timings are observations, not machine-speed thresholds.

The real importer exports exactly 1,000,000 events using the unchanged 500,000
default capacity. The complete installed catalog must be classified: currently
11 dataset-supported templates succeed with CLI/API result parity and independent
known-result assertions; `event_frames` and `active_memory_frame_tree_at_event`
are explicit dataset rejections. Both report commands run through the console:
`peak-memory` succeeds, while `memory-tree` preserves its documented unsupported
dataset contract. Source and every exported member remain unchanged. This is
trusted test-owned producer/replay acceptance, not live capture or upstream GUI
acceptance. Do not turn a missing wheel/skip into a successful nightly gate.

The separate required nightly
`test_installed_default_export_short_final_shard_boundary` retains the original
500,002-event shape: 500,000 real events followed by exactly two. It checks exact
terminal member lifetimes and installed CLI/API completion/survival boundaries,
including unchanged hashes. Its `dataset_boundary_acceptance` JUnit property and
per-test evidence subdirectory preserve independent results without overwriting
the million-event gate's evidence. Both cases are mandatory in the runner.
