# PyTorch 内存快照分析器 - 设计文档

**创建日期**: 2026-04-04  
**状态**: 已批准  
**版本**: 1.0

---

## 一、项目概述

### 1.1 项目定位

**项目名称**: `pt-snap-analyzer` (PyTorch Snapshot Analyzer)

**核心价值**:
- 🔧 **独立 CLI 工具**: 开发者可直接使用命令分析内存快照
- 🤖 **AI 友好**: 提供 SDK + JSON 输出，AI Agent 可轻松调用
- 📚 **RAG 知识库**: 将先验经验文档化，AI 可检索相似案例
- 📊 **SQLite 驱动**: 所有分析基于 SQL 查询，高效处理大数据量

### 1.2 使用场景

1. **内存泄漏检测**: 定位训练/推理过程中的内存泄漏问题
2. **峰值分析**: 识别内存峰值和异常分配
3. **内存效率分析**: 分析内存碎片化、分配效率问题
4. **对比分析**: 对比不同迭代/不同配置的内存使用差异
5. **算子/层分析**: 分析算子/层的内存分配模式

### 1.3 目标用户

- AI Agent: 通过 CLI JSON 输出或 Python SDK 调用分析功能
- 开发者: 直接使用 CLI 工具或 REPL 模式进行交互式分析

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户交互层                               │
├─────────────────────┬─────────────────────┬─────────────────┤
│     CLI 命令行       │   REPL 交互模式      │    AI Agent     │
│  pt-snap analyze    │  pt-snap repl       │  调用 SDK 或     │
│  pt-snap query      │  (探索/保存查询)    │  解析 CLI JSON  │
│  pt-snap rag add    │                     │                 │
└─────────┬───────────┴─────────────────────┴────────┬────────┘
          │                                          │
┌─────────▼──────────────────────────────────────────▼────────┐
│                    Python SDK/API                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Query API    │  │ Analysis API │  │ RAG Management   │   │
│  │ • execute()  │  │ • leak()     │  │ • add_case()     │   │
│  │ • load_cfg() │  │ • peak()     │  │ • search()       │   │
│  │ • save_cfg() │  │ • compare()  │  │ • list_cases()   │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│                   数据访问层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ SQLite DB    │  │ Query Config │  │ SQL Templates    │   │
│  │ (内存快照)   │  │ (YAML/JSON)  │  │ (可复用查询)     │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│                   知识库层                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Vector DB    │  │ Case Archive │  │ Learning Log     │   │
│  │ (Chroma)     │  │ (JSON files) │  │ (分析历史)       │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、数据模型

### 3.1 DB Schema 概览

基于现有的 SnapshotDB schema:

**核心表**:
- `trace_entry_{device}`: 内存事件追踪表
- `block_{device}`: 内存块状态表
- `dictionary`: 枚举值映射表

**命名规则**: 多设备场景下，表名后缀为设备 ID

### 3.2 关键约束

#### 3.2.1 trace_entry.id 约束
- **`id >= 0`**: 快照采集后发生的事件，按时间顺序递增且唯一
- **`id < 0`**: 虚拟事件（从原始 pickle 数据生成），用于还原快照采集时刻的 Segment 状态
  - 事件类型只能是 `segment_map` 或 `segment_alloc`

#### 3.2.2 block.id 约束
- **`id >= 0`**: 与 `allocEventId` 一致，指向 trace_entry 中的分配事件
- **`id < 0`**: 快照采集前就已分配的内存块，无法追溯到分配时间点

#### 3.2.3 block.state 约束
- 仅在 `block.id < 0` 时有意义（历史遗留块）
- `id >= 0` 时，state 无实际意义

#### 3.2.4 requestedSize vs size
- `requestedSize`: 用户请求的大小
- `size`: 实际分配大小（含对齐开销）
- 公式：`size = math.ceil((requestedSize + 32) / 512) * 512`

### 3.3 Python 数据模型

