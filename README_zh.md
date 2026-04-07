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

### 配置管理

`pt-snap` 支持保存上下文状态，避免在分析时每次都指定数据库路径。

#### 设置当前数据库

```bash
# 设置并验证数据库
pt-snap use /path/to/your/snapshot.db
```

设置成功后，数据库路径会自动保存到 `~/.config/pt-snap-cli/config.json`。

#### 查看当前配置

```bash
# 查看当前数据库
pt-snap use
```

#### 使用配置进行查询（无需指定 dbpath）

```bash
# 列出所有查询模板
pt-snap query --list

# 执行查询（自动使用配置的数据库）
pt-snap query --template-use memory_summary_v2

# 带参数查询
pt-snap query --template-use leak_detection_v2 --params '{"min_size": 1024}'

# 指定设备
pt-snap query --template-use active_blocks_v2 --device 0
```

#### 覆盖配置的数据库

即使配置了数据库，仍然可以在命令行中指定不同的数据库：

```bash
# 使用临时指定的数据库（不影响配置）
pt-snap query /path/to/other.db --template-use memory_summary_v2
```

#### 管理配置

```bash
# 查看完整配置
pt-snap config

# 查看配置文件路径
pt-snap config --path

# 清除所有配置
pt-snap config --clear
```

#### 配置文件位置

配置文件保存在：`~/.config/pt-snap-cli/config.json`

配置内容示例：
```json
{
  "current_db_path": "/path/to/your/snapshot.db"
}
```

#### 错误处理

**未配置数据库时查询：**

```bash
pt-snap query --template-use memory_summary_v2
# Error: No database path specified and no database configured.
# Use 'pt-snap use <database_path>' to set a database, or provide db_path argument.
```

**配置的数据库文件不存在：**

如果配置的数据库文件被删除或移动，系统会自动清除配置并提示：

```bash
pt-snap query --template-use memory_summary_v2
# Error: Configured database not found: /path/to/missing.db
# Use 'pt-snap use <new_database_path>' to set a new database.
```

#### 完整工作流程示例

```bash
# 1. 初次使用，设置数据库
pt-snap use examples/snapshot_expandable.pkl.db

# 2. 之后可以直接查询，无需重复指定路径
pt-snap query --template-use memory_summary_v2
pt-snap query --template-use active_blocks_v2 --device 0
pt-snap query --template-use leak_detection_v2

# 3. 查看当前配置
pt-snap config

# 4. 如果需要切换到其他数据库
pt-snap use /path/to/new_snapshot.db

# 5. 清除配置
pt-snap config --clear
```

#### 优势

1. **提高效率**：无需每次查询都输入完整的数据库路径
2. **减少错误**：避免因路径输入错误导致的查询失败
3. **灵活覆盖**：仍然支持在需要时指定不同的数据库路径
4. **自动清理**：当配置的数据库文件不存在时自动清除配置
5. **配置透明**：可以轻松查看和管理配置

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
- `--list`: 列出可用的查询模板
- `--template-info <template>`: 显示指定模板的详细信息（参数和输出 schema）

**示例：**

列出所有可用的查询模板：
```bash
pt-snap query --list
```

使用模板查询（泄漏检测）：
```bash
pt-snap query --template-use leak_detection_v2 --params '{"min_size": 1024}'
```

指定设备查询：
```bash
pt-snap query --template-use active_blocks_v2 --device 0
```

查看模板详细信息：
```bash
pt-snap query --template-info leak_detection_v2
```

### Query 功能使用

Query 模块提供了强大的内存快照查询功能，支持模板化查询和参数化配置。

#### 可用的查询模板

1. **leak_detection_v2** - 内存泄漏检测
   
   检测没有释放事件的内存分配。
   
   ```bash
   pt-snap query --template-use leak_detection_v2 --params '{"min_size": 1024}'
   ```
   
   参数：
   - `min_size`: 最小泄漏大小（字节），默认 1024
   - `device_id`: 设备 ID

2. **callstack_analysis_v2** - 调用栈分析
   
   分析内存分配的调用栈信息。
   
   ```bash
   pt-snap query --template-use callstack_analysis_v2
   ```

3. **memory_timeline_v2** - 内存时间线
   
   展示内存分配的时间线信息。
   
   ```bash
   pt-snap query --template-use memory_timeline_v2
   ```

4. **active_blocks_v2** - 活跃内存块
   
   查看当前活跃的内存块。
   
   ```bash
   pt-snap query --template-use active_blocks_v2
   ```

5. **memory_summary_v2** - 内存摘要
   
   显示内存使用统计摘要。
   
   ```bash
   pt-snap query --template-use memory_summary_v2
   ```

6. **blocks_by_size_v2** - 按大小排序的块
   
   按分配大小排序显示内存块。
   
   ```bash
   pt-snap query --template-use blocks_by_size_v2
   ```

7. **events_by_action_v2** - 按动作分类的事件
   
   按动作类型分组显示事件。
   
   ```bash
   pt-snap query --template-use events_by_action_v2
   ```

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
