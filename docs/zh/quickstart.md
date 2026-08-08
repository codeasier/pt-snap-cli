# 快速开始

[English](../en/quickstart.md) | 中文

几分钟内即可上手 `pt-snap-cli`。

## 安装

从源码 checkout 安装：

```bash
pip install -e .
```

## 第一次分析

### 可选：导入 PyTorch 快照

如果你手上是原始 `.pkl` 内存快照，请先使用内建后端导入：

> **安全警告：** 只能使用可信的 pickle 输入。反序列化 pickle 可能执行任意代码；
> `pt-snap import` 不是沙箱。

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
- [MCP 服务器](mcp.md) — 使用 MCP 服务器进行 AI Agent 集成
- [数据库格式](database.md) — 了解 SnapshotDB 格式
- [SnapshotAnalyzer API](snapshot-analyzer-api.md) — 从 Python 查询 SnapshotDB 文件
