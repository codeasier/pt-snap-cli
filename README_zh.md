# pt-snap-cli

中文文档 | [English](README.md)

用于分析 PyTorch 内存快照的命令行工具。设置快照数据库，运行内置查询，检查内存使用、泄漏和时间线。

## 安装

```bash
pip install -e .
```

## 快速开始

```bash
# 设置快照数据库和设备
pt-snap focus examples/snapshot_expandable.pkl.db --device 0

# 列出可用查询
pt-snap query --list

# 运行查询（自动使用 focus 中设置的设备）
pt-snap query --template-use memory_peak

# 检测潜在内存泄漏
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

完整的入门指南见 [Quick Start](docs/zh/quickstart.md)。

## 命令

| 命令 | 说明 |
|------|------|
| `pt-snap focus` | 设置和管理分析焦点（数据库 + 设备） |
| `pt-snap query` | 运行内存分析查询 |
| `pt-snap config` | 管理全局配置 |
| `pt-snap-mcp` | 启动 MCP 服务器以支持 Agent 集成 |

## MCP 服务器

`pt-snap-cli` 提供了 MCP（Model Context Protocol）服务器，使 AI Agent 能够以编程方式与 PyTorch 内存快照交互。

```bash
# 启动 MCP 服务器
pt-snap-mcp
```

服务器暴露以下工具：

| 工具 | 说明 |
|------|------|
| `get_focus` | 获取当前分析焦点 |
| `set_focus` | 设置焦点到指定数据库和设备 |
| `list_templates` | 列出可用的查询模板 |
| `get_template_info` | 获取模板详情和参数 |
| `execute_query` | 对焦点数据库执行查询模板 |

详见 [MCP 指南](docs/zh/mcp.md)。

## 文档

| 主题 | 指南 |
|------|------|
| 入门指南 | [Quick Start](docs/zh/quickstart.md) |
| Focus 管理 | [Focus Management](docs/zh/focus-management.md) |
| 运行查询 | [Querying](docs/zh/querying.md) |
| MCP 服务器 | [MCP 指南](docs/zh/mcp.md) |
| 数据库格式 | [SnapshotDB Schema](docs/zh/database.md) |
| Python API | [ResultMapper API](docs/zh/result-mapper-api.md) |

## 查询模板

6 个内置模板，3 个分类：

- **Basic**: `block`, `event`, `allocation`
- **Statistical**: `callstack_analysis`, `memory_peak`
- **Business**: `leak_detection`

详见 [Querying](docs/zh/querying.md)。

## 项目结构

```
pt-snap-cli/
├── src/
│   └── pt_snap_cli/
│       ├── cli.py              # CLI 入口
│       ├── context.py          # 数据库连接管理器
│       ├── config.py           # 焦点管理
│       ├── api.py              # Python API 层
│       ├── query/
│       │   ├── builder.py      # 查询构建器
│       │   ├── executor.py     # 查询执行器
│       │   ├── mapper.py       # 结果映射器
│       │   ├── registry.py     # 查询注册表
│       │   ├── condition.py    # 查询条件
│       │   ├── config.py       # 查询配置
│       │   └── templates/      # 查询模板
│       ├── models/             # 数据模型
│       └── mcp/                # MCP 服务器（Agent 集成）
├── tests/                  # 测试文件
├── examples/               # 示例数据
└── docs/                   # 文档
```

## 开发

```bash
pytest                           # 运行所有测试
./tests/run_tests.sh             # 完整测试（含覆盖率）
black . && ruff check .          # 格式化和 lint
python -m build                  # 构建 sdist 和 wheel
```
