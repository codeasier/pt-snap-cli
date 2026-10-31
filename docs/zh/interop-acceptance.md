# 双向互操作验收与有界性能

中文 | [English](../en/interop-acceptance.md)

## 证据分层与固定目标

历史 parser-v2 验收与物理 schema 参考使用
**Ascend/msinsight@101f65b877a267ffd5f66ea3834706057ba243e5**，
它不是当前 parser-v3 导出已验证的消费端目标。
协议/schema、隔离源函数、合成 CI、真实原版生产端产物的读取差分、GUI/C++ 实测是
不同证据层，不能互相替代。**2026-10-11 的有界真实 GUI/C++ 与原版生产端反向验收已通过**，
详见下方记录。[#205 待验收说明](https://github.com/codeasier/pt-snap-cli/issues/205#issuecomment-5987264017)
保留此前人工延期阶段的历史，不代表本次当前状态。本证据本身不关闭 issue，也不批准发行。

验收工具是本地原创接口事实/独立参考实现，没有复制 vendor 实现。
固定 [生产 schema](https://api.github.com/repos/Ascend/msinsight/git/blobs/1fe50a5136f85365db55f4632d58f3cf7090431e)、
[manifest/回填](https://api.github.com/repos/Ascend/msinsight/git/blobs/95612509ef990ac6b7034919dae4938cc6acf3ad)、
[parser 判据](https://api.github.com/repos/Ascend/msinsight/git/blobs/40046e6a92ff5af776ee55bd4cdd4586745af3c2)、
[salt 顺序](https://api.github.com/repos/Ascend/msinsight/git/blobs/ca421c7b33f3a0050df9e7a01e666f558801bc2f)
为接口事实来源。Ascend 源码 Mulan PSL v2、上游 docs 单独 CC BY 4.0，不自动属于
本项目 MIT lineage。真正移植须走 snapshot provenance/PR 声明并保留 notices。
可执行 pickle 的信任是独立 fixture 审核；本验收不新增已提交 pickle。

## 当前 parser-v3 状态与安全重验

当前导出使用 `mem_snapshot_parser_v3`，历史固定消费端使用 `mem_snapshot_parser_v2`，
v3 hash 不匹配时**必然重解析**；该路径先删除 manifest/log，再调用生产者。
不要让旧 GUI 打开唯一的源/缓存副本。历史字段 `ptSnap.identity.targetRevision`
是 schema/接口参考身份，不是消费端支持证明。已核上游 master
[`5c722719e1d288106f8d18588b0a33d979a4065b`](https://api.github.com/repos/Ascend/msinsight/git/blobs/20254ee06471a4acb3757893263d042dd5df47e8)
也仍计算 v2 salt 并拒绝不匹配的 cache hash。因此与这些已核消费端的复用是确定不兼容，
不只是尚未实测；尚未选择任何已验证的 v3 消费端目标。

当前 v3 GUI 缓存复用声明必须满足以下全部条件：

1. 明确不可变消费端 commit 与准确 build，执行前检查 parser salt、manifest/成员/schema
   检查与重解析路径。仅版本标签、当前分支名或旧 v2 GUI receipt 都不足够。
2. 获得该次真实 GUI 运行的明确授权。在新的隔离目录中使用另行信任的 pickle 的字节一致
   副本，并由候选 wheel 生成新的邻接导出。不要搬移或覆盖原缓存，也不要改标签伪装 v2 hash；
   应重新导出。打开前记录源、wheel、manifest、成员 hash 以及设备/容量，
   并核对 `manifest.sourceFile` 指向 pickle 副本的绝对路径。
3. 只用指定 build 打开该可丢弃源/缓存对，保存 `UP_TO_DATE` 与无生产者调用证据，
   对照曲线/block、首尾及跨片事件边界，覆盖重复导航与取消。记录运行后 hash，并区分
   允许的消费端派生缓存、基础数据变更和 parser 重跑。
4. 当前 v3 结果与下方历史 receipt 分开保存。产物 runner 的严格 `saltedCacheHash` 门禁
   会拒绝把旧 v2 receipt 用于 v3 导出；不得修改历史 receipt 或放宽 hash 校验。

本文尚未接受任何当前 v3 消费端 build 或真实 GUI 运行。

## 历史 v2 正向：可信源 → 物理兼容导出 → 真实 GUI

以下固定历史验收使用 `mem_snapshot_parser_v2`，当前导出已使用
`mem_snapshot_parser_v3`；历史 GUI 结果不代表新版解析器已验收。下方命令只记录旧运行，
不是让当前 CLI 对接旧 GUI 的安全操作指引；当前 CLI 执行它们会生成 v3。
新验收请用上方隔离副本方案，不要复用历史缓存/消费端组合。

1. 先独立审核/信任源：pickle 可执行，不是沙箱。记录 SHA256、大小、设备与容量。
   默认 import 仍单库，原生/兼容模式显式区分。
2. 目标必须不存在。GUI 支持入口要求产物邻接**同一原始 pickle**：

   ```bash
   pt-snap import /capture/snapshot.pkl --format msinsight --events-per-slice 2000 --device 0 --no-focus --json
   pt-snap overview /capture/snapshot.pkl.msinsight --json
   ```

   `--format compatibility-v1` 为别名；`--output-dir` 换父目录并不创建 GUI 直接导入目录
   的入口。即使 force 也不覆盖原版/外部缓存，只复用已识别且身份完全相同的 pt-snap
   产物；成员变化使证明失效。`cacheHash=SHA256(b"mem_snapshot_parser_v2" + 原始字节)`
   与源/选项/格式/语义版本/成员构成的 `ptSnap.identity` 独立。
3. 对同源、同选项的已有已审原版产物，逐片比较基础 schema/dictionary、全部九列真实
   event、ID/区间/action/stream/counter/文本及生命周期。非负 block ID **包括0**和七字段
   必须完全相等。负 block ID 是生产端局部 token：全局及逐片比较其余六字段**包括 state**
   的 MULTISET，保留重复数量，并独立验证每份产物的 token 跨片稳定性。这不证明跨生产端
   的负对象身份。不能按地址去重、改写 ID 或修补固定原版源码来制造等价。
4. 获得真实验收的明确授权后，使用记录的真实 GUI build 打开同一原始 pickle，记录下方证据。
   仅物理或 salted hash 相等不等于 GUI 缓存复用通过；2026-10-11 已另行实测真实消费端。

## 反向：已有原版产物 → 完整 focus → canonical 参考

runner 不下载/执行生产端。原版产物必须已经存在、关闭且最终化，并有已审 receipt。
允许没有 metadata/reference/frame 扩展：有效返回为 `unavailable` / `metadata_missing`，
只能记录未知来源，不能捏造 metadata。invalid、未完成校验及未知 reason 都停止。

```bash
pt-snap focus /capture/snapshot.pkl.msinsight/manifest.json --device 0 --json
pt-snap capabilities --json
pt-snap overview /capture/snapshot.pkl.msinsight --json
pt-snap query /capture/snapshot.pkl.msinsight --device 0 --template-use memory_peak --json
pt-snap report peak-memory /capture/snapshot.pkl.msinsight --device 0 --metric reserved --start-id 0 --end-id 100 --limit 20 --json
```

focus 持久化项目选择，应在明确批准的隔离验收项目使用。诊断 skills 本身不写 focus、
不导入/安装。整份数据集 scope 只接受完整校验的目录/manifest，不接受任意目录或单个 ready 片。
明确选择的单成员仍可按单库策略读取，但不是整份数据集 scope。
已关闭兼容 v1 通过 immutable 只读 SQLite 接受 checkpoint 后无 sidecar 的 WAL header；
所有别名及存活/悬空 WAL/SHM/journal 在打开前拒绝。原生仍拒绝持久 WAL；单库仍
`mode=ro`，不加 immutable。

在仓库根目录用预期解释器运行可选本地工具：

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python benchmarks/interop_acceptance.py \
  --artifact /capture/snapshot.pkl.msinsight --receipt /evidence/reviewed-receipt.json \
  --source /capture/snapshot.pkl --device 0 --output /evidence/NEW-acceptance
```

可选 `--compatible /export/snapshot.pkl.msinsight` 比较**已有**正向产物，绝不自动生成。
receipt 字段为完整固定 SHA `revision`、全部相对普通成员路径→SHA256 的 `artifactHashes`；
可选源/正向检查另要求 `fixtureSHA256`、`fixtureBytes`、`saltedCacheHash`。
receipt 真实性依赖调用者审核，hash 本身不能证明生产端身份。源只计算 hash，不反序列化。
在任何 SQLite/产品打开前及之后核对全部成员/hash/sidecar，成员变化失败。
输出必须全新、规范、无符号链接且不与输入重叠；只在其中创建物理 canonical-reference DB、
报告和隔离测试项目 focus，不改外部 focus/cache，不下载/执行生产端。

独立物理 SQL 参考显式物化有限数据（文件总32 MiB、256目录项、64片、含边界的20000条
物理 trace、20000条 block、逐片256 dictionary 行、1 MiB JSON、可选2 MiB源）。这些是
参考工具界限，不是产品 RSS 承诺。它比较全部真实列、完整 alloc/free_completed 来源、
canonical 生命周期/最新状态、终片候选、最早 tie 的全局及逐片峰值、指定点活跃集合/字节、
全部 action 栈统计与全局排序/分页/精确总数。canonical 单库不是又一次原版生产端执行。
活跃归因比较在该参考库上复用产品单库查询实现，是差分检查，不是活跃归因的完全独立第二 oracle。
控制台链在切换隔离 CWD 前后验证同一解释器/相同 API 源路径，再运行真实 focus/query/report
并规范化 CLI/API scope/覆盖。报告记录实际选择的点/区间，不宣称枚举每个 event 的活跃集合。

## 确定性 CI 场景与限制

`pytest tests/test_interop_acceptance.py tests/test_dataset_import_baseline.py
 tests/skills tests/test_bundled_skills.py` 使用小型生成 SQLite 或已有已审/合成运行时 fixture，
不依赖网络、GUI、NPU、live model 或私有绝对基线路径。任何已提交 pickle 运行前先执行
`tests/test_fixture_provenance.py`。下列 owning suites 仍属于门禁：

| 场景 | 确定性回归/口径 |
| --- | --- |
| 长寿命跨多片、地址复用、pending free、静态/预存/未知 | `tests/core/test_dataset_attribution.py`、`test_dataset_global.py`；按已证生命周期而非地址去重，free_completed 而非 free_requested |
| expandable、多设备、原生稀疏/非零 ID、OOM/workspace | `tests/snapshot/test_sharded_replay.py`、`tests/test_native_dataset.py`、`tests/core/test_msinsight_export.py`；原生保留，v1 明确拒绝 OOM/稀疏/非零 ID；原版 OOM 强制转换/workspace raw-frame 丢失不是通过功能 |
| 有序 frames | 只读 ptSnapOrderedFrames v1、实际 schema/覆盖、有限合法类型JSON/深度128/顺序/重复；缺失/未知/未覆盖→text-only，不生成/重建，不冒称原版生产 frames |
| 源/选项/格式/语义身份、成员变化、外部缓存 no-replace | 已有原生/兼容导入 suites 加验收测试；GUI 派生 DB 修改使证明失效，不证明重跑生产端 |
| 写库/回填/转换/源复核/发布/focus/rollback 失败 | `tests/core/test_dataset_import_failures.py`、`test_import_backend_failures.py`、`test_msinsight_export.py` 及分片回放；检查真实旧目标/focus/recovery 字节，不能只检查抛异常 |
| 全11内建、CLI/API/report、分页/预算 | 新物理参考与 `test_dataset_global.py`；自定义 SQL/同名 override 不支持，借用 LRU/终止关闭/handler 清理保持 |

使用同一 YAML catalog 的 `dataset_support` 和声明的可选字段。区间 `scope.range_complete`
与定点 `scope.source_coverage.range_complete`、来源/frame 覆盖及 `has_more/truncated` 独立。
数据集 canonical `source_stack_id` 不是局部 stack ID；代表行优先非空文本。缺引用、字面
missing label、非NULL空文本活动组不能混同。`callstack_analysis` 语义 v2 的旧字段
`alloc_count` 统计全部真实带栈 action，不是 alloc-only，`total_size` 为活动量而非存活字节。
百分比分母保持过滤/top-N 后、caller 行上限前的 included group bytes（单库 SQL / 数据集 post-merge，#179），不使用全 active
计数器。报告 gap/归因/active coverage 来自同一 selected metric event。一次 query/report
共用递减时间及累计100000 fetched/output行、64 MiB序列化值，**不是 RSS**；失败不能给出
部分的虚假全局结论。

## 三片 free-requested fixture

[pt-snap-cli #249](https://github.com/codeasier/pt-snap-cli/issues/249) 在
[`tests/fixtures/interop/`](../../tests/fixtures/interop/README.md) 增加最小合成生产端
fixture：单设备、三个真实事件、三个分片，由真实 CLI 配合 `--events-per-slice 1`
生成。allocation 0、free_requested 1、free_completed 2 各只属于一个分片。
不新增已提交的可执行 pickle，也不引入第三方生产端代码。来源、生成身份、隐私/权利审核、
大小/hash 和限制均记录在该目录的 provenance 中。

```bash
PYTHONPATH="$PWD/src" python -m pytest tests/test_fixture_provenance.py
PYTHONPATH="$PWD/src" python -m pytest tests/test_interop_three_shard.py
PYTHONPATH="$PWD/src" python tests/fixtures/interop/generate_three_shard.py \
  --output /tmp/NEW-three-shard-interop
```

输出目录必须不存在。生成器仅从可检查的 JSON 自建合成 pickle，以
`--device 0 --events-per-slice 1 --no-focus` 分别调用真实 `pt-snap import`：
`msinsight`（compatibility-v1，内联调用栈）与 `pt-snap-native-v2`（interned 调用栈）。
不打开 GUI、不运行原版生产端。已提交的 v1 产物在只读测试打开前校验 checksum；
新生成结果复现物理语义，不承诺含时间/路径/版本差异的逐字节相等。

回归检查事件唯一归属、全部九个物理 event 字段、完整栈文本和 block 引用。
free-requested 行为 ID 1、action 5、address 4096、size 16、stream 7，
allocated/active/reserved 计数器为 0/16/64 字节（消费端的
Caching Allocated/Active/Reserved 字段）。Block 0 保留
`allocEventId=0`、`freeEventId=2`；后者指向 **completed** free。
现有消费端只查当前片的 predicate 在片 0/2 找不到 event 1。
独立 SQL oracle 先按 manifest 寻找与 `allocEventId < id < freeEventId` 相交的候选片；
`freeEventId < 0` 时查到该设备最后一个真实事件，再按 action/address 与相同边界过滤。
另设 v1/v2 地址复用及 open-ended pending-free/allocated 测试，防止关联后一次生命周期，
并校验应返回唯一事件或无事件。原有九事件 `lifecycle_data` 包含 OOM，故不用作此最小
v1 fixture；既有完整回放覆盖继续保留。

另行获准 GUI 复测时，应使用新生成的原始 `three_shard_free_requested.pkl` 及其邻接
`.msinsight` 目录。不要让会写派生缓存表的消费端修改已提交的只读 fixture。
不宣称 native-v2 是 msinsight GUI 输入。本项仅验证生产端/fixture 契约，
没有修复或验证 [msinsight #625](https://gitcode.com/Ascend/msinsight/issues/625)，
也不覆盖下方带日期验收记录中的消费端限制。

## 性能：相同已审小样本，三模式

测量使用 `snapshot_expandable.pkl`，581140字节，SHA256
`3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40`，device0/capacity2000。
旧 `baseline_import.py --samples 8k` 实际选择不同的多设备 fixture，不能当作同样本原版对照。

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_fixture_provenance.py
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python benchmarks/dataset_import_baseline.py \
  --source tests/fixtures/snapshots/snapshot_expandable.pkl \
  --sha256 3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40 \
  --device 0 --capacity 2000 --output /evidence/NEW-three-mode --trusted-pickle
```

这是显式可信 pickle 执行同意，不是自动诊断步骤。不安装/重指 editable、不加载默认大样本、
不重跑原版生产端、不 cleanup。每个 cold/reuse 使用新隔离子进程；cold 是全新输出、无warmup，
不是清空 OS page cache。reuse 必须是本次成功 cold 的未变所有产物，cache miss 禁止重建/覆盖；
同源/模式/phase所有权在 pickle 执行前检查。记录完整命令/退出/错误日志、source/head/script hash、
Python/platform 和全部11查询延迟。[机器可读本地观测](../dataset-performance-baseline.json) 仅存
去私有路径后的测量数据，不是速度断言或 CI 数值 oracle。
同名支持查询的 scope 不一定相同：本次默认单库 `allocation` 返回8094行
（8092真实+2合成边界），数据集全局只返回8092真实行；event定位选择显式真实ID。
解读延迟/行数必须保留差异，不能因模板名称相同就宣称逻辑范围完全相等。

整次 import wall 与实际包装的 load/replay/SQLite/backfill/conversion **inclusive函数时间**不同。
新子进程 RUSAGE_SELF 高水位在 import 结束、查询开始前采集，Darwin原始字节÷1024为KiB，
再÷1024为MiB，包含解释器/import开销。load/replay逐阶段RSS及未插桩剩余阶段时间明确
**unavailable**并给原因，不能减累计高水位，也不能用父进程/上一个子进程的 RUSAGE_CHILDREN。
总磁盘/逐片/重复block行/查询延迟实测，逐行物理page成本不可用。pickle仍整体加载，长寿命block
和兼容内联栈会重复，query hash/scan可能占主导。不承诺未测速度/RSS/磁盘收益。
已有原版唯一冷wall0.160545s没有RSS/phase测量，不是受控比较性能基线。

## 真实验收记录——2026-10-11

[去敏机器可读 receipt](../interop-acceptance-2026-10-11.json) 记录精确身份、依赖 pin、
成员清单和有界结果。它是实测摘要，不是可分发的原始产物，也不能替代 receipt 真实性审核。
不包含截图、协议原始调用栈、私有路径、账户或完整日志。

### 构建与输入身份

- 固定上游 `101f65b877a267ffd5f66ea3834706057ba243e5`，tracked source 干净。
  Linux x86_64、GCC 14.2.0、CMake 3.31.6、Ninja 1.11.1.4、Node 24.19.0。
  仅构建 production framework、Leaks 和 `profiler_server`。前端使用 pnpm 11.25.0、
  frozen lockfile、原有 hoist 规则、strict SSL、禁用 lifecycle scripts；未修改源码/锁文件。
- Server SHA256：`7b1c2325d88d709ad111faad458422099fd34b7f574ba557f9e0643a0108b64f`。
  在隔离 server 目录运行 `./profiler_server --wsPort=9000 --wsHost=127.0.0.1`，
  `LD_LIBRARY_PATH` 指向该目录，并启用完整进程跟踪。
  动态库 hash 和 libuv/uSockets/uWebSockets/RapidJSON/SQLite pin 见 receipt。
  RapidJSON 记录的是本次本地依赖 commit，不是上游历史依赖 pin；不宣称逐字节复现发行包。
- 非 editable wheel：`0.0.post1.dev1`，SHA256
  `884a13f08f65e866cd106c0a80f218d289269da10e9f623f1b0779cafdc67f9a`；
  全部110个已安装 package 成员匹配。其源码 tree 对应
  `cd1aac689f653e2701334d26ae1f25489f7f5af9`，不代表后续 main commit 或已发布 PyPI 版本验过。
- 已审 `snapshot_expandable.pkl`：581140字节，SHA256
  `3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40`；
  device 0，每片2000 events。反序列化前 fixture provenance 测试7/7通过。
  pickle 执行仍需独立信任审核。

### 正向 GUI/C++ 结果与保留情况

- [x] 真实 framework/Leaks GUI 打开原始 pickle 及邻接完整五片 pt-snap 导出。
  Window 1 → 2 → 1 → 4 切换、生命周期曲线、reserved 线及五窗总览正常展示。
  Window 4 展示 event 7430 的 allocated/active 峰值（597642080字节 = 569.956 MiB；
  GUI 标签实际为 `569.956 MB`）。
- [x] Server 记录 `UP_TO_DATE`（state 4）。从启动到终止的完整进程跟踪只有一次 server
  可执行文件启动，无 parser/Python producer 执行。另行反向 producer 运行不属于这份 trace。
- [x] Block 1669（37632字节）从 Window 2 定位 Window 1 的 allocation 1669，
  从 Window 1 定位 Window 2 的 completed-free 2605。Block 详情自动关联 free-requested
  event 2604 时只查询当前片：Window 1 详情缺失，Window 2 存在。这不表示按 event ID
  直接定位不能跨片；本次没有额外从该独立路径查询2604。如实记录 block 详情限制，未修补它。
- [x] 同一已加载的真实 C++ server 通过16个 query cases / 167条 typed assertions，
  零失败/query error。协议采样覆盖前两片的 curve/reserved 端点、events 1999/2000、
  裁剪 block 区间及跨片详情。1999/2000 状态分别为801/802 blocks、
  419457080/419465784 allocated字节。`maxSize` 是 reserved 展示尺度，不是 allocated 峰值。
- [x] 五个 runtime shard 的原表 schema 与全部原行保持一致；两份源和 runtime manifest 不变。
  **Runtime DB 字节已变化**：消费端逐片新增 `memory_allocation_cache_v1_0`，导致未变
  manifest 内的 ptSnap 成员证明失效。另存的 pre-GUI 导出仍逐字节不变。未修复/重新导入
  来隐藏此修改；缓存复用并不表示打开后的产物不可变。
- [x] 实际调用栈仍为 text-only，未重建 ordered frames；运行后 GUI/server/私有 HTTP 服务均已停止。

### 反向结果与限制

另行执行一次未改动的固定原版 producer，最终生成五片、8092真实 events。已安装 wheel
通过全部11内建模板、物理 SQL/参考比较及真实隔离 CLI/API focus/query/report 检查。
数量为10条排除边界、6412物理 block 行、3219 canonical 生命周期、3193重复行、
325终片候选、60个全 action 栈组。选择12个记录点和6个区间，没有穷举每个 event 的活跃集合。
活跃归因在 canonical DB 上复用产品单库查询，因此不是完全独立第二 oracle。

正向 pre-GUI 与原版产物的物理比较通过：全部九列真实 event、schema/dictionary、
精确真实 ID 和负 token 六字段/state multiset。负对象身份不跨生产端成立。
原版 metadata 正确返回 `unavailable` / `metadata_missing`，frames 仍 text-only。
反向原版产物、正向比较副本、源字节及 producer 源码在只读分析后均未变。

[benchmarks/interop_acceptance.py](../../benchmarks/interop_acceptance.py) 只读取已有产物；
其中 `GUI=human-deferred/pending/not-run` 和 `original_producer=not-run by this runner`
说明该工具自身范围，保留原值，不伪装成 runner 执行过 GUI 或 producer。带日期 receipt
汇总分别实测的阶段。复现有界只读比较请使用上面的命令、[fixture 审核](../../tests/fixtures/AGENTS.md)
及另行审核的 receipt；hash 本身不能重建原 manifest 路径，也不能认证执行。

本次不覆盖全部插件、已发行桌面包、GPU/NPU 执行、多设备、穷举 GUI 交互、故障注入或性能改善。
广泛失败/rollback 场景仍依赖上方 owning tests。历史合成检查与性能观测继续作为独立证据；
本次 docs-only 记录不改变运行时行为。
