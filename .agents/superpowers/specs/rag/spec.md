# Spec: pt-snap-analyzer RAG 知识库

**Goal:** 实现 RAG 知识库，支持案例归档、向量搜索和相似案例检索

**Architecture:** 使用 ChromaDB 存储向量，简单的关键词搜索作为备用，CLI 和 SDK 双接口

**Tech Stack:** Python 3.10+, ChromaDB, LangChain（可选）

---

## Why

### 当前痛点
- 内存问题分析经验无法沉淀，每次遇到类似问题都要重新分析
- 专家知识分散在各个开发者脑中，没有系统化的知识库
- 相似案例无法快速检索，重复劳动严重
- AI 辅助分析缺少上下文，无法提供精准建议

### 需要解决的问题
- 建立案例归档系统，将分析过程和结论结构化存储
- 实现智能检索，支持语义搜索和相似度匹配
- 提供 CLI 和 SDK 双接口，便于集成到工作流
- 支持标签分类，便于案例管理和过滤

### 预期的业务价值
- 案例检索时间从小时级降低到分钟级
- 减少 70% 以上的重复分析工作
- 沉淀专家经验，提升团队整体效率
- 为 AI 辅助分析提供知识基础

---

## What Changes

### 新增功能/模块
- RAG 数据模型：AnalysisStep, RAGCase, SearchMatch, SearchResult
- CaseArchive：案例归档系统
- Searcher：案例检索系统
- CLI 命令：rag-add, rag-search, rag-list, rag-tags
- SDK API：Python 接口

### 修改的组件
- `pt_snap_analyzer/cli.py` - 新增 RAG 命令
- `pt_snap_analyzer/__init__.py` - 导出 RAG 模块

### 删除的功能
- 无

### 技术架构变更
- 引入 ChromaDB 向量数据库
- 引入案例归档和检索机制

---

## Impact

### 影响的规格文档
- foundation/spec.md - 依赖 Context 类
- analyzers/spec.md - 依赖分析结果

### 影响的代码模块
- `pt_snap_analyzer/rag/__init__.py` - 新增：包初始化
- `pt_snap_analyzer/rag/models.py` - 新增：RAG 数据模型
- `pt_snap_analyzer/rag/archive.py` - 新增：案例归档
- `pt_snap_analyzer/rag/searcher.py` - 新增：案例检索
- `pt_snap_analyzer/rag/vector_store.py` - 新增：向量存储（可选）

### 影响的依赖
- `chromadb>=0.4.0` - 已有：向量数据库
- `langchain>=0.1.0` - 已有：AI 框架（可选使用）

### 影响的配置
- 归档目录：`~/.local/share/pt-snap-analyzer/rag_archive`
- 向量存储目录：`~/.local/share/pt-snap-analyzer/rag_vectors`

---

## ADDED Requirements

### Requirement: RAGCase 案例模型
系统 SHALL 定义案例数据模型：

- case_id: 唯一标识（自动生成）
- timestamp: 创建时间
- db_snapshot: 快照数据库路径
- analysis_steps: 分析步骤列表
- conclusion: 结论
- root_cause: 根本原因
- solution: 解决方案
- tags: 标签列表
- confidence: 置信度（0-1）
- verified_by: 验证者
- metadata: 额外元数据

#### Scenario: 创建案例
- **GIVEN** 分析完成的案例数据
- **WHEN** 创建 RAGCase 实例
- **THEN** 自动生成 case_id 和 timestamp

### Requirement: CaseArchive 归档系统
系统 SHALL 实现案例归档系统：

- add_case(case: RAGCase) -> str: 添加案例
- get_case(case_id: str) -> RAGCase: 获取案例
- list_cases(tags=None) -> List[RAGCase]: 列出案例
- delete_case(case_id: str) -> bool: 删除案例
- get_tags() -> List[str]: 获取所有标签

#### Scenario: 归档案例
- **GIVEN** 有效的 RAGCase 实例
- **WHEN** 调用 add_case(case)
- **THEN** 返回 case_id，案例持久化存储

#### Scenario: 标签过滤
- **GIVEN** 案例库包含多个案例
- **WHEN** 调用 list_cases(tags=["leak", "cuda"])
- **THEN** 返回同时包含这两个标签的案例（AND 逻辑）

### Requirement: Searcher 检索系统
系统 SHALL 实现案例检索系统：

- search(query: str, top_k=5, tags=None) -> SearchResult: 搜索案例
- _score_case(case: RAGCase, query: str) -> Tuple[float, List[str]]: 评分
- _normalize_text(text: str) -> str: 文本规范化
- get_tags() -> List[str]: 获取标签

#### Scenario: 关键词搜索
- **GIVEN** 案例库包含相关案例
- **WHEN** 调用 search("memory leak cuda 0", top_k=5)
- **THEN** 返回相关案例，按相关性排序

