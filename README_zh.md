# pt-snap-cli

[![PyPI](https://img.shields.io/pypi/v/pt-snap-cli?logo=pypi&logoColor=FFE873&label=PyPI&color=3775A9)](https://pypi.org/project/pt-snap-cli/)
[![Python](https://img.shields.io/pypi/pyversions/pt-snap-cli?logo=python&logoColor=white)](https://pypi.org/project/pt-snap-cli/)
[![MIT License](https://img.shields.io/github/license/codeasier/pt-snap-cli)](LICENSE)
[![Tests](https://github.com/codeasier/pt-snap-cli/actions/workflows/test.yml/badge.svg)](https://github.com/codeasier/pt-snap-cli/actions/workflows/test.yml)

中文文档 | [English](README.md)

用于分析 PyTorch 内存快照的命令行工具。设置快照数据库，运行内置查询，检查内存使用、泄漏和时间线。

## 从这里开始

| 你的输入或目标 | 下一步 |
| --- | --- |
| 已有 `.db` 或完整数据集 | [检查 → 查询 → 报告](docs/zh/quickstart.md#第二步检查目标并选择设备)，无需导入 |
| 可信 pickle | [默认单库导入](docs/zh/quickstart.md#第一步仅在需要时导入) |
| 尚无快照 | [采集前提与入口](docs/zh/quickstart.md#尚需采集快照) |
| 让 Agent 帮忙分析 | [安装 → 重启 → 验证 → 提问](docs/zh/skills.md#首次-agent-会话) |

## 安装

需要 **Python 3.10+**。离线导入/分析无需 PyTorch 或加速器；采集则在工作负载对应的
兼容 GPU/NPU 环境中进行。

```bash
python -m pip install pt-snap-cli
```

源码 checkout 与贡献者安装见[开发](#开发)。

## 快速开始

已有 DB 就跳过导入；否则只使用**可信** pickle。反序列化可能执行任意代码，
`builtins` 限制不代表 `pt-snap import` 是沙箱。

```bash
pt-snap import snapshot.pkl
pt-snap overview snapshot.pkl.db --json
# 将 0 替换为 overview 实际返回的设备。
pt-snap query snapshot.pkl.db --device 0 --template-use memory_peak --json
pt-snap report peak-memory snapshot.pkl.db --device 0 --metric active --limit 20
```

默认导入在 pickle 旁写出 `snapshot.pkl.db`，并更新当前目录的项目
`.pt-snap/focus.json`；加 `--no-focus` 只避免 focus 变化，不防止 DB 替换：单库缓存
未命中或 `--force` 可能替换同名 DB，必要时选择其他 `--output-dir`。显式路径的检查/查询/报告
不持久化 focus，也不修改源数据。[完整示例](docs/zh/quickstart.md)解释字节单位、
allocated/active/reserved 指标、预期输出和报告不完整的情况。

### 其他输入格式

- [原生分库导入](docs/zh/quickstart.md#可选导入原生分库数据集)：用 `--events-per-slice` 显式启用，不是 msinsight 兼容格式。
- [显式 msinsight 导出](docs/zh/quickstart.md#可选导出-msinsight-兼容数据集)：独立的兼容合同与 no-replace 规则，`--force` 也不替换。
- [可回放 pickle 拆分](docs/zh/splitting.md)：只选一种拆分策略并使用新目录，与数据集导入不同。
- [完整数据集寻址](docs/zh/sharded-snapshotdb.md#完整数据集-focus-与寻址p1)、[全局内建支持](docs/zh/querying.md#数据集全局内建支持p3)和[已记录的互操作验收](docs/zh/interop-acceptance.md)：按需查看高级合同与证据，不是第一份报告的前置条件。

## 命令

| 命令 | 说明 |
|------|------|
| `pt-snap focus` | 设置和管理分析焦点（数据库 + 设备） |
| `pt-snap import <snapshot.pkl>` | 将 PyTorch 原始内存快照导入 SnapshotDB |
| `pt-snap split <snapshot.pkl>` | 创建可回放的逐设备快照切片 |
| `pt-snap metadata [database.db]` | 查看 SnapshotDB 的导入来源与兼容性 metadata |
| `pt-snap capabilities` | 列出 CLI 版本、查询模板契约和随包 skill |
| `pt-snap overview [database.db]` | 只读输出设备列表、各设备 event id 边界和导入 metadata 状态 |
| `pt-snap query` | 运行内存分析查询 |
| `pt-snap report` | 生成高层内存分析报告 |
| `pt-snap report memory-tree --event-id <id>` | 按帧分层拆解存活内存；`--format html` 输出交互式火焰图 |
| `pt-snap config` | 管理全局配置 |
| `pt-snap skill` | 列出并安装随包 agent skill |

`pt-snap --help` 含 Agent 提示：在支持该选项的命令上优先使用 `--json`，从 `pt-snap-helper` skill 开始，诊断前先用 `pt-snap capabilities --json` 和 `pt-snap overview --json`，并用 `pt-snap skill list --json` 检查是否已安装。`focus`、`import`、`split`、`query`、`config`、`capabilities`、`overview`、`metadata`、`report peak-memory` 和 `skill list/install/upgrade/uninstall` 均接受 `--json`。

峰值报告会返回归因完整性及同事件 active 字节覆盖率；分组百分比以筛选和排名后的
included bytes 为分母。解读有上限的分组结果前，请参阅
[报告指南](docs/zh/querying.md#report-命令)。

单库导入时保留结构化调用栈帧及原始顺序。用 `event_frames` 查看帧，或执行
`report memory-tree --event-id 100 --format html > memory-tree.html`
按调用路径查看事件时刻的占用。详见[调用栈帧内存拆解](docs/zh/querying.md#调用栈帧内存拆解)；
旧文本数据库需要从原始快照重新导入。
`report memory-tree` 同样支持 `--json`。HTML 支持全树搜索和可键盘操作的子节点列表，
极小占用及零字节帧也能进入查看。

数据集工作预算可通过 `--max-work-rows`、`--max-work-bytes`、
`--max-scratch-db-bytes`、环境变量或不可变 Python `QueryLimits` 配置。
默认仍为 100000 工作行 / 64 MiB 工作字节 / 512 MiB scratch 页；优先级、
深分页成本和整次失败语义见[公开数据集预算](docs/zh/querying.md#公开数据集预算)。

## Agent Skills

诊断长调用栈时，可在 `event` 或 `active_memory_callstack_at_event` 上显式设置
`stack_bytes`，或使用 `report peak-memory --stack-bytes 256`。
身份、字节预算元数据及完整文本检索方式见[紧凑调用栈文本](docs/zh/querying.md#紧凑调用栈文本)。

使用 `pt-snap skill install` 安装随包诊断工作流。Agent 集成入口是 skills 与 CLI，不再提供 MCP 服务器。详见 [Agent Skills 指南](docs/zh/skills.md)。

宿主已加载 `pt-snap-ascend-npu-collect` 时，没有 `pt-snap` 也能进行昇腾 NPU 采集；
helper 会先路由采集，无需先安装 CLI。分析仍需要 CLI 和 SnapshotDB，可信导入是独立决定。

## 文档

全部中英文指南见[文档索引](docs/README.md)。

| 主题 | 指南 |
|------|------|
| 入门指南 | [Quick Start](docs/zh/quickstart.md) |
| Focus 管理 | [Focus Management](docs/zh/focus-management.md) |
| 运行查询 | [Querying](docs/zh/querying.md) |
| 拆分快照 | [拆分快照](docs/zh/splitting.md) |
| Agent skill | [Agent Skills](docs/zh/skills.md) |
| 数据库格式 | [SnapshotDB Schema](docs/zh/database.md) |
| 分片协议、原生导入与兼容边界 | [分片 SnapshotDB 协议](docs/zh/sharded-snapshotdb.md) |
| Python API | [SnapshotAnalyzer API](docs/zh/snapshot-analyzer-api.md) |
| 结果映射工具 | [ResultMapper API](docs/zh/result-mapper-api.md) |

## 开发

统一使用根 [Development and Checks 检查清单](AGENTS.md#development-and-checks)：
fixture provenance、pytest、Ruff、Black、**basedpyright** 和 `git diff --check`，
并在同一入口查看环境隔离、浏览器测试与覆盖率门槛。

```bash
python -m pip install -e ".[dev]"
```


常规套件可用 `pytest -m 'not slow'`。默认容量规模及非 editable 安装包导出测试见
[数据集验收指南](docs/zh/dataset-acceptance.md)。

补充的平台工作流在 macOS 和 Windows 上运行 Python 3.13 非 slow 测试。
Windows 将完整的非 slow 集合确定性地划分为四个互不重叠的分片；macOS 使用一个任务。
五个任务均保持 20 分钟上限，最多同时运行两个。每个 Windows 分片在执行前验证
划分无遗漏、无重复，并随 JUnit 结果上传完整的收集及分片清单。不会为了满足时间上限
而跳过测试。本地复现一个 Windows 分片可运行
`python .github/scripts/run_platform_tests.py --shard 0`（可选 `--shard 0` 至 `--shard 3`）；
增加 `--collect-only` 可仅检查划分，不执行测试。

### 构建分发包

请从目标提交的全新 checkout 或新 worktree 构建，确保没有已有的 `build/` 和
`dist/` 目录。重复构建时，setuptools 可能复用 `build/lib` 中的文件，包括源码中
已删除的模块；构建依赖隔离不会清理这些中间产物。自行删除旧产物前请先检查其内容，
也可以直接使用全新 worktree。

在该 checkout 的根目录运行：

```bash
python -m build                  # 构建 sdist 和 wheel
python .github/scripts/audit_wheel.py --wheel dist/<built-wheel>.whl
```

将 `<built-wheel>` 替换为实际生成的文件名。只读审计会将 Python 模块的路径和字节内容
与 `src/` 比对，并按打包合同独立检查查询 YAML、内置技能、snapshot 许可证及来源记录
资源，允许构建后端生成的分发元数据。发现不匹配时会失败并列出具体路径；请从全新源码树
重新构建并再次审计，通过后再使用 wheel。CI 在安装包验收前审计 wheel；release 会独立
审计实际上传用于发布的 wheel。
