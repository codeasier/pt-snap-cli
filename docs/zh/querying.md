# 运行查询

[English](../en/querying.md) | 中文

对快照数据库执行内存分析查询。

按同一 YAML catalog 的 `dataset_support`/声明字段选择显式有效 target/device/scope。
[离线验收与实测查询延迟](interop-acceptance.md) 区分来源/区间/frame覆盖与 `has_more/truncated`，
说明 text-only降级、全部action栈统计并保持included-byte分母。有界
`report peak-memory --start-id ... --end-id ...` 的 gap/active归因/coverage 使用同一 selected
metric event；整份数据集仍不支持自定义SQL/override。测量不是速度断言。

## Query 命令

```bash
pt-snap query [DB_PATH] [--template-use <template_name>] [--params <json>] \
  [--device <id>] [--list] [--category <category>] \
  [--template-info <template>] [-n <rows>] [--exact-total] [--timeout <seconds>] [--json]
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| `db_path` | 单库 SQLite 文件或完整已校验数据集目录/manifest（已配置 focus 时可选） |
| `--template-use` | 查询模板名称（除非使用 `--list` 或 `--template-info`，否则必需） |
| `--params` | JSON 格式的查询参数 |
| `--device` | 设备 ID |
| `--list` | 列出可用的查询模板 |
| `--category` | 按分类过滤模板：`basic`、`statistical`、`business` |
| `--template-info` | 显示模板详情（参数、输出 schema 和字段语义） |
| `-n` | 最大显示行数；零或负数表示不限制。与 `--timeout` 相互独立。 |
| `--exact-total` | 计数完整匹配集合：单库 SQL COUNT 或数据集合并后的总数。默认 `total` 为返回行数。 |
| `--timeout` | 一次 `query` / `QueryService` 调用的墙钟预算（页面查询与可选 `--exact-total` COUNT 共用），经 SQLite progress handler 生效。`<= 0` 表示关闭。默认：`PT_SNAP_QUERY_TIMEOUT` 或不限制。该环境变量作用于所有模板查询，包括 `report peak-memory`。 |
| `--json` | 输出机器可读 JSON（执行、`--list` 与 `--template-info`） |

## 紧凑调用栈文本

`event` 和 `active_memory_callstack_at_event` 支持显式启用的 `stack_bytes`
参数；`report peak-memory` 可用 `--stack-bytes` 控制调用栈分组文本。
默认 `-1`（或任意负数）保留完整文本及原有行结构。`0` 仅保留栈身份信息，
正数返回不超过指定 UTF-8 字节数的有效文本前缀。

```bash
pt-snap query '<db_path>' --device 0 --template-use event --params '{"action":0,"limit":1000,"stack_bytes":256}' --json
pt-snap query '<db_path>' --device 0 --template-use active_memory_callstack_at_event --params '{"event_id":100,"top_n":20,"stack_bytes":256}' --json
pt-snap report peak-memory '<db_path>' --device 0 --stack-bytes 256 --json
```

请替换为数据库实际路径、设备与事件。Python API 使用相同参数：
`analyzer.execute_query("event", params={"stack_bytes": 256, "limit": 1000})`。
通过 `capabilities --json` 或模板详情确认支持情况和字段定义；其他模板不接受此参数。

每条紧凑行增加 `stack_id`、`stack_kind`、`stack_event_id`、`stack_bytes`
（生效预算）、`stack_original_bytes` 和 `stack_truncated`。数值与 `category`
保持不变。预算只限制 UTF-8 文本值；JSON 转义、身份及其他元数据会额外占用字节。
这既不是整包输出大小硬上限，也不是模型 token 预算。前缀可能在一帧中间结束，
解释被省略的帧前应取回完整文本。

`stack_truncated` 表示**文本缩略**，独立于查询的 `has_more`、`truncated`、
`total`、`total_is_exact`；后者仍描述证据行集合。完整行集合也可能包含缩略文本。
报告行数限制保留既有语义，文本摘要不能证明证据覆盖完整。

在同一未变化的数据库/设备内用 `stack_id` 判断身份：v1 使用完整采集文本的 SHA-256，
v2 使用真实 `callstackId`（相同文本可以有不同 ID）。missing、static、preexisting
归因分别使用独立分类身份。禁止按前缀或显示标签合并分组。
`stack_kind` 区分真实采集文本与合成/缺失归因。

对真实采集栈，在**同一数据库/设备**下使用返回的 `stack_event_id`，省略
`stack_bytes` 即可取回完整文本：

```bash
pt-snap query '<db_path>' --device 0 --template-use event --params '{"id":123}' --json
```

把 `123` 替换为返回的定位事件；此代表事件不是分组身份。missing/static/preexisting
分组没有可取回的采集分配栈；在原查询中省略 `stack_bytes` 可查看完整显示标签。
查询保持只读，摘要不会改动数据库。

## 数据集全局内建支持（P3）

完整 native-v2 与 compatibility-v1 数据集共用以下**单设备**支持矩阵；catalog 与
模板详情的 `dataset_support` 同步返回。设备优先级仍为显式 → focused → 首个发现；
不累加跨设备峰值，设备间没有共同全局事件顺序。

| 模板 | 最终输出窗口之前的数据集语义 |
| --- | --- |
| `event`, `allocation` | 筛选选定范围全部真实事件，按声明的 ID tie-break 全局排序，最后 offset/limit/max_rows；排除负边界 |
| `memory_peak` | allocated/active/reserved 独立真实峰值；同值选最早真实 ID；`start_id/end_id` 可跨片 |
| `allocator_gap` | 使用同样独立选择的全局事件，每个 gap 由**该事件**计数器计算 |
| `active_blocks_at_event`, `active_memory_callstack_at_event` | 路由实际事件到所有者片，分组/top_n 前解析完整跨片来源（见下文） |
| `preexisting_live` | 所有者事件的 preexisting 占用，不是泄漏数 |
| `block` | 已证明的分配事件生命周期及稳定负 token 去重后筛选/排序/分页；最新出现片 state 是观察，不是任意 E 的状态 |
| `freed_block_lifetime` | 已采集分配与已证明 `free_completed` 来源的去重生命周期；event-ID 距离桶，不是时间 |
| `leak_detection` | **数据集终片**中仍存在且无完成释放的已采集动态生命周期，不拼接逐片未释放列表；存活仅为候选，不证明泄漏；拒绝 `--slice` |
| `callstack_analysis` | 全部带栈真实 trace action（含 free/segment/workspace），完整 canonical 来源身份合并后再做全局阈值/排名；加权 `avg_size=total_size/alloc_count` |
| runtime override/自定义模板/任意 SQL | 数据集明确不支持，即使命名为内建模板；需显式传单库 member 使用局部 SQL |

`memory_peak` 与 `allocator_gap` 语义版本 **2** 在**单库** SQL 中也排除负合成行。
`callstack_analysis` 版本 **2** 保留旧 `alloc_count` 字段名，但**不是分配次数**：
v1 统计非 NULL 文本的全部真实行；v2 统计非 NULL 栈引用的全部真实行，缺失/NULL
joined 文本保留为独立 missing 组。空文本单独计数组，与 missing 及真实字面量标签分开；
两种单库布局都按完整文本分组而非局部 v2 ID。数据集还接受明确覆盖的有序原始数组
作为栈证据；缺失文本不改变原始数组
身份。size 总和含非分配 action，不是瞬时活跃占用。

共享 YAML 输出 schema 声明全部可选的仅数据集行字段；单库行形状不变。`block` 与
数据集 `leak_detection` 提供 `lifecycle_id`、身份/来源证明状态、来源载荷、最新观察片/
state scope、category 与终片存活；leak 行另保留 `requestedSize`、`state`、`freeEventId`。
这些观察与证明不等于确认泄漏。数据集统计提供 `source_stack_id`、`stack_kind`、
`text_kind`、`stack_event_id`、`frames_status`。真实代表事件优先选可用的非空采集文本，
但不是 canonical 分组身份，也不一定是 allocation action；无采集文本时可指向空/NULL
文本。`text_kind` 仅为 provenance，不改变原始数组身份。在同一数据集/设备用 `event`
取回真实文本/数组；`frames_status` 不表示从文本重建 frame。

```bash
pt-snap query '<dataset_dir>' --device 0 --template-use memory_peak --params '{"start_id":100,"end_id":700}' --json
pt-snap query '<dataset_dir>' --device 0 --template-use event --params '{"min_id":100,"max_id":700,"limit":20,"offset":20}' --exact-total --json
pt-snap query '<dataset_dir>' --device 0 --template-use leak_detection -n 20 --exact-total --json
pt-snap report peak-memory '<dataset_dir>' --device 0 --metric reserved --start-id 100 --end-id 700 --timeout 10 --json
```

请使用实际范围。区间可包含稀疏缺口，不虚构事件；无真实事件的范围返回 NULL 峰值/ID。
越界/负/反向端点失败；`event(id=gap)` 可为空，active-at-gap 失败。全局筛选、去重、来源
身份、阈值、排序都在最终窗口之前。`exact_total` 忽略行数上限；默认 total 为返回行数，
exactness 标记诚实。`has_more/truncated` 描述窗口，不表示来源/范围完整性。`scope` 返回
请求区间、适用时实际真实事件覆盖、涉及 `slice_indices`、设备、指纹及边界排除；来源覆盖
独立。未证明历史身份按片局部单独表达，不按地址/局部栈 ID 猜合并，不断言为已证明泄漏。

数据集读取先分离批次再查外片来源，使用借用的有界 Context LRU。所有片、来源、分组、
精确总数共用递减 deadline；报告的峰值选择与归因明确共用**一个**预算。累计取回/输出工作上限为
**100000 行 / 64 MiB 序列化值**，含重复来源读取；超限整体失败，不返回冒充完整的部分
结论。物化/排序由工作上限约束，**不由 max_rows 约束**；不是进程 RSS 上限，Python/
SQLite、一个批次及单个 cell 有额外开销。默认仍对 manifest/成员执行完整校验和 hash，
并共用该 deadline：hash 分块、Python 行批次及 SQLite progress handler 都检查取消。
单个文件系统调用不提供 OS 级硬抢占。仅当调用方保证最终产物不可变且文件系统变更时间
可靠时，才可通过 `PT_SNAP_DATASET_CACHE=immutable` 显式启用进程内校验复用；参见
[数据集校验与缓存合同](sharded-snapshotdb.md)。不生成合并临时 DB、不修复或写产物。

## 数据集定点事件归因

完整兼容 v1 或原生 v2 目录/manifest 支持 `event` 寻址，以及接受真实 `event_id` 的
`active_blocks_at_event`、`active_memory_callstack_at_event`。后两者按设备路由实际事件，
从所在片完整生命周期观察计算正向事件**之后**的集合：`allocEventId <= E` 且完成释放
`freeEventId > E`（或 `-1`）。`free_requested` 不移除 active 内存。负边界行表示片内
首事件之前，不是定点端点。原生稀疏 ID 不改号：片内 `event(id=gap)` 可返回空行，
不存在事件的 active 归因则明确失败，不虚构 event 0。

```bash
pt-snap query '<dataset_dir>' --device 0 --template-use active_memory_callstack_at_event --params '{"event_id":700,"top_n":20}' --json
pt-snap query '<dataset_dir>' --device 0 --template-use active_blocks_at_event --params '{"event_id":700,"limit":10}' --exact-total --json
```

请替换实际路径/设备/事件。片外 alloc/free 事件及完整 v1 内联或 v2 局部 ID 栈在
分组/top_n **之前**解析，按实际来源片每批至多 256 个不同事件 ID。不补入外片真实行。
原版产物无需 metadata 或引用表。生命周期用数据集 generation/设备/分配事件或稳定
负身份，不用地址；`state_scope=slice_observation` 提醒存储 `state` 不一定是 E 时的
pending-free 状态。block 行提供 `allocation_source`、`free_source`、状态和
`lifecycle_id`。缺失动态来源仍保留字节及动态类别，与 static/preexisting 未知历史分开；
`free=-1` 表示存活**或未知**，不证明泄漏。

数据集分组始终提供完整 `source_stack_id`/`stack_id`、`stack_kind`、`stack_event_id`。
无扩展的默认 `event` 行保留原始九个值；`stack_bytes>=0` 或已识别有序 frame 声明时
才增加来源/frame 行字段，`scope.source_coverage` 仍返回。
两种数据集布局均按完整文本的 canonical 身份分组；v2 仍按来源片真实局部 ID 查栈，
来源 `local_stack_id`/`slice_index` 是 provenance，不是跨片分组 key。有覆盖的有序数组
只使用精确原始 frame 身份，与格式化文本是否存在无关；`text_kind` 独立描述文本
可用性。明确覆盖的数组（含空数组）是已采集原始证据；分组优先选择有文本的代表
事件以便取回全文。非空 whitespace 和真实采集的字面量
`[missing callstack]` 不是 missing。禁止按局部 ID 或缩略显示标签合并。`stack_bytes`
只缩短显示；在同一数据集/设备用 `event(id=stack_event_id)` 取回全文。明确覆盖的原始
有序 frames 也参与身份；不从文本重建 frames。

`scope.source_coverage` 独立于 `has_more`/`truncated`/精确行数：active 查询覆盖的是
**top_n/分页之前全部筛选 block**，包括 active/dynamic 字节、已解析 alloc/free 数、采集
动态字节、未知/预存数、有序 frame 覆盖及降级。`event` 覆盖仅为 `returned_events`。
完整 manifest/范围不证明历史来源或 frame 完整。百分比分母仍为动态 top_n **之后、
max_rows 之前**所含字节，不是数据集 active 计数器。精确总数忽略行数/排名上限，但
不改变百分比分母。

一次调用的来源批次、分组和精确总数共用 deadline。manifest 校验/hash 及 Context
设置耗时计入预算。校验在 hash 分块与 Python 行批次之间检查取消，SQLite 通过退出即
清除的 progress handler 检查取消。单个文件系统调用不硬抢占，不保证 OS 级时间上限。
Context LRU 有界（默认四个），借用
cache 仍由调用者所有。不生成合并临时数据库。`ReportService.event_attribution(E, ...)`
对给定事件复用同一路径。数据集全局查询及报告遵循上文明确支持矩阵；任意 SQL/
自定义 override 不会因使用内建名字就继承全局合并语义。

### 可选有序 frame reader 合同

这是新增的仅 reader pt-snap 扩展，不是原版 producer 已有功能。当前原生/兼容 writer
**不生成**有序 frame 表。manifest 声明 `extensions.ptSnapOrderedFrames={"version":1}`，
并在有覆盖的来源片使用隔离的实际表：

- `pt_snap_frame_coverage(eventId INTEGER PRIMARY KEY, frameCount INTEGER)`
- `pt_snap_frame(eventId INTEGER, frameIndex INTEGER, frameJson TEXT, PRIMARY KEY(eventId,frameIndex))`

原始 object 必须是有限数字的标准 JSON，嵌套深度至多 128；超深、非有限数或解析
失败（包括递归错误）安全降级。每个覆盖的真实事件须有非负整数 `frameCount`、恰好 `0..frameCount-1` 索引及保留全部
原始类型字段的 JSON **object**。保持顺序和重复帧；空数组须有明确 count=0 行。
只有已识别版本/schema 及有效逐事件覆盖才输出 `frames`、`frames_status=ordered`。
未知版本、缺失 schema/行、无效 JSON 或覆盖不全降级为 `frames=null`、
`frames_status=text_only`；不会切分/反转格式化文本伪造原始 frames。P0/overview 的
数据集级 `structured_frames=false` 仍是保守校验能力，不表示定点来源载荷必然无 frames。
本接口不提供树渲染或 GUI 验收。

## 查询模板

模板分为三个分类。用 `pt-snap capabilities --json` 一次查看完整清单（CLI 版本、全部模板契约和随包 skill），或用 `pt-snap query --list` 查看名称与描述。用 `--category` 过滤。

### Basic Queries

原始数据查询。

| 模板 | 说明 |
|------|------|
| `block` | 灵活字段过滤的内存块查询 |
| `event` | 灵活字段过滤的内存事件查询 |
| `allocation` | 内存分配时间线（id, allocated, active, reserved） |

`event`、`callstack_analysis` 和 `active_memory_callstack_at_event` 对外保持同一契约，
并根据数据库布局选择 v1 或 v2 SQL。见
[调用栈布局兼容](database.md#调用栈布局兼容)。

### Statistical Queries

聚合分析。

| 模板 | 说明 |
|------|------|
| `callstack_analysis` | 调用栈分析 |
| `memory_peak` | 峰值内存指标 |
| `active_blocks_at_event` | 查询某个事件时刻仍然活跃的 block，可选包含静态与 preexisting 存活内存 |
| `allocator_gap` | 比较 allocated、active、reserved 三类峰值事件及其同事件 gap |

### Business Queries

领域特定分析。

| 模板 | 说明 |
|------|------|
| `leak_detection` | 查找已采集分配且没有释放完成记录的候选（不是已确认泄漏） |
| `active_memory_callstack_at_event` | 对某个事件时刻的活跃内存块按分配调用栈做聚合，并单独标识静态与 preexisting 内存 |
| `preexisting_live` | 统计某个事件时刻仍存活的 preexisting 块（`allocEventId=-1`，包含 `freeEventId IS NULL`） |
| `freed_block_lifetime` | 按 `freeEventId - allocEventId` 距离分桶统计已成功释放的块（不是经过时间） |

## 泄漏检测

```bash
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

