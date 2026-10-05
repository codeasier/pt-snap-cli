# 分片 SnapshotDB 协议（P0，兼容 v1）

中文 | [English](../en/sharded-snapshotdb.md)

## 范围与版本

本阶段冻结产物协议和共享校验模型，**不新增 CLI 导出器或跨片查询引擎**。现有
`import` 默认仍生成一个原生 v2 DB；`split` 仍输出可回放 pickle/JSON。现有单库
v1/v2 单库分析不变。下述 P1 reader 新增将 complete 兼容 v1 manifest 或目录作为
focus；`complete` 门槛只约束数据集，不约束旧单库分析。

`pt_snap_cli.core.dataset_contract` 提供 `parse_manifest`、`validate_event_ids`、
`validate_dataset`、不可变 manifest/device/slice 模型、`QueryScope` 和带
`location/code` 的 `DatasetContractError`。生产端可在发布前与读取端共用同一合同。
校验不加载 pickle、不创建缺失数据库、不迁移 SQLite、不写 focus。

版本轴分别管理：

- `schemaVersion=1`：本文的 manifest 和兼容基础表协议。
- `pt_snap_metadata.import_format_version`：已有 pt-snap 导入格式，当前为 2；
  **不是** manifest 版本，外部产物不要求该表。
- 后续结构化 frame 扩展独立版本化。未知扩展不影响基础读取，也不意味着支持结构化 frames。

## 目录与 manifest

生产端布局为 `<原始 snapshot 路径>.msinsight/manifest.json`，分片相对于该目录放在
`device_<id>/slice_<index:05d>.db`。允许显式指定已搬迁的产物目录进行校验；
`sourceFile` 记录来源，不是要打开的路径。检查时不得加载源 pickle。

```json
{
  "schemaVersion": 1,
  "status": "complete",
  "sourceFile": "/capture/snapshot.pkl",
  "cacheHash": "producer-specific-opaque-identity",
  "eventsPerSlice": 2,
  "devices": {
    "0": {
      "eventCount": 4,
      "sliceCount": 2,
      "readySlices": [0, 1],
      "slices": [
        {"index": 0, "startEventId": 0, "endEventId": 1, "file": "device_0/slice_00000.db", "ready": true},
        {"index": 1, "startEventId": 2, "endEventId": 3, "file": "device_0/slice_00001.db", "ready": true}
      ]
    }
  }
}
```

示例中所有字段必需。整数不能是布尔或浮点数；计数/区间使用有符号 64 位整数，
版本/index/sliceCount/device ID 使用非负有符号 32 位整数。设备 key 为规范十进制
ID（`0` 而非 `00`）。`sourceFile` 非空。`cacheHash` 是生产端不透明 token，
外部产物可为空：**不能**假定它是 SHA-256 或源内容证据。未来缓存需要区分源内容、
生产端/格式、基础/扩展版本、所选设备、容量和最终化 generation；单独的源路径、
size/mtime、`cacheHash` 或单片 index 都不足以复用。本 P0 模块不执行缓存复用。

`building` 只允许用 `parse_manifest(..., require_complete=False)` 检查部分就绪状态，
仍须声明完整计划区间。`complete` 必须在**身份/生命周期回填结束后**使所有片就绪。
就绪 index 不重复、不越界，并与各片布尔值一致。`validate_dataset` 只接受所有文件
齐全的 complete 数据集；不会创建缺片。重复 JSON 成员被拒绝。

各设备分片从 index 0 顺序排列；闭区间无重叠/缺口地连续覆盖 `0..eventCount-1`。
每片最多 `eventsPerSlice` 个真实事件（允许中间片较短）。按真实事件位置计数，不能
用 `max(id)+1` 推算。兼容 v1 **拒绝非零起点、稀疏、乱序或重复的原始真实 ID**，
不得静默改号。空设备和仅有静态 block 的设备无法表示：请求此类设备时明确拒绝，
不得虚构 event 0；全部为空的数据集被拒绝。可明确选择其他设备，但生产端必须披露省略。

路径须严格对应声明的 device/index 相对路径；拒绝绝对/盘符/UNC 路径、`..`、`.`、
空分量、反斜线、NUL、设备错配、别名及成员/父目录符号链接。校验以 `mode=ro`
打开 SQLite，包括失败路径都关闭资源。这不是 OS 沙箱，也不锁住并发发布。

## 固定基础 SQLite schema

