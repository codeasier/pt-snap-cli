# PyTorch 内存快照分析器 - 产品需求文档 (PRD)

**创建日期**: 2026-04-04  
**状态**: 待开发
**版本**: 1.0  
**关联设计文档**: [2026-04-04-pt-snap-analyzer-design.md](../specs/2026-04-04-pt-snap-analyzer-design.md)

---

## Executive Summary

**Problem**: PyTorch 开发者花费大量时间调试内存问题，现有工具要么不可自动化（GUI），要么输出不结构化（AI 无法解析）。

**Solution**: pt-snap-analyzer —— AI 友好的 CLI + SDK 分析工具，基于 SQLite 和 RAG 知识库。

**Success Metrics**:
- CLI 命令响应时间 < 1s（600M 数据库）
- 泄漏检测准确率 > 90%（相比人工分析）
- RAG 检索 Top-3 相关度 > 80%（用户反馈评分）
- 单元测试覆盖率 > 80%
- AI Agent 调用成功率 > 95%（无语法/格式错误）

---

## Problem Statement

PyTorch 开发者在训练大型模型时面临内存问题（内存泄漏、峰值过高、碎片化等），但缺乏有效的分析工具：

1. **内存泄漏难定位**: 训练过程中内存持续增长，但无法快速定位泄漏源头（哪个算子/哪行代码）
2. **峰值分析困难**: 内存峰值出现时，无法回溯分析是哪些分配导致的
3. **缺乏历史对比**: 无法对比不同迭代、不同配置下的内存使用模式差异
4. **工具链割裂**: 现有工具要么是 GUI（不可自动化），要么输出不结构化（AI 无法解析）
5. **经验无法沉淀**: 解决问题的经验难以文档化和复用，每次都要重新摸索

这些问题导致开发者花费大量时间调试内存问题，影响模型研发效率。

---

## Solution

构建 `pt-snap-analyzer` —— 一个 AI 友好的 PyTorch 内存快照分析工具，核心特性：

1. **CLI + SDK 双接口**: 
   - CLI: 命令行工具，输出结构化 JSON，AI 可解析
   - SDK: Python API，可集成到自动化工作流

2. **SQLite 驱动分析**: 基于 SQLite 数据库存储快照，所有分析能力基于 SQL 查询，可处理 GB 级快照数据

3. **插件式分析器**: 泄漏检测、峰值分析、趋势分析、调用栈分析等模块化设计

4. **RAG 知识库**: 将分析案例和解决方案文档化，AI 可检索相似问题的解决经验

5. **配置化查询**: 预定义查询模板通过 YAML 配置管理，支持动态扩展

**核心价值**:
- 🔧 **独立 CLI**: 开发者可直接使用命令分析内存快照
- 🤖 **AI 友好**: SDK + JSON 输出，AI Agent 可自动调用分析
- 📚 **RAG 知识库**: 先验经验文档化，AI 可检索相似案例
- 📊 **SQLite 驱动**: 基于 SQL 查询，高效处理大数据量

---

## User Stories

### CLI 使用场景

1. **作为开发者**，我想要通过 `pt-snap use <db_path>` 命令设置当前分析的数据库，以便快速切换分析目标
   - **Acceptance Criteria**:
     - [ ] 成功时输出 `Using database: <path>`
     - [ ] 数据库不存在时输出错误到 stderr，退出码 1
     - [ ] 数据库路径持久化到 `~/.config/pt-snap-analyzer/current_db`

2. **作为开发者**，我想要通过 `pt-snap analyze leak --json` 命令检测内存泄漏，以便快速定位未释放的内存块
   - **Acceptance Criteria**:
     - [ ] 输出必须是合法 JSON 格式
     - [ ] 包含泄漏块 ID、地址、大小、调用栈
     - [ ] 按大小降序排列
     - [ ] 支持 --min-size 参数过滤
     - [ ] 错误时输出到 stderr 且退出码非零

3. **作为开发者**，我想要通过 `pt-snap analyze peak --json` 命令分析内存峰值，以便识别异常分配
   - **Acceptance Criteria**:
     - [ ] 输出峰值事件列表（时间、大小、调用栈）
     - [ ] 支持 --top-k 参数限制结果数量
     - [ ] 输出峰值前后的内存变化趋势
     - [ ] JSON 包含统计信息（峰值大小、时间点）

