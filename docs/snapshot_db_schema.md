# SnapshotDB Schema 文档

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

### 1. trace_entry_{device} - 事件跟踪表

记录内存管理事件的完整追踪信息。

#### Schema

```sql
CREATE TABLE trace_entry_0 (
    `id` INTEGER PRIMARY KEY,           -- 事件 ID
    `action` INTEGER,                   -- 动作类型编码
    `address` INTEGER,                  -- 内存地址
    `size` INTEGER,                     -- 大小（字节）
    `stream` INTEGER,                   -- CUDA/CANN 流 ID
    `allocated` INTEGER,                -- 已分配总量（字节）
    `active` INTEGER,                   -- 活跃总量（字节）
    `reserved` INTEGER,                 -- 内存池保留总量（字节）
    `callstack` TEXT                    -- 调用栈信息（多行文本）
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

### 2. block_{device} - 内存块表

记录内存块的详细信息和生命周期状态。

#### Schema

```sql
CREATE TABLE block_0 (
    `id` INTEGER PRIMARY KEY,           -- 块 ID
    `address` INTEGER,                  -- 内存地址
    `size` INTEGER,                     -- 实际分配大小
    `requestedSize` INTEGER DEFAULT 99, -- 请求大小
    `state` INTEGER DEFAULT 99,         -- 状态编码
    `allocEventId` INTEGER,             -- 分配事件 ID
    `freeEventId` INTEGER               -- 释放事件 ID
);
```

#### 字段说明

| 字段名 | 类型 | 约束 | 默认值 | 说明 |
|--------|------|------|--------|------|
| id | INTEGER | PRIMARY KEY | - | 块唯一标识，通常为负数 |
| address | INTEGER | NOT NULL | - | 内存地址 |
| size | INTEGER | NOT NULL | - | 实际分配大小（含对齐开销） |
| requestedSize | INTEGER | NOT NULL | 99 | 用户请求的大小 |
| state | INTEGER | NOT NULL | 99 | 状态编码（见下表） |
| allocEventId | INTEGER | NULL | -1 | 关联的分配事件 ID |
| freeEventId | INTEGER | NULL | -1 | 关联的释放事件 ID |

#### 状态编码（state 字段）

| 值 | 名称 | 说明 |
|----|------|------|
| -1 | inactive | 非活跃状态（已释放） |
| 0 | active_pending_free | 活跃，待释放 |
| 1 | active_allocated | 活跃，已分配 |
| 99 | unknown | 未知状态（默认值） |

#### 数据示例

```
id=-320, address=20697531023360, size=4194816, requestedSize=4194304
state=1, allocEventId=-1, freeEventId=-1
```

---

### 3. dictionary - 字典映射表

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