```python
class EventType(IntEnum):
    SEGMENT_MAP = 0
    SEGMENT_UNMAP = 1
    SEGMENT_ALLOC = 2
    SEGMENT_FREE = 3
    ALLOC = 4
    FREE_REQUESTED = 5
    FREE_COMPLETED = 6
    WORKSPACE_SNAPSHOT = 7

@dataclass
class MemoryEvent:
    """内存事件记录"""
    id: int
    action: EventType
    address: int
    size: int
    stream: int
    allocated: int
    active: int
    reserved: int
    callstack: Optional[str]
    
    @property
    def is_virtual_event(self) -> bool:
        return self.id < 0
    
    @property
    def is_runtime_event(self) -> bool:
        return self.id >= 0

@dataclass
class MemoryBlock:
    """内存块记录"""
    id: int
    address: int
    size: int
    requestedSize: int
    state: int
    allocEventId: Optional[int]
    freeEventId: Optional[int]
    
    @property
    def is_historical_block(self) -> bool:
        return self.id < 0
    
    @property
    def is_active(self) -> bool:
        if self.is_historical_block:
            return self.state == 1
        return self.freeEventId is None or self.freeEventId == -1
```

---

## 四、核心功能设计

### 4.1 CLI 工具

#### 4.1.1 上下文管理

```bash
# 设置当前使用的数据库
$ pt-snap use <database_path>

# 配置设备
$ pt-snap config devices <device_ids>  # 如：0,1 或 all

# 查看当前配置
$ pt-snap config show
```

#### 4.1.2 分析命令

```bash
# 内存泄漏检测
$ pt-snap analyze leak --json

# 峰值分析
$ pt-snap analyze peak --json

# 内存趋势分析
$ pt-snap analyze trend --plot

# 调用栈分析
$ pt-snap analyze stack --top-k 10

# 对比分析
$ pt-snap compare <db1> <db2> --metric memory
```

#### 4.1.3 查询命令

```bash
# 列出所有预定义查询
$ pt-snap query list

# 执行预定义查询
$ pt-snap query exec <query_name> --format table

# 执行自定义 SQL
$ pt-snap query custom "SELECT ..." --json
```

#### 4.1.4 REPL 模式

```bash
$ pt-snap repl

# 支持的命令:
snapshot> show tables
snapshot> describe trace_entry_0
snapshot> SELECT ... (直接执行 SQL)
snapshot> save query <name> --description "..."
snapshot> generate python
```

#### 4.1.5 RAG 命令

```bash
# 添加案例到知识库
$ pt-snap rag add \
    --case <case_id> \
    --db <database_path> \
    --analysis-result <result_json> \
    --conclusion "..." \
    --tags "tag1,tag2"

# 检索案例
$ pt-snap rag search "query text" --top-k 3

# 列出案例
$ pt-snap rag list --tags memory-leak

# 更新/删除案例
$ pt-snap rag update <case_id> --conclusion "..."
$ pt-snap rag remove <case_id>
```

### 4.2 Python SDK

```python
from pt_snap_analyzer import Context, Analyzer, RAGSearcher

# 创建上下文
ctx = Context(
    db_path="snapshot.pkl.db",
    devices=[0, 1]
)

# 分析器使用
analyzer = Analyzer(ctx)

# 内存泄漏检测
leaks = analyzer.detect_leaks()

# 内存趋势分析
trend = analyzer.analyze_trend(metrics=["allocated", "active"])

# 调用栈分析
stack = analyzer.analyze_stack_trace(top_k=10)

# RAG 检索
rag = RAGSearcher("knowledge_base/")
cases = rag.search("memory leak in attention layer")

# 添加案例
rag.add_case(
    case_id="memory_leak_demo",
    db_path="snapshot.db",
    analysis_result=leaks,
    conclusion="Attention 层的 key/value cache 未正确释放",
    tags=["memory-leak", "transformer"]
)
```

### 4.3 预定义查询模板

#### 4.3.1 内存泄漏检测 (leak_detection_v2)

```sql
-- 历史遗留块泄漏
SELECT 
  b.id as block_id,
  b.address,
  b.size as actual_size,
  b.requestedSize as requested_size,
  (b.size - b.requestedSize) as alignment_overhead,
  'historical' as leak_type
FROM block_{device} b
WHERE b.id < 0 AND b.state = 1
ORDER BY b.size DESC;

-- 运行时分配未释放
SELECT 
  b.id as block_id,
  b.address,
  b.size as actual_size,
  b.requestedSize as requested_size,
  b.allocEventId,
  t.callstack,
  'current' as leak_type
FROM block_{device} b
LEFT JOIN trace_entry_{device} t ON b.allocEventId = t.id
WHERE b.id >= 0
  AND b.allocEventId IS NOT NULL
  AND (b.freeEventId IS NULL OR b.freeEventId = -1)
  AND NOT EXISTS (
    SELECT 1 FROM trace_entry_{device} 
    WHERE id = b.freeEventId AND action = 6
  )
ORDER BY b.size DESC;
```