4. **作为开发者**，我想要通过 `pt-snap analyze trend --plot` 命令查看内存使用趋势，以便了解内存变化模式
   - **Acceptance Criteria**:
     - [ ] 输出时间序列数据（时间戳、allocated、active、reserved）
     - [ ] --plot 模式生成 ASCII 图或保存为 PNG
     - [ ] 支持 --interval 参数指定采样间隔

5. **作为开发者**，我想要通过 `pt-snap analyze stack --top-k 10` 命令分析调用栈，以便找出分配最多的代码路径
   - **Acceptance Criteria**:
     - [ ] 输出 Top-K 调用栈及其分配次数/总大小
     - [ ] 调用栈按出现频率降序排列
     - [ ] 支持 --group-by 参数（按函数/按文件）
     - [ ] JSON 包含调用栈树结构

6. **作为开发者**，我想要通过 `pt-snap query list` 命令查看预定义查询列表，以便了解可用的分析查询
   - **Acceptance Criteria**:
     - [ ] 输出查询名称、描述、参数列表
     - [ ] 支持 --format json | table 切换输出格式
     - [ ] 包含用户自定义查询（从 YAML 配置加载）

7. **作为开发者**，我想要通过 `pt-snap query exec <query_name>` 命令执行预定义查询，以便复用已有的分析逻辑
   - **Acceptance Criteria**:
     - [ ] 支持 --param key=value 传递参数
     - [ ] 输出查询结果（JSON 或表格）
     - [ ] 查询不存在时输出错误和建议查询列表
     - [ ] 支持 --device 参数指定设备

8. **作为开发者**，我想要通过 `pt-snap compare <db1> <db2>` 命令对比两个快照，以便分析不同配置的内存差异
   - **Acceptance Criteria**:
     - [ ] 输出两个数据库的统计对比（总分配、峰值、泄漏数）
     - [ ] 标识差异超过阈值的指标（可配置）
     - [ ] 支持 --metrics 参数指定对比指标
     - [ ] JSON 包含差异百分比

9. **作为 AI Agent**，我想要解析 CLI 的 JSON 输出，以便自动提取分析结果并生成报告
   - **Acceptance Criteria**:
     - [ ] 所有 --json 输出符合预定义 schema
     - [ ] JSON 键名稳定、可预测
     - [ ] 包含元数据（数据库路径、分析时间、设备）

10. **作为 AI Agent**，我想要组合多个 CLI 命令（如 leak + peak + stack），以便完成复杂的内存分析任务
    - **Acceptance Criteria**:
      - [ ] 命令间状态独立（无副作用）
      - [ ] 错误信息包含上下文（哪个命令失败）
      - [ ] 支持 --output-file 保存结果到文件

### SDK 使用场景

11. **作为开发者**，我想要通过 `Context(db_path, devices)` 创建分析上下文，以便管理数据库连接和配置
    - **Acceptance Criteria**:
      - [ ] 验证数据库文件存在
      - [ ] 加载数据库 schema 并验证版本
      - [ ] 支持设备列表参数（默认 all）
      - [ ] 抛出自定义异常（DatabaseNotFoundError, SchemaVersionError）

12. **作为开发者**，我想要调用 `analyzer.detect_leaks()` API 检测泄漏，以便集成到自己的工具链中
    - **Acceptance Criteria**:
      - [ ] 返回 LeakResult 对象（可序列化为 JSON）
      - [ ] 支持 min_size 参数过滤
      - [ ] 支持 device 参数指定设备
      - [ ] 包含泄漏块列表和统计信息

13. **作为开发者**，我想要调用 `analyzer.analyze_trend(metrics)` 分析趋势，以便获取内存使用的时间序列数据
    - **Acceptance Criteria**:
      - [ ] metrics 参数指定 [allocated, active, reserved]
      - [ ] 返回时间序列（列表）
      - [ ] 支持 start_time/end_time 参数
      - [ ] 返回统计信息（均值、趋势斜率）

14. **作为开发者**，我想要调用 `analyzer.analyze_stack_trace(top_k)` 分析调用栈，以便找出热点分配路径
    - **Acceptance Criteria**:
      - [ ] 返回 Top-K 调用栈列表
      - [ ] 每个调用栈包含调用链、分配次数、总大小
      - [ ] 支持 group_by 参数（function/file）
      - [ ] 返回调用栈树结构