`min_size` 表示候选泄漏的最小字节数，默认值为 `0`。目标设备应通过命令级
`--device` 选项指定，而不是放进 `--params`。`leak_detection` 返回的是捕获范围内
仍存活的候选，不是已确认泄漏。用 `pt-snap query --template-info leak_detection`
读取字段单位与解释限制。

### 获取完整候选窗口

`leak_detection` 只接受 `min_size` 与 `limit`，**没有 `offset`**。传入
`offset` 会被拒绝（CLI JSON 返回 `INVALID_PARAMETER`，Python API 抛出
`TemplateRenderError`）。`has_more: true` 表示结果不完整，不保证支持 offset 分页。

先执行有界查询。需要完整候选集时，在保持返回窗口有界的前提下获取精确计数：

```bash
pt-snap query '<db_path>' --device <device_id> --template-use leak_detection --params '{"min_size":1024}' -n 100 --exact-total --json
```

精确 `total` 是匹配的**行数**，不是字节数或 GiB，且忽略 `limit`。若为零，
报告没有匹配候选即可，不要再用 `-n 0` 查询（它表示不限制）。只有总数为正且
内存/输出预算可承受时，才使用同一数据库、设备和过滤条件，通过
`-n <positive_total>` 单次获取该行数：

```bash
pt-snap query '<db_path>' --device <device_id> --template-use leak_detection --params '{"min_size":1024}' -n <positive_total> --json
```