#### 4.3.2 内存趋势分析 (memory_timeline_v2)

```sql
SELECT 
  (id / :bucket_size) as bucket,
  MIN(id) as start_id,
  MAX(id) as end_id,
  COUNT(*) as event_count,
  AVG(allocated) as avg_allocated,
  MAX(allocated) as peak_allocated,
  MIN(allocated) as min_allocated,
  AVG(active) as avg_active,
  MAX(active) as peak_active,
  AVG(reserved) as avg_reserved,
  MAX(reserved) as peak_reserved
FROM trace_entry_{device}
WHERE id >= 0  -- 仅真实事件
GROUP BY bucket
ORDER BY bucket ASC;
```

#### 4.3.3 调用栈分析 (callstack_analysis_v2)

```sql
SELECT 
  COALESCE(callstack, '<snapshot-initial>') as callstack,
  COUNT(*) as alloc_count,
  SUM(size) as total_bytes,
  AVG(size) as avg_bytes,
  MAX(size) as max_single_alloc,
  CASE 
    WHEN MIN(id) < 0 THEN 'includes_snapshot_initial'
    ELSE 'runtime_only'
  END as phase
FROM trace_entry_{device}
WHERE action = 4  -- alloc
GROUP BY callstack
ORDER BY total_bytes DESC
LIMIT :top_k;
```

---

## 五、快速迭代机制

### 5.1 插件式分析模块

```python
# analyzers/__init__.py
from .leak_detector import LeakDetector
from .peak_analyzer import PeakAnalyzer
from .stack_analyzer import StackAnalyzer
from .trend_analyzer import TrendAnalyzer

__all__ = [
    "LeakDetector",
    "PeakAnalyzer", 
    "StackAnalyzer",
    "TrendAnalyzer",
]

# analyzers/base.py
class AnalyzerBase(ABC):
    """分析器基类"""
    
    name: str
    description: str
    
    def __init__(self, context: Context):
        self.context = context
    
    @abstractmethod
    def analyze(self, **kwargs) -> AnalysisResult:
        pass
```

### 5.2 配置化查询

查询配置文件格式 (YAML):

```yaml
name: query_name
description: 查询描述
devices: all  # 或 [0, 1]
parameters:
  param_name:
    default: value
    type: int|string|float
    description: 参数描述
query: |
  SELECT ...
output_schema:
  - column_name: type
```

### 5.3 REPL 探索模式

支持的功能:
- 直接执行 SQL 查询
- 查看表结构
- 保存查询为配置文件
- 生成 Python SDK 代码

---

## 六、RAG 知识库设计

### 6.1 案例数据结构

```json
{
  "case_id": "memory_leak_in_transformer_attention",
  "timestamp": "2026-04-04T10:30:00Z",
  "db_snapshot": "snapshot.db",
  "analysis_steps": [
    {
      "step": 1,
      "action": "query",
      "query": "peak_detection",
      "result_summary": "发现 500MB 异常分配"
    }
  ],
  "conclusion": "Attention 层的 key/value cache 未正确释放导致泄漏",
  "root_cause": "transformers 库 v4.30.0 的 bug",
  "solution": "升级 transformers 库到 v4.31.0",
  "tags": ["memory-leak", "transformer", "attention"],
  "confidence": 0.95,
  "verified_by": "human_feedback"
}
```

### 6.2 实现技术

- **向量数据库**: ChromaDB
- **嵌入模型**: 可选用轻量级模型如 `all-MiniLM-L6-v2`
- **检索接口**: 相似度搜索 + 标签过滤

---

## 七、技术选型

| 模块 | 技术选择 | 理由 |
|------|---------|------|
| CLI 框架 | `typer` | 基于 type hints，自动生成 help，支持子命令 |
| SDK | 原生 Python | 低依赖、易集成 |
| JSON 输出 | `pydantic` | 结构化输出、类型校验 |
| RAG | `langchain` + `chromadb` | 成熟方案、易扩展 |
| SQL 构建 | 原生 sqlite3 + 模板引擎 | 轻量、可控 |
| YAML 解析 | `pyyaml` | 标准库，广泛使用 |
| 文档生成 | `mkdocs` | 可选，用于生成 API 文档 |

---

## 八、分阶段交付计划

### 阶段 1: MVP 核心框架 (2-3 周)

**目标**: 验证架构可行性