15. **作为开发者**，我想要调用 `rag.search(query)` 检索案例，以便查找相似问题的解决方案
    - **Acceptance Criteria**:
      - [ ] 支持关键词搜索和向量搜索
      - [ ] 返回案例列表（按相关度排序）
      - [ ] 支持 top_k 参数
      - [ ] 支持 tags 过滤

16. **作为开发者**，我想要调用 `rag.add_case(...)` 添加案例，以便将成功的分析经验归档到知识库
    - **Acceptance Criteria**:
      - [ ] 验证案例数据完整性
      - [ ] 自动生成 case_id（如果未提供）
      - [ ] 生成向量嵌入并存储
      - [ ] 返回案例 ID

17. **作为 AI Agent**，我想要通过 SDK 直接调用分析 API，以便在 Python 代码中集成分析能力
    - **Acceptance Criteria**:
      - [ ] SDK API 文档完整（docstring）
      - [ ] 所有返回对象支持 .model_dump_json()
      - [ ] 异常可捕获且包含详细信息
      - [ ] 提供示例代码（examples/ 目录）

### RAG 知识库场景

18. **作为开发者**，我想要将成功的分析案例保存到知识库，以便后续复用分析经验
    - **Acceptance Criteria**:
      - [ ] CLI 命令 `rag add --file <case.json>` 支持添加案例
      - [ ] SDK API `rag.add_case(case_dict)` 验证数据结构
      - [ ] 自动生成向量嵌入
      - [ ] 支持 tags 标签（用于过滤）

19. **作为开发者**，我想要通过关键词检索案例（如 "memory leak transformer"），以便找到相似问题的解决方案
    - **Acceptance Criteria**:
      - [ ] CLI 命令 `rag search <query>` 输出相关案例
      - [ ] 支持 --top-k 参数限制结果数
      - [ ] 输出案例摘要和置信度
      - [ ] 支持 --tags 过滤

20. **作为开发者**，我想要通过标签过滤案例（如 `--tags memory-leak,transformer`），以便精确定位相关案例
    - **Acceptance Criteria**:
      - [ ] 支持多标签 AND/OR 逻辑
      - [ ] 标签列表可通过 `rag tags` 查看
      - [ ] 标签支持自动补全（CLI）

21. **作为 AI Agent**，我想要在分析失败时检索 RAG 知识库，以便尝试其他分析策略
    - **Acceptance Criteria**:
      - [ ] 分析器失败时抛出包含错误上下文的异常
      - [ ] AI 可捕获异常并构造查询词
      - [ ] RAG 返回相似案例的解决策略

22. **作为 AI Agent**，我想要将成功的分析路径（查询序列 + 结论）归档，以便学习优化分析策略
    - **Acceptance Criteria**:
      - [ ] 分析路径可序列化为 JSON
      - [ ] 包含查询序列、参数、结果、结论
      - [ ] 可通过 `rag add --analysis-path <path.json>` 添加

### 可维护性场景

23. **作为开发者**，我想要通过 YAML 配置定义新的查询模板，以便无需修改代码即可扩展分析能力
    - **Acceptance Criteria**:
      - [ ] YAML 配置放在 `~/.config/pt-snap-analyzer/queries/`
      - [ ] 配置包含 name, description, parameters, query, output_schema
      - [ ] 启动时自动加载配置
      - [ ] 配置错误时输出详细错误信息（行号、字段）

24. **作为开发者**，我想要为新的分析场景编写插件式分析器，以便快速添加定制化分析能力
    - **Acceptance Criteria**:
      - [ ] 继承 AnalyzerBase 抽象基类
      - [ ] 实现 analyze() 方法返回 AnalysisResult
      - [ ] 通过 entry_point 注册到 CLI
      - [ ] 提供插件示例代码

25. **作为维护者**，我想要每个分析模块有独立的单元测试，以便保证代码质量和可维护性
    - **Acceptance Criteria**:
      - [ ] 测试文件与模块一一对应（test_leak_detector.py, etc.）
      - [ ] 使用 pytest 框架
      - [ ] 测试数据隔离（fixture）
      - [ ] CI 自动运行测试

---

## Implementation Decisions

### 技术栈选择

