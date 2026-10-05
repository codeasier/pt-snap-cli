# 快速开始

[English](../en/quickstart.md) | 中文

几分钟内即可上手 `pt-snap-cli`。

## 安装

```bash
pip install pt-snap-cli
```

这会安装 `pt-snap` 命令行工具。从源码 checkout 开发时，可使用
`pip install -e ".[dev]"`；详见仓库 README 的[开发](../../README_zh.md#开发)一节。

## 第一次分析

### 可选：导入 PyTorch 快照

如果你手上是原始 `.pkl` 内存快照，请先使用内建后端导入：

> **安全警告：** 只能使用可信的 pickle 输入。反序列化 pickle 可能执行任意代码；
> 实现会拒绝非 builtins 全局对象，但 `pt-snap import` 不是沙箱。

```bash
pt-snap import snapshot.pkl
pt-snap metadata snapshot.pkl.db
pt-snap query --list
```

导入命令会在数据库内保存原始文件的 SHA-256 和导入兼容性 metadata。再次使用相同设备配置
导入相同内容时，会直接复用已有 DB。如需明确重建，可使用：

```bash
pt-snap import snapshot.pkl --force
```

当前导入流程会先完整加载 pickle，再开始处理，因此内存峰值可能明显高于输入文件大小，
具体取决于对象图和 frame 数量。导入大型快照时请预留充足内存。`--device` 只能减少
后续回放和数据库写入量，无法降低最初加载 pickle 时的内存峰值。

导入时，pt-snap 会回放所选设备的分配器历史，而不是直接复制原始事件。生成的
SnapshotDB 会记录每个事件后的 `allocated`、`active`、`reserved` 总量和 block
生命周期，供 `pt-snap query` 与 `pt-snap report` 使用。回放是命令工作流的一部分；
快照运行时的 Python 模块不是公开 API。

### 可选：导入原生分库数据集

```bash
pt-snap import snapshot.pkl --events-per-slice 50000 --output-dir captures --json
pt-snap overview captures/snapshot.pkl.pt-snap-native-v2 --json
pt-snap query --template-use event --slice 0 --json
```

不指定 `--events-per-slice` 时仍生成已有单 DB；指定后生成
`<output-dir>/<完整输入文件名>.pt-snap-native-v2/`，省略 `--output-dir` 则放在源文件旁。
此模式可显式指定 `--format pt-snap-native-v2`；`--format single-db` 不允许容量参数。
原生产物**不是** msinsight 兼容导出；显式 `--format msinsight`（别名
`compatibility-v1`）选择下述独立兼容模式。

容量按**各设备**的真实时间顺序位置计数，不使用 `max(id)+1`，不计负 ID 合成边界。
保留原始稀疏/非零 ID、OOM 和 workspace 事件。`--device` 选择一个有事件设备，默认
导入全部有事件设备；空/仅静态及未选设备位置由 `omitted_devices` 披露。选择空设备或
全部为空的输入会失败。分库不限制 pickle 加载、registry/block 行数或峰值 RSS。

缓存复用须校验完整 manifest 与**全部**已关闭成员，并匹配源 SHA256、设备选择、容量、
原生格式、manifest、导入语义、扩展及 metadata/布局合同版本。仅 CLI 发布版本变化不会
重建；原生身份与后续兼容格式及 msinsight salted `cacheHash` 分离。JSON 增加
`dataset_path`、`devices`、`slice_count`、`format`、`omitted_devices`、`reused` 和
`rebuilt`；此模式下 `db_path` 为数据集目录。

匹配目标可复用；不同或成员损坏的已识别原生数据集会保留，除非显式 `--force` 替换。
未知目录、无关额外文件、非法 manifest 和符号链接目标即使 force 也不会被接管或删除，
请换一个 `--output-dir`。所有设备/分片在目标同级暂存，完成回填、关闭、metadata 写入与
校验，并在发布前复核源哈希；部分就绪片不构成缓存。

新目标使用排他的目录 rename 发布。force 先把旧产物移入所有权受检的恢复目录，再发布
新产物；**路径有短暂空档，不是单次原子 swap**。请求的项目 focus 纳入补偿，写入已修改
文件后才抛错也要处理：普通失败恢复旧产物及旧 focus 原始字节/状态（或原先不存在）。
`--no-focus` 完全跳过 focus。回滚自身失败会保留并明确报告恢复路径，检查证据前不要删除。
不保证任意 I/O 故障、并发 writer 或崩溃下无条件原子恢复。

数据集 focus 当前只支持有界 `event` 寻址，不会静默在一片上运行峰值/生命周期/聚合。
详见[原生 manifest 合同](sharded-snapshotdb.md#已发布原生数据集p2)。
`SnapshotAnalyzer` 仍只负责分析，不新增 import/split 方法。

### 可选：导出 msinsight 兼容数据集

```bash
pt-snap import snapshot.pkl --format msinsight --json
pt-snap overview snapshot.pkl.msinsight --json
pt-snap query --template-use event --slice 0 --json
```

此**显式**模式仅对齐 `Ascend/msinsight@101f65b877a267ffd5f66ea3834706057ba243e5`
的原始 pickle 导入入口，不是独立目录入口。GUI 发现要求同一原始 pickle 邻接
`<完整输入文件名>.msinsight/`；pt-snap 可在没有 pickle 时分析已搬迁完整产物。
可选 `--events-per-slice N` 默认 `500000`；`--output-dir` 选择其他父目录，不意味着
GUI 支持独立入口。`--device` 选择有事件设备，并披露省略设备。非零/稀疏真实 ID、
OOM/未知 action、空/仅静态选择明确失败，不静默映射；原生模式仍保留稀疏 ID、OOM、
workspace。可信 pickle 与完整加载的内存成本仍适用。

基础表是物理内联 v1 表，metadata import format 为 `1`。调用栈文本按**每个事件**
复制，不按不同栈只存一次，磁盘与暂存转换空间可能明显增加；原生去重不变。
不从格式化文本虚构有序结构化 frames。数据集当前只支持有界 `event` 查询。

兼容发布采用 **no-replace**：外部/原版/用户缓存即使 `--force` 也不覆盖、不删除。
仅完整、已证明且身份相同的 pt-snap 缓存可复用（force 也复用）；否则换新
`--output-dir`。源内容、sourceFile、选项、全部成员哈希和合同版本须独立于 salted
`cacheHash` 匹配。GUI 修改派生缓存可能使该证明失效，但不等于重跑生产者。
全部暂存成员关闭/最终化/校验后才排他发布并写请求的 focus；普通失败补偿旧 focus
原始字节，回滚失败则保留恢复证据。单库/原生 force 策略不变，`SnapshotAnalyzer` 只分析。

**GUI 待验收/未运行。** complete/ready、安全路径/设备表及派生 allocation cache
存在或可构建同样重要；hash 相同不证明 GUI 复用或显示一致。详见
[兼容协议及固定源码证据](sharded-snapshotdb.md#显式-msinsight-兼容导出p2)。

### 可选：拆分快照

如需生成更小、可独立回放的文件，可使用 `pt-snap split`。该命令不会读取或修改 focus：

```bash
pt-snap split snapshot.pkl --max-entries 50000 --output snapshot-slices
```

`--slices` 和 `--max-entries` 必须且只能指定一个。多设备行为、格式、命名和原子发布
保证见[拆分快照](splitting.md)。

### 第一步：设置快照数据库和设备

将 `pt-snap` 指向你的 SQLite 快照数据库文件：

```bash
pt-snap focus snapshot.pkl.db --device 0
```

该命令会验证数据库，并将路径和设备 ID 保存到当前目录的 `.pt-snap/focus.json`，之后无需重复指定。

如果只需设置数据库（暂不指定设备）：

```bash
pt-snap focus snapshot.pkl.db
```

### 第二步：列出可用查询

```bash
pt-snap query --list
```

### 第三步：运行查询

```bash
pt-snap query --template-use memory_peak
```

### 第四步：尝试高级查询

```bash
# 检测潜在内存泄漏
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'

# 查询自动使用 focus 中设置的设备，也可以显式覆盖
pt-snap query --template-use block --device 0 --params '{"min_size": 1048576}'
```

## 下一步

- [Focus 管理](focus-management.md) — 学习如何在多个项目和会话之间管理数据库和设备焦点
- [运行查询](querying.md) — 查询流程、模板发现、参数和输出说明
- [拆分快照](splitting.md) — 创建可独立回放的逐设备切片
- [Agent Skills](skills.md) — 将随包 agent 工作流安装到共享 agents 目录和 Claude
- [数据库格式](database.md) — 了解 SnapshotDB 格式
- [SnapshotAnalyzer API](snapshot-analyzer-api.md) — 从 Python 查询 SnapshotDB 文件
