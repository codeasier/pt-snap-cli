# pt-snap-cli

中文文档 | [English](README.md)

用于分析 PyTorch 内存快照的命令行工具。设置快照数据库，运行内置查询，检查内存使用、泄漏和时间线。

## 安装

从源码 checkout 安装：

```bash
pip install -e .
```

## 快速开始

> **安全警告：** 只导入来自可信来源的 pickle 快照。反序列化 pickle 可能执行任意代码；
> 实现会拒绝非 builtins 全局对象，但 `pt-snap import` 不是沙箱。

```bash
# 从原始 pickle 导入；相同内容和配置会自动复用已有 DB
pt-snap import snapshot.pkl
pt-snap metadata snapshot.pkl.db

# 设置快照数据库和设备
pt-snap focus snapshot.pkl.db --device 0

# 列出可用查询
pt-snap query --list

# 运行查询（自动使用 focus 中设置的设备）
pt-snap query --template-use memory_peak

# 检测潜在内存泄漏
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

如需先把大型快照拆成可独立回放的文件，请只选择一种拆分策略，并指定一个尚不存在的
输出目录：

```bash
pt-snap split snapshot.pkl --slices 4 --output snapshot-slices
```

设备选择、JSON 输出、确定性命名、回放验证和失败安全发布见
[拆分快照](docs/zh/splitting.md)。

完整的入门指南见 [Quick Start](docs/zh/quickstart.md)。

## 命令

| 命令 | 说明 |
|------|------|
| `pt-snap focus` | 设置和管理分析焦点（数据库 + 设备） |
| `pt-snap import <snapshot.pkl>` | 将 PyTorch 原始内存快照导入 SnapshotDB |
| `pt-snap split <snapshot.pkl>` | 创建可回放的逐设备快照切片 |
| `pt-snap metadata [database.db]` | 查看 SnapshotDB 的导入来源与兼容性 metadata |
| `pt-snap query` | 运行内存分析查询 |
| `pt-snap report` | 生成高层内存分析报告 |
| `pt-snap config` | 管理全局配置 |
| `pt-snap-mcp` | 启动 MCP 服务器以支持 Agent 集成 |

## MCP 服务器

`pt-snap-cli` 提供了 MCP（Model Context Protocol）服务器，使 AI Agent 能够以编程方式与 PyTorch 内存快照交互。

```bash
# 启动 MCP 服务器
pt-snap-mcp
```

详见 [MCP 指南](docs/zh/mcp.md)。

## 文档

全部中英文指南见[文档索引](docs/README.md)。

| 主题 | 指南 |
|------|------|
| 入门指南 | [Quick Start](docs/zh/quickstart.md) |
| Focus 管理 | [Focus Management](docs/zh/focus-management.md) |
| 运行查询 | [Querying](docs/zh/querying.md) |
| 拆分快照 | [拆分快照](docs/zh/splitting.md) |
| MCP 服务器 | [MCP 指南](docs/zh/mcp.md) |
| 数据库格式 | [SnapshotDB Schema](docs/zh/database.md) |
| Python API | [SnapshotAnalyzer API](docs/zh/snapshot-analyzer-api.md) |
| 结果映射工具 | [ResultMapper API](docs/zh/result-mapper-api.md) |

## 开发

```bash
pip install -e ".[dev]"         # 安装开发依赖
pytest                           # 运行所有测试
black --check . && ruff check .  # 检查格式和 lint
python -m build                  # 构建 sdist 和 wheel
```