每片须有本设备的**实际表**，不能用兼容 VIEW 替代：`trace_entry_<id>`、`block_<id>`、
`dictionary`。上游部分 `SELECT *` 按位置读取，因此列序属于合同。原生 v2 的
`callstackId` 不能替代内联文本。

| 表 | 按顺序排列的列（SQLite 声明类型） |
| --- | --- |
| `trace_entry_<id>` | `id INTEGER PRIMARY KEY`, `action INTEGER`, `address INTEGER`, `size INTEGER`, `stream INTEGER`, `allocated INTEGER`, `active INTEGER`, `reserved INTEGER`, `callstack TEXT` |
| `block_<id>` | `id INTEGER PRIMARY KEY`, `address INTEGER`, `size INTEGER`, `requestedSize INTEGER`, `state INTEGER`, `allocEventId INTEGER`, `freeEventId INTEGER` |
| `dictionary` | `table TEXT`, `column TEXT`, `key TEXT`, `value TEXT` |

dictionary 的十进制整数 key 以文本存储，使用真实带设备后缀的表名与列名。每片包含
以下完整且精确的映射：

| 列 | key → value |
| --- | --- |
| `trace_entry_<id>.action` | `0 → segment_map`, `1 → segment_unmap`, `2 → segment_alloc`, `3 → segment_free`, `4 → alloc`, `5 → free_requested`, `6 → free_completed`, `7 → workspace_snapshot` |
| `block_<id>.state` | `-1 → inactive`, `0 → active_pending_free`, `1 → active_allocated` |

不接受未知基础 action/state。特别是原生 pt-snap 的 `oom=8` 不在固定版本兼容基线内；
未来导出器须拒绝或协商独立扩展，不得重标记。指标/大小单位为字节；event ID 是按时间
排序的身份，**不是时间戳**。

## 边界事件与 block 生命周期

- 真实事件保留非负原始 ID。`eventCount`、容量、范围及真实事件峰值只计数/筛选 `id >= 0`。
- 负 trace ID 独立标识合成的左边界状态行（`segment_map=0` 或 `segment_alloc=2`）。
  即使内存总量很大，也不能竞争真实峰值或占容量。ID 在片内局部，使用
  `(device, slice, 负 ID)` 标识边界行；重复边界 segment 不等于新真实分配。
  校验分别报告 `real_event_count/boundary_event_count`，不执行峰值查询。
- 已解析 block 的身份是 `(device ID, 原始 allocation event ID)`；所有出现片中
  `block.id == allocEventId >= 0`。释放后同地址复用产生**另一个** block。
  禁止按地址或片内行号去重。
- 预存/未解析 block 使用数据集/设备内稳定的负 `block.id`，`allocEventId=-1`。
  重复出现保留 ID，同地址不同对象不得碰撞。负身份不是已知分配事件；未来增强身份/覆盖表
  可区分预存和其他未解析情况。
- `freeEventId=-1` 表示没有观察到释放（存活**或未知**，不证明泄漏）；否则必须是设备内
  真实 ID，不能早于已知 alloc。`allocEventId=-1` 表示未知/预存，不是 event 0；
  其他负生命周期哨兵非法。最终化的完整 ID/生命周期可指向当前片范围外。各片状态观察可
  不同，但重复身份的地址、大小、requested size、alloc/free ID 必须一致。已解析分配
  最终化后不得遗留临时占位 ID。

若生产端已丢失身份，基础格式无法证明两个碰撞的未解析记录是不同对象；生产端必须正确跟踪。

## 扩展、scope 与能力

可选 metadata、去重 stack、有序 frame 使用隔离的 `pt_snap_*` 扩展表或 sidecar，
不能向按位置读取的基础表追加列。尤其**不能给内联 v1 附加未命名隔离的原生
`callstack` 表**：现有布局检测会正确报告 v1/v2 冲突。原生 v2 仍是独立单库布局，
不是本兼容基础格式。这里不要求 `pt_snap_metadata` 或辅助引用表。

基础校验忽略未知 `extensions` 声明/表。`DatasetValidation.text_callstacks=True`
表示有内联文本列，不保证每个事件有栈。即使 manifest 声称 frames，
`structured_frames=False` 仍为假：完整结构化 frame 能力要求已识别的独立扩展版本、
有序 frame 行、合法引用及覆盖率，本 P0 不实现。文本栈不能代替这些保证。

`QueryScope.validate(manifest)` 只定义 selector，不宣称支持执行：

