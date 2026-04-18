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

### Business Queries

领域特定分析。

| 模板 | 说明 |
|------|------|
| `leak_detection` | 查找未匹配释放事件的分配 |

**示例：**
```bash
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

参数：
- `min_size`: 最小泄漏大小（字节），默认 0
- `device_id`: 设备 ID

## 输出格式

结果以列表形式展示：
- 显示前 10 条结果
- 超过 10 条时，显示剩余数量

```
Found 150 results:
  {'id': 1, 'address': '0x1000', 'size': 2048, ...}
  ...
  ... and 140 more
```

## 模板架构

查询模板使用 YAML 格式定义，包含：
- `version`: 模板版本
- `queries`: 查询定义，包含描述、支持的设备、参数、SQL（Jinja2 模板语法）和输出 schema

**支持的类型转换器：** `int`、`float`、`str`、`bool`、`hex`、`datetime`

## Python API

编程式使用方式见 [ResultMapper API](result-mapper-api.md)。
