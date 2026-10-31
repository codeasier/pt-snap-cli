# Interoperability acceptance and bounded performance

[中文](../zh/interop-acceptance.md) | English

## Evidence layers and fixed target

The historical parser-v2 acceptance and physical-schema reference use
**Ascend/msinsight@101f65b877a267ffd5f66ea3834706057ba243e5**. This is not a
verified consumer target for current parser-v3 exports.
Protocol/schema validation, isolated source-function checks, synthetic CI,
reading an actual original-producer artifact, and actual GUI/C++ consumption are
DIFFERENT evidence layers. None implies the next. **The bounded real GUI/C++ and
original-producer reverse acceptance passed on 2026-10-11**, as recorded below.
The earlier [#205 pending note](https://github.com/codeasier/pt-snap-cli/issues/205#issuecomment-5987264017)
records the historical human-deferred stage; it is not the current run status.
This evidence does not itself close an issue or approve a release.

The acceptance tools are original interface-facts/reference code, not vendor
copies. Fixed [producer schema](https://api.github.com/repos/Ascend/msinsight/git/blobs/1fe50a5136f85365db55f4632d58f3cf7090431e),
[manifest/backfill](https://api.github.com/repos/Ascend/msinsight/git/blobs/95612509ef990ac6b7034919dae4938cc6acf3ad),
[parser predicates](https://api.github.com/repos/Ascend/msinsight/git/blobs/40046e6a92ff5af776ee55bd4cdd4586745af3c2)
and [salt order](https://api.github.com/repos/Ascend/msinsight/git/blobs/ca421c7b33f3a0050df9e7a01e666f558801bc2f)
are the source of protocol facts. Ascend source is Mulan PSL v2; upstream docs
are separately CC BY 4.0, not automatically covered by this project's MIT lineage.
A port needs snapshot provenance/PR decisions and retained notices. Executable
pickle trust is a SEPARATE fixture review; no new committed pickle is added here.

## Current parser-v3 status and safe retest

Current exports use `mem_snapshot_parser_v3`. The pinned historical consumer uses
`mem_snapshot_parser_v2` and **will reparse** a v3 hash mismatch; its parse path
removes the manifest/log before invoking the producer. Do not point that old GUI
at the only source/cache copy. The legacy `ptSnap.identity.targetRevision` field
is a schema/reference identity anchor, not proof of consumer support.
The reviewed upstream master
[`5c722719e1d288106f8d18588b0a33d979a4065b`](https://api.github.com/repos/Ascend/msinsight/git/blobs/20254ee06471a4acb3757893263d042dd5df47e8)
also still computes the v2 salt and rejects a mismatched cache hash. Reuse with
these reviewed consumers is therefore incompatible, not merely untested. No
verified v3 consumer target has been selected.

A current v3 GUI cache-reuse claim requires all of the following:

1. Identify an immutable consumer commit and exact build; inspect its parser salt,
   manifest/member/schema checks and reparse path before execution. A version
   label, current branch name, or the old v2 GUI receipt is insufficient.
2. Obtain explicit authorization for that real GUI run. Use a new isolated
   directory, a byte-identical copy of the separately trusted pickle, and a new
   adjacent export produced by the candidate wheel. Never move or overwrite the
   original cache; re-export rather than relabel v2 hashes. Record source, wheel,
   manifest and member hashes plus device/capacity before opening anything;
   verify `manifest.sourceFile` names the copied pickle's absolute path.
3. Open only that disposable source/cache pair with the identified build. Retain
   `UP_TO_DATE` and no-producer-invocation evidence, compare curves/blocks and
   first/last/cross-shard event boundaries, and exercise repeated navigation and
   cancellation. Record post-run hashes and distinguish permitted consumer-derived
   caches from base-data mutation or parser reruns.
4. Keep current v3 results separate from the historical receipt below. The
   artifact-only runner's strict `saltedCacheHash` gate intentionally rejects
   applying an old v2 receipt to v3 output; never alter that receipt or relax hashes.

No current v3 consumer build or real GUI run is accepted by this document.

## Historical v2 forward chain: trusted source → physical export → real GUI

The pinned historical acceptance below used `mem_snapshot_parser_v2`. Current
exports use `mem_snapshot_parser_v3`; the historical GUI result does not verify
the new parser version. The commands below document the old run, not a safe
current-CLI procedure against the old GUI. Running them with a current CLI emits
v3; use the isolated-copy plan above, not the historical cache/consumer pair.

1. Review/trust the source separately: pickle is executable input, not a sandbox.
   Record exact source SHA256, size, selected device and capacity. Default import
   stays single-db; native and compatible outputs are explicit distinct modes.
2. Use an ABSENT destination. For the original-source GUI entrance, the
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
4. With explicit authorization for a real acceptance run, open the same original
   pickle using the exact recorded real GUI build. Record the evidence below.
   Physical equality and salted-hash equality alone are NOT GUI cache-reuse
   acceptance. The 2026-10-11 run separately observed the real consumer.

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

The independent physical SQL reference materializes bounded rows in memory (32 MiB files,
256 entries, 64 slices, 20000 physical trace rows INCLUDING boundaries, 20000 block
rows, 256 dictionary rows/shard, 1 MiB JSON, optional 2 MiB source). These are
reference-tool limits, NOT a product RSS contract. It compares all real columns,
full completed-free/allocation source identity, canonical lifetimes/latest state,
terminal candidates, global earliest-tie peaks/full and shard ranges, selected
active sets/bytes, all-action stack statistics and global sort/page/exact totals.
The canonical standalone reference is NOT another original producer run.
Active-attribution comparisons reuse the product's standalone query implementation
on that reference DB; they are a differential check, not a wholly independent
second oracle for active attribution.
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

## Three-shard free-requested fixture

[pt-snap-cli #249](https://github.com/codeasier/pt-snap-cli/issues/249) adds a
minimal, synthetic producer fixture under
[`tests/fixtures/interop/`](../../tests/fixtures/interop/README.md): one device,
three real events and three shards, generated by the real CLI with
`--events-per-slice 1`. Allocation 0, free_requested 1 and free_completed 2 each
belong to exactly one shard. There is no new committed executable pickle or
third-party producer code. Source, generation identity, privacy/rights review,
size/hash records and limitations are in the linked provenance record.

```bash
PYTHONPATH="$PWD/src" python -m pytest tests/test_fixture_provenance.py
PYTHONPATH="$PWD/src" python -m pytest tests/test_interop_three_shard.py
PYTHONPATH="$PWD/src" python tests/fixtures/interop/generate_three_shard.py \
  --output /tmp/NEW-three-shard-interop
```

Use an absent output directory. The generator creates its own synthetic pickle
from the inspectable JSON and invokes `pt-snap import` for both `msinsight`
(compatibility-v1, inline callstack) and `pt-snap-native-v2` (interned callstack),
with `--device 0 --events-per-slice 1 --no-focus`. It does not open the GUI or run
an original producer. The committed v1 artifact is checksum-verified before
read-only tests; fresh output reproduces its physical semantics, not necessarily
its timestamp/path/version-dependent bytes.

The regression checks event ownership, all nine physical event fields, complete
stack text and block references. The free-requested row has ID 1, action 5,
address 4096, size 16, stream 7 and allocated/active/reserved counters 0/16/64
bytes (the consumer's Caching Allocated/Active/Reserved fields). Block 0 retains
`allocEventId=0`, `freeEventId=2`; `freeEventId` identifies **completed** free.
The existing current-shard-only consumer predicate misses event 1 in shard 0/2.
An independent SQL oracle searches manifest candidates intersecting
`allocEventId < id < freeEventId`, or through the device's final real event when
`freeEventId < 0`, then filters by action/address and the same bounds. Separate
v1/v2 cases prove address reuse cannot attach a later lifetime's request and
open-ended pending-free/allocated lifetimes yield the right event or no event.
The older OOM-containing nine-event `lifecycle_data` is intentionally not used as
this minimal v1 fixture; existing full-replay coverage is retained.

For a separately authorized GUI retest, use the newly generated original
`three_shard_free_requested.pkl` beside its generated `.msinsight` directory.
Do not expose the immutable committed fixture to a consumer that writes derived
cache tables. Native-v2 is not a claimed msinsight GUI input. This work proves
producer/fixture contracts only: it neither fixes nor verifies
[msinsight #625](https://gitcode.com/Ascend/msinsight/issues/625), and does not
supersede the consumer limitation in the dated acceptance record below.

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

## Recorded real acceptance — 2026-10-11

The [sanitized machine-readable receipt](../interop-acceptance-2026-10-11.json)
records exact identities, dependency pins, inventories and bounded results. It is
an observation summary, not a distributable original artifact or a replacement
for reviewing receipt authenticity. No screenshots, raw protocol call stacks,
private paths, accounts or full logs are included.

### Build and input identity

- Fixed upstream: `101f65b877a267ffd5f66ea3834706057ba243e5`; clean tracked source.
  Linux x86_64, GCC 14.2.0, CMake 3.31.6, Ninja 1.11.1.4, Node 24.19.0.
  Only the production framework and Leaks bundles plus `profiler_server` were
  built. Frontend installation used pnpm 11.25.0, the frozen lockfile, original
  hoist patterns, strict SSL and disabled lifecycle scripts. No source/lock edits.
- Server SHA256: `7b1c2325d88d709ad111faad458422099fd34b7f574ba557f9e0643a0108b64f`.
  The staged server ran as `./profiler_server --wsPort=9000 --wsHost=127.0.0.1`
  with its directory on `LD_LIBRARY_PATH` and process tracing enabled.
  Shared-library hashes and libuv/uSockets/uWebSockets/RapidJSON/SQLite pins are
  in the receipt. RapidJSON's recorded local commit is not an upstream historical
  dependency pin; this is not byte-identical vendor-release reproduction.
- Noneditable wheel: `0.0.post1.dev1`, SHA256
  `884a13f08f65e866cd106c0a80f218d289269da10e9f623f1b0779cafdc67f9a`;
  all 110 installed package members matched. Its source tree corresponds to
  `cd1aac689f653e2701334d26ae1f25489f7f5af9`, not a claim that later main commits
  or a published PyPI release were exercised.
- Reviewed `snapshot_expandable.pkl`: 581140 bytes, SHA256
  `3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40`;
  device 0, 2000 events per slice. Fixture provenance tests passed 7/7 before
  deserialization. Pickle execution still requires independent trust review.

### Forward GUI/C++ results and preservation

- [x] The real framework/Leaks GUI opened the original pickle with its adjacent
  complete five-shard pt-snap export. Window transitions 1 → 2 → 1 → 4, lifetime
  curves, reserved line and five-window overview rendered. Window 4 displayed the
  allocated/active peak at event 7430 (597642080 bytes = 569.956 MiB; the GUI
  label reads `569.956 MB`).
- [x] The server logged `UP_TO_DATE` (state 4). Full launch-to-termination process
  tracing recorded one executable launch, the server itself, and no parser/Python
  producer execution. The separate reverse-producer run is outside this trace.
- [x] Block 1669 (37632 bytes) resolved allocation 1669 in Window 1 from Window 2,
  and completed-free 2605 in Window 2 from Window 1. The block-details automatic
  association of free-requested event 2604 queried only the current shard: absent
  from Window 1 detail, present in Window 2. This does not imply that direct lookup
  by event ID cannot cross shards; that separate path was not additionally queried
  for 2604 in this run. The observed block-details limitation was not patched.
- [x] The same loaded real C++ server passed 16 query cases / 167 typed assertions,
  with zero failures/query errors. Protocol samples covered the first two slices,
  curve/reserved endpoints, events 1999/2000, clipped block ranges and cross-shard
  details. At 1999/2000 the state had 801/802 blocks and 419457080/419465784 allocated
  bytes. `maxSize` is the reserved display scale, not an allocated peak.
- [x] Original table schemas and every original row were preserved in all five
  runtime shards; both source copies and the runtime manifest were unchanged.
  **Runtime DB bytes changed:** the consumer added `memory_allocation_cache_v1_0`
  to each shard, invalidating the unchanged manifest's ptSnap member attestation.
  The separate pre-GUI export stayed byte-identical. No repair/reimport was used
  to hide the mutation. Cache reuse does not mean the opened artifact is immutable.
- [x] Actual call stacks remained text-only; no ordered frames were reconstructed.
  GUI/server/private HTTP services were stopped after the run.

### Reverse results and limits

A separate unmodified fixed producer invocation finalized five shards with 8092
real events. The installed wheel passed all eleven built-in templates, physical
SQL/reference comparisons and actual isolated CLI/API focus/query/report checks.
Counts: 10 excluded boundaries, 6412 physical block rows, 3219 canonical lifecycles,
3193 repeated rows, 325 terminal candidates and 60 all-action stack groups.
Twelve recorded event points and six ranges were selected; active sets were not
exhaustively checked at every event. Active attribution reuses standalone product
queries on the canonical DB, so it is not a fully independent second oracle.

Forward/pre-GUI versus original-producer physical comparison passed all nine
real-event columns, schemas/dictionaries, exact real IDs and negative-token
six-field/state multisets. Negative identity does not transfer between producers.
Original-producer metadata correctly returned `unavailable` / `metadata_missing`;
frames remained text-only. The reverse original artifact, forward comparison copy,
source bytes and producer sources remained unchanged under read-only analysis.

The runner in [benchmarks/interop_acceptance.py](../../benchmarks/interop_acceptance.py)
only reads existing artifacts; its `GUI=human-deferred/pending/not-run` and
`original_producer=not-run by this runner` fields describe that tool's own scope.
They are retained, not rewritten as if the runner executed the GUI or producer.
The dated receipt combines the separately observed stages. Use the commands above
and [fixture review](../../tests/fixtures/AGENTS.md) to repeat the bounded read-only
comparison with a separately reviewed receipt; hashes alone cannot recreate its
original manifest paths or authenticate execution.

This run does not cover all plugins, a shipped desktop package, GPU/NPU execution,
multiple devices, exhaustive GUI interactions, fault injection or performance
improvements. Broader failure/rollback scenarios still require the owning tests
listed above. Historical synthetic checks and performance observations remain
separate evidence; this docs-only record introduces no runtime behavior change.