| scope | 必需 selector 与范围 |
| --- | --- |
| `dataset` | 无 selector；所有声明设备的完整真实 trace |
| `device` | `device_id`；一个声明设备的完整真实 trace |
| `slice` | `device_id`, `slice_index`；该片真实区间，边界独立 |
| `event_range` | `device_id`、设备内闭区间 `start_event_id/end_event_id`；可跨片 |

设备间没有全局事件顺序。边界 ID 不能作为范围端点。P0 的
`DatasetValidation.query_execution=False` 描述校验而非执行。下述 P1 resolver
使 CLI/API 接受完整 manifest/目录；跨片执行仍留后续。

```python
from pt_snap_cli.core.dataset_contract import QueryScope, validate_dataset

inspection = validate_dataset("/capture/snapshot.pkl.msinsight")
QueryScope("event_range", device_id=0, start_event_id=1, end_event_id=3).validate(
    inspection.manifest
)
assert not inspection.structured_frames
```

## 完整数据集 focus 与寻址（P1）

已搬迁的兼容 v1 目录或其 `manifest.json` 可直接 focus；不要求原始 pickle、导入
metadata、辅助引用表或扩展表：

```bash
pt-snap focus /capture/snapshot.pkl.msinsight --device 0 --json
pt-snap overview --json
pt-snap query --template-use event --params '{"id": 3}' --json
pt-snap query --template-use event --slice 1 --json
```

`overview.dataset` 输出格式、manifest 版本/状态、内容指纹、真实/边界事件数、逐设备
分片路径/范围及能力。事件范围排除负 ID 合成行（单库 overview 也如此）。支持文本调用栈，
不保证每行有栈；结构化 frames 与跨片查询**不可用**，未知扩展的能力声明不会提升它们。
数据集级导入 metadata 为 unavailable；逐片 metadata 不是整份数据集的来源证明。

路径优先级仍为显式 → `PT_SNAP_DB_PATH` → 最近项目 focus → legacy global config；
设备优先级仍为显式 → focused → 首个发现设备。CLI focus 只写选定的项目/全局 focus 文件，
不写产物或检测布局；API 会话 focus 不写配置：

```python
from pathlib import Path
from pt_snap_cli import SnapshotAnalyzer

with SnapshotAnalyzer(Path("/capture/snapshot.pkl.msinsight"), device_id=0) as analyzer:
    event = analyzer.execute_query("event", {"id": 3})
    page = analyzer.execute_query("event", slice_index=1, exact_total=True)
    print(event["scope"], page["total_is_exact"])
```

数据集 focus 当前只支持 `event` 模板：真实 ID 路由至所在片，闭区间 `min_id/max_id`
必须落在一个片内，`--slice`/`slice_index` 列出该片真实事件。负 ID 不能作为整份数据集
selector。输出 `scope` 标识实际 DB/device/slice、受限真实区间、数据集指纹和边界排除。
总数和分页针对该 scope，**不是**隐式截断的整份数据集。CLI `effective_params` 的调用者
参数默认值另受 `scope` 约束。跨片区间、无界多片查询、聚合/生命周期模板明确失败，不会
静默选首片/最新片。直接对单库 v1/v2 查询保持原有语义。

`core.dataset_resolver.DatasetResolver.inspect(path)` 返回不可变 `ResolvedDataset`
（单库返回 `None`）；其 `paths(QueryScope(...))` 可寻址跨片范围的全部文件，但不执行查询。
每次调用重新校验最终化 P0 合同并对 manifest/所有成员取内容哈希，不保存无界 manifest/
连接缓存。哈希按有界块读取，工作量与产物大小成正比，不宣称性能收益。Context LRU 默认
最多四个；数据集 generation 变化在下次 lookup 使旧 Context 失效，即使 size/mtime 相同。
analyzer 自有缓存在退出时关闭，注入缓存仍由调用者所有；校验逐片打开并关闭连接。

building、缺片/矛盾片、未知基础版本、不安全路径在 focus 写入或查询前拒绝。在打开
**任何**分片前，resolver 先检查全部成员的规范非符号链接路径、SQLite header 及
WAL/journal/SHM sidecar（包含悬空符号链接）。即使 checkpoint 已移除 sidecar，持久 WAL
模式仍被拒绝：`mode=ro` 也可能重新创建它们。reader 不修复、不执行 checkpoint、不删除
sidecar、不改变 journal mode；单库行为不变。这是只读检查，不是文件系统沙箱或并发生产端锁。native-v2 replay 的私有
staging **没有已发布 manifest**，不能作为数据集；其中单个 DB 仍由已有单库入口读取。
后续兼容 v1 生产端可直接使用同一 reader，不依赖生产端专属 metadata。本项不虚构
native-v2 manifest 协议，不新增导出、缓存发布、迁移或跨片生命周期重建。