#### Scenario: 向量搜索（可选）
- **GIVEN** 启用了 ChromaDB 向量搜索
- **WHEN** 调用 search(query)
- **THEN** 返回语义相似的案例

### Requirement: 案例存储格式
系统 SHALL 定义案例存储格式：

- 存储格式：JSON
- 存储目录：`~/.local/share/pt-snap-analyzer/rag_archive`
- 文件命名：`{case_id}.json`
- 序列化：包含所有字段

#### Scenario: 案例持久化
- **GIVEN** 案例已添加
- **WHEN** 系统重启
- **THEN** 案例仍然存在且可检索

### Requirement: CLI 命令
系统 SHALL 提供 CLI 命令：

- `rag-add <file.json>`: 添加案例
- `rag-search <query>`: 搜索案例
- `rag-list [--tags TAG1,TAG2]`: 列出案例
- `rag-tags`: 列出所有标签

#### Scenario: 添加案例
- **GIVEN** JSON 格式的案例文件
- **WHEN** 执行 `pt-snap rag-add case.json`
- **THEN** 案例添加到知识库

#### Scenario: 搜索案例
- **GIVEN** 案例库包含数据
- **WHEN** 执行 `pt-snap rag-search "leak"`
- **THEN** 显示匹配的案例

---

## MODIFIED Requirements
无

## REMOVED Requirements
无

---

## 1. Overview

### 1.1 Purpose
构建 RAG 知识库系统，支持 PyTorch 内存问题案例的归档、搜索和检索，提供 AI 辅助分析能力。

### 1.2 Scope
- RAG 数据模型定义
- 案例归档系统
- 案例检索系统（关键词 + 向量）
- CLI 命令集成
- SDK API 设计

---

## 2. Technical Architecture

### 2.1 File Structure
```
pt_snap_analyzer/
├── rag/
│   ├── __init__.py       # Package exports
│   ├── models.py         # RAG data models
│   ├── archive.py        # Case archive system
│   ├── searcher.py       # Case search system
│   └── vector_store.py   # Vector store (optional)
└── cli.py                # Add RAG commands
```

### 2.2 Data Models

#### AnalysisStep
**A step in the analysis process**

**Attributes:**
- `step: int` - Step number
- `command: str` - Command executed
- `parameters: Dict` - Command parameters
- `result_summary: str` - Summary of results
- `description: str` - Step description

#### RAGCase
**A case in the RAG knowledge base**

**Attributes:**
- `case_id: str` - Unique case identifier (auto-generated UUID)
- `timestamp: str` - ISO 8601 timestamp
- `db_snapshot: str` - Path to the snapshot database
- `analysis_steps: List[AnalysisStep]` - Analysis steps
- `conclusion: str` - Final conclusion
- `root_cause: str` - Root cause analysis
- `solution: str` - Solution or workaround
- `tags: List[str]` - Tags for filtering
- `confidence: float` - Confidence level (0-1)
- `verified_by: str` - Who verified the case
- `metadata: Dict` - Additional metadata

**Key Methods:**
- `__post_init__()` - Generate case_id and timestamp
- `to_dict()` -> Dict - Serialize to dictionary
- `from_dict(data)` -> RAGCase - Deserialize from dictionary

#### SearchMatch
**A matched case from search**

**Attributes:**
- `case: RAGCase` - The matched case
- `score: float` - Relevance score (0-1)
- `query_match: List[str]` - Which query terms matched

#### SearchResult
**Result of RAG search**

**Attributes:**
- `matches: List[SearchMatch]` - Matched cases
- `total_results: int` - Total number of matches
- `query: str` - Original search query

### 2.3 Case Archive System

#### CaseArchive Class
**Manages case storage and retrieval**

**Responsibilities:**
- Store and retrieve RAG cases
- Filter cases by tags
- Validate case data
- Serialize/deserialize cases

**Key Methods:**
- `add_case(case: RAGCase) -> str` - Add a case
- `get_case(case_id: str) -> Optional[RAGCase]` - Get case by ID
- `list_cases(tags=None) -> List[RAGCase]` - List cases with filter
- `delete_case(case_id: str) -> bool` - Delete a case
- `_case_to_dict(case) -> Dict` - Serialize case
- `_dict_to_case(data) -> RAGCase` - Deserialize case
- `_get_archive_dir() -> Path` - Get archive directory

### 2.4 Searcher System

#### Searcher Class
**Searches for similar cases**

**Responsibilities:**
- Search for similar cases
- Score cases against query
- Filter by tags
- Return ranked results

**Key Methods:**
- `search(query: str, top_k=5, tags=None) -> SearchResult` - Search
- `_score_case(case: RAGCase, query: str) -> Tuple[float, List[str]]` - Score
- `_normalize_text(text: str) -> str` - Normalize text
- `get_tags() -> List[str]` - Get all tags

**Search Strategy:**

