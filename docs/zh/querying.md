# 运行查询

[English](../en/querying.md) | 中文

对快照数据库执行内存分析查询。

## Query 命令

```bash
pt-snap query [DB_PATH] [--template-use <template_name>] [--params <json>] \
  [--device <id>] [--list] [--category <category>] \
  [--template-info <template>] [-n <rows>] [--exact-total] [--timeout <seconds>] [--json]
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| `db_path` | SQLite 数据库文件路径（已配置 focus 时可选） |
| `--template-use` | 查询模板名称（除非使用 `--list` 或 `--template-info`，否则必需） |
| `--params` | JSON 格式的查询参数 |
| `--device` | 设备 ID |
| `--list` | 列出可用的查询模板 |
| `--category` | 按分类过滤模板：`basic`、`statistical`、`business` |
| `--template-info` | 显示模板详情（参数、输出 schema 和字段语义） |
| `-n` | 最大显示行数；零或负数表示不限制。与 `--timeout` 相互独立。 |
| `--exact-total` | 对匹配集合做 `COUNT`。默认 `total` 等于已返回行数。 |
| `--timeout` | 执行超时（秒），经 SQLite progress handler 生效。`<= 0` 表示关闭。默认：`PT_SNAP_QUERY_TIMEOUT` 或不限制。 |
| `--json` | 输出机器可读 JSON（执行、`--list` 与 `--template-info`） |

## 查询模板

模板分为三个分类。使用 `pt-snap query --list` 查看所有模板，或用 `--category` 过滤。

### Basic Queries

原始数据查询。

| 模板 | 说明 |
|------|------|
| `block` | 灵活字段过滤的内存块查询 |
| `event` | 灵活字段过滤的内存事件查询 |
| `allocation` | 内存分配时间线（id, allocated, active, reserved） |

`event`、`callstack_analysis` 和 `active_memory_callstack_at_event` 对外保持同一契约，
并根据数据库布局选择 v1 或 v2 SQL。见
[调用栈布局兼容](database.md#调用栈布局兼容)。

### Statistical Queries

聚合分析。

| 模板 | 说明 |
|------|------|
| `callstack_analysis` | 调用栈分析 |
| `memory_peak` | 峰值内存指标 |
| `active_blocks_at_event` | 查询某个事件时刻仍然活跃的 block，可选包含静态与 preexisting 存活内存 |
| `allocator_gap` | 比较 allocated、active、reserved 三类峰值事件及其同事件 gap |

### Business Queries

领域特定分析。

| 模板 | 说明 |
|------|------|
| `leak_detection` | 查找已采集分配且没有释放完成记录的候选（不是已确认泄漏） |
| `active_memory_callstack_at_event` | 对某个事件时刻的活跃内存块按分配调用栈做聚合，并单独标识静态与 preexisting 内存 |

## 泄漏检测

```bash
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

`min_size` 表示候选泄漏的最小字节数，默认值为 `0`。目标设备应通过命令级
`--device` 选项指定，而不是放进 `--params`。`leak_detection` 返回的是捕获范围内
仍存活的候选，不是已确认泄漏。用 `pt-snap query --template-info leak_detection`
读取字段单位与解释限制。

## 参数校验

`--params` 会在渲染任何 SQL 之前按模板定义进行校验：

- 每个键都必须是模板声明的参数。未声明的键会被拒绝而不是忽略，因此把
  `min_size` 拼成 `min_sze` 会得到 `Unknown parameter(s) for template
  'leak_detection': min_sze (accepted: min_size, limit)`，而不是悄悄返回一份
  未过滤的结果。
- 值会按声明的类型（`int`、`float`、`str`、`bool`）转换。
- 会被当作 SQL 标识符或关键字渲染的参数（如 `order_by`、`order_dir`）只接受
  `--template-info` 中 `[choices: ...]` 列出的取值。字符串取值不区分大小写，
  并按声明的写法渲染（`desc` 会变成 `DESC`）；其他任何值都会在到达数据库之前
  被拒绝。

```bash
pt-snap query --template-info allocation
#   order_by: str (optional) [choices: id, allocated, active, reserved] [default: id]
#   order_dir: str (optional) [choices: ASC, DESC] [default: ASC]

pt-snap query --template-use allocation --params '{"order_by": "reserved", "order_dir": "desc"}' -n 5
```

