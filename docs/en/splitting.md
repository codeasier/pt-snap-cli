# Splitting Snapshots

[中文](../zh/splitting.md) | English

`pt-snap split` divides an original PyTorch memory snapshot into smaller files
that can each reconstruct the allocator state at its boundary and replay its own
event range. It does not truncate trace arrays, read focus, update focus, or create
a SnapshotDB. Import a produced pickle separately when you need SQLite queries.

> **Security warning:** Use trusted pickle input only. Deserializing the source
> snapshot and any pickle slice can execute arbitrary code. The loader rejects
> non-`builtins` global objects, but `pt-snap split` is not a sandbox.

## Command Contract

```bash
pt-snap split SNAPSHOT_PATH \
  --output OUTPUT_DIRECTORY \
  [--device DEVICE_ID] \
  (--slices COUNT | --max-entries COUNT) \
  [--format pickle|json]
```

The source must be an existing regular `.pkl` or `.pickle` file. `--output` is
required, its parent directory must already exist, and the output path itself
must not exist as a file, directory, or symbolic link. Split never merges with or
overwrites an existing destination.

Exactly one strategy is required:

| Option | Meaning |
| --- | --- |
| `--slices COUNT` | Request up to a positive target number of slices for each selected device; partitioning may emit fewer |
| `--max-entries COUNT` | Limit each slice to a positive maximum event count |

`--format` accepts exactly `pickle` or `json` and defaults to `pickle`.

Exclusive atomic directory publication requires `renamex_np(RENAME_EXCL)` on
Darwin, `renameat2(RENAME_NOREPLACE)` on Linux, or Windows rename semantics.
Unsupported platforms or missing libc symbols fail publication preflight before
the source pickle is loaded.

## Devices And Names

With `--device ID`, only that nonempty device is split. Without `--device`, every
device with trace entries is selected and sliced independently with the same
strategy. Empty devices are skipped in all-device mode. The command fails rather
than publishing an empty directory when no device has trace entries or when an
explicitly selected device is missing or empty.

Every output contains events from one device and has this deterministic name:

```text
<source-stem>__device-<id>__slice-<index>.<ext>
```

The index is zero-based. The extension is `pkl` for pickle or `json` for JSON.
Identical input and options produce the same ordered names.

Examples:

```bash
# Target up to four slices for each nonempty device
pt-snap split snapshot.pkl --slices 4 --output snapshot-slices

# Split only device 1, with at most 50000 events in each normalized JSON file
pt-snap split snapshot.pkl --device 1 --max-entries 50000 \
  --format json --output snapshot-json
```

## Pickle Or JSON

- `pickle` is the complete, runtime-coupled representation and is the format
  accepted by `pt-snap import`. It retains Python-specific values but must be
  treated as executable, trusted input.
- `json` is a normalized, compact UTF-8 representation intended for inspection
  and interchange. It preserves replay-relevant values and event order, but it
  is not accepted by `pt-snap import`; use pickle when the next step is SnapshotDB.

Both formats are loaded and replayed by pt-snap before publication. This validates
that each file can reconstruct its boundary state and process its event range; it
does not make untrusted pickle safe.

## Publication And Errors

Split validates arguments, source/output paths, format, strategy, and device
selection before publishing anything. Generated files are written to a unique
hidden sibling staging directory under the output parent, so staging and the
destination are on the same filesystem. Every file is then loaded and replayed.
Only after every device and slice passes validation does pt-snap atomically rename
the whole staging directory to `--output` with no-replace semantics.

Failures identify one of the argument, path, conflict, device, load/engine,
generated-validation, or publication phases. On failure, pt-snap makes a
best-effort attempt to remove only the staging directory it created and leaves no
partial destination. It verifies staging identity immediately before path-based
removal; if identity verification or cleanup fails, the hidden staging directory
can remain for manual inspection. If another process creates the destination
during the run, publication fails without replacing or merging that path.

After a successful pickle split, import and query one slice normally:

```bash
pt-snap import snapshot-slices/snapshot__device-0__slice-0.pkl --no-focus
pt-snap query snapshot-slices/snapshot__device-0__slice-0.pkl.db \
  --device 0 --template-use memory_peak
```
