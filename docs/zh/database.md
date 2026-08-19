# SnapshotDB Schema

[English](../en/database.md) | 中文

## 概述

SnapshotDB 是内存快照数据的 SQLite 数据库存储格式，用于持久化内存分配追踪信息。支持多设备（多 GPU）快照数据的存储和查询。
需要说明的是，它不仅仅是将内存快照原始pickle数据转成了SQLite数据库，而是针对原始内存快照数据进行了一次完整的“回放”，并记录了回放过程中的额外信息，如
1. 任一事件发生后的内存池总大小、总分配内存块大小；
2. 采集周期中，所有的内存块的完整生命周期（在哪个事件申请、哪个事件释放）

**数据库示例文件**: `snapshot.pkl.db`

## 生成 SnapshotDB

如果输入是 PyTorch 原始 `.pkl` 内存快照，可以直接导入：

> **安全警告：** 只能导入可信的 pickle 文件。反序列化 pickle 可能执行任意代码；
> 实现会拒绝非 builtins 全局对象，但 `pt-snap import` 不是沙箱。

```bash
pt-snap import snapshot.pkl
```

默认情况下，内建快照运行时会在输入文件旁生成 `snapshot.pkl.db`，并更新当前项目的
focus，后续命令可直接使用：

```bash
pt-snap query --list
```

也可以使用其他兼容生产者生成相同格式的 SnapshotDB，再将生成的 `.db` 文件传给
`pt-snap focus`。

### 导入缓存与 metadata

新生成的数据库包含 `pt_snap_metadata` 表，记录原始文件 SHA-256、精确设备选择、导入格式
版本、生产者版本和完成时间。只有完整 SHA-256、导入格式版本和设备选择均匹配时，重复导入
才会复用已有 DB；仅升级 `pt-snap-cli` 包版本不会让缓存失效。

```bash
pt-snap metadata snapshot.pkl.db
pt-snap metadata snapshot.pkl.db --json
pt-snap import snapshot.pkl --force
```

旧版或外部生成且结构兼容的 DB 仍可正常查询。若没有 metadata，查询会返回 unavailable，
下一次执行对应 pickle 导入时会重建一次。

### 查询工作流

导入过程会回放分配器事件，并将其规范化为逐设备的 `trace_entry_<device>` 和
`block_<device>` 表。Focus 用于选择数据库和可选设备，查询模板再解析对应的设备表名：

```bash
pt-snap focus snapshot.pkl.db --device 0
pt-snap query --template-use memory_peak
pt-snap query --template-use block --params '{"min_size": 1048576}'
```

使用 `pt-snap query --list` 和 `pt-snap query --template-info <name>` 查看受支持的
查询入口。完整流程见[运行查询](querying.md)。

---

## 数据库结构

### 表列表

| 表名 | 说明 | 记录数（示例） |
|------|------|---------------|
| `dictionary` | 字典映射表 | - |
| `trace_entry_0` | 设备 0 的事件跟踪表 | 8,094 |
| `block_0` | 设备 0 的内存块表 | - |
| `pt_snap_metadata` | 第一方导入来源与缓存 metadata | 1 |

> **命名规则**: 多设备场景下，表名后缀为设备 ID，如 `trace_entry_1`、`block_1` 表示设备 1 的数据。

---

## 表详细定义

### 1. trace_entry_{device} — 事件跟踪表

记录内存管理事件的完整追踪信息。

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

#### 字段说明

| 字段名 | 类型 | 约束 | 说明 | 示例值 |
|--------|------|------|------|--------|
| id | INTEGER | PRIMARY KEY | 事件唯一标识，负数表示系统自动生成 | `1`, `-100` |
| action | INTEGER | — | 动作类型编码（见下表） | `4` |
| address | INTEGER | — | 内存地址 | `20697535234048` |
| size | INTEGER | — | 分配大小（字节） | `41943040` |
| stream | INTEGER | — | 流 ID（CUDA/CANN） | `1276474240` |
| allocated | INTEGER | — | 当前已分配总量 | `136426496` |
| active | INTEGER | — | 当前活跃总量 | `136426496` |
| reserved | INTEGER | — | 内存池保留总量 | `155189248` |
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
| 7 | workspace_snapshot | NPU特有的workspace内存池快照 |

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
    `address` INTEGER,
    `size` INTEGER,
    `requestedSize` INTEGER,
    `state` INTEGER DEFAULT 99,
    `allocEventId` INTEGER,
    `freeEventId` INTEGER
);
```

#### 字段说明

| 字段名 | 类型 | SQL 默认值 | 说明 |
|--------|------|--------|------|
| id | INTEGER | — | 块唯一标识；动态块使用分配事件 ID，采集开始前已存在的块使用负数 ID |
| address | INTEGER | — | 内存地址 |
| size | INTEGER | — | 实际分配大小（含对齐开销） |
| requestedSize | INTEGER | — | 用户请求的大小 |
| state | INTEGER | 99 | 状态编码（见下表） |
| allocEventId | INTEGER | — | 关联的分配事件 ID；未采集到时生产者写入 `-1` |
| freeEventId | INTEGER | — | 关联的释放完成事件 ID；未采集到时生产者写入 `-1` |

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

#### allocEventId约束

| 条件 | 约束 |
|------|------|
| `allocEventId >= 0` | `block.id` 与 `allocEventId` 一致，共同指向 `trace_entry` 中相同 ID 的分配事件 |
| `allocEventId == -1` | 代表在内存快照采集期间，未采集到该内存块的申请事件（在开始采集之前该内存块就已经申请分配完成） |

#### freeEventId约束

| 条件 | 约束 |
|------|------|
| `freeEventId >= 0` | 指向 `trace_entry` 中对应的释放完成事件，与 `block.id` 相互独立 |
| `freeEventId == -1` | 代表在内存快照采集期间，未采集到该内存块的释放完成事件（在结束采集时该内存块并未释放） |

#### state 约束

`block.state` 仅在 `block.id` 为负数时才有实际意义，否则无实际用途。

#### requestedSize 约束

`block.requestedSize` 是用户请求大小，`block.size` 是实际分配大小。两者来自快照生产者
或回放后的分配器状态，其关系取决于分配器配置，不能使用单一对齐公式推导。

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
    `key` TEXT,       -- 编码后的整数值（字符串）
    `value` TEXT      -- 原始字符串值
);
```

#### 字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| table | TEXT | 所属表名，如 `trace_entry_0`、`block_0` |
| column | TEXT | 所属列名，如 `action`、`state` |
| key | TEXT | 编码后的整数值（字符串格式），如 `4`、`1` |
| value | TEXT | 原始字符串值，如 `alloc`、`active_allocated` |

#### 数据示例

```
table=trace_entry_0, column=action, key=4, value=alloc
table=block_0, column=state, key=1, value=active_allocated
```

### 4. pt_snap_metadata — 导入 Metadata 表

第一方导入会创建一条 metadata 记录，用于来源追踪和缓存兼容性检查：

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

旧版或外部生成的兼容数据库可以不包含此表，仍可正常查询；`pt-snap metadata` 会将其
metadata 状态报告为 unavailable。
