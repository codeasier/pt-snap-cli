# SnapshotDB Schema

[English](database.md) | [中文](../zh/database.md)

## Overview

SnapshotDB is the SQLite database format for persisting PyTorch memory profiling data. It supports multi-device (multi-GPU) snapshot storage and querying. Notably, it does more than simply converting raw pickle snapshot data into SQLite — it performs a complete "replay" of the raw memory snapshot data and records additional information during the replay, such as:
1. The total memory pool size and total allocated block size after any event;
2. The complete lifecycle of all memory blocks during the collection period (which event allocated them, which event freed them).

**Example database file**: `snapshot_expandable.pkl.db`

---

## Database Structure

### Tables

| Table | Description | Records (example) |
|-------|-------------|-------------------|
| `dictionary` | Enum mapping dictionary | - |
| `trace_entry_0` | Device 0 event trace table | 8,094 |
| `block_0` | Device 0 memory block table | - |

> **Naming convention**: For multi-device scenarios, table names are suffixed with the device ID, e.g., `trace_entry_1` and `block_1` for device 1.

---

## Table Definitions

### 1. trace_entry_{device} — Event Trace Table

Records complete trace information for memory management events.

#### Schema

```sql
CREATE TABLE trace_entry_0 (
    `id` INTEGER PRIMARY KEY,
    `action` INTEGER NOT NULL,
    `address` INTEGER NOT NULL,
    `size` INTEGER NOT NULL,
    `stream` INTEGER NOT NULL,
    `allocated` INTEGER NOT NULL,
    `active` INTEGER NOT NULL,
    `reserved` INTEGER NOT NULL,
    `callstack` TEXT
);
```

#### Columns

| Column | Type | Constraints | Description | Example |
|--------|------|-------------|-------------|---------|
| id | INTEGER | PRIMARY KEY | Unique event ID; negative values indicate system-generated events | `1`, `-100` |
| action | INTEGER | NOT NULL | Action type code (see below) | `4` |
| address | INTEGER | NOT NULL | Memory address | `20697535234048` |
| size | INTEGER | NOT NULL | Allocation size in bytes | `41943040` |
| stream | INTEGER | NOT NULL | CUDA/CANN stream ID | `1276474240` |
| allocated | INTEGER | NOT NULL | Total allocated bytes | `136426496` |
| active | INTEGER | NOT NULL | Total active bytes | `136426496` |
| reserved | INTEGER | NOT NULL | Memory pool reserved bytes | `155189248` |
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
    `address` INTEGER NOT NULL,
    `size` INTEGER NOT NULL,
    `requestedSize` INTEGER NOT NULL DEFAULT 99,
    `state` INTEGER NOT NULL DEFAULT 99,
    `allocEventId` INTEGER DEFAULT -1,
    `freeEventId` INTEGER DEFAULT -1
);
```

#### Columns

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | — | Unique block ID, typically negative |
| address | INTEGER | — | Memory address |
| size | INTEGER | — | Actual allocated size (includes alignment overhead) |
| requestedSize | INTEGER | 99 | User-requested allocation size |
| state | INTEGER | 99 | State code (see below) |
| allocEventId | INTEGER | -1 | Associated allocation event ID |
| freeEventId | INTEGER | -1 | Associated free event ID |

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
| `freeEventId >= 0` | `block.id` matches `freeEventId`, pointing to the same-ID free event in `trace_entry` |
| `freeEventId == -1` | The free completion event for this block was not captured during snapshot collection (the block was not freed when collection ended) |

#### State Usage

`block.state` is only meaningful when `block.id` is negative; otherwise it has no practical use.

#### Size Calculation

`block.size` is the actual allocated size (including alignment overhead), while `block.requestedSize` is the user-requested size. The calculation is:

```
size = math.ceil((requestedSize + 32) / 512) * 512
```

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
    `key` TEXT,       -- Original string value
    `value` TEXT      -- Encoded integer value (as string)
);
```

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| table | TEXT | Parent table name, e.g., `trace_entry_0`, `block_0` |
| column | TEXT | Column name, e.g., `action`, `state` |
| key | TEXT | Original string value, e.g., `alloc`, `active_allocated` |
| value | TEXT | Encoded integer value as string, e.g., `4`, `1` |

#### Data Example

```
table=trace_entry_0, column=action, key=alloc, value=4
table=block_0, column=state, key=active_allocated, value=1
```