| 模块 | 技术选择 | 理由 |
|------|---------|------|
| CLI 框架 | `typer` | 基于 type hints，自动生成 help，支持子命令 |
| SDK | 原生 Python | 低依赖、易集成 |
| JSON 输出 | `pydantic` | 结构化输出、类型校验 |
| RAG | `chromadb` + `langchain` | 成熟方案、易扩展 |
| SQL 构建 | 原生 sqlite3 + 模板引擎 | 轻量、可控 |
| YAML 解析 | `pyyaml` | 标准库，广泛使用 |
| 文档生成 | `mkdocs` | 可选，用于生成 API 文档 |

### 依赖管理

- 使用 **conda** 管理依赖
- 工作环境：`openclaw` (已在规则中配置)
- 依赖列表：`typer`, `pydantic`, `pyyaml`, `chromadb`, `langchain`, `sqlite3` (内置)

### 项目结构

采用**单一包**结构，CLI 和 SDK 共享核心逻辑：

```
pt-snap-cli/
├── pt_snap_analyzer/          # 主包
│   ├── __init__.py
│   ├── cli.py                 # CLI 入口
│   ├── context.py             # Context 类
│   ├── analyzers/             # 分析器模块
│   │   ├── __init__.py
│   │   ├── base.py            # AnalyzerBase 抽象基类
│   │   ├── leak_detector.py   # 泄漏检测
│   │   ├── peak_analyzer.py   # 峰值分析
│   │   ├── trend_analyzer.py  # 趋势分析
│   │   └── stack_analyzer.py  # 调用栈分析
│   ├── query/                 # 查询模块
│   │   ├── __init__.py
│   │   ├── executor.py        # 查询执行器
│   │   ├── config.py          # YAML 配置管理
│   │   └── templates/         # 预定义 SQL 模板
│   │       ├── leak_detection_v2.yaml
│   │       ├── memory_timeline_v2.yaml
│   │       └── callstack_analysis_v2.yaml
│   ├── rag/                   # RAG 模块
│   │   ├── __init__.py
│   │   ├── searcher.py        # RAG 检索
│   │   ├── archive.py         # 案例归档
│   │   └── models.py          # RAG 数据模型
│   └── models/                # 数据模型
│       ├── __init__.py
│       ├── event.py           # MemoryEvent
│       └── block.py           # MemoryBlock
├── tests/                     # 测试目录
│   ├── test_cli.py
│   ├── test_analyzers.py
│   ├── test_query.py
│   └── test_rag.py
├── docs/                      # 文档
└── pyproject.toml             # 项目配置
```

### 核心数据模型

#### 枚举类型

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
```

#### MemoryEvent

```python
@dataclass
class MemoryEvent:
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
```

#### MemoryBlock

```python
@dataclass
class MemoryBlock:
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

### 分析器接口

所有分析器继承自 `AnalyzerBase`：

```python
class AnalyzerBase(ABC):
    name: str
    description: str
    
    def __init__(self, context: Context):
        self.context = context
    
    @abstractmethod
    def analyze(self, **kwargs) -> AnalysisResult:
        pass
```

具体分析器实现：
- `LeakDetector`: `detect_leaks()` → `LeakResult`
- `PeakAnalyzer`: `analyze_peaks()` → `PeakResult`
- `TrendAnalyzer`: `analyze_trend(metrics)` → `TrendResult`
- `StackAnalyzer`: `analyze_stack_trace(top_k)` → `StackResult`

### 查询配置格式

YAML 配置示例：

```yaml
name: leak_detection_v2
description: 内存泄漏检测 v2
devices: all
parameters:
  min_size:
    default: 1024
    type: int
    description: 最小泄漏块大小（字节）
query: |
  SELECT b.id, b.address, b.size, t.callstack
  FROM block_{device} b
  LEFT JOIN trace_entry_{device} t ON b.allocEventId = t.id
  WHERE b.id >= 0 AND b.freeEventId IS NULL
  ORDER BY b.size DESC
output_schema:
  - block_id: int
  - address: int
  - size: int
  - callstack: str
```

### RAG 案例数据结构

