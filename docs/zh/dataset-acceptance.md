# 数据集正确性及默认规模验收

数据集测试区分三类证据。合成 SQL 夹具通过，不代表生产端、采集器或导出器已运行。

## 常规正确性门禁

`tests/core/test_dataset_realistic.py` 默认在兼容 v1 和原生 v2 两种布局上各执行
20 个确定性种子；夜间配置将同一批种子扩展至 200 个。原有八个回归种子及二十种
查询形态完整保留。每个种子每种布局运行 69–73 个查询用例（20 种子共 2,896 次
成对比较，200 种子共 28,864 次），覆盖十一个文本查询契约。
帧树由 `test_dataset_frame_tree.py` 单独验证真实导入的单库/数据集对齐、递归、跨片来源、
损坏、预算及只读守恒；仅 `event_frames` 保留明确数据集拒绝测试，
不会计为差分成功。

两种布局使用相同的独立生成 80-event 历史，并分别与同布局单库 SQL 参考结果比较。
容量 2/3/4/5/10/16 产生 5–40 片，包括非满尾片。原生夹具包含真实局部栈引用、
最终 block-reference 表、元数据和成员 hash，并通过实际原生 reader 校验；栈 ID
在不同片间变化。这是合成 reader/query 证据，不代表执行了原生 replay/export。
每片只包含窗口内新分配及进入窗口时仍存活的生命周期，已完成释放的生命周期
不进入后续窗口，全局分配和完成释放 ID 不变。每个种子均含地址复用、
preexisting/static、NULL/空/空白栈、字面量缺失栈标签，以及分离的请求释放与完成
释放事件。首尾、分片、请求/完成释放、复用等关键边界在两种 static 策略下均查询，
并独立对照生成模型的 active ID、大小和计数器。

随机参数覆盖合法事件范围、筛选、排序、offset/limit、`max_rows`、`top_n`、
`include_static` 和两种 `exact_total`。event/allocation/peak/gap 查询还覆盖
首片、尾片及随机片范围。每个种子固定包含空页、完整页、截断页及越过结果尾部的
分页。多片用例断言实际构建 scratch reducer，而非仅凭片数推断；查询后核对
输入 hash 不变，且没有 SQLite 写 sidecar。

所有比较严格相等，包括四位小数百分比。1-byte / 127-byte 最小用例要求 `0.7813`，
8-MiB 倍率另检查六位小数 GiB 舍入。契约是与当前 SQLite 运行时的运算及 `ROUND`
严格一致，不是数学上的 half-up 近似。3/2,000,000、7/2,000,000 比例、临近值及大数
GiB 转换都以同一运行时的单库 SQL 为参考，因为 SQLite 版本间的二进制浮点格式化
可能不同。标量舍入使用短生命周期且显式关闭的内存连接，不读取来源或创建合并表；
两个舍入阶段的超时测试也验证连接/cursor 关闭。公共 schema 比较排除
数据集独有来源元数据。定点 block 的存储 `state` 是观察值，不是该事件时刻状态；
全局 block 两侧都采用最后一个包含该生命周期的窗口观察。

另一个双设备原生 v2 用例执行真实 replay/import，再附加明确构造的有序 frame 扩展。
不同成员中的相同局部栈 ID 不得合并不同有序数组；顺序、重复项及额外原始 frame
字段都与输入数组核对。公共事件/block 字段与单库 SQL 比较；该扩展夹具不声称原生
writer 会生成有序 frames。

```bash
pytest tests/test_fixture_provenance.py
pytest tests/core/test_dataset_realistic.py tests/core/test_dataset_attribution.py tests/core/test_dataset_global.py
```

定时/手动 CI 的 `dataset-acceptance` job 在安装包 nightly 门禁之后，另行执行
必需的 200 种子差分步骤。`.github/scripts/run_differential_acceptance.py` 严格
验证 400 个不同的已执行测试 ID、全部 200 个预期种子的两种布局、JUnit 与逐种子
覆盖记录一致、预期比较数/模板数、零个意外错误及实际 scratch 执行。skip、缺失/
重复用例、旧报告或证据不一致均导致 job 失败。源码 SHA、摘要、日志、XML 和种子
timeline/coverage/failure JSON 始终上传为 `differential-acceptance-<commit>`；生成的
SQLite 可由种子复现，不存入 CI artifact。该步骤属于源码查询验收；
安装包证据仍由单独门禁提供。

### 种子配置与复现

