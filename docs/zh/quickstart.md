# 快速开始

[English](../en/quickstart.md) | 中文

从已有输入得到一份可读的峰值内存报告。默认路径是单个 SnapshotDB，无需先选择分库格式。

## 安装

在希望使用 CLI 的环境中准备 **Python 3.10 或更新版本**：

```bash
python -m pip install pt-snap-cli
pt-snap --help
```

离线导入和分析不需要 PyTorch、TorchNPU、CUDA 或加速器硬件。采集则不同：它在运行
工作负载的、兼容的 PyTorch/CUDA 或 TorchNPU/Ascend 环境中进行。贡献者请使用独立的
[开发与完整检查入口](../../AGENTS.md#development-and-checks)。

## 准备输入

| 你已有的输入 | 最短下一步 |
| --- | --- |
| SnapshotDB `.db` | 跳过导入，在第二步直接使用其路径。 |
| 完整的原生或 compatibility-v1 数据集目录 / `manifest.json` | 跳过导入，在第二步显式指定该目标。保留全部成员，不能只拿一个 ready 分片。 |
| 可信的 `.pkl` / `.pickle` 快照 | 完成第一步，再分析生成的 DB。 |
| 尚无快照 | 先看下面的采集入口，随后单独决定是否进行可信导入。 |

### 尚需采集快照？

- **CUDA/PyTorch：** 在工作负载的 GPU 环境中，按
  [PyTorch 官方快照指南](https://docs.pytorch.org/docs/stable/torch_cuda_memory.html)
  记录分配器历史。核实已安装 PyTorch 版本的 API，选择有界记录窗口，在相关工作负载
  阶段结束后导出快照。安装离线 CLI 不会自动插桩或启动训练任务。
- **昇腾 NPU：** 使用 [pt-snap-ascend-npu-collect](../../skills/pt-snap-ascend-npu-collect/SKILL.md)
  检查 TorchNPU API/环境并选择框架对应的采集路径。明确采集 rank、step 窗口和输出位置。
  宿主已加载该 skill 时，无需先有 CLI 即可指导采集；参见 [Agent Skills](skills.md)。
- CSV、SVG 或截图不是 SnapshotDB。请获取数据库或原始可信 pickle，不要将可视化文件
  改名为 `.db`。

采集会改变工作负载的记录行为并写出 pickle，不是只读分析，应单独审阅采集计划。
把 pickle 复制到离线机器并不会使反序列化变得安全。

## 第一次分析

### 第一步：仅在需要时导入

> **安全警告：** 只能导入你信任的 pickle 快照。反序列化可能执行任意代码；实现会
> 拒绝非 `builtins` 全局对象，但 `pt-snap import` 不是沙箱。Agent 的 setup 或采集
> 授权不等于 pickle 导入授权。

```bash
pt-snap import snapshot.pkl
```

默认在**源 pickle 旁**生成 `snapshot.pkl.db`，并更新当前工作目录中的
`.pt-snap/focus.json`（项目 focus）。`--output-dir captures` 改变输出父目录，不改变
文件名。若希望创建或复用 DB，**但不修改 focus**：

```bash
pt-snap import snapshot.pkl --no-focus
```

**`--no-focus` 不等于 no-replace：** 单库缓存未命中或使用 `--force` 时，可能替换
已有同名 `.db`。请先确认该输出可被替换，或在导入前选择另一个 `--output-dir`。

下面的分析示例均显式传入路径和设备，两种导入选择都可使用。将 `snapshot.pkl.db`
换成实际 DB 或完整数据集路径。导入是写操作；`overview`、内建查询和报告不修改源数据，
也不持久化 focus。数据集查询可能在[工作限额](querying.md#公开数据集预算)内使用私有临时
scratch 存储。

### 第二步：检查目标并选择设备

```bash
pt-snap overview snapshot.pkl.db --json
```

检查 `db_path`，从 `devices` 中选择 `device_id`。下文以 `0` 为例，请替换为实际返回的
设备。数据集还需检查 `dataset.status`、format 和 fingerprint。目标无效或
`import_metadata.status: "invalid"` 时停止；旧数据的 `"unavailable"` 且 reason 为
`"metadata_missing"` 表示导入来源未知，不等于已确认损坏。其他未知状态/原因应先调查，
再进行诊断。

### 第三步：读取计数器

```bash
pt-snap query snapshot.pkl.db --device 0 --template-use memory_peak --json
```

以下是**示意**的 `rows[0]`，不是对你的快照输出的承诺：

```json
{
  "peak_allocated": 8388608,
  "peak_allocated_event_id": 10,
  "peak_active": 10485760,
  "peak_active_event_id": 12,
  "peak_reserved": 16777216,
  "peak_reserved_event_id": 10
}
```

三个大小均以**字节（bytes）**为单位，此例分别为 8、10、16 MiB
（`1 MiB = 1048576 bytes`）。

| 计数器 | 分配器回放历史中的含义 |
| --- | --- |
| `allocated` | 已分配 block 的字节数，不含已标为 pending free 的 block；是 block 大小，不是请求的 tensor payload 大小。 |
| `active` | 已分配与 pending-free、尚不可复用的 block 字节数之和。 |
| `reserved` | 分配器持有的 segment 总字节数，包含 inactive 容量；不是整个进程/设备的全部内存。 |

各指标独立选取最早达到峰值的事件，event ID 表示顺序而非时间戳。不能把不同事件的峰值
直接相减当作同一时刻的差值。真实事件范围为空时峰值为 null，不得虚构事件。
reserved/active 差值大，本身不能证明碎片、泄漏或 OOM 原因。

### 第四步：生成可读报告

```bash
pt-snap report peak-memory snapshot.pkl.db --device 0 --metric active --limit 20
```

输出包含 **Peak memory report**、选定的设备/指标/事件、各项独立峰值、同事件分配器
差值和 **Active memory by callstack**。报告解释所选峰值事件的 active blocks，
不是分解全部 reserved 字节。下结论前检查归因完整性标签和 active 字节覆盖率：
分组百分比以过滤/排名后 `included_bytes` 为分母，并非全部 active 内存。
有上限的报告可能不完整；预算错误不等于部分分析成功。自动化可加 `--json`。
限额与分母详见[报告合同](querying.md#report-命令)。

### 可选：记住此目标

```bash
pt-snap focus snapshot.pkl.db --device 0
pt-snap report peak-memory
```

与上面的显式路径分析不同，`focus <path>` 会写项目 focus。不想改变共享项目状态就跳过。
默认导入可能已经选择了 DB；此命令还会选择你指定的设备。参见
[focus 优先级与会话隔离](focus-management.md)。

## 高级输入选项

这些都是可选项，不是第一份报告的前置条件。

### 可选：导入原生分库数据集

`--events-per-slice` 显式启用原生数据集，但不会让 pickle 加载变为流式，也不限制峰值
RSS。输出路径、完整成员校验、force/恢复行为及支持的内建查询见
[原生导入合同](sharded-snapshotdb.md#已发布原生数据集p2)和
[全局支持矩阵](querying.md#数据集全局内建支持p3)。原生产物不是 msinsight 兼容格式。

### 可选：导出 msinsight 兼容数据集

`--format msinsight` 是显式选择。已有兼容目标即使 `--force` 也不替换；兼容性、
缓存校验、GUI 入口及固定版本证据有独立的
[协议合同](sharded-snapshotdb.md#显式-msinsight-兼容导出p2)。声称 GUI 复用前请阅读
[已记录的互操作验收](interop-acceptance.md)，仅 hash 相同不等于 GUI 验收通过。

### 可选：拆分快照

`pt-snap split` 生成可独立回放的文件，不是待查询数据集。它同样需要可信 pickle，
只选一种拆分策略，并使用尚不存在的输出目录；不会改变 focus。参见[拆分快照](splitting.md)。

### 复用、重建与内存成本

单库导入保存源 SHA-256 和兼容性 metadata，相同内容/选项可复用 DB；缓存未命中
（包括缺失/无效 metadata）和 `--force` 都会重建，并可能替换同名 DB。它与原生/兼容
目录的策略不同，并没有未知目标保护门禁。请先确认输出所有权或选择其他 `--output-dir`。
不要仅因分析失败就强制重建，应先检查错误。
导入会在回放前完整加载 pickle；`--device` 减少后续工作，不降低最初的加载峰值。
请预留足够内存。snapshot 运行时模块不是公开 API。

## 下一步

- [Agent Skills](skills.md) — 安装、重启、验证并发起诊断
- [查询指南](querying.md) — 模板、有界结果、栈详情与报告
- [Focus 管理](focus-management.md) — 可选的持久化/会话目标
- [数据库格式](database.md) — 计数器、metadata 与哨兵含义
- [SnapshotAnalyzer API](snapshot-analyzer-api.md) — 明确资源生命周期的 Python 分析
