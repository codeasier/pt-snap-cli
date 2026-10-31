# SnapshotAnalyzer API

[English](../en/snapshot-analyzer-api.md) | 中文

`SnapshotAnalyzer` 是用于查看 focus、发现模板、列出能力清单、查看数据库概览、
执行查询和检查 SnapshotDB 导入 metadata 的高层 Python 门面。应从
`pt_snap_cli.api` 导入；包根目录不会重新导出它。

`list_templates()` 和 `execute_query()` 返回普通字典，分别使用
`pt_snap_cli.api` 中的 `TemplateSummaryPayload` 和 `QueryResultPayload`
（`TypedDict`）进行类型标注。动态查询单元格和 metadata 值标注为 `object`；
进行有类型约束的操作前，应按模板输出契约收窄类型。这些标注不会转换值或改变结果键。

## 创建 Analyzer

```python
from pathlib import Path

from pt_snap_cli.api import SnapshotAnalyzer

analyzer = SnapshotAnalyzer(
    db_path=Path("/path/to/snapshot.db"),
    device_id=0,
)
```

构造参数 `db_path` 是当前 analyzer 实例的显式数据库，`device_id` 是查询时默认使用的
显式设备覆盖。省略 `db_path` 时，数据库解析顺序与 CLI 相同：`PT_SNAP_DB_PATH`、
最近的 `.pt-snap/focus.json`，最后是 legacy 全局配置。

## 数据集查询预算

可从 `pt_snap_cli.api` 与 `SnapshotAnalyzer` 一起导入冻结的 `QueryLimits`，直接调用
服务时也可从 `pt_snap_cli.core` 导入。它只包含三个不可变上限，不含共享可变计数器：

```python
from pt_snap_cli.api import QueryLimits, SnapshotAnalyzer

limits = QueryLimits.resolve(max_work_rows=300_000, max_work_bytes=128 * 1024**2)
with SnapshotAnalyzer(Path("/path/to/dataset"), query_limits=limits) as analyzer:
    result = analyzer.execute_query("event", {"offset":100_000, "limit":5})
    print(result["scope"]["work_budget"])
    # 只覆盖本次调用；后续仍使用构造时的配置。
    other = analyzer.execute_query("event", query_limits=QueryLimits(max_work_rows=400_000))
```

`QueryLimits()` 始终使用内建默认值：`max_work_rows=100000`、
`max_work_bytes=67108864`、`max_scratch_db_bytes=536870912`。
`QueryLimits.resolve(...)` 对省略的字段读取相应 `PT_SNAP_MAX_WORK_ROWS`、
`PT_SNAP_MAX_WORK_BYTES`、`PT_SNAP_MAX_SCRATCH_DB_BYTES` 环境变量，再回退默认值。
显式字段覆盖对应环境变量，即使该环境值非法。工作上限必须是正整数，不接受布尔值或
浮点数；scratch 接受整数零（禁用）或 4096 至 4294967296 字节。没有无限工作预算；
非法值抛出 core `InvalidParameterError`。

每次操作的 `query_limits` 替换整个构造配置；构造配置又覆盖环境/默认值解析。两处均
省略时，每次操作重新读取环境。若只覆盖部分字段、其余继续读取环境，应调用
`QueryLimits.resolve(...)`。`get_template_info(..., query_limits=...)` 可查看单次覆盖，
`list_capabilities()` 则反映该 analyzer 的常规有效默认配置。

