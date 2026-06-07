# 运行查询

[English](../en/querying.md) | 中文

对快照数据库执行内存分析查询。

## Query 命令

```bash
pt-snap query [--template-use <template_name>] [--params <json>] [--device <id>] [--list] [--template-info <template>]
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| `db_path` | SQLite 数据库文件路径（已配置 context 时可选） |
| `--template-use` | 查询模板名称（除非使用 `--list` 或 `--template-info`，否则必需） |
| `--params` | JSON 格式的查询参数 |
| `--device` | 设备 ID |
| `--list` | 列出可用的查询模板 |
| `--category` | 按分类过滤模板：`basic`、`statistical`、`business` |
| `--template-info` | 显示模板详情（参数和输出 schema） |

## 查询模板

模板分为三个分类。使用 `pt-snap query --list` 查看所有模板，或用 `--category` 过滤。

### Basic Queries

原始数据查询。

| 模板 | 说明 |
|------|------|
| `block` | 灵活字段过滤的内存块查询 |
| `event` | 灵活字段过滤的内存事件查询 |
| `allocation` | 内存分配时间线（id, allocated, active, reserved） |

### Statistical Queries

聚合分析。

| 模板 | 说明 |
|------|------|
| `callstack_analysis` | 调用栈分析 |
| `memory_peak` | 峰值内存指标 |
| `active_blocks_at_event` | 查询某个事件时刻仍然活跃的 block，可选包含静态内存 |
| `allocator_gap` | 比较 allocated、active、reserved 三类峰值事件及其同事件 gap |

### Business Queries

领域特定分析。

| 模板 | 说明 |
|------|------|
| `leak_detection` | 查找未匹配释放事件的分配 |
| `active_memory_callstack_at_event` | 对某个事件时刻的活跃内存块按分配调用栈做聚合，并单独标识静态内存 |

## 峰值内存归因工作流

这些新增能力把“先找到峰值，再解释峰值时刻哪些内存仍然活跃”的手工分析流程产品化了。

### 1. 先定位峰值事件

```bash
pt-snap query --template-use memory_peak
```

这个模板会返回 `allocated`、`active`、`reserved` 的峰值，以及各自对应的事件 ID。

### 2. 查看该事件时刻仍然活跃的 block

```bash
pt-snap query --template-use active_blocks_at_event --params '{"event_id": 1234, "include_static": true}'
```

`active_blocks_at_event` 认为 block 在 `event_id` 时刻仍然活跃的条件是：

- `allocEventId <= event_id`
- 且 `freeEventId = -1` 或 `freeEventId > event_id`

当 `include_static=true` 时，还会包含 `allocEventId=-1 AND freeEventId=-1` 的 block，并标记为 `static`。

### 3. 对该时刻的活跃内存做调用栈归因

```bash
pt-snap query --template-use active_memory_callstack_at_event --params '{"event_id": 1234, "include_static": true, "top_n": 20}'
```

这个查询会：

- 先从 `event_id` 时刻的活跃 block 集合开始
- 把动态 block 回连到 `trace_entry_<device>` 的分配事件
- 按分配调用栈做聚合
- 对静态内存单独分组，而不是伪造调用栈

### 4. 比较不同指标的峰值与 gap

```bash
pt-snap query --template-use allocator_gap
```

这个模板会报告：

- `allocated`、`active`、`reserved` 的峰值事件
- 它们是否发生在同一个事件
- 同一事件上的 gap，例如 `reserved - active`、`reserved - allocated`

这样可以避免误把不同事件上的峰值直接相减，并错误解释为同一时刻的碎片或缓存 gap。

## Report 命令

如果需要更高层的摘要，可以使用：

```bash
pt-snap report peak-memory [db_path] [--device <id>] [--metric active|allocated|reserved] [--include-static|--exclude-static] [--limit <n>] [--json]
```

示例：

```bash
# 生成基于 active 峰值事件的文本报告
pt-snap report peak-memory /path/to/snapshot.db

# 改为查看 reserved 峰值
pt-snap report peak-memory /path/to/snapshot.db --metric reserved

# 输出机器可读 JSON
pt-snap report peak-memory /path/to/snapshot.db --json
```

这个 report 命令会组合：

- `memory_peak`
- `allocator_gap`
- `active_memory_callstack_at_event`

并输出人类可读摘要或 JSON。

**示例：**
```bash
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

参数：
- `min_size`: 最小泄漏大小（字节），默认 0
- `device_id`: 设备 ID

## 输出格式

默认情况下显示所有结果。使用 `-n` 限制显示行数：

```
# 显示所有结果（默认）
pt-snap query --template-use leak_detection

# 仅显示前 5 条
pt-snap query --template-use leak_detection -n 5

# 显示所有结果（显式）
pt-snap query --template-use leak_detection -n 0
```

示例输出（使用 `-n 2`）：

```
Found 150 results, showing 2:
  {'id': 1, 'address': '0x1000', 'size': 2048, ...}
  {'id': 2, 'address': '0x2000', 'size': 4096, ...}
  ... and 148 more (use -n to show more)
```

## 模板架构

查询模板使用 YAML 格式定义，包含：
- `version`: 模板版本
- `queries`: 查询定义，包含描述、支持的设备、参数、SQL（Jinja2 模板语法）和输出 schema

**支持的类型转换器：** `int`、`float`、`str`、`bool`、`hex`、`datetime`

## Python API

编程式使用方式见 [ResultMapper API](result-mapper-api.md)。
