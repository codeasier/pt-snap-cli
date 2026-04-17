# pt-snap-cli

中文文档 | [English](README.md)

用于分析 PyTorch 内存快照的命令行工具。设置快照数据库，运行内置查询，检查内存使用、泄漏和时间线。

## 安装

```bash
pip install -e .
```

## 快速开始

```bash
# 设置快照数据库（保存上下文供后续查询使用）
pt-snap use examples/snapshot_expandable.pkl.db

# 列出可用查询
pt-snap query --list

# 运行查询
pt-snap query --template-use memory_summary

# 检测潜在内存泄漏
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

完整的入门指南见 [Quick Start](docs/zh/quickstart.md)。

## 命令

| 命令 | 说明 |
|------|------|
| `pt-snap use` | 设置和管理快照数据库上下文 |
| `pt-snap query` | 运行内存分析查询 |
| `pt-snap config` | 管理全局配置 |

## 文档

| 主题 | 指南 |
|------|------|
| 入门指南 | [Quick Start](docs/zh/quickstart.md) |
| Context 管理 | [Context Management](docs/zh/context-management.md) |
| 运行查询 | [Querying](docs/zh/querying.md) |
| 数据库格式 | [SnapshotDB Schema](docs/zh/database.md) |
| Python API | [ResultMapper API](docs/zh/result-mapper-api.md) |

## 查询模板

7 个内置模板，3 个分类：

- **Basic**: `active_blocks`, `blocks_by_size`, `events_by_action`, `memory_timeline`
- **Statistical**: `callstack_analysis`, `memory_summary`
- **Business**: `leak_detection`

详见 [Querying](docs/zh/querying.md)。

## 项目结构

```
pt-snap-cli/
├── src/
│   └── pt_snap_cli/
│       ├── cli.py              # CLI 入口
│       ├── context.py          # 上下文管理
│       ├── query/
│       │   ├── builder.py      # 查询构建器
│       │   ├── executor.py     # 查询执行器
│       │   ├── mapper.py       # 结果映射器
│       │   ├── registry.py     # 查询注册表
│       │   ├── condition.py    # 查询条件
│       │   ├── config.py       # 查询配置
│       │   └── templates/      # 查询模板
│       └── models/             # 数据模型
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
