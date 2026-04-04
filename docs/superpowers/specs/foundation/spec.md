# Spec: pt-snap-analyzer 基础架构

**Goal:** 构建 CLI 框架、数据模型和核心 Context，提供基础 API 支撑

**Architecture:** 基于 Typer 构建 CLI 框架，Pydantic 定义数据模型，SQLite 管理数据库连接

**Tech Stack:** Python 3.10+, Typer, Pydantic, SQLite3

---

## Why

### 当前痛点
- PyTorch 内存快照分析工具缺失，开发者难以理解内存分配模式
- 现有工具缺乏 CLI 接口，不利于集成到自动化流程
- 没有统一的数据模型和分析上下文管理，代码复用困难
- 内存问题排查依赖人工经验，效率低下

### 需要解决的问题
- 提供易用的 CLI 工具，支持快速查看和分析内存快照
- 定义标准化的数据模型，统一事件和块的表示
- 实现数据库连接管理，简化查询操作
- 为后续分析器、查询系统、RAG 知识库奠定基础

### 预期的业务价值
- 提升 PyTorch 内存问题排查效率 50% 以上
- 降低内存泄漏和碎片化问题的定位时间
- 支持 AI 辅助分析，减少人工介入
- 提供可扩展的架构，便于后续功能迭代

---

## What Changes

### 新增功能/模块
- CLI 框架：基于 Typer 的命令行接口
- 数据模型：EventType、BlockState 枚举，MemoryEvent、MemoryBlock 数据类
- Context 类：数据库连接管理和生命周期控制
- 项目配置：pyproject.toml、版本管理

### 修改的组件
- 无（全新模块）

### 删除的功能
- 无

### 技术架构变更
- 无（全新架构）

---

## Impact

### 影响的规格文档
- 无（初始版本）

### 影响的代码模块
- `pt_snap_analyzer/__init__.py` - 新增：包初始化
- `pt_snap_analyzer/version.py` - 新增：版本信息
- `pt_snap_analyzer/cli.py` - 新增：CLI 入口
- `pt_snap_analyzer/context.py` - 新增：Context 类
- `pt_snap_analyzer/models/__init__.py` - 新增：模型导出
- `pt_snap_analyzer/models/_enums.py` - 新增：枚举定义
- `pt_snap_analyzer/models/event.py` - 新增：MemoryEvent 模型
- `pt_snap_analyzer/models/block.py` - 新增：MemoryBlock 模型

### 影响的依赖
- `typer>=0.9.0` - 新增：CLI 框架
- `pydantic>=2.0.0` - 新增：数据验证（后续使用）
- `pyyaml>=6.0` - 新增：YAML 支持（后续使用）
- `chromadb>=0.4.0` - 新增：向量数据库（RAG 使用）
- `langchain>=0.1.0` - 新增：AI 框架（RAG 使用）
- `pytest>=7.0.0` - 新增：测试框架（dev）
- `pytest-cov>=4.0.0` - 新增：覆盖率工具（dev）
- `black>=23.0.0` - 新增：代码格式化（dev）
- `ruff>=0.0.280` - 新增：代码检查（dev）

### 影响的配置
- `pyproject.toml` - 新增：项目配置
- 环境变量：无
- 配置文件：无
- 数据库：使用现有快照数据库（只读）

---

## ADDED Requirements

### Requirement: CLI 框架
系统 SHALL 提供命令行接口：

- 命令名称：pt-snap
- 参数：db_path - 数据库路径
- 功能：设置当前分析数据库

#### Scenario: 使用有效数据库
- **GIVEN** 存在有效的 SQLite 数据库文件
- **WHEN** 执行 `pt-snap use <db_path>`
- **THEN** 输出 "Using database: <db_path>"

#### Scenario: 数据库不存在
- **GIVEN** 数据库文件不存在
- **WHEN** 执行 `pt-snap use <db_path>`
- **THEN** 输出错误信息并退出