**交付物**:
- [ ] CLI 基础命令 (context, analyze, query)
- [ ] SQLite 查询接口封装
- [ ] 内存泄漏检测算法 (leak_detector)
- [ ] JSON 输出格式定义
- [ ] 基础单元测试
- [ ] 预定义查询配置系统

### 阶段 2: SDK + 高级分析 (2-3 周)

**目标**: 完善分析能力，提供 SDK

**交付物**:
- [ ] Python SDK 封装
- [ ] 峰值分析 (peak_analyzer)
- [ ] 趋势分析 (trend_analyzer)
- [ ] 调用栈分析 (stack_analyzer)
- [ ] 对比分析 (comparator)
- [ ] REPL 交互模式
- [ ] AI Agent 调用示例/文档

### 阶段 3: RAG 知识库集成 (2-3 周)

**目标**: 知识库集成，智能化提升

**交付物**:
- [ ] 知识库文档结构设计
- [ ] RAG 检索引擎集成
- [ ] CLI/SDK 集成 RAG 接口
- [ ] 案例归档功能 (rag add)
- [ ] 完整文档和示例

---

## 九、AI 友好设计要点

1. **结构化输出**: 所有命令默认输出 JSON，便于 AI 解析
2. **确定性行为**: 相同输入 → 相同输出，AI 可预测结果
3. **错误可解释**: 错误信息包含原因 + 建议修复方案
4. **SDK 即代码**: AI 可直接生成 SDK 调用代码
5. **知识库可检索**: RAG 让 AI 可访问先验经验
6. **CLI 可组合**: AI 可组合多个 CLI 命令完成复杂分析

---

## 十、风险与缓解

### 10.1 技术风险

**风险**: SQLite 查询性能在大数据量场景下可能不足

**缓解**:
- 为常用查询字段添加索引
- 支持查询分页
- 考虑缓存热点查询结果

### 10.2 数据风险

**风险**: DB schema 变更导致兼容性问题

**缓解**:
- 设计 schema 版本检测
- 提供 schema 迁移工具
- SDK 增加 schema 适配层

### 10.3 使用风险

**风险**: RAG 知识库质量参差不齐

**缓解**:
- 引入案例质量评分机制
- 支持人工审核和标记
- 提供置信度指标

---

## 十一、成功标准

### 功能完整性
- [ ] 所有预定义分析功能正常工作
- [ ] CLI 命令覆盖所有核心场景
- [ ] SDK API 文档完整

### AI 友好性
- [ ] AI Agent 可成功调用 CLI 和 SDK
- [ ] JSON 输出格式稳定、可解析
- [ ] RAG 检索准确率 > 80%

### 代码质量
- [ ] 单元测试覆盖率 > 80%
- [ ] 通过 type checking (mypy)
- [ ] 通过 lint (ruff)

### 用户体验
- [ ] CLI help 信息清晰完整
- [ ] 错误信息友好、可操作
- [ ] 示例文档齐全

---

## 附录

### A. CLI 命令完整列表

```bash
# 上下文管理
pt-snap use <db_path>
pt-snap config devices <device_ids>
pt-snap config show

# 分析
pt-snap analyze leak [--json]
pt-snap analyze peak [--json]
pt-snap analyze trend [--plot]
pt-snap analyze stack [--top-k N]

# 查询
pt-snap query list
pt-snap query exec <query_name> [--format table|json]
pt-snap query custom "<sql>" [--json]

# REPL
pt-snap repl

# RAG
pt-snap rag add --case <id> --conclusion "..." --tags "..."
pt-snap rag search "<query>" [--top-k N]
pt-snap rag list [--tags ...]
pt-snap rag update <id> --conclusion "..."
pt-snap rag remove <id>

# 对比
pt-snap compare <db1> <db2> --metric memory
```

### B. SDK API 参考

```python
# Context
Context(db_path: str, devices: Union[List[int], str])

# Analyzer
Analyzer(context: Context)
  - detect_leaks() -> LeakResult
  - analyze_trend(metrics: List[str]) -> TrendResult
  - analyze_stack_trace(top_k: int) -> StackResult
  - analyze_peak() -> PeakResult

# RAGSearcher
RAGSearcher(kb_path: str)
  - search(query: str, top_k: int) -> List[Case]
  - add_case(**kwargs) -> str (case_id)
  - list_cases(tags: List[str]) -> List[Case]
```

### C. 相关文件

- [Schema 文档](../../snapshot_db_schema.md)
- [约束规范](../../snapshot_db_constraint_spec.md)
- [示例数据库](../../examples/snapshot_expandable.pkl.db)