```json
{
  "case_id": "memory_leak_in_transformer_attention",
  "timestamp": "2026-04-04T10:30:00Z",
  "db_snapshot": "snapshot.db",
  "analysis_steps": [...],
  "conclusion": "Attention 层的 key/value cache 未正确释放",
  "root_cause": "transformers 库 v4.30.0 的 bug",
  "solution": "升级 transformers 库到 v4.31.0",
  "tags": ["memory-leak", "transformer", "attention"],
  "confidence": 0.95,
  "verified_by": "human_feedback"
}
```

### CLI 命令设计

使用 `typer` 的子命令结构：

```python
# cli.py
app = typer.Typer()

@app.command()
def use(db_path: str):
    """设置当前使用的数据库"""
    ...

@app.command()
def config():
    """配置管理"""
    ...

@app.command()
def analyze():
    """内存分析"""
    ...

@app.command()
def query():
    """查询管理"""
    ...

@app.command()
def rag():
    """RAG 知识库管理"""
    ...

@app.command()
def compare(db1: str, db2: str):
    """对比分析"""
    ...
```

### 错误处理策略

- CLI 错误输出到 stderr，退出码非零
- SDK 抛出自定义异常：`AnalyzerError`, `QueryError`, `RAGError`
- 所有异常包含错误原因和建议修复方案

---

## Integration Points

### 外部系统交互

| 组件 | 交互方式 | 说明 |
|------|---------|------|
| **数据库** | SQLite (.db 文件) | 由 PyTorch 内存快照工具生成，只读模式打开 |
| **RAG 向量库** | ChromaDB | 本地存储，路径 `~/.local/share/pt-snap-analyzer/rag_db` |
| **配置管理** | YAML 文件 | 路径 `~/.config/pt-snap-analyzer/queries/` |
| **Python 版本** | 3.10+ | 使用 type hints 和 match 语法 |
| **Conda 环境** | openclaw | 工作环境，已在规则中配置 |

### 数据流

```
用户/Agent → CLI/SDK → Context → Analyzers → SQLite
                      ↓
                 Query Executor → YAML Templates
                      ↓
                 RAG → ChromaDB
```

---

## Security & Privacy

### 数据安全

- **数据本地化**: 所有分析在本地执行，不上传任何数据到云端
- **数据库只读**: 分析时以 `file:...?mode=ro` 只读模式打开 SQLite，避免修改原始快照
- **临时文件**: 临时文件存储在 `/tmp/pt-snap-analyzer-<pid>/`，退出时清理

### 敏感信息处理

- **调用栈脱敏**: RAG 案例中的调用栈默认脱敏用户路径
  ```python
  # 原始：/home/zhangsan/projects/my-model/train.py:123
  # 脱敏：/home/<user>/projects/<project>/train.py:123
  ```
- **文件路径**: 可选 --no-redact 保留原始路径（用于调试）
- **案例审核**: RAG 添加案例时提示用户检查敏感信息

### 权限要求

- **数据库文件**: 需要 read 权限
- **配置文件**: 需要 read/write 权限（~/.config/）
- **RAG 数据库**: 需要 read/write 权限（~/.local/share/）

---

## Testing Decisions

### 测试原则

1. **只测试外部行为**: 不测试内部实现细节，只测试公开 API 的输入输出
2. **测试隔离**: 每个测试用例独立，不依赖其他测试的状态
3. **使用示例数据库**: 所有测试基于 `examples/snapshot_expandable.pkl.db`

### 测试模块

1. **test_cli.py**: CLI 命令测试
   - 测试 `use` 命令设置数据库
   - 测试 `config` 命令配置设备
   - 测试 `analyze` 命令输出 JSON 格式
   - 测试 `query` 命令执行查询
   - 测试错误处理（无效数据库、无效查询等）

2. **test_analyzers.py**: 分析器测试
   - 测试 `LeakDetector.detect_leaks()` 返回正确结果
   - 测试 `TrendAnalyzer.analyze_trend()` 返回时间序列
   - 测试 `StackAnalyzer.analyze_stack_trace()` 返回 Top-K 调用栈
   - 测试分析器边界条件（空数据库、大数据量）

3. **test_query.py**: 查询模块测试
   - 测试 YAML 配置加载
   - 测试 SQL 模板渲染
   - 测试查询执行和结果格式化
   - 测试参数替换正确性

4. **test_rag.py**: RAG 模块测试
   - 测试案例添加和检索
   - 测试向量相似度搜索
   - 测试标签过滤
   - 测试案例更新/删除

