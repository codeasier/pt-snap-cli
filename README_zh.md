# pt-snap-cli

中文文档 | [English](README.md)

用于分析 PyTorch 内存快照的命令行工具。设置快照数据库，运行内置查询，检查内存使用、泄漏和时间线。

## 安装

```bash
pip install pt-snap-cli
```

源码 checkout 与贡献者安装见[开发](#开发)。

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

完整兼容 v1 分片产物可以目录或 `manifest.json` 为 focus，无需已归档 pickle。
只读 overview、事件路由、`--slice` 和跨片限制见
[完整数据集 focus 与寻址](docs/zh/sharded-snapshotdb.md#完整数据集-focus-与寻址p1)。

用 `pt-snap import snapshot.pkl --events-per-slice 50000 --output-dir captures --json`
显式生成**原生、非 msinsight 兼容**数据集 `captures/snapshot.pkl.pt-snap-native-v2/`。
默认单库导入不变；复用校验全部片及内容/选项/语义版本。不匹配的已识别目标须
`--force`，未知目标保留。发布/focus 失败会补偿，回滚自身失败则保留并报告恢复证据
（force 不是单次崩溃原子 swap）。详见
[原生分库导入](docs/zh/quickstart.md#可选导入原生分库数据集)。数据集 `event` 寻址及定点
`active_blocks_at_event` / `active_memory_callstack_at_event` 共用跨片 alloc/free 批量来源，
原版无扩展产物也适用。内建全局峰值、事件分页、canonical 栈统计、去重生命周期、
终片泄漏候选及 `report peak-memory` 共用有界 core 语义；数据集仍不支持自定义 SQL/override。
详见[全局支持矩阵](docs/zh/querying.md#数据集全局内建支持p3)及
[数据集定点归因与覆盖](docs/zh/querying.md#数据集定点事件归因)。
超过 SQLite 附加上限的生命周期查询使用私有、限制主库页数空间的临时派生数据库，源分片
保持只读；存储限额、清理及内存边界见全局支持矩阵。

显式 `pt-snap import snapshot.pkl --format msinsight --json` 生成
`snapshot.pkl.msinsight/`，对齐固定 msinsight 版本的**同一原始 pickle + 邻接缓存**入口。
内联栈比原生去重占更多空间；即使 `--force` 也不替换已有兼容目标，只复用完整校验且
身份相同的 pt-snap 缓存。GUI **待验收/未运行**，hash 相等不代表验收通过。详见
[兼容导出及限制](docs/zh/sharded-snapshotdb.md#显式-msinsight-兼容导出p2)。

[离线双向验收与有界性能](docs/zh/interop-acceptance.md) 提供固定版本两条链路、
确定性独立参考工具、真实三模式测量及明确**待验收/not-run 的 GUI 清单**。
诊断 skills 接受显式选择的完整已校验数据集，不接受任意目录。

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
`report memory-tree` 同样支持 `--json`。

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

```bash
pip install -e ".[dev]"         # 安装开发依赖
pytest                           # 运行所有测试
black --check . && ruff check .  # 检查格式和 lint
```

常规套件可用 `pytest -m 'not slow'`。默认容量规模及非 editable 安装包导出测试见
[数据集验收指南](docs/zh/dataset-acceptance.md)。

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
