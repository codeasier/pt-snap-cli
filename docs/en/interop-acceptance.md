# Interoperability acceptance and bounded performance

[中文](../zh/interop-acceptance.md) | English

## Evidence layers and fixed target

The ONLY upstream target is **Ascend/msinsight@101f65b877a267ffd5f66ea3834706057ba243e5**.
Protocol/schema validation, isolated source-function checks, synthetic CI,
reading an actual original-producer artifact, and actual GUI/C++ consumption are
DIFFERENT evidence layers. None implies the next. **GUI is human-deferred,
pending/not-run**; the issue stays open. The existing pending note is
[#205](https://github.com/codeasier/pt-snap-cli/issues/205#issuecomment-5987264017).

The acceptance tools are original interface-facts/reference code, not vendor
copies. Fixed [producer schema](https://api.github.com/repos/Ascend/msinsight/git/blobs/1fe50a5136f85365db55f4632d58f3cf7090431e),
[manifest/backfill](https://api.github.com/repos/Ascend/msinsight/git/blobs/95612509ef990ac6b7034919dae4938cc6acf3ad),
[parser predicates](https://api.github.com/repos/Ascend/msinsight/git/blobs/40046e6a92ff5af776ee55bd4cdd4586745af3c2)
and [salt order](https://api.github.com/repos/Ascend/msinsight/git/blobs/ca421c7b33f3a0050df9e7a01e666f558801bc2f)
are the source of protocol facts. Ascend source is Mulan PSL v2; upstream docs
are separately CC BY 4.0, not automatically covered by this project's MIT lineage.
A port needs snapshot provenance/PR decisions and retained notices. Executable
pickle trust is a SEPARATE fixture review; no new committed pickle is added here.

## Forward chain: trusted source → physical export → FUTURE GUI

1. Review/trust the source separately: pickle is executable input, not a sandbox.
   Record exact source SHA256, size, selected device and capacity. Default import
   stays single-db; native and compatible outputs are explicit distinct modes.
2. Use an ABSENT destination. For the future original-source GUI entrance, the
   compatible artifact must be adjacent to the SAME original pickle:

   ```bash
   pt-snap import /capture/snapshot.pkl --format msinsight --events-per-slice 2000 --device 0 --no-focus --json
   pt-snap overview /capture/snapshot.pkl.msinsight --json
   ```

   `--format compatibility-v1` is the alias. `--output-dir` chooses a different
   parent, which does NOT create a direct-directory GUI entrance. Do not overwrite
   an existing original/external cache even with force. Only identical recognized
   pt-snap ownership/identity can reuse; changed members invalidate attestation.
   `cacheHash=SHA256(b"mem_snapshot_parser_v2" + raw_source_bytes)` is distinct from
   `ptSnap.identity` (source/options/format/semantic-version/member identity).
3. Compare physical base schemas, dictionaries, ALL nine real-event columns,
   real ID/range/action/stream/counter/text values and lifecycle rows against an
   existing reviewed original artifact of the SAME source/options. Real block
   IDs INCLUDING zero remain exact. Negative block IDs are producer-local tokens:
   compare all other six fields INCLUDING state as MULTISETS globally/per shard,
   preserving multiplicity; validate each artifact's own token stability. This
   does not prove cross-producer negative object identity. Never deduplicate by
   address, rewrite IDs, or patch the fixed producer to force equality.
4. **Later, after explicit human authorization**, open the same original pickle
   using the exact recorded real GUI build. Complete the checklist below. Physical
   equality and salted-hash equality are NOT GUI cache-reuse acceptance.

## Reverse chain: existing original artifact → complete focus → canonical reference

No producer is downloaded or executed by the runner. An original artifact must
already exist, be closed/finalized, and have a reviewed receipt. It may have NO
metadata/reference/frame extensions. Its valid metadata result is
`unavailable` / `metadata_missing`, not invented provenance. Invalid metadata,
incomplete validation and unknown reasons stop.

```bash
pt-snap focus /capture/snapshot.pkl.msinsight/manifest.json --device 0 --json
pt-snap capabilities --json
pt-snap overview /capture/snapshot.pkl.msinsight --json
pt-snap query /capture/snapshot.pkl.msinsight --device 0 --template-use memory_peak --json
pt-snap report peak-memory /capture/snapshot.pkl.msinsight --device 0 --metric reserved --start-id 0 --end-id 100 --limit 20 --json
```

`focus` persists a project choice: use an isolated explicitly approved acceptance
project. Diagnostic skills themselves do NOT persist focus, import or install.
For WHOLE-DATASET scope only COMPLETE validated directories/manifests are accepted,
not arbitrary folders or a single ready slice. An explicitly chosen member can
remain a standalone input under standalone policies, NOT whole-dataset scope. Closed compatibility-v1 uses immutable read-only SQLite,
including checkpointed sidecar-free WAL headers; all aliases/live or dangling
WAL/SHM/journal sidecars are rejected before opening. Native retains its stricter
WAL policy; standalone analysis stays `mode=ro` without immutable.

Optional local runner, from the repository root using the intended interpreter:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python benchmarks/interop_acceptance.py \
  --artifact /capture/snapshot.pkl.msinsight --receipt /evidence/reviewed-receipt.json \
  --source /capture/snapshot.pkl --device 0 --output /evidence/NEW-acceptance
```

Optional `--compatible /export/snapshot.pkl.msinsight` compares an EXISTING forward
export; it never generates it. Receipt fields are `revision` (exact full SHA),
`artifactHashes` (ALL relative regular member names → SHA256), and, for the optional
source/forward checks, `fixtureSHA256`, `fixtureBytes`, `saltedCacheHash`.
Receipt authenticity is caller-reviewed evidence, NOT established by hashes.
The source is HASHED ONLY, never unpickled. All member hashes/sidecars are checked
BEFORE SQLite/product opens and after; changed membership fails. The output must
be NEW, canonical, non-symlink and disjoint from inputs. It contains a new physical
canonical-reference DB, report and isolated test project focus, never modifies
external focus/cache and never automatically downloads/executes a producer.

The small independent oracle materializes bounded rows in memory (32 MiB files,
256 entries, 64 slices, 20000 physical trace rows INCLUDING boundaries, 20000 block
rows, 256 dictionary rows/shard, 1 MiB JSON, optional 2 MiB source). These are
reference-tool limits, NOT a product RSS contract. It compares all real columns,
full completed-free/allocation source identity, canonical lifetimes/latest state,
terminal candidates, global earliest-tie peaks/full and shard ranges, selected
active sets/bytes, all-action stack statistics and global sort/page/exact totals.
The canonical standalone reference is NOT another original producer run.
The console chain verifies identical interpreter/API source across its isolated
CWD, then actual focus/query/report and normalized CLI/API scope/coverage.
Selected points/ranges are recorded, NOT an exhaustive all-event active-set proof.

## Deterministic CI scenarios and limits

`pytest tests/test_interop_acceptance.py tests/test_dataset_import_baseline.py
 tests/skills tests/test_bundled_skills.py` uses small generated SQLite or existing
reviewed/synthetic runtime fixtures; no network, GUI, NPU, live model or private
absolute baseline paths. Always run `tests/test_fixture_provenance.py` BEFORE any
committed-pickle runtime test. The owning suites below remain part of the gate:

| Scenario | Deterministic owning regression / interpretation |
| --- | --- |
| Long-lived blocks across many shards; address reuse; pending free; static/preexisting/unknown | `tests/core/test_dataset_attribution.py`, `test_dataset_global.py`; dedup by proved lifetime, not address; free_completed, not free_requested |
| Expandable segments, multi-device, sparse/nonzero native IDs, OOM/workspace | `tests/snapshot/test_sharded_replay.py`, `tests/test_native_dataset.py`, `tests/core/test_msinsight_export.py`; native preserves, v1 explicitly rejects OOM/sparse/nonzero IDs; no upstream OOM coercion or workspace raw-frame-loss claim |
| Ordered frames | Reader-only ptSnapOrderedFrames version 1, actual schema/coverage, finite typed JSON/depth128/order/duplicates; missing/unknown/uncovered → text-only, NO emitter/reconstruction or original-produced-frame claim |
| Cache/source/options/format/semantic identity; member mutation; no-replace external cache | Existing native/compatible import suites plus acceptance tests; GUI-derived DB mutation invalidates attestation, NOT proof of producer rerun |
| Write/backfill/conversion/source recheck/publication/focus/rollback failures | `tests/core/test_dataset_import_failures.py`, `test_import_backend_failures.py`, `test_msinsight_export.py`, sharded replay suite; assert ACTUAL old destination/focus/recovery bytes, not just exceptions |
| All eleven built-ins, CLI/API/report, paging and budgets | New physical reference + `test_dataset_global.py`; custom SQL/built-in-name overrides unsupported; borrowed LRU/terminal closure/handler cleanup unchanged |

Use the SAME YAML catalog's `dataset_support` and optional declared row fields.
`scope.range_complete` (ranges) and `scope.source_coverage.range_complete` (points),
allocation/frame-source coverage and result `has_more`/`truncated` are independent.
Dataset canonical `source_stack_id` differs from local stack ID provenance;
representatives prefer nonempty text. Missing references, captured literal labels
and non-NULL empty activity groups are not interchangeable. `callstack_analysis`
semantics v2 legacy `alloc_count` counts ALL real stack-bearing actions;
`total_size` is activity, not live bytes. Percentages retain included group bytes (standalone SQL or dataset post-merge)
after filters/top-N BEFORE caller row caps (#179), not the whole active counter.
Reports use gap/attribution/active coverage at the SAME selected metric event.
One query/report shares diminishing time and cumulative 100000 fetched/output rows
/64 MiB serialized values, NOT RSS. Failure yields no partial false global result.

## Performance: same reviewed fixture, three modes

The bounded measured fixture is `snapshot_expandable.pkl`, 581140 bytes,
SHA256 `3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40`,
device0/capacity2000. `baseline_import.py --samples 8k` selects a DIFFERENT
multi-device fixture, so it is not this original-reference comparison.

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_fixture_provenance.py
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python benchmarks/dataset_import_baseline.py \
  --source tests/fixtures/snapshots/snapshot_expandable.pkl \
  --sha256 3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40 \
  --device 0 --capacity 2000 --output /evidence/NEW-three-mode --trusted-pickle
```

This is explicit trusted-pickle execution consent, not an automatic diagnostic
step. No installs/repointing, large default sample, original-producer rerun or
cleanup. Each cold/reuse measurement uses a fresh isolated child; cold means NEW
output/no warmup, NOT cleared OS page cache. Reuse requires this run's unchanged
owned cold result; cache miss cannot rebuild/overwrite. Same-source/mode/phase
ownership is checked BEFORE pickle execution. Exact commands/exits/error logs,
source/head/script hashes, Python/platform and all eleven supported query latencies
are recorded. [Machine-readable local observation](../dataset-performance-baseline.json)
contains sanitized measured data, not speed assertions or CI numerical oracles.
Supported-query scope is not identical across modes: this observation's default
standalone `allocation` returns 8094 rows (8092 real + 2 synthetic boundary rows),
while dataset-global `allocation` returns only 8092 real rows. Event lookup selects
an explicit real ID. Preserve these differences when interpreting latency/row
counts; availability of the same template name does not prove equal logical scope.

Whole import wall and actual inclusive wrapped load/replay/SQLite/backfill/conversion
function times are distinct. `RUSAGE_SELF` fresh-child high-water is captured through
import BEFORE queries; Darwin raw bytes are divided by1024 to KiB, then1024 to MiB.
It includes interpreter/import overhead. Per-phase load/replay RSS and uninstrumented
remainder timings are **unavailable**, with reasons; do not subtract cumulative
high-waters or use parent/previous-child `RUSAGE_CHILDREN`. Total disk, individual
shards, repeated block rows and query latency are measured; per-row physical page
cost is unavailable. Pickle still loads fully; shards repeat long-lived blocks and
compatible inline text. Query hashing/scans may dominate. No unmeasured speed/RSS/
disk-saving promise. The existing original run's single cold wall0.160545s has NO
RSS/phase measurements and is not a controlled comparative performance baseline.

## FUTURE GUI checklist — every row PENDING / NOT-RUN

- [ ] Exact real version/build/commit/package SHA, interpreter/server provenance,
  environment and exact startup/open command; don't invent executable syntax.
- [ ] SAME original pickle path/hash/size and adjacent complete artifact; all
  manifest/member/checksum inventories BEFORE and AFTER opening, source unchanged.
- [ ] UP_TO_DATE/cache-reuse logs AND absence of producer/parser script invocation,
  with process/log observation that could detect rebuilding; hash alone is not proof.
- [ ] Curves/counters/ranges/real IDs excluding boundaries at recorded points;
  blocks/sizes/states and cross-shard allocation/free_completed source/details.
- [ ] Ordered-frame claims only where actual recognized coverage exists; original
  text-only artifacts remain text-only. Record unavailable views honestly.
- [ ] Inspect derived allocation-cache mutation separately: it may change DB bytes
  without producer rerun and invalidate ptSnap ownership attestation. Preserve both
  inventories, never repair/overwrite an original cache just to make reuse pass.

Synthetic/schema/original-artifact checks and static skill grades cannot tick
these rows. No GUI/C++ execution/compile occurred in this acceptance package.