在目标 checkout/解释器中执行；`PYTHONPATH="$PWD/src"` 可选择独立 worktree，
无需改变其他目录的 editable 安装：

```bash
# PR/默认：20 种子、两种布局，以及生成器/参考比较器校验
PYTHONPATH="$PWD/src" pytest tests/core/test_dataset_differential_cases.py tests/core/test_dataset_realistic.py

# 夜间：200 种子，保留逐种子证据及 JUnit 属性
PYTHONPATH="$PWD/src" PT_SNAP_DIFFERENTIAL_SEEDS=200 pytest \
  tests/core/test_dataset_realistic.py -k seeded \
  --basetemp=test_reports/differential --junitxml=test_reports/differential.xml \
  -o junit_family=xunit1

# 复现单个种子和布局；单种子配置优先于种子数量
PYTHONPATH="$PWD/src" PT_SNAP_DIFFERENTIAL_SEED=196 pytest \
  tests/core/test_dataset_realistic.py -k 'seeded and v2'
```

`PT_SNAP_DIFFERENTIAL_SEEDS` 接受 1–10,000；`PT_SNAP_DIFFERENTIAL_SEED` 接受
0–2^63−1。非法或空值导致 collection 失败，不会静默跳过。种子列表先保留原八个
回归种子，再按升序补充不重复整数；200 种子严格包含默认集合。pytest 的
`--basetemp` 是可丢弃目录，下一次运行时会清空。

每个成功种子写入 `timeline.json`、`coverage.json`，记录种子、布局、容量、片数、
比较数、模板、实际 scratch 构建次数及零个意外错误；JUnit 包含同样的覆盖属性。
失败时输出种子/格式/参数及复现命令，并在 `differential-failure.json` 保存两边
完整结果或异常详情。单边错误及两边同时错误均失败。预期的不支持模板拒绝另行
验证。诊断 CI 失败时应保留 XML 和临时目录产物。

这里的终片泄漏候选等价性只适用于已证明、成员符合窗口的历史，所有存活分配均
出现在终片；不消除 inactive、仅早期片出现或 unproved 历史上单库/dataset 的
有意区别。`test_dataset_lifecycle_contract.py` 保留 attached SQL、scratch、有界
fallback 三条路径的这些契约。`top_n=0` 完整性另有空/static/dynamic/混合用例，
覆盖两种布局和 reducer。

## slow 规模及安装包导出门禁

`tests/core/test_dataset_scale_acceptance.py` 标记为 `slow`，包括：

- 合成兼容 v1 SQLite：1,000,000 个真实事件，两个默认大小的 500,000-event 成员，
  block 成员符合生命周期窗口。全局 peak、gap、event/allocation 分页、block 分页及
  终片泄漏候选及栈聚合必须在真实默认工作预算内成功；无界物化仍需触发真实行数上限。测试不调低
  或关闭预算。有序 frame 聚合可能仍需有界原始 frame 回退路径；此门禁不声称所有
  大规模有序 frame 或无界输出查询均可成功。
- 独立 10,000-event / 8-KiB 内联栈数据集验证聚合/小页成功，以及完整输出触发真实
  64-MiB 上限，无需创建 8-GB 数据文件。
- 受信、测试自行构造的 1,000,000 个 alloc/free-request/free-completion 事件快照，
  经干净 venv 中安装的 `pt-snap import --format msinsight`，**不覆盖容量默认值**，
  生成两个完整的 500,000-event 成员。所有已安装目录模板均被分类：12 个支持数据集的
  模板核对 CLI/API 一致性及独立结果。帧树模板及 `memory-tree` 报告成功，并验证根节点/自身占用守恒；仅 `event_frames` 保留数据集拒绝。
- 第二个必需的安装包用例保留原有 500,002-event 工作负载及 500,000 + 2 成员布局，
  验证跨界完成生命周期、最终存活分配、分页及定点事件结果。两个安装包用例均要求
  查询前后输入、manifest 及成员 hash 不变。