`SnapshotAnalyzer.execute_query()` 遵循同样的规则，并以相同的错误信息抛出
`TemplateRenderError`。

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

- 动态 block：`allocEventId != -1 AND allocEventId <= event_id`，且 `freeEventId` 为 `NULL`、负数或大于 `event_id`
- 无分配事件的 block（`allocEventId = -1`）：`freeEventId` 为 `NULL`、负数或大于 `event_id`

当 `include_static=true` 时，还会包含无分配事件且在 `event_id` 时刻仍活跃的 block：

- `allocEventId=-1 AND freeEventId=-1` 标记为 `static`
- 其余无分配事件但存活的 block（例如快照采集前已分配、之后才释放）标记为 `preexisting_live_at_event`

### 3. 对该时刻的活跃内存做调用栈归因

```bash
pt-snap query --template-use active_memory_callstack_at_event --params '{"event_id": 1234, "include_static": true, "top_n": 20}'
```

这个查询会：

- 先从 `event_id` 时刻的活跃 block 集合开始
- 把动态 block 回连到 `trace_entry_<device>` 的分配事件
- 按分配调用栈做聚合
- 对静态内存和 preexisting 内存单独分组，而不是伪造调用栈

`top_n` 只限制动态调用栈分组的数量；`static` 和 `preexisting_live_at_event` 分组始终返回，不会被更大的动态分组挤出结果。

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

## JSON 输出

`--json` 向 stdout 写一个 JSON 对象。成功结果包含 `schema_version`（当前为 `1`）、
`ok: true` 以及命令字段：

| 分支 | 额外字段 |
|------|----------|
| 执行 | `db_path`、`focus_source`、`device_id`、`template`、`effective_params`、`semantics_version`、`total`、`returned`、`has_more`、`truncated`、`total_is_exact`、`timeout_s`、`rows` |
| `--list` | `category`、`templates`（`name`、`description`、`category`） |
| `--template-info` | 与 `get_template_info()` 对齐的模板元数据，另加 `template` |

`-n` 仍然限制 `rows` 与 `returned`。默认 `total` 等于 `returned`（本页行数）；
仅当本页就是完整匹配集合（`has_more` 为 false 且 `offset` 为 0）时
`total_is_exact` 为 true。`--exact-total` 会对匹配集合做 `COUNT`（忽略
`limit` / `offset` / `top_n`）并把 `total_is_exact` 设为 true。存在有限
`LIMIT` 时，执行器会多取一行来设置 `has_more`，不必先做计数。`truncated`
表示本次响应不是完整匹配集合（`has_more`、正 `offset`，或精确 `total`
大于 `returned`）。`timeout_s` 是生效的执行超时秒数，未限制时为 `null`。
`--timeout` / `PT_SNAP_QUERY_TIMEOUT` 走 SQLite progress handler，不改变行数上限。

`effective_params` 是应用默认值并按 `choices` 规范化后的参数。带 `-n` 时，
`limit` 是与执行器相同的**尾部** SQL `LIMIT`：已声明的模板 `limit` 与 `-n`
取较小值；渲染后的 SQL 没有尾部 `LIMIT` 时追加 `-n`。CTE 内部的 `top_n`
仍是独立参数，不会改写 `limit`。
`--template-info --json` 包含 `semantics_version`、`interpretation_limits`
以及 `output_schema` 上的字段语义。

`event`、`block` 与 `allocation` 用 `limit` / `offset` 分页，并在 `order_by`
之后用 `id` 做稳定次序。截断后应带着相同排序键提高 `offset`（或 `-n`）续页，
不要把当前页当成完整集合。

`--json` 失败时 stdout 为空，stderr 为：

```json
{
  "schema_version": 1,
  "ok": false,
  "error": {
    "code": "TEMPLATE_NOT_FOUND",
    "message": "Template 'missing' not found",
    "hint": "Use 'pt-snap query --list --json' to list available templates."
  }
}
```