### 测试覆盖率目标

- 单元测试覆盖率 > 80%
- 关键路径（分析器、查询执行）覆盖率 > 90%
- 通过 type checking (mypy)
- 通过 lint (ruff)

---

## Out of Scope

以下内容**不**在本 PRD 范围内：

1. **GUI 界面**: 不提供图形化界面，仅 CLI 和 SDK
2. **实时分析**: 不支持实时内存监控，仅分析离线快照
3. **多设备并行分析**: 阶段 1 仅支持单设备分析，多设备为后续扩展预留接口
4. **自动修复**: 仅分析问题，不自动修复代码
5. **性能优化**: 阶段 1 优先保证功能正确性，性能优化在后续迭代
6. **其他框架支持**: 仅支持 PyTorch，不支持 TensorFlow/JAX 等
7. **云端集成**: 不支持上传到云端分析，仅本地分析

---

## Further Notes

### 分阶段交付

#### 阶段 1: MVP 核心框架 (2-3 周)
- CLI 基础命令 (use, config, analyze, query)
- SQLite 查询接口封装
- 内存泄漏检测 (LeakDetector)
- JSON 输出格式定义
- 基础单元测试
- 预定义查询配置系统
- AI Agent 调用示例/文档

#### 阶段 2: SDK + 高级分析 (2-3 周)
- Python SDK 封装
- 峰值分析 (PeakAnalyzer)
- 趋势分析 (TrendAnalyzer)
- 调用栈分析 (StackAnalyzer)
- 对比分析 (Comparator)
- 查询配置管理 API
- SDK 使用文档

#### 阶段 3: RAG 知识库集成 (2-3 周)
- 知识库文档结构设计
- RAG 检索引擎集成
- CLI/SDK 集成 RAG 接口
- 案例归档功能 (rag add)
- 完整文档和示例

### AI 友好设计要点

1. **结构化输出**: 所有命令默认输出 JSON，便于 AI 解析
2. **确定性行为**: 相同输入 → 相同输出，AI 可预测结果
3. **错误可解释**: 错误信息包含原因 + 建议修复方案
4. **SDK 即代码**: AI 可直接生成 SDK 调用代码
5. **知识库可检索**: RAG 让 AI 可访问先验经验
6. **CLI 可组合**: AI 可组合多个 CLI 命令完成复杂分析

### AI Agent Integration

#### SDK 调用示例

```python
from pt_snap_analyzer import Context, LeakDetector, PeakAnalyzer

# AI Agent 创建分析上下文
ctx = Context("snapshot.db", devices=[0])

# 检测内存泄漏
leak_detector = LeakDetector(ctx)
leak_result = leak_detector.detect_leaks(min_size=1024)

# AI 解析结果生成报告
print("Leaks found:", len(leak_result.leaks))
for leak in leak_result.leaks:
    print(f"  Block {leak.id}: {leak.size} bytes")
    print(f"  Callstack: {leak.callstack}")

# 输出 JSON 供 AI 解析
print(leak_result.model_dump_json())
```

#### CLI 组合调用

```bash
# AI Agent 依次执行多个命令组合分析
pt-snap use snapshot.db
pt-snap analyze leak --json --min-size 1024 > leaks.json
pt-snap analyze peak --json --top-k 5 > peaks.json
pt-snap analyze stack --top-k 10 --json > stacks.json

# AI 解析三个 JSON 生成综合报告
python -c "
import json
leaks = json.load(open('leaks.json'))
peaks = json.load(open('peaks.json'))
stacks = json.load(open('stacks.json'))
# AI 分析...
"
```

#### 错误处理示例

```python
from pt_snap_analyzer import Context
from pt_snap_analyzer.exceptions import DatabaseNotFoundError, SchemaVersionError

try:
    ctx = Context("invalid.db", devices=[0])
except DatabaseNotFoundError as e:
    print(f"Database not found: {e.path}")
    print(f"Suggestion: Check if file exists or provide correct path")
except SchemaVersionError as e:
    print(f"Schema version mismatch: expected {e.expected}, got {e.got}")
    print(f"Suggestion: Run migration tool or regenerate snapshot")
```

### 已知风险

