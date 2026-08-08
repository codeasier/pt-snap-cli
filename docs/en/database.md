# SnapshotDB Schema

[中文](../zh/database.md) | English

## Overview

SnapshotDB is the SQLite database format for persisting PyTorch memory profiling data. It supports multi-device (multi-GPU) snapshot storage and querying. Notably, it does more than simply converting raw pickle snapshot data into SQLite — it performs a complete "replay" of the raw memory snapshot data and records additional information during the replay, such as:
1. The total memory pool size and total allocated block size after any event;
2. The complete lifecycle of all memory blocks during the collection period (which event allocated them, which event freed them).

**Example database file**: `snapshot.pkl.db`

---

## Producing a snapshot DB

`pt-snap` analyzes SQLite SnapshotDB files. If you start with a raw PyTorch memory snapshot pickle, import the snapshot with the built-in backend:

> **Security warning:** Import trusted pickle files only. Pickle deserialization
> can execute arbitrary code. `pt-snap import` is not a sandbox.

```bash
pt-snap import snapshot.pkl
```

The import command uses pt-snap-cli's first-party snapshot runtime to produce `snapshot.pkl.db` next to the input file by default, then updates project focus so subsequent commands can use it directly:

```bash
pt-snap query --list
```

You can also generate the same SnapshotDB format with another compatible producer, then point `pt-snap focus` at the resulting `.db` file.

### Import cache and metadata

Generated databases contain a `pt_snap_metadata` table with the source SHA-256, exact device
selection, import format version, producer version, and completion time. `pt-snap import` reuses an
existing target only when the full source SHA-256, import format version, and device selection match.
Package version changes alone do not invalidate the cache.

```bash
# Inspect provenance and compatibility metadata
pt-snap metadata snapshot.pkl.db
pt-snap metadata snapshot.pkl.db --json

# Bypass a matching cache
pt-snap import snapshot.pkl --force
```

Legacy or externally generated compatible databases without this table remain queryable. Their
metadata status is reported as unavailable, and a later import rebuilds them once before reuse.

### Query workflow

Import replays allocator events and normalizes them into per-device
`trace_entry_<device>` and `block_<device>` tables. Focus chooses a database and
optional device; query templates then resolve those device-specific table names:

```bash
pt-snap focus snapshot.pkl.db --device 0
pt-snap query --template-use memory_peak
pt-snap query --template-use block --params '{"min_size": 1048576}'
```

Use `pt-snap query --list` and `pt-snap query --template-info <name>` to inspect
the supported query surface. See [Querying](querying.md) for the complete workflow.

---

## Database Structure

### Tables

| Table | Description | Records (example) |
|-------|-------------|-------------------|
| `dictionary` | Enum mapping dictionary | - |
| `trace_entry_0` | Device 0 event trace table | 8,094 |
| `block_0` | Device 0 memory block table | - |
| `pt_snap_metadata` | First-party import provenance and cache metadata | 1 |

> **Naming convention**: For multi-device scenarios, table names are suffixed with the device ID, e.g., `trace_entry_1` and `block_1` for device 1.

---

## Table Definitions

### 1. trace_entry_{device} — Event Trace Table

Records complete trace information for memory management events.

#### Schema

```sql
CREATE TABLE trace_entry_0 (
    `id` INTEGER PRIMARY KEY,
    `action` INTEGER,
    `address` INTEGER,
    `size` INTEGER,
    `stream` INTEGER,
    `allocated` INTEGER,
    `active` INTEGER,
    `reserved` INTEGER,
    `callstack` TEXT
);
```

#### Columns

| Column | Type | Constraints | Description | Example |
|--------|------|-------------|-------------|---------|
| id | INTEGER | PRIMARY KEY | Unique event ID; negative values indicate system-generated events | `1`, `-100` |
| action | INTEGER | — | Action type code (see below) | `4` |
| address | INTEGER | — | Memory address | `20697535234048` |
| size | INTEGER | — | Allocation size in bytes | `41943040` |
| stream | INTEGER | — | CUDA/CANN stream ID | `1276474240` |
| allocated | INTEGER | — | Total allocated bytes | `136426496` |
| active | INTEGER | — | Total active bytes | `136426496` |
| reserved | INTEGER | — | Memory pool reserved bytes | `155189248` |
| callstack | TEXT | NULL | Callstack information (multi-line text) | See example |

#### Action Type Codes

| Value | Name | Description |
|-------|------|-------------|
| 0 | segment_map | Memory segment mapped (expandable segment) |
| 1 | segment_unmap | Memory segment unmapped |
| 2 | segment_alloc | Memory segment allocated |
| 3 | segment_free | Memory segment freed |
| 4 | alloc | Memory allocation event |
| 5 | free_requested | Free request |
| 6 | free_completed | Free completed |
| 7 | workspace_snapshot | NPU-specific workspace memory pool snapshot |

#### ID Constraints

