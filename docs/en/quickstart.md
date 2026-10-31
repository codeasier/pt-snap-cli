# Quick Start

[中文](../zh/quickstart.md) | English

Go from an existing input to a readable peak-memory report. The default path is
one SnapshotDB; you do not need to choose a sharded format to start.

## Installation

Use **Python 3.10 or newer** in the environment where you want the CLI:

```bash
python -m pip install pt-snap-cli
pt-snap --help
```

Offline import and analysis do not require PyTorch, TorchNPU, CUDA, or accelerator
hardware. Collection is different: it runs beside the workload in a compatible
PyTorch/CUDA or TorchNPU/Ascend environment. Contributors should use the separate
[Development and Checks entry](../../AGENTS.md#development-and-checks).

## Prepare Your Input

| What you have | Shortest next step |
| --- | --- |
| An existing SnapshotDB `.db` | Skip import; use its path in Step 2. |
| A complete native or compatibility-v1 dataset directory / `manifest.json` | Skip import; use that explicit target in Step 2. Keep every member, not just one ready shard. |
| A trusted `.pkl` / `.pickle` snapshot | Use Step 1, then analyze the generated DB. |
| No snapshot yet | Follow the collection entry below, then make a separate trusted-import decision. |

### Need to Collect a Snapshot?

- **CUDA/PyTorch:** collect allocator history in your workload's GPU environment
  using the [official PyTorch snapshot guide](https://docs.pytorch.org/docs/stable/torch_cuda_memory.html).
  Verify the APIs for your installed PyTorch version, choose a bounded history
  window, and dump the snapshot after the relevant workload section. Installing
  this offline CLI does not instrument or start your training job.
- **Ascend NPU:** use [pt-snap-ascend-npu-collect](../../skills/pt-snap-ascend-npu-collect/SKILL.md)
  for TorchNPU API/environment checks and the framework-specific capture route.
  Choose the capture ranks, step window and output location. The skill can guide
  collection without the CLI if the host has loaded it; see [Agent Skills](skills.md).
- A CSV, SVG or screenshot is not a SnapshotDB. Obtain the database or the
  original trusted pickle; do not rename a visualization to `.db`.

Collection changes the workload's recording behavior and writes a pickle; it is
not read-only analysis. Review that plan separately. Copying a pickle to an
offline machine does not make it safe to deserialize.

## Your First Analysis

### Step 1: Import Only If Needed

> **Security warning:** Import only pickle snapshots you trust. Deserialization
> can execute arbitrary code. The loader rejects non-`builtins` global objects,
> but `pt-snap import` is not a sandbox. Agent setup or collection approval is
> not approval to import a pickle.

```bash
pt-snap import snapshot.pkl
```

By default this creates `snapshot.pkl.db` **beside the source pickle** and
updates `.pt-snap/focus.json` in the current working directory (project focus).
`--output-dir captures` changes the output parent, not the filename. To create
or reuse the DB **without changing focus**, use:

```bash
pt-snap import snapshot.pkl --no-focus
```

**`--no-focus` is not no-replace:** a standalone cache miss or `--force` can
replace an existing same-named `.db`. Confirm that output is disposable, or use
a different `--output-dir` before importing.

The remaining examples pass an explicit path and device and work with either
choice. Replace `snapshot.pkl.db` with your actual DB or complete dataset path.
Import is a write operation; `overview`, built-in queries, and reports do not
change source data or persist focus. Dataset queries may use private temporary
scratch storage within their [work limits](querying.md#public-dataset-limits).

### Step 2: Inspect the Target and Choose a Device

```bash
pt-snap overview snapshot.pkl.db --json
```

Check `db_path` and choose a `device_id` from `devices`. Below we use `0` as an
example; substitute a device that was actually returned. For a dataset also
check `dataset.status`, format and fingerprint. Stop on an invalid target or
`import_metadata.status: "invalid"`; legacy `"unavailable"` with reason
`"metadata_missing"` means unknown import provenance, not known corruption.
Other unknown statuses/reasons need investigation before diagnosis.

### Step 3: Read the Counters

```bash
pt-snap query snapshot.pkl.db --device 0 --template-use memory_peak --json
```

An **illustrative** `rows[0]` (not a promised result for your snapshot):

```json
{
  "peak_allocated": 8388608,
  "peak_allocated_event_id": 10,
  "peak_active": 10485760,
  "peak_active_event_id": 12,
  "peak_reserved": 16777216,
  "peak_reserved_event_id": 10
}
```

All three sizes are **bytes**: here 8, 10 and 16 MiB (`1 MiB = 1048576 bytes`).

| Counter | Meaning in the replayed allocator history |
| --- | --- |
| `allocated` | Bytes in allocated blocks, excluding blocks already marked pending free. This is block size, not requested tensor payload size. |
| `active` | Allocated plus pending-free block bytes that are not yet reusable. |
| `reserved` | Total segment bytes held by the allocator, including inactive capacity; not all process/device memory. |

Each metric has its own earliest peak event; event IDs are ordering markers,
not timestamps. Do not subtract independent peaks as if they were simultaneous.
Empty real-event ranges return null peaks: do not invent an event. A large
reserved/active gap alone does not prove fragmentation, a leak or OOM causality.

### Step 4: Generate a Readable Report

```bash
pt-snap report peak-memory snapshot.pkl.db --device 0 --metric active --limit 20
```

Expect **Peak memory report**, the selected device/metric/event, separate peak
counters, same-event allocator gaps, and **Active memory by callstack**. The
report explains active blocks at the selected peak, not every reserved byte.
Check the attribution completeness label and active-byte coverage before making
claims: group percentages use `included_bytes` after filtering/ranking, not all
active memory. A capped report can be partial; a budget error is not a partial
successful analysis. Add `--json` for automation. See the
[report contract](querying.md#report-command) for limits and denominators.

### Optional: Remember This Target

```bash
pt-snap focus snapshot.pkl.db --device 0
pt-snap report peak-memory
```

Unlike the explicit-path analysis above, `focus <path>` writes project focus.
Skip it if you do not want shared project state. The import default may already
have selected the DB; this command also selects your chosen device. See
[focus precedence and session isolation](focus-management.md).

## Advanced Input Options

These are optional, not prerequisites for the first report.

### Optional: Import a Native Sharded Dataset

`--events-per-slice` opts into a native dataset; it does not make pickle loading
streaming or bound peak RSS. For output paths, complete-member validation,
force/recovery behavior and supported built-ins, read the
[native import contract](sharded-snapshotdb.md#published-native-dataset-p2) and
[global support matrix](querying.md#dataset-global-built-in-support-p3).
Native output is not msinsight-compatible.

### Optional: Export an msinsight-Compatible Dataset

`--format msinsight` is explicit opt-in. Existing compatible targets are never
replaced, even with `--force`; compatibility, cache validation, GUI entrance and
fixed-version evidence have their own [protocol contract](sharded-snapshotdb.md#explicit-msinsight-compatible-export-p2).
Read [recorded interoperability acceptance](interop-acceptance.md) before claiming
GUI reuse. A matching hash alone is not GUI acceptance.

### Optional: Split a Snapshot

`pt-snap split` creates independently replayable files, not a queried dataset.
It also requires trusted pickle input, exactly one split strategy, and an absent
output directory. It does not change focus. See [Splitting Snapshots](splitting.md).

### Reuse, Rebuild and Memory Costs

Standalone import stores source SHA-256 and compatibility metadata. Identical
content/options can reuse the DB; cache misses (including missing/invalid
metadata) and `--force` rebuild and can replace the same-named standalone DB.
Unlike native/compatible directory policies, this is not an unknown-target
protection gate. Confirm ownership or choose another `--output-dir` first.
Do not force a rebuild merely because analysis failed; inspect the error. Import loads the entire
pickle before replay; `--device` reduces subsequent work, not that initial peak.
Use sufficient memory headroom. Snapshot runtime modules are not a public API.

## What's Next

- [Agent Skills](skills.md) — install, restart, verify and ask for a diagnosis
- [Querying](querying.md) — templates, bounded results, stack detail and reports
- [Focus Management](focus-management.md) — optional persisted/session targets
- [Database Schema](database.md) — counters, metadata and sentinel meanings
- [SnapshotAnalyzer API](snapshot-analyzer-api.md) — analysis with owned Python resources
