# SnapshotAnalyzer API

[English](../en/snapshot-analyzer-api.md) | 中文

`SnapshotAnalyzer` 是用于查看 focus、发现模板、执行查询和检查 SnapshotDB 导入
metadata 的高层 Python 门面。应从 `pt_snap_cli.api` 导入；包根目录不会重新导出它。

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
| `has_more` | 还有后续页时为 true（有行数上限时多取一行判断） |
| `truncated` | 本次响应不是完整匹配集合时为 true |
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
`exact_total=True` 可得到匹配行 `COUNT`。`timeout_s` 是墙钟执行超时（秒），
也可由 `PT_SNAP_QUERY_TIMEOUT` 提供；它不改变行数上限。

查询行包含原始 SQLite 值，不会自动应用模板的 `output_schema` metadata。需要转换后的值
或模型映射时，使用可选的 [ResultMapper API](result-mapper-api.md)。

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

- `set_focus()` 在数据库不存在时抛出 `FileNotFoundError`，在 SnapshotDB schema 无效时
  抛出 `ValueError`。设备校验使用共享的 `InvalidDeviceError`；没有任何可解析数据库时只
  设置设备会抛出 `RuntimeError`。
- `execute_query()` 在无法解析数据库时抛出 `RuntimeError`；其他查询、参数、设备和数据库
  错误遵循共享 service 层异常。
- `get_database_metadata()` 在没有已解析数据库时抛出 `RuntimeError`，文件不存在时抛出
  `FileNotFoundError`，schema 无效时抛出 `ValueError`。
- `SnapshotAnalyzer` 不负责导入或拆分原始 pickle，也不生成 report。相关工作流应使用
  [快速开始](quickstart.md)、[拆分快照](splitting.md)和[运行查询](querying.md)中记录的
  CLI 命令。