| Condition | Constraint |
|-----------|------------|
| `id >= 0` | Event IDs strictly follow the chronological order after snapshot collection starts, incrementing and unique |
| `id < 0` | Synthetic events generated from raw pickle data to reconstruct Segments that existed at snapshot collection start; event type is always `segment_map` or `segment_alloc` |

#### Data Example

```
id=1, action=4, address=20697535234048, size=41943040, stream=1276474240
allocated=136426496, active=136426496, reserved=155189248
callstack:
  /home/liuyekang/dev/projects/test/memory_leaks_demo.py:60 <module>
  /home/liuyekang/dev/projects/test/memory_leaks_demo.py:34 main
  /home/liuyekang/dev/projects/test/memory_leaks_demo.py:24 train
  /home/liuyekang/dev/projects/test/memory_leaks_demo.py:12 train_one_step
```

---

### 2. block_{device} — Memory Block Table

Records detailed information about memory blocks and their lifecycle state.

#### Schema

```sql
CREATE TABLE block_0 (
    `id` INTEGER PRIMARY KEY,
    `address` INTEGER,
    `size` INTEGER,
    `requestedSize` INTEGER,
    `state` INTEGER DEFAULT 99,
    `allocEventId` INTEGER,
    `freeEventId` INTEGER
);
```

#### Columns

| Column | Type | SQL default | Description |
|--------|------|---------|-------------|
| id | INTEGER | — | Unique block ID; dynamic blocks use their allocation event ID, while preexisting blocks use a negative ID |
| address | INTEGER | — | Memory address |
| size | INTEGER | — | Actual allocated size (includes alignment overhead) |
| requestedSize | INTEGER | — | User-requested allocation size |
| state | INTEGER | 99 | State code (see below) |
| allocEventId | INTEGER | — | Associated allocation event ID; the producer writes `-1` when it was not captured |
| freeEventId | INTEGER | — | Associated free-completion event ID; the producer writes `-1` when it was not captured |

#### State Codes

| Value | Name | Description |
|-------|------|-------------|
| -1 | inactive | Inactive (freed) |
| 0 | active_pending_free | Active, pending free |
| 1 | active_allocated | Active, allocation |
| 99 | unknown | Unknown (default) |

#### ID Constraints

| Condition | Constraint |
|-----------|------------|
| `id >= 0` | `block.id` matches `allocEventId`, pointing to the same-ID allocation event in `trace_entry` |
| `id < 0` | The block was already allocated before snapshot collection began. Only its existence and initial state are known from pickle data; allocation time is unknown. The negative value itself carries no semantic meaning beyond uniqueness |

#### allocEventId Constraints

| Condition | Constraint |
|-----------|------------|
| `allocEventId >= 0` | `block.id` matches `allocEventId`, pointing to the same-ID allocation event in `trace_entry` |
| `allocEventId == -1` | The allocation event for this block was not captured during snapshot collection (the block was already allocated before collection started) |

#### freeEventId Constraints

| Condition | Constraint |
|-----------|------------|
| `freeEventId >= 0` | Points to the corresponding free-completion event in `trace_entry`; it is independent of `block.id` |
| `freeEventId == -1` | The free completion event for this block was not captured during snapshot collection (the block was not freed when collection ended) |

#### State Usage

`block.state` is only meaningful when `block.id` is negative; otherwise it has no practical use.

#### Size Calculation

`block.size` is the actual allocated size, while `block.requestedSize` is the
user-requested size. Both values come from the snapshot producer or replayed
allocator state. Their relationship depends on allocator configuration and must
not be inferred with one universal alignment formula.

#### Data Example

```
id=-320, address=20697531023360, size=4194816, requestedSize=4194304
state=1, allocEventId=-1, freeEventId=-1
```

---

### 3. dictionary — Mapping Dictionary

Stores enum value mappings used to decode fields like `action` and `state`.

#### Schema

```sql
CREATE TABLE dictionary (
    `table` TEXT,     -- Table name
    `column` TEXT,    -- Column name
    `key` TEXT,       -- Encoded integer value (as string)
    `value` TEXT      -- Original string value
);
```

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| table | TEXT | Parent table name, e.g., `trace_entry_0`, `block_0` |
| column | TEXT | Column name, e.g., `action`, `state` |
| key | TEXT | Encoded integer value as string, e.g., `4`, `1` |
| value | TEXT | Original string value, e.g., `alloc`, `active_allocated` |

#### Data Example

```
table=trace_entry_0, column=action, key=4, value=alloc
table=block_0, column=state, key=1, value=active_allocated
```

### 4. pt_snap_metadata — Import Metadata Table

First-party imports create one metadata row for provenance and cache
compatibility checks:

```sql
CREATE TABLE pt_snap_metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    metadata_schema_version INTEGER NOT NULL,
    import_format_version INTEGER NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_size INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    requested_device INTEGER,
    importer_name TEXT NOT NULL,
    importer_version TEXT NOT NULL,
    completed_at TEXT NOT NULL
);
```

Legacy and externally produced compatible databases may omit this table. They
remain queryable, but `pt-snap metadata` reports their metadata as unavailable.