1. **Keyword-based search:**
   - Normalize text (lowercase, remove accents)
   - Tokenize query
   - Count term matches in case fields
   - Score based on match frequency

2. **Vector search (optional):**
   - Use ChromaDB for semantic similarity
   - Embed query and cases
   - Return top-k nearest neighbors

### 2.5 CLI Commands

#### rag-add
Add a case to the RAG knowledge base

```bash
pt-snap rag-add <file.json> [--verify]
```

#### rag-search
Search the RAG knowledge base

```bash
pt-snap rag-search <query> [--top-k N] [--tags TAG1,TAG2] [--json]
```

#### rag-list
List all cases

```bash
pt-snap rag-list [--tags TAG1,TAG2] [--json]
```

#### rag-tags
List all available tags

```bash
pt-snap rag-tags
```

---

## 3. Implementation Requirements

### 3.1 Storage
- Cases stored as JSON files
- Archive directory: `~/.local/share/pt-snap-analyzer/rag_archive`
- JSON serialization for portability
- Atomic writes to prevent corruption

### 3.2 Search Strategy

**Keyword-based search (default):**
- Normalize text (lowercase, remove accents)
- Tokenize query
- Count term matches in case fields
- Score based on match frequency
- Fields searched: conclusion, root_cause, solution, tags

**Vector search (future enhancement):**
- ChromaDB vector search
- LangChain integration
- Semantic similarity

### 3.3 Testing Strategy
- 单元测试：模型、归档、检索器
- 集成测试：完整工作流
- CLI 测试：命令执行
- SDK 测试：API 可用性
- 覆盖率目标：>80%

---

## 4. Success Criteria
- [ ] RAG 案例可以正确归档
- [ ] 案例检索正确工作
- [ ] 标签过滤正确实现
- [ ] CLI 命令正常运行
- [ ] SDK API 可用
- [ ] 所有单元测试通过
- [ ] 测试覆盖率 >80%
- [ ] 代码通过 ruff 检查
- [ ] 代码通过 black 格式化

---

## 5. Risks and Mitigations

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 案例数据格式不一致 | 高 | 中 | 严格的数据验证，schema 检查 |
| 搜索准确性低 | 高 | 中 | 关键词 + 向量混合搜索，提供置信度 |
| 向量搜索性能差 | 中 | 中 | 默认使用关键词搜索，向量搜索可选 |
| 标签管理混乱 | 中 | 中 | 提供标签列表，支持标签建议 |
| 存储空间增长快 | 低 | 低 | 案例压缩存储，定期清理 |
| ChromaDB 依赖冲突 | 低 | 低 | 固定版本，使用虚拟环境 |

---

## 6. Appendix

### 参考文档
- [ChromaDB 文档](https://docs.trychroma.com/)
- [LangChain 文档](https://python.langchain.com/)
- [JSON Schema](https://json-schema.org/)

### 相关讨论
- 案例格式设计
- 搜索算法选择
- 标签体系设计

### 设计决策记录
1. **JSON 存储而非数据库**: 便于备份和迁移，无需额外依赖
2. **关键词搜索优先**: 简单快速，向量搜索作为可选增强
3. **CLI 和 SDK 双接口**: 既支持命令行使用，也支持程序化调用
4. **自动生成 case_id**: 使用 UUID，避免冲突

### 示例案例 JSON
```json
{
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-04-04T10:00:00Z",
  "db_snapshot": "/path/to/snapshot.db",
  "analysis_steps": [
    {
      "step": 1,
      "command": "leak-detect",
      "parameters": {"min_size": 1024},
      "result_summary": "Found 5 leaks",
      "description": "Run leak detection"
    }
  ],
  "conclusion": "Memory leak in training loop",
  "root_cause": "Tensor not released after use",
  "solution": "Use .detach() or del tensor",
  "tags": ["leak", "cuda", "training"],
  "confidence": 0.95,
  "verified_by": "expert1"
}
```

### 示例搜索
```bash
# 搜索泄漏相关案例
pt-snap rag-search "memory leak cuda"

# 搜索并限制结果数量
pt-snap rag-search "oom" --top-k 3

# 搜索并过滤标签
pt-snap rag-search "leak" --tags training,cuda

# JSON 输出
pt-snap rag-search "leak" --json
```

### 示例 SDK 使用
```python
from pt_snap_analyzer.rag import CaseArchive, Searcher

# 添加案例
archive = CaseArchive()
case = RAGCase(
    db_snapshot="/path/to/snapshot.db",
    conclusion="Memory leak",
    root_cause="...",
    solution="...",
    tags=["leak", "cuda"]
)
case_id = archive.add_case(case)

# 搜索案例
searcher = Searcher()
result = searcher.search("memory leak", top_k=5)
for match in result.matches:
    print(f"Score: {match.score}, Case: {match.case.conclusion}")
```
