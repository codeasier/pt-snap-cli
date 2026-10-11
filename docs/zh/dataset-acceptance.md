# 数据集正确性及默认规模验收

数据集测试区分三类证据。合成 SQL 夹具通过，不代表生产端、采集器或导出器已运行。

## 常规正确性门禁

`tests/core/test_dataset_realistic.py` 对八个固定种子各运行二十种查询形态，并与单库
参考结果比较。每片仅包含窗口内新分配及进入窗口时仍存活的 block；已完成释放的
生命周期不进入后续窗口，全局分配/完成释放 ID 保持不变。覆盖地址复用、跨窗口
pending free、preexisting/static、NULL/空/空白栈、字面量缺失栈标签、排序、分页、
筛选及动态组 `top_n` 截断。

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
