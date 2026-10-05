# Quick Start

[中文](../zh/quickstart.md) | English

Get up and running with `pt-snap-cli` in a few minutes.

## Installation

```bash
pip install pt-snap-cli
```

This installs the `pt-snap` CLI. Contributors working from a source checkout can
use `pip install -e ".[dev]"`; see [Development](../../README.md#development)
in the repository README.

## Your First Analysis

### Optional: Import a PyTorch Snapshot

If you have a raw `.pkl` memory snapshot, import it first with the built-in backend:

> **Security warning:** Use trusted pickle input only. Deserializing a pickle can
> execute arbitrary code. The loader rejects non-`builtins` global objects, but
> `pt-snap import` is not a sandbox.

```bash
pt-snap import snapshot.pkl
pt-snap metadata snapshot.pkl.db
pt-snap query --list
```

The import command stores a SHA-256 source fingerprint and import compatibility metadata inside the
generated database. Repeating the same import with the same device selection reuses the existing DB.
Use `--force` when you intentionally need to rebuild it:

```bash
pt-snap import snapshot.pkl --force
```

Import currently loads the entire pickle before processing it, so peak memory can be
substantially larger than the input file depending on its object graph and frame count.
Run large imports with sufficient memory headroom. `--device` limits subsequent replay
and database writes, but does not reduce the initial pickle-loading memory peak.

During import, pt-snap replays the selected device's allocator history instead of
copying raw events directly. The resulting SnapshotDB records event-by-event
`allocated`, `active`, and `reserved` totals plus block lifecycles, which makes it
the supported input for `pt-snap query` and `pt-snap report`. This replay behavior
is part of the command workflow; snapshot runtime Python modules are not a public API.

### Optional: Import a Native Sharded Dataset

```bash
pt-snap import snapshot.pkl --events-per-slice 50000 --output-dir captures --json
pt-snap overview captures/snapshot.pkl.pt-snap-native-v2 --json
pt-snap query --template-use event --slice 0 --json
```

Without `--events-per-slice`, import still produces the existing single DB. With
it, the output is `<output-dir>/<full-input-filename>.pt-snap-native-v2/`, or the
same directory beside the source if `--output-dir` is omitted. `--format
pt-snap-native-v2` is optional in this mode; `--format single-db` forbids a capacity.
`--format compatibility-v1` and `msinsight` are reserved and explicitly rejected:
native output is **not** an msinsight-compatible export.

Capacity counts real chronological positions **per device**, not `max(id)+1` or
negative synthetic boundaries. Original sparse/nonzero IDs, OOM and workspace
events remain native. `--device` selects one event-bearing device; otherwise all
such devices are imported. Empty/static-only and unselected device positions are
reported in `omitted_devices`; selecting an empty device or an all-empty input
fails. Sharding does not bound pickle loading, registry/block rows or peak RSS.

Reuse requires a validated complete manifest and **every** closed member, with
matching source SHA256, device selection, capacity, native format, manifest,
semantic import, extension and metadata/layout contracts. CLI release version
changes alone do not rebuild. Native identity is separate from future compatible
format identities and from msinsight's salted `cacheHash`. JSON adds `dataset_path`,
`devices`, `slice_count`, `format`, `omitted_devices`, `reused` and `rebuilt`;
`db_path` denotes the dataset directory in this mode.

A matching target is reused. A different/corrupt recognized native artifact is
preserved unless `--force` explicitly requests replacement. Unknown directories,
extra unrelated files, malformed manifests and symlink targets are never adopted
or deleted, even with force: choose a new `--output-dir`. All devices/shards are
staged beside the target, finalized, closed, metadata-attested and validated; the
source is hashed again before publication. No partial shard is a reusable cache.

New publication uses an exclusive directory rename. Force replacement first
renames the old artifact into an owned recovery directory, then publishes the
new one; **there is a transient path gap, not a single atomic swap**. Requested
project focus is part of compensation, including a focus write that mutates
before raising: ordinary failure restores old artifact and exact old focus
bytes/state (or previous absence). `--no-focus` skips focus entirely. If rollback
itself fails, recovery paths are preserved and explicitly reported. Do not delete
them before inspecting the evidence. Arbitrary I/O failures, concurrent writers
and crashes do not have unconditional atomic restoration guarantees.

Dataset focus currently supports only bounded `event` addressing; it does not
silently run peak/lifecycle/aggregate queries over one shard. See the
[native manifest contract](sharded-snapshotdb.md#published-native-dataset-p2).
`SnapshotAnalyzer` remains analysis-only, without import/split methods.

### Optional: Split a Snapshot

Use `pt-snap split` when you need smaller, independently replayable files. Split
does not read or change focus:

```bash
pt-snap split snapshot.pkl --max-entries 50000 --output snapshot-slices
```

Use exactly one of `--slices` and `--max-entries`. See
[Splitting Snapshots](splitting.md) for all-device behavior, formats, names, and
atomic publication guarantees.

### Step 1: Set the Snapshot Database and Device

Point `pt-snap` to your SQLite snapshot database file:

```bash
pt-snap focus snapshot.pkl.db --device 0
```

This validates the database and saves the path and device ID to `.pt-snap/focus.json` in your current directory, so you don't need to repeat it.

If you only want to set the database (no device yet):

```bash
pt-snap focus snapshot.pkl.db
```

### Step 2: List Available Queries

```bash
pt-snap query --list
```

### Step 3: Run a Query

```bash
pt-snap query --template-use memory_peak
```

### Step 4: Try Advanced Queries

```bash
# Detect potential memory leaks
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'

# Query automatically uses the focused device, or you can override it
pt-snap query --template-use block --device 0 --params '{"min_size": 1048576}'
```

## What's Next

- [Focus Management](focus-management.md) — Learn how to manage database and device focus across projects and sessions
- [Querying](querying.md) — Query workflows, template discovery, parameters, and output
- [Splitting Snapshots](splitting.md) — Create independently replayable per-device slices
- [Agent Skills](skills.md) — Install bundled agent workflows into the shared agents directory and Claude
- [Database Schema](database.md) — Understand the SnapshotDB format
- [SnapshotAnalyzer API](snapshot-analyzer-api.md) — Query SnapshotDB files from Python
