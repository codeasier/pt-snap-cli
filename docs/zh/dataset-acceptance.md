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
- 受信、测试自行构造的 1,000,000 个 alloc/free-request/free-completion 事件快照，
  经干净 venv 中安装的 `pt-snap import --format msinsight`，**不覆盖容量默认值**，
  生成两个完整的 500,000-event 成员。所有已安装目录模板均被分类：11 个支持数据集的
  模板核对 CLI/API 一致性及独立结果；`event_frames` 和
  `active_memory_frame_tree_at_event` 保留明确的数据集拒绝。`peak-memory` 报告成功，
  `memory-tree` 保留数据集拒绝。
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