删除 `--params` 中显式的 `limit`，或同步增大到该总数；否则较小的 `limit`
仍会限制扩大后的窗口。确认 `returned` 等于精确计数，且 `has_more` 与
`truncated` 均为 false。用新结果**替换**旧结果，不要追加重叠窗口或累加各次
计数/字节数。API 采用相同流程，使用 `exact_total=True` 和正数 `max_rows`。

完整结果超出预算时，保留有界样本并明确报告候选/字节覆盖不完整。精确行数
无法给出候选总字节数。增大 `min_size` 会改变分析范围，需要重新计数，不能
据此声称已经覆盖原始范围的全部结果。

## 参数校验

`--params` 会在渲染任何 SQL 之前按模板定义进行校验：

- 每个键都必须是模板声明的参数。未声明的键会被拒绝而不是忽略，因此把
  `min_size` 拼成 `min_sze` 会得到 `Unknown parameter(s) for template
  'leak_detection': min_sze (accepted: min_size, limit)`，而不是悄悄返回一份
  未过滤的结果。
- 值会按声明的类型（`int`、`float`、`str`、`bool`）转换。
- 会被当作 SQL 标识符或关键字渲染的参数（如 `order_by`、`order_dir`）只接受
  `--template-info` 中 `[choices: ...]` 列出的取值。字符串取值不区分大小写，
  并按声明的写法渲染（`desc` 会变成 `DESC`）；其他任何值都会在到达数据库之前
  被拒绝。