### Requirement: EventType 枚举
系统 SHALL 定义内存事件类型：

- SEGMENT_MAP = 0
- SEGMENT_UNMAP = 1
- SEGMENT_ALLOC = 2
- SEGMENT_FREE = 3
- ALLOC = 4
- FREE_REQUESTED = 5
- FREE_COMPLETED = 6
- WORKSPACE_SNAPSHOT = 7

#### Scenario: 枚举值正确
- **GIVEN** EventType 枚举已定义
- **WHEN** 访问枚举值
- **THEN** 返回正确的整数值

### Requirement: BlockState 枚举
系统 SHALL 定义内存块状态：

- INACTIVE = -1
- ACTIVE_PENDING_FREE = 0
- ACTIVE_ALLOCATED = 1
- UNKNOWN = 99

#### Scenario: 枚举值正确
- **GIVEN** BlockState 枚举已定义
- **WHEN** 访问枚举值
- **THEN** 返回正确的整数值

### Requirement: MemoryEvent 数据类
系统 SHALL 定义内存事件数据类：

- id: 事件 ID
- action: EventType
- address: 内存地址
- size: 分配大小
- stream: CUDA/CANN 流 ID
- allocated: 总已分配内存
- active: 总活跃内存
- reserved: 总保留内存
- callstack: 调用栈信息

#### Scenario: 虚拟事件检测
- **GIVEN** 事件 ID < 0
- **WHEN** 访问 is_virtual_event 属性
- **THEN** 返回 True

#### Scenario: 运行时事件检测
- **GIVEN** 事件 ID >= 0
- **WHEN** 访问 is_runtime_event 属性
- **THEN** 返回 True

### Requirement: MemoryBlock 数据类
系统 SHALL 定义内存块数据类：

- id: 块 ID
- address: 内存地址
- size: 实际分配大小
- requestedSize: 用户请求大小
- state: 块状态
- allocEventId: 分配事件 ID
- freeEventId: 释放事件 ID

#### Scenario: 历史块检测
- **GIVEN** 块 ID < 0
- **WHEN** 访问 is_historical_block 属性
- **THEN** 返回 True

#### Scenario: 活跃块检测
- **GIVEN** 块未释放（freeEventId is None 或 -1）
- **WHEN** 访问 is_active 属性
- **THEN** 返回 True

### Requirement: Context 类
系统 SHALL 实现数据库上下文管理：

- db_path: 数据库路径
- devices: 设备 ID 列表（可选）
- device_ids: 获取设备 ID 列表
- cursor(): 获取数据库游标
- connect(): 上下文管理器
- close(): 关闭连接

#### Scenario: 打开有效数据库
- **GIVEN** 有效的 SQLite 数据库文件
- **WHEN** 创建 Context 实例
- **THEN** 成功打开连接

#### Scenario: 数据库不存在
- **GIVEN** 数据库文件不存在
- **WHEN** 创建 Context 实例
- **THEN** 抛出 DatabaseNotFoundError

#### Scenario: Schema 验证失败
- **GIVEN** 数据库缺少 dictionary 表
- **WHEN** 创建 Context 实例
- **THEN** 抛出 SchemaVersionError

---

## MODIFIED Requirements
无

## REMOVED Requirements
无

---

## 1. Overview

### 1.1 Purpose
构建 pt-snap-analyzer 项目的基础框架，包括 CLI 入口、数据模型定义、Context 类管理数据库连接。

### 1.2 Scope
- CLI 命令框架设计与实现
- 数据模型定义（EventType、BlockState 枚举，MemoryEvent、MemoryBlock 数据类）
- Context 类实现数据库连接管理和生命周期控制
- 版本管理和项目配置

---

## 2. Technical Architecture

### 2.1 File Structure
```
pt_snap_analyzer/
├── __init__.py           # Package exports
├── cli.py                # CLI entry point with Typer
├── context.py            # Context class for DB management
├── models/
│   ├── __init__.py       # Models exports
│   ├── _enums.py         # Enum types (EventType, BlockState)
│   ├── event.py          # MemoryEvent model
│   └── block.py          # MemoryBlock model
├── version.py            # Package version
└── __init__.py
```