按照[分发包构建说明](../../README_zh.md#构建分发包)，从目标干净 checkout 构建 wheel：

```bash
pytest tests/test_fixture_provenance.py
PT_SNAP_ACCEPTANCE_WHEEL="$(realpath dist/<built-wheel>.whl)" \
  pytest tests/core/test_dataset_scale_acceptance.py --junitxml=dataset-acceptance.xml
```

将 `<built-wheel>` 替换为实际名称。每个安装包用例创建独立且不含系统包的全新 venv，
安装该确切 wheel 及运行依赖，清除源码 `PYTHONPATH`，并核对产品包和运行依赖均来自
该 venv。依赖安装可能访问包索引。可将 `PT_SNAP_ACCEPTANCE_WHEELHOUSE` 指向包含兼容
依赖 wheel 的目录，以 `--no-index --find-links` 离线安装。
未设置 `PT_SNAP_ACCEPTANCE_WHEEL` 时，两个安装包用例均明确 skip；skip 不算 E2E 通过。
完整 PR 层使用 `pytest -m 'not nightly'`；兼容层使用
`pytest -m 'not slow and not nightly'`。

百万事件安装包用例写入 `acceptance.json` 和 `dataset_acceptance` JUnit 属性，包含
wheel/source hash、运行环境身份、事件数量及命令/查询证据。短终片用例单独保存其证据。
`PT_SNAP_ACCEPTANCE_EVIDENCE_DIR` 可指定持久证据目录，否则使用 pytest 临时目录。
必需的 nightly runner 拒绝缺失或未通过的用例。耗时仅为观察记录；这些安装包用例
不设固定时限，也不承诺进程 RSS。

## 证据边界

[历史性能基线](../dataset-performance-baseline.json) 使用 581,140-byte 已审核快照及
容量 2,000；分片模式仅 8,092 个真实事件、五片。保留此历史证据，但它不能证明默认
容量可扩展性。

新增导出门禁在可审查的测试输入上执行真实第一方 replay/export/query 链路；不执行
实时 PyTorch/NPU 采集、上游 msinsight 生产端或 GUI，这些验收仍独立。未增加任何提交
到仓库的 pickle。provenance 门禁在收集测试前运行；临时受信输入在测试期间自行写入。

## 并发读取与进程中断

`tests/core/test_dataset_concurrency.py` 对同一份合成数据集分别启动两个和四个
独立读取者，覆盖线程、spawn 子进程，以及 ATTACH 和 scratch 两条路径。
屏障位于实际 SQLite 读取或 scratch 插入完成之后，保证所有读取者同时持有各自的
查询资源。完整结果必须一致，scratch 目录必须互不相同且在正常完成后移除，源文件
哈希必须保持不变。这不代表同一个 analyzer 或其 SQLite 连接可以跨线程共享。

`tests/test_dataset_signal_boundaries.py` 在实际 scratch 插入完成后向 CLI 发送
真实 POSIX 信号。正常完成和 SIGINT 会展开产品资源并移除 scratch。
**目前 SIGTERM 和 SIGKILL 会直接终止进程，未执行上述清理，私有
`pt-snap-lifecycle-*` 目录及 `derived.db` 会残留。** 测试明确记录这一限制，
不会把测试清理当作产品清理，也不宣称已经满足 issue #252 的 kill 后无残留目标。
源文件哈希保持不变，不发布部分查询结果。本次未引入信号处理器、启动回收或自动删除策略。

这些小规模、确定性测试进入常规套件（信号用例仅限 POSIX）。超时及错误的清理与
进程被直接终止是不同边界：Python 异常展开不能证明 SIGTERM 或 SIGKILL 会执行
`finally`。

`tests/test_dataset_mutation_acceptance.py` 在 spawn 子进程中的 CLI/API 查询实际
读取第一片的行或计数之后暂停，由父进程原地修改测试自有成员。默认强校验和显式
immutable 缓存模式都必须拒绝已变更的 generation，不发布部分行或计数。
未变更的运行必须成功且符合独立计算的结果。哈希工作量断言明确兼容 v1 的冷/热查询成本：
默认分别对每个 manifest/成员扫描三次/两次（准入加最终检查）；POSIX immutable
模式对成员分别扫描一次/零次，对 manifest 分别扫描两次/零次。最终检查本身在默认模式
增加一次完整扫描，在纯元数据 immutable 模式不增加哈希扫描，并共用查询 deadline。
非 POSIX 上的 immutable 请求不会根据创建时间复用准入：冷/热查询都对每个成员扫描
两次、对 manifest 扫描三次，包含完整的最终哈希检查。默认强校验在非 POSIX 上仍可复用
经过内容验证的热准入。测试还通过仅替换 resolver 的平台对象，确定性覆盖这一保守策略；
此模拟不是实际 Windows 执行证据。
这是工作量断言，不是固定耗时或 RSS 保证。检查会检测这些受控变更，但不会创建原子文件系统
快照，也不证明所有先变更再恢复的竞态都能被检测。