```bash
pt-snap query --template-info allocation
#   order_by: str (optional) [choices: id, allocated, active, reserved] [default: id]
#   order_dir: str (optional) [choices: ASC, DESC] [default: ASC]

pt-snap query --template-use allocation --params '{"order_by": "reserved", "order_dir": "desc"}' -n 5
```

`SnapshotAnalyzer.execute_query()` 遵循同样的规则，并以相同的错误信息抛出
`TemplateRenderError`。

## 峰值内存归因工作流

这些新增能力把“先找到峰值，再解释峰值时刻哪些内存仍然活跃”的手工分析流程产品化了。

### 1. 先定位峰值事件

```bash
pt-snap query --template-use memory_peak
```

这个模板会返回 `allocated`、`active`、`reserved` 的峰值，以及各自对应的事件 ID。

### 2. 查看该事件时刻仍然活跃的 block

```bash
pt-snap query --template-use active_blocks_at_event --params '{"event_id": 1234, "include_static": true}'
```

`active_blocks_at_event` 认为 block 在 `event_id` 时刻仍然活跃的条件是：

- 动态 block：`allocEventId != -1 AND allocEventId <= event_id`，且 `freeEventId` 为 `NULL`、负数或大于 `event_id`
- 无分配事件的 block（`allocEventId = -1`）：`freeEventId` 为 `NULL`、负数或大于 `event_id`