### 2.2 Data Models

#### EventType (IntEnum)
- `SEGMENT_MAP = 0` - Segment mapping
- `SEGMENT_UNMAP = 1` - Segment unmapping
- `SEGMENT_ALLOC = 2` - Segment allocation
- `SEGMENT_FREE = 3` - Segment freeing
- `ALLOC = 4` - Memory allocation
- `FREE_REQUESTED = 5` - Free requested
- `FREE_COMPLETED = 6` - Free completed
- `WORKSPACE_SNAPSHOT = 7` - Workspace snapshot

#### BlockState (IntEnum)
- `INACTIVE = -1` - Inactive state
- `ACTIVE_PENDING_FREE = 0` - Active, pending free
- `ACTIVE_ALLOCATED = 1` - Active, allocated
- `UNKNOWN = 99` - Unknown state

### 2.3 Context Class
**Responsibilities:**
- Database connection management (read-only mode)
- Schema version validation
- Device ID discovery and filtering
- Connection lifecycle control

**Key Methods:**
- `__init__(db_path, devices=None)` - Initialize context
- `device_ids` - Get list of device IDs
- `cursor()` - Get database cursor
- `connect()` - Context manager for connection
- `close()` - Close database connection

---

## 3. Implementation Requirements

### 3.1 Dependencies
```toml
dependencies = [
    "typer>=0.9.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "chromadb>=0.4.0",
    "langchain>=0.1.0",
]
```

### 3.2 Testing Strategy
- Unit tests for each module
- Coverage target: >80%
- Test database with sample schema

---

## 4. Success Criteria
- [ ] CLI 可以正常运行 `pt-snap --help`
- [ ] 所有数据模型正确实现
- [ ] Context 类可以正确连接和管理数据库
- [ ] 所有单元测试通过
- [ ] 项目可以正常安装 `pip install -e .[dev]`
- [ ] 测试覆盖率 >80%
- [ ] 代码通过 ruff 检查
- [ ] 代码通过 black 格式化

---

## 5. Risks and Mitigations

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 数据库格式变更 | 高 | 低 | Context 类实现 schema 版本验证，提前检测不兼容 |
| 依赖库版本冲突 | 中 | 中 | 在 pyproject.toml 中固定最小版本，使用 dev 依赖隔离 |
| SQLite 只读模式限制 | 低 | 低 | 仅读取数据，不需要写入，只读模式更安全 |
| 大型数据库性能问题 | 中 | 中 | 数据库以只读模式打开，避免锁竞争；后续考虑索引优化 |
| Python 版本兼容性 | 中 | 低 | 限制 Python 3.10+，使用类型注解和新特性 |
| CLI 参数验证不足 | 中 | 中 | 使用 Typer 的参数验证功能，添加适当的错误处理 |

---

## 6. Appendix

### 参考文档
- [Typer 文档](https://typer.tiangolo.com/)
- [Pydantic 文档](https://docs.pydantic.dev/)
- [SQLite3 文档](https://docs.python.org/3/library/sqlite3.html)
- [pytest 文档](https://docs.pytest.org/)

### 相关讨论
- PyTorch 内存快照格式分析
- 数据库 schema 设计讨论

### 设计决策记录
1. **选择 Typer 而非 argparse**: Typer 提供类型注解支持，更现代，自动帮助文档
2. **使用 dataclass 而非 Pydantic**: 基础模块保持轻量，Pydantic 用于后续复杂场景
3. **SQLite 只读模式**: 分析工具不应修改原始数据，保证数据完整性
4. **枚举使用 IntEnum**: 便于与数据库整数值互操作

### 示例数据库
- 位置：`examples/snapshot_expandable.pkl.db`
- 格式：SQLite3
- Schema 版本：v1.0（通过 dictionary 表验证）
