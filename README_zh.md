# pt-snap-cli

中文文档 | [English](README.md)

PyTorch Memory Snapshot Analysis CLI - 用于分析 PyTorch 内存快照的命令行工具。

## 安装

```bash
pip install -e .
```

## 使用方法

### pt-snap CLI 使用

#### 1. 查看版本

```bash
pt-snap --version
```

#### 2. 设置数据库

使用 snapshot 数据库文件：

```bash
pt-snap use <path/to/snapshot.pkl.db>
```

示例：
```bash
pt-snap use examples/snapshot_large.pickle.db
```

该命令会验证数据库并显示可用的设备列表。

### Context 管理

`pt-snap` 支持项目级上下文，避免不同终端、Agent 或工作目录分析不同数据库时互相覆盖。

#### 设置项目数据库

```bash
# 为当前项目目录设置并验证数据库
pt-snap use /path/to/your/snapshot.db
```

设置成功后，数据库路径会保存到当前目录的 `.pt-snap/context.json`。

#### Session 级覆盖

当某个 shell 或 Agent 需要独立数据库，且不想修改项目 context 时，使用 `PT_SNAP_DB_PATH`：

```bash
export PT_SNAP_DB_PATH=/path/to/agent-specific/snapshot.db
pt-snap query --template-use memory_summary
```

也可以先验证数据库并输出 export 命令：

```bash
pt-snap use /path/to/agent-specific/snapshot.db --session
```

#### 查看当前生效 Context

```bash
# 查看当前生效数据库及来源
pt-snap use
```

#### 使用 Context 进行查询（无需指定 dbpath）

```bash
# 列出所有查询模板
pt-snap query --list

# 执行查询（自动使用解析出的数据库 context）
pt-snap query --template-use memory_summary

# 带参数查询
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'

# 指定设备
pt-snap query --template-use active_blocks --device 0
```

#### 解析优先级

数据库 context 按以下顺序解析：

1. 显式 `pt-snap query <db_path>`
2. `PT_SNAP_DB_PATH`
3. 从当前目录向上查找最近的 `.pt-snap/context.json`
4. legacy 全局配置 `~/.config/pt-snap-cli/config.json`

即使已经配置 context，仍然可以在命令行中指定不同的数据库：

```bash
# 使用临时指定的数据库（不影响 context）
pt-snap query /path/to/other.db --template-use memory_summary
```

#### Legacy 全局配置

全局配置会保留用于兼容旧版本和个人默认值；并发 Agent 场景推荐使用项目 context 或 `PT_SNAP_DB_PATH`。

```bash
# 写入 ~/.config/pt-snap-cli/config.json
pt-snap use /path/to/your/snapshot.db --global
```

#### 管理 Legacy 全局配置

```bash
# 查看全局配置
pt-snap config

# 查看全局配置文件路径
pt-snap config --path

# 清除全局配置
pt-snap config --clear
```

#### Context 文件位置

项目 context 保存在：`.pt-snap/context.json`

legacy 全局配置保存在：`~/.config/pt-snap-cli/config.json`

context 内容示例：
```json
{
  "current_db_path": "/path/to/your/snapshot.db"
}
```

#### 错误处理

**未配置数据库时查询：**

```bash
pt-snap query --template-use memory_summary
# Error: No database path specified and no database configured.
# Use 'pt-snap use <database_path>' to set a project database, or provide db_path argument.
```

**配置的数据库文件不存在：**

如果解析出的数据库文件被删除或移动，`pt-snap` 会报告 context 来源，并保留 context 文件不做隐式清理：

```bash
pt-snap query --template-use memory_summary
# Error: Database from project context not found: /path/to/missing.db
# Use 'pt-snap use <new_database_path>' to set a new project database, or provide db_path argument.
```

#### 完整工作流程示例

```bash
# 1. 初次使用，设置项目数据库
pt-snap use examples/snapshot_expandable.pkl.db

# 2. 之后可以直接查询，无需重复指定路径
pt-snap query --template-use memory_summary
pt-snap query --template-use active_blocks --device 0
pt-snap query --template-use leak_detection

# 3. 查看当前生效 context 及来源
pt-snap use

# 4. 如果当前 shell 或 Agent 需要另一个数据库
export PT_SNAP_DB_PATH=/path/to/agent_snapshot.db

# 5. 如果项目要切换到其他数据库
pt-snap use /path/to/new_snapshot.db

# 6. 仅清除 legacy 全局配置
pt-snap config --clear
```

#### 优势

1. **提高效率**：无需每次查询都输入完整的数据库路径
2. **减少错误**：避免因路径输入错误导致的查询失败
3. **并发 Agent 安全**：项目 context 与 `PT_SNAP_DB_PATH` 避免跨进程全局状态冲突
4. **灵活覆盖**：显式 db path 和 session 环境变量仍可覆盖项目默认值
5. **Context 透明**：`pt-snap use` 会显示当前生效数据库及来源

