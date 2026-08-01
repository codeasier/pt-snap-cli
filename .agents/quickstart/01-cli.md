# CLI 模块

## 职责

提供 `pt-snap` 命令行工具，支持数据库设置、查询执行等核心功能。

## 核心组件

### `app` (Typer)
Typer 应用实例，管理所有 CLI 命令。

### `focus_database()`
设置当前分析的数据库文件，验证有效性并显示可用设备。

### `query_database()`
执行查询命令，支持：
- `--template-use`: 指定查询模板
- `--params`: JSON 格式参数
- `--device`: 指定设备 ID
- `--list`: 列出可用模板

### `version_callback()`
版本信息回调函数。

## 依赖关系

- **依赖**：`Context` (context.py) - 数据库上下文
- **依赖**：`QueryExecutor` (query/executor.py) - 查询执行
- **依赖**：`typer` - CLI 框架

## 使用示例

```python
from pt_snap_cli.cli import app

# 运行 CLI
app()
```

```bash
# 查看版本
pt-snap --version

# 设置数据库
pt-snap focus examples/snapshot.pkl.db

# 执行查询
pt-snap query snapshot.pkl.db --template-use leak_detection --params '{"min_size": 1024}'

# 列出模板
pt-snap query snapshot.pkl.db --list
```

## 相关文件

- [cli.py](../../src/pt_snap_cli/cli.py) - 完整实现
- [context.py](../../src/pt_snap_cli/context.py) - 数据库上下文
- [query/executor.py](../../src/pt_snap_cli/query/executor.py) - 查询执行器
