# 快速开始

[English](../en/quickstart.md) | 中文

几分钟内即可上手 `pt-snap-cli`。

## 安装

```bash
pip install -e .
```

## 第一次分析

### 第一步：设置快照数据库

将 `pt-snap` 指向你的 SQLite 快照数据库文件：

```bash
pt-snap use examples/snapshot_expandable.pkl.db
```

该命令会验证数据库，并将路径保存到当前目录的 `.pt-snap/context.json`，之后无需重复指定。

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

# 查看设备 0 上的活跃内存块
pt-snap query --template-use active_blocks --device 0
```

## 下一步

- [Context 管理](context-management.md) — 学习如何在多个项目和会话之间管理数据库
- [运行查询](querying.md) — 所有查询模板、参数和输出的完整指南
- [数据库格式](database.md) — 了解 SnapshotDB 格式