## 内部持续回放（P1）

`core.sharded_replay_service.ShardedReplayService.stage(source, directory,
events_per_slice=..., device=None)` 是**内部生产边界**，不是新 CLI/API 导入命令。
它只加载一次可信 pickle，每个所选非空设备只创建一个持续模拟器，从末片向前写入
新的、调用者所有的**私有 staging 目录**。`omitted_devices` 披露全部未选/空设备位置。
现有 `import`、`split`、`SnapshotAnalyzer` 与单库 v1/v2 读取保持不变。

返回的不可变结果标识 **native-v2** 分片，不是兼容 v1 产物：trace 使用
`callstackId` 和片内 `callstack` 表，保留原生 OOM action 8 与 workspace 事件。
原生真实 ID 可以稀疏或非零起点，但必须非负、唯一且按时间递增；窗口按列表位置计数，
不是 `max(id)+1`。这些原生片**不能**通过 `validate_dataset`。兼容导出、兼容 manifest、
缓存/发布及数据集查询属于后续独立工作。不生成 `manifest.json`、`readySlices` 或增量
ready 通知；仅所有设备完成回填及校验后的成功返回结果可交给后续发布层。
失败保留调用者所有的私有部分文件，不将其宣称为完整数据集。

`SimulateDeviceSnapshot.replay_until(remaining_events)` 倒序回放到剩余指定数量的
时间顺序列表事件。端点是**位置**而非 event ID；重复暂停/继续与完整 replay 共用
hooks 和错误路径。真实事件行记录事件**之后**的状态（undo 之前）。undo 窗口首事件后，
活跃 block 观察和负 ID `segment_alloc`/`segment_map` 行重建首事件**之前**的状态；
边界行不计入容量或真实事件峰值。

设备内 registry 跨 writer 保留原始 block 对象，不用 hook 副本或仅地址作为身份。
遇到真实 alloc 后，每次出现都最终指向原 alloc ID；未知/预存生命周期保持稳定负身份。
所有 writer 关闭后才逐 DB 事务批量回填并校验。`freeEventId` 始终是 `free_completed`，
不是 `free_requested`；边界 `active_pending_free` 观察保留 state 0。同地址复用及不同
stream 的同地址块不会合并。每个原生片加入
`pt_snap_block_reference(blockId, stream, allocCallstack, freeCallstack)`，保留最终化的
片外生命周期引用的文本调用栈来源。NULL 表示未观察到来源事件；空文本表示已观察事件
没有 frames。旧有片内查询 JOIN 不自动消费这个内部表；它不是跨片查询引擎或结构化
frame 扩展。

pickle 仍可能整体加载。分库只限制**单库真实事件数**，不限制 block 行数、总 staging
字节、registry 大小或峰值 RSS。合成回归及已审 expandable/多设备 fixture 覆盖回放
等价和资源失败路径；不宣称真实上游 GUI 或性能验收。

## 来源证据与限制

接口事实已从固定版本真实源码读取：
[manifest 校验](https://github.com/Ascend/msinsight/blob/101f65b877a267ffd5f66ea3834706057ba243e5/server/src/modules/memsnapshot/service/MemSnapshotSliceService.cpp)、
[SQLite 按位置读取](https://github.com/Ascend/msinsight/blob/101f65b877a267ffd5f66ea3834706057ba243e5/server/src/modules/memsnapshot/database/MemSnapshotDatabase.cpp)、
[基础 schema](https://api.github.com/repos/Ascend/msinsight/git/blobs/1fe50a5136f85365db55f4632d58f3cf7090431e)、
[发布/回填](https://api.github.com/repos/Ascend/msinsight/git/blobs/95612509ef990ac6b7034919dae4938cc6acf3ad)。
这些源码包含 Huawei Mulan PSL v2 声明。本文合同、Python 校验器和合成测试是本地原创的
接口事实实现，没有向包内复制上游实现；上游 docs 单独使用 CC BY 4.0，不能替代源码声明。

complete 就绪一致性和规范路径规则刻意严于上游 parser（上游也支持 building）。
合成合同测试/真实源函数对照不是 GUI 验收、原生导出器验收、性能测量，也不证明其他版本互通。