当 `include_static=true` 时，还会包含无分配事件且在 `event_id` 时刻仍活跃的 block：

- `allocEventId=-1 AND freeEventId=-1` 标记为 `static`
- 其余无分配事件但存活的 block（例如快照采集前已分配、之后才释放）标记为 `preexisting_live_at_event`

### 3. 对该时刻的活跃内存做调用栈归因

```bash
pt-snap query --template-use active_memory_callstack_at_event --params '{"event_id": 1234, "include_static": true, "top_n": 20}' -n 22 --json
```

这个查询会：

- 先从 `event_id` 时刻的活跃 block 集合开始
- 把动态 block 回连到 `trace_entry_<device>` 的分配事件
- 按分配调用栈做聚合
- 对静态内存和 preexisting 内存单独分组，而不是伪造调用栈

`top_n` 只限制动态调用栈分组的数量；启用包含且实际存在的 `static` 和
`preexisting_live_at_event` 分组不受这层内部筛选限制。外层 `-n` 仍限制所有
输出行，可能裁掉特殊组或动态 top 组。对于有限正整数 `top_n=N` 且
`include_static=true`，使用 `-n N+2`（代入计算后的整数：`top_n=1` 配
`-n 3`，`top_n=20` 配 `-n 22`）。这只保证排名结果不被二次裁剪，不保证
动态全集完整。代表 block 查询有独立的 `limit` / `-n` 上限，不需要额外两行。

