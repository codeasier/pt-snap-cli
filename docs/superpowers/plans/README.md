# pt-snap-analyzer 开发计划

这篇文档整理了 pt-snap-analyzer 的完整开发计划，按照功能模块解耦拆分为多个独立的计划。

## 计划概览

| 计划名称 | 说明 | 文件 |
|---------|------|------|
| **基础架构** | 构建 CLI 框架、数据模型和核心 Context | [2026-04-04-pt-snap-analyzer-foundation.md](./2026-04-04-pt-snap-analyzer-foundation.md) |
| **分析器模块** | 实现核心分析器：泄漏检测、峰值分析、趋势分析、调用栈分析 | [2026-04-04-pt-snap-analyzer-analyzers.md](./2026-04-04-pt-snap-analyzer-analyzers.md) |
| **查询系统** | 实现 YAML 配置的 SQL 模板和查询执行器 | [2026-04-04-pt-snap-analyzer-query.md](./2026-04-04-pt-snap-analyzer-query.md) |
| **RAG 知识库** | 实现案例归档、向量搜索和相似案例检索 | [2026-04-04-pt-snap-analyzer-rag.md](./2026-04-04-pt-snap-analyzer-rag.md) |

## 计划详情

### 1. 基础架构

**Goal**: 构建 CLI 框架、数据模型和核心 Context，提供基础 API 支撑

**Tech Stack**: Python 3.10+, Typer, Pydantic, SQLite3

**主要内容**:
- 项目初始化和配置（pyproject.toml, __init__.py）
- 数据模型：枚举类型、MemoryEvent、MemoryBlock
- Context 类：数据库连接管理
- CLI 框架：命令结构和子命令
- 集成测试

**文件结构**:
```
pt_snap_analyzer/
├── __init__.py
├── cli.py
├── context.py
├── models/
│   ├── _enums.py
│   ├── event.py
│   ├── block.py
│   └── result.py (基础类)
└── version.py
```

**测试目标**: 15+ tests, 覆盖率 > 80%

---

### 2. 分析器模块

**Goal**: 实现核心分析器模块：泄漏检测、峰值分析、趋势分析、调用栈分析

**Tech Stack**: Python 3.10+, SQLite3, Pydantic

**主要内容**:
- 分析器基类和结果模型
- LeakDetector：泄漏检测
- PeakAnalyzer：峰值分析
- TrendAnalyzer：趋势分析
- StackAnalyzer：调用栈分析
- CLI 集成

**文件结构**:
```
pt_snap_analyzer/
├── analyzers/
│   ├── base.py
│   ├── leak_detector.py
│   ├── peak_analyzer.py
│   ├── trend_analyzer.py
│   └── stack_analyzer.py
└── models/
    ├── result.py
    ├── leak.py
    ├── peak.py
    ├── trend.py
    └── stack.py
```

**测试目标**: 20+ tests, 覆盖率 > 80%

---

### 3. 查询系统

**Goal**: 实现查询配置系统，支持 YAML 配置的 SQL 模板和查询执行器

**Tech Stack**: Python 3.10+, SQLite3, PyYAML, Jinja2

**主要内容**:
- 查询配置加载器（QueryConfigLoader）
- 查询执行器（QueryExecutor）
- 预定义 SQL 模板
- CLI 命令集成

**文件结构**:
```
pt_snap_analyzer/
└── query/
    ├── config.py
    ├── executor.py
    └── templates/
        ├── leak_detection_v2.yaml
        ├── memory_timeline_v2.yaml
        └── callstack_analysis_v2.yaml
```

**测试目标**: 25+ tests, 覆盖率 > 80%

---

### 4. RAG 知识库

**Goal**: 实现 RAG 知识库，支持案例归档、向量搜索和相似案例检索

**Tech Stack**: Python 3.10+, ChromaDB

**主要内容**:
- RAG 数据模型（RAGCase, SearchResult 等）
- 案例归档系统（CaseArchive）
- 案例检索系统（Searcher）
- CLI 命令集成
- SDK API

**文件结构**:
```
pt_snap_analyzer/
└── rag/
    ├── models.py
    ├── archive.py
    └── searcher.py
```

**测试目标**: 33+ tests, 覆盖率 > 80%

---

## 执行方式

每个计划都使用 **writing-plans** 技术编写，包含详细的步骤和代码示例。执行时可以选择：

### 1. Subagent-Driven（推荐）

每个任务由独立的 subagent 执行，任务间进行审查，快速迭代开发。

### 2. Inline Execution

在当前会话中执行任务，使用 executing-plans，批次执行加检查点。

---

## 运行测试

每个计划完成后都需要运行测试：

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/ -v
```

---

## 开发顺序建议

推荐按照以下顺序开发：

1. **基础架构** → 2. **分析器模块** → 3. **查询系统** → 4. **RAG 知识库**

这样可以确保基础功能先行，逐步添加高级功能。

---

## 文件清单

| 文件 | 描述 |
|------|------|
| [2026-04-04-pt-snap-analyzer-foundation.md](./2026-04-04-pt-snap-analyzer-foundation.md) | 基础架构计划 |
| [2026-04-04-pt-snap-analyzer-analyzers.md](./2026-04-04-pt-snap-analyzer-analyzers.md) | 分析器模块计划 |
| [2026-04-04-pt-snap-analyzer-query.md](./2026-04-04-pt-snap-analyzer-query.md) | 查询系统计划 |
| [2026-04-04-pt-snap-analyzer-rag.md](./2026-04-04-pt-snap-analyzer-rag.md) | RAG 知识库计划 |

---

## 相关文档

- [PRD 文档](../prds/2026-04-04-pt-snap-analyzer-prd.md) - 产品需求文档
- [设计文档](../specs/2026-04-04-pt-snap-analyzer-design.md) - 系统设计文档
- [DB Schema](../../snapshot_db_schema.md) - 数据库 schema 定义

---

## 下一步

选择一个计划开始执行：

1. 基础架构计划
2. 分析器模块计划
3. 查询系统计划
4. RAG 知识库计划

推荐从 **基础架构计划** 开始，建立项目框架。
