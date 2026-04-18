# 快速开始

[English](../en/quickstart.md) | 中文

几分钟内即可上手 `pt-snap-cli`。

## 安装

```bash
pip install -e .
```

## 第一次分析

### 第一步：设置快照数据库和设备

将 `pt-snap` 指向你的 SQLite 快照数据库文件：

```bash
pt-snap focus examples/snapshot_expandable.pkl.db --device 0
```

该命令会验证数据库，并将路径和设备 ID 保存到当前目录的 `.pt-snap/focus.json`，之后无需重复指定。

如果只需设置数据库（暂不指定设备）：

```bash
pt-snap focus examples/snapshot_expandable.pkl.db
```

### 第二步：列出可用查询

```bash
pt-snap query --list
```

### 第三步：运行查询

```bash
pt-snap query --template-use memory_summary
```

### 第四步：尝试高级查询

```bash
# 检测潜在内存泄漏
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'

# 查询自动使用 focus 中设置的设备，也可以显式覆盖
pt-snap query --template-use active_blocks --device 1
```

## 下一步

- [Focus 管理](focus-management.md) — 学习如何在多个项目和会话之间管理数据库和设备焦点
- [运行查询](querying.md) — 所有查询模板、参数和输出的完整指南
- [数据库格式](database.md) — 了解 SnapshotDB 格式