固定 `top_n` 时，增大 `-n` 不改变共有行及其百分比：分母是内部排名后、
外层行数截断前所包含分组的字节数。裁剪后的列表百分比之和可能不足 100%。
增大 `top_n` 则可能改变分母。宣称完整覆盖前应检查完整性标志；排名窗口已满
会保守地设置 `has_more=true`，即使动态组恰好只有 N 个。扩大窗口或使用
`--exact-total` 可消除这种不确定性。

### 4. 比较不同指标的峰值与 gap

```bash
pt-snap query --template-use allocator_gap
```

这个模板会报告：

- `allocated`、`active`、`reserved` 的峰值事件
- 它们是否发生在同一个事件
- 同一事件上的 gap，例如 `reserved - active`、`reserved - allocated`

这样可以避免误把不同事件上的峰值直接相减，并错误解释为同一时刻的碎片或缓存 gap。

## Report 命令

如果需要更高层的摘要，可以使用：

```bash
pt-snap report peak-memory [db_path] [--device <id>] [--metric active|allocated|reserved] [--include-static|--exclude-static] [--limit <n>] [--start-id <id>] [--end-id <id>] [--timeout <seconds>] [--json]
```

示例：

```bash
# 生成基于 active 峰值事件的文本报告
pt-snap report peak-memory /path/to/snapshot.db

# 改为查看 reserved 峰值
pt-snap report peak-memory /path/to/snapshot.db --metric reserved

# 输出机器可读 JSON
pt-snap report peak-memory /path/to/snapshot.db --json
```

这个 report 命令会组合：

- `allocator_gap`，其结果同时提供原有的六个 `peak_*` 字段
- `active_memory_callstack_at_event`

并输出人类可读摘要或 JSON。`--start-id/--end-id` 限制峰值选择；归因仍解析所选事件
完整活跃集合，包含更早分配。`--timeout`（或 `PT_SNAP_QUERY_TIMEOUT`）是递减的
**报告整体** deadline，不会在查询之间重置。JSON 新增峰值 `scope`、独立归因
`source_coverage`、`timeout_s` 与 `budget_scope="report_composition"`。

数据集报告只检查一次数据集，峰值选择与归因复用同一个已验证 fingerprint。
若在步骤之间或执行期间检测到 manifest 或成员变化，整个报告会失败；这是版本检查，
不是并发写入锁。所选区间只计算一次 counter 峰值。归因仍消耗同一个累计工作预算，
因此活跃集合很大时，即使单独峰值查询成功，报告仍可能合理地超出预算。

原有 `callstack_groups` 和 `percent_of_active_blocks` 数值保持不变。JSON 还会
返回归因的 `has_more`、`truncated`、`total_is_exact` 和 `effective_params`
（`event_id`、`include_static`、`min_size`、`top_n`）。动态分组恰好填满 `top_n`
窗口时会保守标记为**可能不完整**，即使实际上已包含所有分组；文本输出显示 partial。
可在有限预算内增大 `--limit`，用新结果替换旧结果，不要把不同排名窗口累加。
包含静态内存时，static 和 preexisting 分组是动态 `--limit` 上限之外的额外行。

`included_bytes` 是所有返回分组的字节总和。`percent_denominator: "included_bytes"`
说明行百分比是筛选、截断后集合的字节占比，而非全部 active 内存或块数量的占比。
`active_bytes_at_event` 是**所选 metric 对应事件**的 active counter，对 allocated
和 reserved 报告也一样。`coverage_percent` 为
`100 * included_bytes / active_bytes_at_event`；该 counter 缺失、非正数或没有事件时
为 `null`（文本显示 unknown）。覆盖率不是完整性标志：`--exclude-static` 可以在
没有截断时降低覆盖率，而满窗口即使覆盖率达到 100% 也仍可能不完整。
空 trace 返回空分组、零 included bytes 和未知覆盖率。