稳定错误码包括 `TEMPLATE_NOT_FOUND`、`INVALID_PARAMETER`、
`DATABASE_NOT_FOUND`、`DEVICE_NOT_FOUND` 和 `FOCUS_NOT_CONFIGURED`，退出码非零。
`pt-snap` 控制台入口的用法/解析错误（例如 `query -n abc --json`）也走同一信封，
错误码为 `INVALID_PARAMETER`，退出码 2。Click 在 `--json` 回调之前失败时，
该路径是 best-effort 的 argv 扫描：`--` 之前的精确 `--json` 词，且不是前一个
选项的值。`--opt=value` 与 `-1` 这类数字词不会吞掉下一个参数。
`pt-snap` 控制台入口返回 Typer/Click 的退出码（失败非零）。Ctrl-C / EOF
在文本模式向 stderr 写 `Aborted!`（退出码 1；Typer 返回 130 时为 130）。
带 `--json` 时 stdout 仍为空，stderr 为本信封（`ERROR`，message 为 `Aborted!`）。
文本模式保持不变：`Error:` 仍写到 stdout（包括缺失模板的 `--template-info`，它已经以退出码 1 失败）。

已有的 `metadata --json` 与 `report peak-memory --json` 字段名保持兼容。这两条命令在带 `--json` 失败时也使用同一套 stderr 错误信封。

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

示例输出（使用 `-n 2`，默认 `total` 语义）：

```
Found 2 results, showing 2:
  {'id': 1, 'address': 4096, 'size': 2048, ...}
  {'id': 2, 'address': 8192, 'size': 4096, ...}
  ... more available (use -n, offset, or --exact-total)
```

加上 `--exact-total` 时，"Found N" 是匹配行总数，页脚可以给出剩余行数。
`SnapshotAnalyzer.execute_query()` 默认 `max_rows=None`（不截断）且
`exact_total=False`，与 CLI 在未指定 `-n` / `max_rows` 或 `--exact-total` /
`exact_total` 时一致。`timeout_s` 与行数上限相互独立。

CLI 和 Python API 的查询结果包含原始 SQLite 值。模板的 `output_schema`
只是 metadata，查询执行时不会自动应用。需要十六进制地址字符串等转换值时，
应显式调用 `ResultMapper`。结果行不重复字段说明；用 `--template-info`
（或 `get_template_info`）按产生这些行的模板查阅 `semantics_version` 与解释限制。
`SnapshotAnalyzer.execute_query()` 的结果还包含 `template` 与 `semantics_version`，
便于把行与契约对应起来。

## 模板架构

查询模板使用 YAML 格式定义，包含：
- `version`: YAML 文件格式版本，既不是字段语义契约，也不是 SnapshotDB schema 版本
- `queries`: 查询定义，包含描述、支持的设备、参数、SQL（Jinja2 模板语法）和输出 schema
- 每个参数声明 `type`、`default`、`required`、`description`，以及可选的 `choices`（允许取值的封闭列表；会被渲染为 SQL 标识符或关键字的参数必须声明它）
- 查询可选声明 `semantics_version`（正整数）和 `interpretation_limits`；`output_schema` 各列还可声明 `units`、`metric_semantics`、`scope`、`denominator`、`sentinel`、`interpretation_limits`
- `semantics_version` 是 Agent 应引用的解释契约。同一模板的 v1/v2 SQL 变体共享该契约。未同时声明两者时模板仍有效；未注解的 `output_schema` 条目仅含 `column` 与 `type`

封闭词表：

- `units`：`bytes`、`gib`、`percent`、`event_id`、`count`、`address`、`flag`、`text`
- `metric_semantics`：`instantaneous_occupancy`、`same_event_gap`、`share_of_included_rows`、`identifier`、`classification`、`ordering_marker`
- `scope`：`dynamic`、`static`、`preexisting`、`mixed`、`captured_range`、`same_event`。一列按行混合多种范围时用 `mixed`（见 `active_memory_callstack_at_event` 的 `category`）

显式传给 `ResultMapper` 时，可识别的映射类型包括 `int`、`float`、`str`、
`bool`、`hex` 和 `datetime`；当前 `datetime` 只是透传声明，不执行解析。

## 可选结果映射

可选的行转换和模型映射方式见 [ResultMapper API](result-mapper-api.md)。

高层编程式 focus 和查询门面见 [SnapshotAnalyzer API](snapshot-analyzer-api.md)。
