# SnapshotDB Schema

[English](../en/database.md) | 中文

## 概述

SnapshotDB 是内存快照数据的 SQLite 数据库存储格式，用于持久化内存分配追踪信息。支持多设备（多 GPU）快照数据的存储和查询。

**数据库示例文件**: `snapshot_expandable.pkl.db`

---

## 数据库结构

### 表列表

| 表名 | 说明 | 记录数（示例） |
|------|------|---------------|
| `dictionary` | 字典映射表 | - |
| `trace_entry_0` | 设备 0 的事件跟踪表 | 8,094 |
| `block_0` | 设备 0 的内存块表 | - |

> **命名规则**: 多设备场景下，表名后缀为设备 ID，如 `trace_entry_1`、`block_1` 表示设备 1 的数据。

---

## 表详细定义

### 1. trace_entry_{device} — 事件跟踪表

记录内存管理事件的完整追踪信息。

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

#### 字段说明

| 字段名 | 类型 | 约束 | 说明 | 示例值 |
|--------|------|------|------|--------|
| id | INTEGER | PRIMARY KEY | 事件唯一标识，负数表示系统自动生成 | `1`, `-100` |
| action | INTEGER | NOT NULL | 动作类型编码（见下表） | `4` |
| address | INTEGER | NOT NULL | 内存地址 | `20697535234048` |
| size | INTEGER | NOT NULL | 分配大小（字节） | `41943040` |
| stream | INTEGER | NOT NULL | 流 ID（CUDA/CANN） | `1276474240` |
| allocated | INTEGER | NOT NULL | 当前已分配总量 | `136426496` |
| active | INTEGER | NOT NULL | 当前活跃总量 | `136426496` |
| reserved | INTEGER | NOT NULL | 内存池保留总量 | `155189248` |
| callstack | TEXT | NULL | 调用栈，多行文本格式 | 见示例 |

#### 动作类型编码（action 字段）

| 值 | 名称 | 说明 |
|----|------|------|
| 0 | segment_map | 内存段映射（可扩展段） |
| 1 | segment_unmap | 内存段解除映射 |
| 2 | segment_alloc | 内存段分配 |
| 3 | segment_free | 内存段释放 |
| 4 | alloc | 内存分配事件 |
| 5 | free_requested | 释放请求 |
| 6 | free_completed | 释放完成 |
| 7 | workspace_snapshot | 工作区快照 |

#### id 字段约束

| 条件 | 约束 |
|------|------|
| `id >= 0` | 事件 ID 严格按照启动内存快照采集后的发生顺序递增，且唯一 |
| `id < 0` | 为从原始 pickle 数据中虚拟生成的事件，事件类型一定为 `segment_map` 或 `segment_alloc`，用于还原启动内存快照采集时刻已有的 Segment |

#### 数据示例

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

### 2. block_{device} — 内存块表

记录内存块的详细信息和生命周期状态。

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

#### 字段说明

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| id | INTEGER | — | 块唯一标识，通常为负数 |
| address | INTEGER | — | 内存地址 |
| size | INTEGER | — | 实际分配大小（含对齐开销） |
| requestedSize | INTEGER | 99 | 用户请求的大小 |
| state | INTEGER | 99 | 状态编码（见下表） |
| allocEventId | INTEGER | -1 | 关联的分配事件 ID |
| freeEventId | INTEGER | -1 | 关联的释放事件 ID |

#### 状态编码（state 字段）

| 值 | 名称 | 说明 |
|----|------|------|
| -1 | inactive | 非活跃状态（已释放） |
| 0 | active_pending_free | 活跃，待释放 |
| 1 | active_allocated | 活跃，已分配 |
| 99 | unknown | 未知状态（默认值） |

#### id 字段约束

| 条件 | 约束 |
|------|------|
| `id >= 0` | `block.id` 与 `allocEventId` 一致，共同指向 `trace_entry` 中相同 ID 的分配事件 |
| `id < 0` | 仅代表通过原始 pickle 数据中的 Segment 信息得知该内存块在采集开始时已分配，无从得知分配时间。负数值本身无实际含义，仅用于唯一标识 |

#### state 约束

`block.state` 仅在 `block.id` 为负数时才有实际意义，否则无实际用途。

#### requestedSize 约束

`block.requestedSize` 是请求大小，`block.size` 是实际分配大小（含对齐开销）。计算公式：

```
size = math.ceil((requestedSize + 32) / 512) * 512
```

#### 数据示例

```
id=-320, address=20697531023360, size=4194816, requestedSize=4194304
state=1, allocEventId=-1, freeEventId=-1
```

---

### 3. dictionary — 字典映射表

存储枚举值的编码映射关系，用于解码 action 和 state 等字段。

#### Schema

```sql
CREATE TABLE dictionary (
    `table` TEXT,     -- 表名
    `column` TEXT,    -- 列名
    `key` TEXT,       -- 原始值（字符串）
    `value` TEXT      -- 编码值（字符串）
);
```

#### 字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| table | TEXT | 所属表名，如 `trace_entry_0`、`block_0` |
| column | TEXT | 所属列名，如 `action`、`state` |
| key | TEXT | 原始字符串值，如 `alloc`、`active_allocated` |
| value | TEXT | 编码后的整数值（字符串格式），如 `4`、`1` |

#### 数据示例

```
table=trace_entry_0, column=action, key=alloc, value=4
table=block_0, column=state, key=active_allocated, value=1
```