## JSON 输出

`--json` 向 stdout 写一个 JSON 对象。成功结果包含 `schema_version`（当前为 `1`）、
`ok: true` 以及命令字段：

| 分支 | 额外字段 |
|------|----------|
| 执行 | `db_path`、`focus_source`、`device_id`、`template`、`effective_params`、`semantics_version`、`total`、`returned`、`has_more`、`truncated`、`total_is_exact`、`timeout_s`、`rows` |
| `--list` | `category`、`templates`（`name`、`description`、`category`） |
| `--template-info` | 与 `get_template_info()` 对齐的模板元数据，另加 `template` |
| `capabilities` | `cli_version`、完整 `templates` 契约、`skills` |
| `overview` | `db_path`、`focus_source`、`devices`（`device_id`、`first_event_id`、`last_event_id`）、`import_metadata` |

`-n` 仍然限制 `rows` 与 `returned`。默认 `total` 等于 `returned`（本页行数）；
仅当本页就是完整匹配集合（`has_more` 为 false 且 `offset` 为 0）时
`total_is_exact` 为 true。`--exact-total` 计数匹配集合（忽略 `limit` / `offset` /
`top_n`）并设置 exactness；单库使用 SQL `COUNT`，数据集内建查询计数完整合并/去重后、
全局窗口前的匹配集合，不计数已截断的局部片行。单库路径存在有限
尾部 `LIMIT` 时，执行器会多取一行来设置 `has_more`，不必先做计数。CTE
内部的有限 `top_n` 不是尾部 `LIMIT`：排名窗口已满时会置 `has_more` /
`truncated`，避免把默认页报成完整集合；精确 `COUNT` 若等于 `returned`
则可清除该信号。`truncated` 表示本次响应不是完整匹配集合（`has_more`、
正 `offset`，或精确 `total` 大于 `returned`）。`timeout_s` 是生效的执行
超时秒数，未限制时为 `null`。`--timeout` / `PT_SNAP_QUERY_TIMEOUT` 是一次
QueryService 调用的共享预算（页面查询与可选 COUNT 共用），作用于所有
模板查询（含 `report peak-memory`），不改变行数上限。非数字的
`PT_SNAP_QUERY_TIMEOUT` 归为 `INVALID_PARAMETER`，不是 `QUERY_FAILED`。

`effective_params` 是应用默认值并按 `choices` 规范化后的参数。数据集 `limit` 表示
最终全局输出窗口上限（相同的正上限取小规则），不是逐片 SQL LIMIT；筛选/合并已经完成。
单库路径带 `-n` 时，`limit` 是与执行器相同的**尾部** SQL `LIMIT`：已声明的模板 `limit` 与 `-n`
取较小值；渲染后的 SQL 没有尾部 `LIMIT` 时追加 `-n`。CTE 内部的 `top_n`
仍是独立参数，不会改写 `limit`。
`--template-info --json` 包含 `semantics_version`、`interpretation_limits`
以及 `output_schema` 上的字段语义。