`QueryService`、`ReportService` 构造函数也接受 `query_limits`；`execute_query`、
`peak_memory_report`、`event_attribution`、`memory_tree_report` 接受单次覆盖。
峰值报告步骤共用累计计数器和 deadline，独立操作使用全新计数器。可变内部
`QueryBudget` 不是公开配置接口。预算只约束数据集工作，不约束单库结果物化、RSS 或
所有 SQLite 临时空间。深分页成本、失败语义及保持不变的默认上限见
[公开配置说明](querying.md#公开数据集预算)。

## 连接生命周期与缓存所有权

analyzer 会为查询和概览复用只读 SQLite 连接。使用 `with` 可确定性释放连接，
操作抛出异常时也会清理：

```python
with SnapshotAnalyzer(Path("/path/to/snapshot.db")) as scoped_analyzer:
    overview = scoped_analyzer.get_database_overview()
    result = scoped_analyzer.execute_query("leak_detection")
```

对于下文示例中 `analyzer` 这样的长生命周期实例，使用完毕后应在 `finally` 中调用
`analyzer.close()`。`close()` 是幂等的；上下文管理器退出时会调用它，且不会吞掉异常。
关闭后，focus、发现、metadata、概览和查询方法，以及再次进入 `with`，均抛出
`RuntimeError("SnapshotAnalyzer is closed.")`。需要继续工作时请新建 analyzer。

默认情况下 analyzer 拥有缓存，关闭时会释放缓存内所有连接。如果传入
`context_cache=shared_cache`，该缓存属于**借用**：关闭 analyzer 不会使缓存失效，
也不会关闭其他 analyzer 仍依赖的连接。调用方须在所有借用者使用完毕后调用
`shared_cache.close()`：

```python
from contextlib import closing
from pt_snap_cli.core.context_cache import ContextCache

with closing(ContextCache()) as shared_cache:
    with SnapshotAnalyzer(Path("/path/to/snapshot.db"), context_cache=shared_cache) as first:
        first.get_database_overview()
    with SnapshotAnalyzer(Path("/path/to/snapshot.db"), context_cache=shared_cache) as second:
        second.execute_query("leak_detection")  # 复用仍然打开的缓存。
```

公开的 `context_cache` 属性与 `invalidate_context_cache(db_path=None)` 保持可用，
关闭后也可访问。显式失效操作仍会关闭指定的缓存连接，包括共享连接。与 analyzer 的
`close()` 不同，缓存失效（或 `context_cache.close()`）不会终止尚未关闭的 analyzer：
下一次查询或概览可以重新填充缓存。直接使用公开 cache 时，其生命周期由调用方独立管理。

## 查看和修改 Focus

```python
state = analyzer.get_focus()
print(state.db_path)
print(state.device_id)
print(state.available_devices)
print(state.callstack_layout)
print(state.source)

state = analyzer.set_focus(
    db_path="/path/to/other.db",
    device_id=1,
)
```

`set_focus()` 会验证传入的数据库，但只更新当前 `SnapshotAnalyzer` 对象。它不会写入
`.pt-snap/focus.json`，不会修改 `PT_SNAP_DB_PATH`，也不会更新全局配置。传入的设备会立即
针对新传入或当前解析出的数据库进行验证；验证失败不会改变 analyzer 状态。

传入新的 `db_path` 但省略 `device_id` 时，会清除 analyzer 之前的设备覆盖；这与 CLI
切换 focus 时省略 `--device` 的行为一致。

analyzer 有显式 `db_path` 时，`get_focus()` 会报告 analyzer 的设备，不会继承项目或全局
focus 中的设备。没有显式 `db_path` 时，已验证的 analyzer 设备覆盖会由 `get_focus()`
报告，并在执行查询时生效。

`get_focus()` 返回包含以下字段的 `FocusState`：

| 字段 | 含义 |
| --- | --- |
| `db_path` | 解析后的数据库路径，或 `None` |
| `device_id` | analyzer 设备覆盖；未设置覆盖时为已解析 focus 所附带的设备 |
| `source` | `explicit`、`env`、`project`、`global`、`none` 等解析来源 |
| `available_devices` | 从 `trace_entry_<device>` 表发现的设备 ID |
| `callstack_layout` | 内联调用栈文本为 `"v1"`，去重 `callstackId` 为 `"v2"`，无法识别或冲突时为 `None` |
| `callstack_layout_error` | 布局无法使用时的冲突原因，否则为 `None` |

完整解析和持久化模型见 [Focus 管理](focus-management.md)。

## 列出能力清单

```python
catalog = analyzer.list_capabilities()
print(catalog["cli_version"])
print([item["name"] for item in catalog["templates"]])
print([item["name"] for item in catalog["skills"]])
```

`list_capabilities()` 返回与 `pt-snap capabilities --json` 相同的清单（不含 CLI
信封）：`cli_version`、完整模板契约（与 `get_template_info()` 一致）以及随包
skill 列表。

## 发现模板

```python
templates = analyzer.list_templates()
basic_templates = analyzer.list_templates(category="basic")

info = analyzer.get_template_info("memory_peak")
if info is not None:
    print(info["parameters"])
    print(info["output_schema"])
```

`list_templates()` 返回包含 `name`、`description` 和 `category` 的字典。
`get_template_info()` 返回完整模板 metadata；仅当指定模板不存在时返回 `None`，registry
内部错误会继续向调用方抛出。返回值包含 `parameters`、`output_schema`、
`semantics_version` 和 `interpretation_limits`。`semantics_version` 是字段解释契约，
有别于 YAML `version` 以及 SnapshotDB schema / callstack 布局。未标注的模板
`semantics_version` 为 `null`，列上只有 `column`/`type`；已标注列还可包含
`units`、`metric_semantics`、`scope`、`denominator`、`sentinel` 以及字段级
`interpretation_limits`。该字典可直接 JSON 序列化。

## 执行查询

```python
result = analyzer.execute_query(
    "leak_detection",
    params={"min_size": 1024},
    max_rows=20,
)

print(result["device_id"])
print(result["total"])
print(result["returned"])
for row in result["rows"]:
    print(row)
```

结果包含：

| 键 | 含义 |
| --- | --- |
| `total` | `exact_total=True` 时为匹配集合的 `COUNT`；否则等于已返回行数 |
| `returned` | `rows` 中实际返回的行数 |
| `has_more` | 存在更多行时为 true；内部 `top_n` 窗口已满时也会保守地设为 true（即使恰好只有 N 个组） |
| `truncated` | 本次响应不完整，或内部排名窗口已满而完整性未确认时为 true |
| `total_is_exact` | `total` 来自 `COUNT`，或本页就是完整匹配集合时为 true |
| `timeout_s` | 生效的执行超时秒数；未限制时为 `None` |
| `device_id` | 本次执行选择的设备 |
| `rows` | 字典形式的查询行（原始 SQLite 值，不含长说明） |
| `template` | 产生这些行的模板名 |
| `semantics_version` | 通过 `get_template_info()` 查阅的解释契约，未声明时为 `None` |

向 `execute_query()` 传入 `device_id` 可以仅覆盖本次调用的 analyzer 设备。否则依次使用
analyzer 设备；未设置显式 analyzer 数据库时，再使用已解析项目或全局 focus 的设备；
最后使用发现的第一个设备。只有显式 analyzer 数据库而没有 analyzer 设备时，不会继承
配置中的设备。`max_rows=None`、零或负数均表示不限制行数。传入
`exact_total=True` 可得到匹配行 `COUNT`。`timeout_s` 是一次
`execute_query()` 调用的墙钟预算（秒），也可由 `PT_SNAP_QUERY_TIMEOUT`
提供；页面查询与可选 COUNT 共用该预算。该环境变量作用于所有模板查询，
包括 `report peak-memory`。它不改变行数上限。
`active_memory_callstack_at_event` 应增大 `top_n` 扩大窗口，`max_rows`（CLI `-n`）
无法突破 CTE 上限。对于有限正整数 `top_n=N` 且 `include_static=True`，设置
`max_rows=N+2` 可在动态 top N 之外保留最多两个特殊组。这可避免外层二次截断，
但不保证内部排名完整。窗口已满本身不证明存在更多组；扩大窗口或使用
`exact_total=True` 可确认。新窗口替换旧窗口，不要累加。固定 `top_n` 时，
改变 `max_rows` 不改变共有行的百分比；改变 `top_n` 则可能改变分母。

查询行包含原始 SQLite 值，不会自动应用模板的 `output_schema` metadata。需要转换后的值
或模型映射时，使用可选的 [ResultMapper API](result-mapper-api.md)。

## 检查数据库概览

```python
overview = analyzer.get_database_overview()
print(overview["devices"])
print(overview["import_metadata"]["status"])
```

`get_database_overview()` 是 `pt-snap overview` 使用的只读概览：设备列表、各设备
首/末 event id，以及导入 metadata 状态。它不会持久化 focus，也不会写入数据库。
未配置 focus 时抛出 `RuntimeError`；文件不存在时抛出 `FileNotFoundError`；
SnapshotDB schema 无效或 `.pt-snap/focus.json` 损坏时抛出 `ValueError`。

## 检查导入 Metadata

```python
metadata = analyzer.get_database_metadata()

# 检查另一个数据库，但不改变当前 analyzer 的显式 focus。
other_metadata = analyzer.get_database_metadata("/path/to/other.db")
```

第一方导入会返回 `status="available"` 和 metadata 对象。没有 `pt_snap_metadata` 的兼容
旧版或外部数据库会返回 `status="unavailable"` 及原因。metadata 格式错误或 schema
版本不受支持时返回 `status="invalid"`。

## 错误与范围

同一个 analyzer 上并发调用 `active_memory_frame_tree_at_event` 时，只执行最新请求。
新请求会中断旧任务的 Python 计算和 SQLite 语句，排队中已过期的请求不会继续计算。
旧调用抛出 `pt_snap_cli.core.QueryCancelledError`（JSON 错误码为 `QUERY_CANCELLED`），
不会返回成功的部分树。关闭 analyzer 或清理其 context 缓存也会取消未结束的拆解任务。
每个任务在执行线程中关闭自己持有的数据库连接后，下一任务才开始计算。其它模板保留
原有并发约定；不同 analyzer/service 实例、不同 CLI 进程之间互不取消。这不会增加
持久化的拆解结果缓存。

- `set_focus()` 在数据库不存在时抛出 `FileNotFoundError`，在 SnapshotDB schema 无效时
  抛出 `ValueError`。设备校验使用共享的 `InvalidDeviceError`；没有任何可解析数据库时只
  设置设备会抛出 `RuntimeError`。
- `execute_query()` 在无法解析数据库时抛出 `RuntimeError`；其他查询、参数、设备和数据库
  错误遵循共享 service 层异常。
- `get_database_overview()` 在没有已解析数据库时抛出 `RuntimeError`，文件不存在时抛出
  `FileNotFoundError`，schema 无效或 `.pt-snap/focus.json` 损坏时抛出 `ValueError`。
- `get_database_metadata()` 在没有已解析数据库时抛出 `RuntimeError`，文件不存在时抛出
  `FileNotFoundError`，schema 无效时抛出 `ValueError`。
- `SnapshotAnalyzer` 不负责导入或拆分原始 pickle，也不生成 report。相关工作流应使用
  [快速开始](quickstart.md)、[拆分快照](splitting.md)和[运行查询](querying.md)中记录的
  CLI 命令。
