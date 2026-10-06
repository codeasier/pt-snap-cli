# 双向互操作验收与有界性能

中文 | [English](../en/interop-acceptance.md)

## 证据分层与固定目标

唯一上游目标是 **Ascend/msinsight@101f65b877a267ffd5f66ea3834706057ba243e5**。
协议/schema、隔离源函数、合成 CI、真实原版生产端产物的读取差分、GUI/C++ 实测是
不同证据层，不能互相替代。**GUI 已由人明确延期，待验收/not-run**；issue 保持开放。
已有说明见 [#205](https://github.com/codeasier/pt-snap-cli/issues/205#issuecomment-5987264017)，不重复发布。

验收工具是本地原创接口事实/独立参考实现，没有复制 vendor 实现。
固定 [生产 schema](https://api.github.com/repos/Ascend/msinsight/git/blobs/1fe50a5136f85365db55f4632d58f3cf7090431e)、
[manifest/回填](https://api.github.com/repos/Ascend/msinsight/git/blobs/95612509ef990ac6b7034919dae4938cc6acf3ad)、
[parser 判据](https://api.github.com/repos/Ascend/msinsight/git/blobs/40046e6a92ff5af776ee55bd4cdd4586745af3c2)、
[salt 顺序](https://api.github.com/repos/Ascend/msinsight/git/blobs/ca421c7b33f3a0050df9e7a01e666f558801bc2f)
为接口事实来源。Ascend 源码 Mulan PSL v2、上游 docs 单独 CC BY 4.0，不自动属于
本项目 MIT lineage。真正移植须走 snapshot provenance/PR 声明并保留 notices。
可执行 pickle 的信任是独立 fixture 审核；本验收不新增已提交 pickle。

## 正向：可信源 → 物理兼容导出 → 未来 GUI

1. 先独立审核/信任源：pickle 可执行，不是沙箱。记录 SHA256、大小、设备与容量。
   默认 import 仍单库，原生/兼容模式显式区分。
2. 目标必须不存在。未来 GUI 支持入口要求产物邻接**同一原始 pickle**：

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
4. **将来另经人明确授权后**，使用记录的真实 GUI build 打开同一原始 pickle，补下方清单。
   物理或 salted hash 相等都不等于 GUI 缓存复用通过。

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

小型独立 oracle 显式物化有限数据（文件总32 MiB、256目录项、64片、含边界的20000条
物理 trace、20000条 block、逐片256 dictionary 行、1 MiB JSON、可选2 MiB源）。这些是
参考工具界限，不是产品 RSS 承诺。它比较全部真实列、完整 alloc/free_completed 来源、
canonical 生命周期/最新状态、终片候选、最早 tie 的全局及逐片峰值、指定点活跃集合/字节、
全部 action 栈统计与全局排序/分页/精确总数。canonical 单库不是又一次原版生产端执行。
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

## 未来 GUI 清单——全部待验收 / NOT-RUN

- [ ] 精确真实version/build/commit/package SHA、解释器/server来源、环境、启动/open命令；不猜可执行语法。
- [ ] 同一原始pickle路径/hash/size、邻接complete产物；打开前后全部manifest/member/hash清单，源不变。
- [ ] UP_TO_DATE/cache-reuse日志、没有producer/parser脚本调用，并有足以发现重建的process/log观察；hash不足以证明。
- [ ] 指定点的曲线/counter/range/真实ID（排除边界），block/size/state及跨片alloc/free_completed来源详情。
- [ ] 仅实际recognized覆盖允许ordered frame声明，原版文本产物保持text-only；不可用展示如实记录。
- [ ] 派生allocation cache修改单独检查：可能不运行生产端就改DB并使ptSnap证明失效；保留前后清单，
  不能修复/覆盖原版缓存来让reuse通过。

schema/合成/原版产物读取和静态skill评分不能勾选GUI项；本验收包不执行/编译GUI或C++。