`event`、`block` 与 `allocation` 支持 `offset` 分页，在主排序后用 `id` 做稳定
次序。它们带 `limit` / `offset` 的截断列表应带着相同排序键提高 `offset` 续页。
`leak_detection` 也有稳定的 `id` 次序，但没有 `offset`，应遵循上文的
[完整候选窗口流程](#获取完整候选窗口)。增大 `-n` 是替换先前窗口，不是获取
不重叠的下一页。`has_more` 不代表支持 offset。
`active_memory_callstack_at_event` 没有 `offset`，`-n`
也无法突破 CTE 内的 `top_n`；该模板应增大 `top_n` 扩大窗口，并在包含静态组时
保持 `-n` 至少为 `top_n + 2`。新排名结果替换旧结果，不要拼接或累加重叠窗口。

`--json` 失败时 stdout 为空，stderr 为：

```json
{
  "schema_version": 1,
  "ok": false,
  "error": {
    "code": "TEMPLATE_NOT_FOUND",
    "message": "Template 'missing' not found",
    "hint": "Use 'pt-snap query --list --json' to list available templates."
  }
}
```

稳定错误码包括 `TEMPLATE_NOT_FOUND`、`INVALID_PARAMETER`、
`DATABASE_NOT_FOUND`、`DEVICE_NOT_FOUND` 和 `FOCUS_NOT_CONFIGURED`，退出码非零。
`pt-snap` 控制台入口的用法/解析错误（例如 `query -n abc --json`）也走同一信封，
错误码为 `INVALID_PARAMETER`，退出码 2。Click 在 `--json` 回调之前失败时，
该路径是 best-effort 的 argv 扫描：`--` 之前的精确 `--json` 词，且不是前一个
选项的值。`--opt=value` 与 `-1` 这类数字词不会吞掉下一个参数。
`pt-snap` 控制台入口返回 Typer/Click 的退出码（失败非零）。Ctrl-C / EOF
在文本模式向 stderr 写 `Aborted!`（退出码 1；Typer 返回 130 时为 130）。
带 `--json` 时 stdout 仍为空，stderr 为本信封（`ERROR`，message 为 `Aborted!`）。
文本模式保持不变：`Error:` 仍写到 stdout（包括缺失模板的 `--template-info`，它已经以退出码 1 失败）。

已有的 `metadata --json` 与 `report peak-memory --json` 字段名保持兼容。这两条命令在带 `--json` 失败时也使用同一套 stderr 错误信封。

## 输出格式

默认情况下显示所有结果。使用 `-n` 限制显示行数：

```
# 显示所有结果（默认）
pt-snap query --template-use leak_detection

# 仅显示前 5 条
pt-snap query --template-use leak_detection -n 5

# 显示所有结果（显式）
pt-snap query --template-use leak_detection -n 0
```

示例输出（使用 `-n 2`，默认 `total` 语义）：

```
Found 2 results, showing 2:
  {'id': 1, 'address': 4096, 'size': 2048, ...}
  {'id': 2, 'address': 8192, 'size': 4096, ...}
  ... more available (use -n, offset, top_n, or --exact-total)
```

加上 `--exact-total` 时，"Found N" 是匹配行总数，页脚可以给出剩余行数。
`SnapshotAnalyzer.execute_query()` 默认 `max_rows=None`（不截断）且
`exact_total=False`，与 CLI 在未指定 `-n` / `max_rows` 或 `--exact-total` /
`exact_total` 时一致。`timeout_s` 与行数上限相互独立。

CLI 和 Python API 的查询结果包含原始 SQLite 值。模板的 `output_schema`
只是 metadata，查询执行时不会自动应用。需要十六进制地址字符串等转换值时，
应显式调用 `ResultMapper`。结果行不重复字段说明；用 `--template-info`
（或 `get_template_info`）按产生这些行的模板查阅 `semantics_version` 与解释限制。
`SnapshotAnalyzer.execute_query()` 的结果还包含 `template` 与 `semantics_version`，
便于把行与契约对应起来。

## 模板架构

查询模板使用 YAML 格式定义，包含：
- `version`: YAML 文件格式版本，既不是字段语义契约，也不是 SnapshotDB schema 版本
- `queries`: 查询定义，包含描述、支持的设备、参数、SQL（Jinja2 模板语法）和输出 schema
- 每个参数声明 `type`、`default`、`required`、`description`，以及可选的 `choices`（允许取值的封闭列表；会被渲染为 SQL 标识符或关键字的参数必须声明它）
- 查询可选声明 `semantics_version`（正整数）和 `interpretation_limits`；`output_schema` 各列还可声明 `units`、`metric_semantics`、`scope`、`denominator`、`sentinel`、`interpretation_limits`
- `semantics_version` 是 Agent 应引用的解释契约。同一模板的 v1/v2 SQL 变体共享该契约。未同时声明两者时模板仍有效；未注解的 `output_schema` 条目仅含 `column` 与 `type`

封闭词表：

- `units`：`bytes`、`gib`、`percent`、`event_id`、`count`、`address`、`flag`、`text`
- `metric_semantics`：`instantaneous_occupancy`、`same_event_gap`、`share_of_included_rows`、`identifier`、`classification`、`ordering_marker`
- `scope`：`dynamic`、`static`、`preexisting`、`mixed`、`captured_range`、`same_event`。一列按行混合多种范围时用 `mixed`（见 `active_memory_callstack_at_event` 的 `category`）

显式传给 `ResultMapper` 时，可识别的映射类型包括 `int`、`float`、`str`、
`bool`、`hex` 和 `datetime`；当前 `datetime` 只是透传声明，不执行解析。

## 可选结果映射

可选的行转换和模型映射方式见 [ResultMapper API](result-mapper-api.md)。

高层编程式 focus 和查询门面见 [SnapshotAnalyzer API](snapshot-analyzer-api.md)。