1. **SQLite 性能**: 大数据量场景下查询性能可能不足
   - **影响**: >10GB 数据库查询超时（>5s）
   - **概率**: 中
   - **缓解**:
     - 为常用字段（block.address, block.size, block.freeEventId）添加索引
     - 支持分页查询（LIMIT/OFFSET）
     - 基准测试：600MB 数据库查询 < 1s
     - 提供 --timeout 参数，超时后建议升级硬件

2. **Schema 变更**: DB schema 变更导致兼容性问题
   - **影响**: 旧版本数据库无法分析
   - **概率**: 低（schema 稳定）
   - **缓解**:
     - 在数据库中添加 version 表记录 schema 版本
     - 提供 migrate 工具自动升级
     - 不支持时给出明确错误和升级指引
     - 示例："Schema v1 detected, current supported: v2. Run 'pt-snap migrate <db>'"

3. **RAG 质量**: 知识库案例质量参差不齐
   - **影响**: 检索到不相关/错误的解决方案
   - **概率**: 中
   - **缓解**:
     - 引入案例评分机制（1-5 星）
     - 支持人工审核（rag verify <case_id>）
     - 检索时过滤低分案例（--min-score 3.0）
     - 显示案例来源（human_verified vs auto_generated）

4. **内存消耗**: ChromaDB 向量库占用大量内存
   - **影响**: 案例数 > 10k 时内存占用 > 1GB
   - **概率**: 低（初期案例少）
   - **缓解**:
     - 使用持久化存储（磁盘）
     - 支持 --rag-db-path 自定义路径
     - 定期清理低质量案例

5. **调用栈解析**: 不同 Python 版本/平台调用栈格式差异
   - **影响**: 调用栈解析失败或格式不一致
   - **概率**: 中
   - **缓解**:
     - 使用标准库 traceback 解析
     - 提供调用栈格式检测
     - 无法解析时输出原始字符串

### 成功标准

#### 功能完整性 (Must Have)
- [ ] 所有预定义分析功能正常工作（leak, peak, trend, stack）
- [ ] CLI 命令覆盖所有核心场景（use, config, analyze, query, rag, compare）
- [ ] SDK API 文档完整（docstring 覆盖率 100%）
- [ ] 查询配置系统正常工作（YAML 加载、渲染、执行）
- [ ] RAG 知识库支持添加和检索

#### AI 友好性 (Must Have)
- [ ] AI Agent 可成功调用 CLI 和 SDK（无语法/格式错误）
- [ ] JSON 输出格式稳定、可解析（schema 验证通过）
- [ ] RAG 检索准确率 > 80%（Top-3 相关度评分）
- [ ] 错误信息包含原因和建议修复方案
- [ ] CLI help 信息完整（--help 输出清晰）

#### 代码质量 (Must Have)
- [ ] 单元测试覆盖率 > 80%
- [ ] 关键路径（分析器、查询执行）覆盖率 > 90%
- [ ] 通过 type checking (mypy --strict)
- [ ] 通过 lint (ruff check --select ALL)
- [ ] 无严重/高危安全漏洞（bandit 扫描）

#### 用户体验 (Should Have)
- [ ] CLI help 信息清晰完整（每个子命令 --help 可用）
- [ ] 错误信息友好、可操作（包含建议）
- [ ] 示例文档齐全（examples/ 目录）
- [ ] 快速开始指南（README.md 前 3 屏内完成第一个分析）

#### 性能指标 (Should Have)
- [ ] CLI 命令响应时间 < 1s（600MB 数据库）
- [ ] 泄漏检测 < 2s（10k 内存块）
- [ ] 调用栈分析 < 3s（10k 事件）
- [ ] RAG 检索 < 1s（1k 案例）

#### 量化 KPI (Nice to Have)
- [ ] 泄漏检测准确率 > 90%（相比人工分析）
- [ ] AI Agent 调用成功率 > 95%（无错误）
- [ ] RAG 用户满意度 > 4.0/5.0（反馈评分）
- [ ] 文档阅读到实践转化率 > 30%（GitHub 访问/README 访问）


### 相关文件

- [设计文档](../specs/2026-04-04-pt-snap-analyzer-design.md)
- [Schema 文档](../../snapshot_db_schema.md)
- [约束规范](../../snapshot_db_constraint_spec.md)
- [示例数据库](../../examples/snapshot_expandable.pkl.db)
