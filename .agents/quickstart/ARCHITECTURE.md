# pt-snap-analyzer 架构概览

## 项目定位

PyTorch Memory Snapshot Analysis Tool - 用于分析 PyTorch 内存快照的命令行工具。

## 核心架构

```
pt_snap_analyzer/
├── cli.py          # CLI 入口，提供 pt-snap 命令
├── context.py      # 数据库上下文管理
├── models/         # 数据模型定义
└── query/          # 查询引擎
```

## 模块依赖关系

```
CLI (cli.py)
  ↓
Context (context.py) → SQLite 数据库连接
  ↓
Query 模块
  ├── QueryExecutor   # 查询执行器
  ├── QueryBuilder    # SQL 构建器
  ├── QueryMapper     # 结果映射器
  ├── Condition       # 条件表达式
  └── Registry        # 模板注册表
  ↓
Models 模块
  ├── Block          # 内存块
  └── Event          # 内存事件
```

## 数据流

1. **CLI 接收命令** → 解析参数
2. **Context 加载数据库** → 只读模式连接 SQLite
3. **Query 执行查询** → 使用模板或自定义查询
4. **Models 组织结果** → 结构化输出

## 关键设计决策

- **只读数据库访问**：确保分析过程不修改原始快照数据
- **模板化查询**：预定义查询模板（leak_detection、callstack_analysis 等）
- **Fluent API**：QueryBuilder 提供链式调用接口
- **设备隔离**：支持多 GPU 设备的数据分离

## 快速导航

- [CLI 模块详情](01-cli.md) - 命令行接口
- [Context 模块详情](02-context.md) - 数据库上下文
- [Models 模块详情](03-models.md) - 数据模型
- [Query 模块详情](04-query.md) - 查询引擎

## 典型使用场景

```bash
# 1. 设置数据库
pt-snap use snapshot.pkl.db

# 2. 执行泄漏检测
pt-snap query snapshot.pkl.db --template leak_detection

# 3. 调用栈分析
pt-snap query snapshot.pkl.db --template callstack_analysis
```

## 相关文件

- [README.md](../../README.md) - 使用指南
- [pyproject.toml](../../pyproject.toml) - 项目配置
