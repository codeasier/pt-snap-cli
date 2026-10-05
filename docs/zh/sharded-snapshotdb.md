# 分片 SnapshotDB 协议（兼容 v1 与原生 v2）

中文 | [English](../en/sharded-snapshotdb.md)

## 范围与版本

本文定义产物协议、共享校验模型及下述**显式**兼容 CLI 导出器，不实现跨片查询引擎。
`import` 默认仍生成一个原生 v2 DB；`split` 仍输出可回放 pickle/JSON。现有单库
v1/v2 单库分析不变。下述 P1 reader 新增将 complete 兼容 v1 manifest 或目录作为
focus；`complete` 门槛只约束数据集，不约束旧单库分析。

`pt_snap_cli.core.dataset_contract` 提供 `parse_manifest`、`validate_event_ids`、
`validate_dataset`、不可变 manifest/device/slice 模型、`QueryScope` 和带
`location/code` 的 `DatasetContractError`。生产端可在发布前与读取端共用同一合同。
校验不加载 pickle、不创建缺失数据库、不迁移 SQLite、不写 focus。

版本轴分别管理：

- `schemaVersion=1`：本文的 manifest 和兼容基础表协议。
- `pt_snap_metadata.import_format_version`：pt-snap 导入格式，原生为 `2`，兼容内联为 `1`；
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
使 CLI/API 接受完整 manifest/目录；通用跨片聚合仍留后续，定点来源解析见
[查询指南](querying.md#数据集定点事件归因)。

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
外部数据集级导入 metadata 为 unavailable；逐片 metadata 不足以证明整体来源。
下述兼容导出器提供可识别的整份 `ptSnap` 证明，其完整校验后的 metadata 为 available。

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

数据集 focus 的 `event` 模板支持有界寻址：真实 ID 路由至所在片，闭区间 `min_id/max_id`
必须落在一个片内，`--slice`/`slice_index` 列出该片真实事件。负 ID 不能作为整份数据集
selector。输出 `scope` 标识实际 DB/device/slice、受限真实区间、数据集指纹和边界排除。
总数和分页针对该 scope，**不是**隐式截断的整份数据集。CLI `effective_params` 的调用者
参数默认值另受 `scope` 约束。定点 `active_blocks_at_event` 和
`active_memory_callstack_at_event` 现于分组/排名前批量解析 alloc/free/完整栈来源，
原版无扩展产物也适用。生命周期身份、独立来源/frame 覆盖及版本化有序 frame reader
接口详见[定点归因](querying.md#数据集定点事件归因)。数据集全局聚合/peak/list/leak、
跨片事件区间及无界多片 event 查询仍明确失败，不静默选首片/最新片。直接单库 v1/v2
查询保留现有语义。

`core.dataset_resolver.DatasetResolver.inspect(path)` 返回不可变 `ResolvedDataset`
（单库返回 `None`）；其 `paths(QueryScope(...))` 可寻址跨片范围的全部文件，但不执行查询。
每次调用重新校验最终化 P0 合同并对 manifest/所有成员取内容哈希，不保存无界 manifest/
连接缓存。哈希按有界块读取，工作量与产物大小成正比，不宣称性能收益。Context LRU 默认
最多四个；数据集 generation 变化在下次 lookup 使旧 Context 失效，即使 size/mtime 相同。
analyzer 自有缓存在退出时关闭，注入缓存仍由调用者所有；校验逐片打开并关闭连接。

building、缺片/矛盾片、未知基础版本、不安全路径在 focus 写入或查询前拒绝。
**任何** SQLite 打开之前，裸 P0 validator 与 resolver 均先检查**全部**成员/父目录别名及
存活/悬空 WAL、journal、SHM sidecar。最终化、已关闭的兼容 v1 成员使用
`mode=ro&immutable=1`，缓存查询的 Context 连接也一样；接受固定原始生产端已 checkpoint、
无 sidecar 的 WAL header，不创建 sidecar、不改变字节。immutable 只适用于已关闭最终化
产物，**不是读取 live WAL 的捷径**，不保证并发 writer 安全。不修复、不 checkpoint、
不改变 journal mode、不迁移、不删除。原生数据集仍拒绝持久 WAL，单库 Context 默认仍
为不带 immutable 的 `mode=ro`。Cache 身份包含传输模式与 generation。这是只读校验，
不是文件系统沙箱或生产端锁。

native-v2 私有 staging **没有已发布 manifest**，不能作为数据集；单个 DB 仍由单库
入口读取。已发布原生格式与兼容导出是下述独立显式协议。跨片生命周期执行仍属独立工作，
安全读取原版 WAL 不等于 GUI 验收。

## 已发布原生数据集（P2）

这是 pt-snap **原创、独立命名和版本化**的协议，不是重标记的 P0 产物。ImportService/CLI
将内部原生回放结果发布至 `<output-dir>/<完整源文件名>.pt-snap-native-v2/`。根目录只能
包含 `manifest.json` 与声明的 `device_<id>` 目录；各设备目录只能有规范的
`slice_<index:05d>.db` 成员。

原生 manifest 必需字段：

| 字段 | 合同 |
| --- | --- |
| `format` | 严格为 `pt-snap-native-v2`，与 compatibility-v1 独立分派 |
| `schemaVersion`, `status` | 原生 manifest 版本 `1`，只允许 `complete` |
| `sourceFile` | 非空源 basename，与 `metadata.source_name` 一致，分析不打开源文件 |
| `identity` | 精确字段 `sourceSha256`、`requestedDevice`、`eventsPerSlice`、`outputFormat`、`manifestContractVersion`、`formatContractVersion`、`importContractVersion`、`extensionContractVersion`、`metadataSchemaVersion`、`importFormatVersion` |
| `metadata` | 完整已有 `ImportMetadata` 对象，与每片唯一 metadata 行一致 |
| `omittedDevices` | 不重复的未选/空/仅静态源设备位置，与所选设备不相交 |
| `devices` | 规范十进制 key，正 `eventCount/sliceCount`，全部按序 `readySlices` 及按序 `slices` |
| 各 slice | `index`、`startPosition/endPosition`、`startEventId/endEventId`、规范相对 `file`、`ready: true`、已关闭成员 `sha256` |

所有语义合同版本初始为 `1`；原生 metadata schema 为 `1`、DB import format 为 `2`。
`requestedDevice` 为 null（全部有事件设备）或一个非负整数；SHA256 为 64 位小写十六进制。
CLI `metadata.importer_version` 仅提供信息，**不是**缓存失效轴。原生与后续兼容格式身份
独立版本化，不生成原生 `cacheHash`，也不接受它替代缓存身份。

位置在各设备内连续覆盖 `0..eventCount-1`，末片之前全部满容量，末片至多容量个事件。
ID 区间为原始时间顺序闭边界，可稀疏/非零；真实计数来自位置和实际行，不是
`max(id)+1`。负 ID 合成行单独计数。各成员须有本设备的原生 v2 trace/block 实际表、
`dictionary`、`callstack`、`pt_snap_metadata` 与最终化 `pt_snap_block_reference` v1。
trace 列与单库 v2 一致（`callstackId`，非内联文本），保留 OOM action 8。block 身份/
生命周期和文本引用须最终化、跨片一致，并引用原设备真实 ID。未知扩展声明/表不会
提升结构化 frame 能力。

原生 resolver 校验全部成员哈希、实际 schema/dictionary、真实计数/范围、metadata 和
最终化引用，保留 P1 打开前的别名/sidecar/持久 WAL 检查及有界借用 cache 所有权。
无需源 pickle 即可 focus、metadata、overview 和单片 `event` 寻址。原生数据集 metadata
为 available，外部兼容数据集为 unavailable（下述可识别兼容证明除外）。原生模式不隐含
迁移、修复、数据集全局聚合/peak/list/leak、兼容导出、salted hash 或 GUI 验收；定点
来源解析通过上述共享查询路径可用。P0 schema/manifest
语义不变，仅兼容最终化 WAL 的只读传输修正见上文。

发布、force/focus 补偿见[导入指南](quickstart.md#可选导入原生分库数据集)。完整 manifest
只能与全部最终化成员同时可见，单个 ready 片不构成完整产物。

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

## 显式 msinsight 兼容导出（P2）

`pt-snap import snapshot.pkl --format msinsight --json`（别名
`--format compatibility-v1`）**仅**对齐
`Ascend/msinsight@101f65b877a267ffd5f66ea3834706057ba243e5`。支持入口是在该目标版本
打开**同一原始 pickle**及邻接 `<原始路径>.msinsight/`，不是 GUI 直接导入独立目录。
`--output-dir` 为 pt-snap 选择其他父目录，搬迁本身不创建上游入口。`sourceFile` 记录
绝对原始源路径。容量默认 `500000`，可用 `--events-per-slice` 调整；默认单库及显式
native-v2 输出仍独立且不变。

第一方转换器消费已关闭/最终化的原生暂存，物化精确位置内联 v1 **实际表**，去除
未隔离原生 `callstack`，写入物理格式 metadata `1`。保留原始真实 ID、action、stream/
指标、设备内稳定 block 身份、`free_completed` 和片外生命周期文本来源引用，不插入
外片真实事件掩盖片内 JOIN 缺口。OOM/未知 action、非零/稀疏 ID、空/仅静态选择失败；
原生保留更广合同。所有选中成员最终化、关闭、校验后才发布 complete。
`pt_snap_block_reference` v1 是隔离文本扩展，不是有序 frames 或跨来源查询承诺；
跨来源查询/全局聚合仍属后续独立工作。文本不能恢复原始有序 frame 数组；原版 workspace
raw-frame 丢失与字符串 OOM action 强制转换属于已知局限，不应仿制为兼容能力。

`cacheHash = SHA256(b"mem_snapshot_parser_v2" + 原始_pickle_字节)`，salt **前置**。
独立 `ptSnap.identity` 字段为 `sourceSha256`、`requestedDevice`、`eventsPerSlice`、
`outputFormat=compatibility-v1`、`manifestContractVersion=1`、`exportContractVersion=1`、
`referenceContractVersion=1`、`metadataSchemaVersion=1`、`importFormatVersion=1`、完整
`targetRevision`。`ptSnap` 另含 `metadata`、`omittedDevices` 和 `members`（规范相对路径
→ 最终化 SHA256）。整体已校验所有权/身份要求每个成员/哈希及逐片 metadata 相同；
不接管未知/外部缓存或无关文件。CLI 版本变化本身不使缓存失效。

兼容发布 **force 也 no-replace**。已识别、身份相同的 pt-snap 缓存不加载 pickle 即复用，
force 不绕过该规则。源路径/内容、选项/合同变化、成员损坏或 GUI 修改 DB 后须换新
`--output-dir`，不修复、不覆盖、不删除旧产物。排他发布与 focus 补偿使用已有受检事务，
发布/复用前再次核对源 SHA256；原生 force 替换与恢复语义不变。

内联文本成本按每个事件的 UTF-8 调用栈字节求和，不按不同栈各存一份；原生去重仍可用。
转换暂时并存两种布局，可能留下 SQLite free pages；容量不是 RSS/registry/block/磁盘
上限。不生成可选 frame 增强。

**GUI 待验收/未运行。** 固定源码 parser 在 UP_TO_DATE 前检查 complete manifest、
非空相同 hash、每个 ready/可解析/存在成员、只读 DB/设备校验，以及 allocation cache
存在**或可构建**。派生 allocation cache 可在不运行生产者时修改 DB，mtime 或新派生表
不能单独证明重跑。后续 GUI 验收须保留 UP_TO_DATE/无 script 调用日志并对照曲线、block、
跨片展示。源码检查及原版产物的生产 reader 读取不是 GUI、C++ server/编译或完整差分/
性能验收。

不可变固定 blob 证据：
[parser 判据](https://api.github.com/repos/Ascend/msinsight/git/blobs/40046e6a92ff5af776ee55bd4cdd4586745af3c2)、
[salt 顺序](https://api.github.com/repos/Ascend/msinsight/git/blobs/ca421c7b33f3a0050df9e7a01e666f558801bc2f)、
[allocation cache 判据/构建](https://api.github.com/repos/Ascend/msinsight/git/blobs/3d1ecc0ebd0d8e3eb0c984eda6b750ec4ce0e4f1)。
Ascend 源码为 Mulan PSL v2，docs 单独为 CC BY 4.0；此最小转换器是本地原创接口事实实现，
未复制 vendor 实现，也不把 Ascend blob 自动重新许可为 MIT。已有 pt-snap 运行时 lineage
属于独立许可证/来源历史。

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