### 执行查询

使用 `query` 命令执行内存分析查询：

```bash
pt-snap query [--template-use <template_name>] [--params <json>] [--device <id>] [--list] [--template-info <template>]
```

**参数说明：**
- `db_path`: SQLite 数据库文件路径（可选，已配置时不需要）
- `--template-use`: 查询模板名称（必需，除非使用 --list 或 --template-info）
- `--params`: JSON 格式的查询参数（可选）
- `--device`: 设备 ID（可选）
- `--list`: 列出可用的查询模板（按分类分组）
- `--category`: 使用 --list 时按分类过滤（`basic`、`statistical`、`business`）
- `--template-info <template>`: 显示指定模板的详细信息（参数和输出 schema）

**示例：**

列出所有可用的查询模板：
```bash
pt-snap query --list
```

使用模板查询（泄漏检测）：
```bash
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

指定设备查询：
```bash
pt-snap query --template-use active_blocks --device 0
```

查看模板详细信息：
```bash
pt-snap query --template-info leak_detection
```

### Query 功能使用

Query 模块提供了强大的内存快照查询功能，支持模板化查询和参数化配置。

#### 可用的查询模板

模板按功能分为三类。使用 `pt-snap query --list` 查看分组列表，或使用 `pt-snap query --list --category <basic|statistical|business>` 按分类过滤。

**Basic Queries** — 原始数据查询：

1. **active_blocks** - 活跃内存块
2. **blocks_by_size** - 按大小排序的块
3. **events_by_action** - 按动作分类的事件
4. **memory_timeline** - 内存时间线

**Statistical Queries** — 聚合分析：

5. **callstack_analysis** - 调用栈分析
6. **memory_summary** - 内存摘要

**Business Queries** — 业务分析：

7. **leak_detection** - 内存泄漏检测

   ```bash
   pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
   ```

   参数：
   - `min_size`: 最小泄漏大小（字节），默认 0
   - `device_id`: 设备 ID

#### 查询输出

查询结果会以列表形式显示：
- 显示前 10 条结果
- 如果结果超过 10 条，会显示剩余数量

示例输出：
```
Found 150 results:
  {'id': 1, 'address': '0x1000', 'size': 2048, ...}
  {'id': 2, 'address': '0x2000', 'size': 4096, ...}
  ...
  ... and 140 more
```

#### 高级用法

**使用 ResultMapper 自定义结果映射：**

```python
from pt_snap_cli.query.mapper import ResultMapper, map_result, map_results

# 创建映射器
mapper = ResultMapper()

# 注册自定义类型转换器
mapper.register_type_converter("custom", lambda x: f"custom_{x}")

# 注册模型工厂
mapper.register_model_factory("MyModel", lambda d: MyModel(d))

# 映射单行结果
row = {"id": "1", "size": "1024"}
schema = [
    {"column": "id", "type": "int"},
    {"column": "size", "type": "int"},
]
result = mapper.map(row, schema)

# 映射所有结果
results = mapper.map_all(rows, schema)

# 映射到模型对象
model = mapper.map_to_model(row, "MyModel")
models = mapper.map_all_to_model(rows, "MyModel")
```

**使用便捷函数：**

```python
from pt_snap_cli.query.mapper import map_result, map_results

# 映射单个结果
mapped = map_result(row, schema)

# 映射多个结果
mapped_all = map_results(rows, schema)
```

#### Query 架构

查询模板使用 YAML 格式定义，包含：
- `version`: 模板版本
- `queries`: 查询定义
  - `description`: 查询描述
  - `devices`: 支持的设备列表
  - `parameters`: 参数定义（类型、默认值、是否必需）
  - `query`: SQL 查询语句（支持 Jinja2 模板语法）
  - `output_schema`: 输出 schema 定义（列名和类型）

支持的类型转换器：
- `int`: 整数
- `float`: 浮点数
- `str`: 字符串
- `bool`: 布尔值
- `hex`: 十六进制（整数转 hex 字符串）
- `datetime`: 日期时间

## 项目结构

```
pt-snap-cli/
├── pt_snap_cli/
│   ├── cli.py              # CLI 入口
│   ├── context.py          # 上下文管理
│   ├── query/
│   │   ├── builder.py      # 查询构建器
│   │   ├── executor.py     # 查询执行器
│   │   ├── mapper.py       # 结果映射器
│   │   ├── registry.py     # 查询注册表
│   │   ├── condition.py    # 查询条件
│   │   ├── config.py       # 查询配置
│   │   └── templates/      # 查询模板
│   └── models/             # 数据模型
├── tests/                  # 测试文件
├── examples/               # 示例数据
└── docs/                   # 文档
```

## 开发

运行测试：
```bash
pytest
```

## 版本

当前版本：参见 [pyproject.toml](pyproject.toml)
