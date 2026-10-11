# 数据集正确性及默认规模验收

数据集测试区分三类证据。合成 SQL 夹具通过，不代表生产端、采集器或导出器已运行。

## 常规正确性门禁

`tests/core/test_dataset_realistic.py` 默认在兼容 v1 和原生 v2 两种布局上各执行
20 个确定性种子；夜间配置将同一批种子扩展至 200 个。原有八个回归种子及二十种
查询形态完整保留。每个种子每种布局运行 69–73 个查询用例（20 种子共 2,896 次
成对比较，200 种子共 28,864 次），覆盖全部十一个 dataset 支持模板。
仅单库支持的 `event_frames`、`active_memory_frame_tree_at_event` 另有明确拒绝测试，
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
- 受信、测试自行构造的 500,002 个 alloc/free-request/free-completion 事件快照，
  经非 editable 安装的 `pt-snap import --format msinsight`，**不覆盖容量默认值**。
  先核对 500,000 + 2 成员布局及跨界生命周期，再通过该安装包的 CLI/API 验证峰值、
  分页、终片候选、定点事件及报告。查询前后产物 hash 必须不变。

按照[分发包构建说明](../../README_zh.md#构建分发包)，从目标干净 checkout 构建 wheel：

```bash
pytest tests/test_fixture_provenance.py
PT_SNAP_ACCEPTANCE_WHEEL="$(realpath dist/<built-wheel>.whl)" \
  pytest tests/core/test_dataset_scale_acceptance.py --junitxml=dataset-acceptance.xml
```

将 `<built-wheel>` 替换为实际名称。测试以 `--no-deps --no-index` 将该确切 wheel 安装到
临时目录，子进程清除源码 `PYTHONPATH` 并核对 `pt_snap_cli` 来自该安装目录。运行依赖
复用测试解释器环境，不代表全新依赖解析测试。未设置 `PT_SNAP_ACCEPTANCE_WHEEL` 时，
仅安装包用例明确 skip；skip 不算 E2E 通过。常规套件可用 `pytest -m 'not slow'`。

安装包用例在 pytest 临时目录写 `acceptance.json`，并记录 `dataset_acceptance` JUnit
属性，包括 wheel/source SHA-256、包路径、事件数量、导入耗时及查询断言。耗时只是
单次观察，不设固定时限断言，也不承诺进程 RSS。

## 证据边界

[历史性能基线](../dataset-performance-baseline.json) 使用 581,140-byte 已审核快照及
容量 2,000；分片模式仅 8,092 个真实事件、五片。保留此历史证据，但它不能证明默认
容量可扩展性。

新增导出门禁在可审查的测试输入上执行真实第一方 replay/export/query 链路；不执行
实时 PyTorch/NPU 采集、上游 msinsight 生产端或 GUI，这些验收仍独立。未增加任何提交
到仓库的 pickle。provenance 门禁在收集测试前运行；临时受信输入在测试期间自行写入。
