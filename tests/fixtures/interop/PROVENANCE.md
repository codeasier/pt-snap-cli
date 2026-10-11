# Three-shard free-requested interoperability fixture

## Introduction record: 2026-10-11, pt-snap-cli #249

Purpose: an independently authored, minimal producer-side regression for
[pt-snap-cli #249](https://github.com/codeasier/pt-snap-cli/issues/249) and a
retest input for [msinsight #625](https://gitcode.com/Ascend/msinsight/issues/625).
This record does **not** establish a consumer fix or a successful GUI run.

### Source, rights and privacy

- `three_shard_free_requested.json` is new synthetic data authored for this
  repository, under its MIT license. It contains one device, one 64-byte segment,
  one 16-byte block, and exactly three events: alloc 0, free_requested 1,
  free_completed 2. Stream 7 and address 4096 are invented constants.
- Frame filenames/functions are invented. There are no user captures, model
  sessions, account details, host paths from a user machine, or vendor code.
  Nothing was copied from or run in msinsight. SQL predicates/schema are
  independently expressed interface facts; the fixed target remains
  Ascend/msinsight `101f65b877a267ffd5f66ea3834706057ba243e5`.
- The committed artifacts are inspectable JSON/Python and SQLite, **not pickle**.
  The executable-snapshot acceptance records in `../snapshots/` are unchanged.
  Their historical approvals do not approve new pickle inputs.

### Generation and reproducibility boundary

The generator used pt-snap-cli source commit
`55b5981fc03df93a60b809153e8abee5f980ed29`, Python 3.12.14 and SQLite 3.53.1.
It created a new primitive-only protocol-4 pickle from the adjacent JSON in
`/tmp/pt-snap-249-reviewed-fixture/`, then called the actual CLI subprocess:

```bash
PYTHONPATH="$PWD/src" python tests/fixtures/interop/generate_three_shard.py \
  --output /tmp/pt-snap-249-reviewed-fixture
```

The directory must be absent. No external pickle is read by the generator;
imports deserialize only this locally constructed synthetic source. The stored
pickle for that generation was 695 bytes, SHA256
`3c9513c7a8dca98d589cd82fc90ef7e177eec70b57887a1601b601f418a79f1f`.
Static opcode inspection finds no GLOBAL/STACK_GLOBAL, REDUCE/BUILD,
INST/OBJ/NEWOBJ/NEWOBJ_EX, persistent-ID or extension opcodes. The pickle is not
committed; this observation is not a claim that arbitrary pickles are safe.

The committed `three_shard_free_requested.pkl.msinsight/` is the unmodified
compatibility-v1 output: three 53,248-byte SQLite shards and a 2,174-byte complete
manifest. Its `sourceFile` is the public, disposable generation path above, not
a relocatable GUI entry or a path expected to exist on the reader's machine.
The CLI timestamp and importer version remain the actual recorded values.
The native-v2 export is generated and tested but not duplicated in the repository.

Reproduction means equal physical real events, lifecycle references, ownership,
and manifest ranges, verified against explicit expectations in
`tests/test_interop_three_shard.py`. It is not a cross-Python/SQLite byte-for-byte
reproducible-build claim. New generation timestamps, source locations, versions,
SQLite serialization and therefore artifact hashes may differ. Never normalize
or rewrite shipped metadata to hide those differences. `checksums.json` records
exact bytes and SHA256 for the recorded JSON, generator, manifest and every DB;
tests verify them before opening the committed databases and check read-only
inspection leaves them unchanged. Changing an input/artifact requires review and
an explicit checksum/provenance update; do not refresh checksums to silence a
regression. Preserve this introduction record when recording future changes.

### Expectations and limitations

- All real event rows appear once, only in their owning shard. Negative synthetic
  boundary rows are separate and must not be counted as real events.
- The free-requested row is `(id=1, action=5, address=4096, size=16, stream=7,
  allocated=0, active=16, reserved=64)` and has the complete two-frame text stack.
  These three counters correspond to the consumer's Caching Allocated/Active/
  Reserved fields, in bytes. No reconstructed ordered-frame extension is claimed.
- Block 0 has `allocEventId=0` and `freeEventId=2` in every shard. The latter refers
  to **free_completed**, never free_requested. Its allocation and completed-free
  reference text is preserved across shards.
- A current-shard-only free-requested lookup misses event 1 when viewing shard 0
  or 2. Candidate discovery intersects manifest ranges with
  `allocEventId < id < freeEventId`; for `freeEventId < 0`, it includes the
  device's final real ID. Then action/address and the same bounds select rows.
- Address reuse and open-ended pending-free/allocated lifetimes are separate
  generated tests, not extra events hidden in the dedicated three-shard artifact.
  The older nine-event `lifecycle_data` includes OOM and cannot be this minimal
  v1 fixture. Existing full-replay event coverage remains useful and unchanged.
- Only pt-snap producer/SQL contracts are tested here. The msinsight GUI/C++ fix,
  original-producer execution and #625 consumer acceptance remain separate work.

## Portability follow-up: 2026-10-11

Checksum member keys use POSIX separators on every host. Narrow Git attributes
pin the recorded JSON/Python/manifest text to LF and SQLite members to binary,
so `core.autocrlf=true` does not change their accepted bytes. A temporary-repository
checkout regression checks actual Git attributes and byte preservation alongside
an unprotected CRLF-converted control. No recorded artifact bytes or checksums
were changed for this portability correction.
