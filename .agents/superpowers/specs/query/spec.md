# Spec: pt-snap-analyzer 查询系统

**Goal:** 实现查询配置系统，支持 YAML 配置的 SQL 模板和查询执行器

**Architecture:** YAML 配置存储 SQL 模板，查询执行器渲染模板并执行查询，支持参数替换和设备适配

**Tech Stack:** Python 3.10+, SQLite3, PyYAML, Jinja2

---

## Why

### 当前痛点
- 硬编码 SQL 查询语句，难以维护和扩展
- 每次新增查询需要修改代码，不符合开闭原则
- 查询参数化困难，不同场景需要不同的查询条件
- 无法灵活配置查询输出格式和字段

### 需要解决的问题
- 将 SQL 查询模板化，支持配置化管理
- 实现查询执行器，支持动态参数替换
- 提供设备适配能力，支持多 GPU 场景
- 支持自定义查询输出 schema

### 预期的业务价值
- 查询开发效率提升 80%，无需修改代码
- 支持用户自定义查询，增强扩展性
- 降低 SQL 注入风险，参数自动转义
- 统一查询接口，便于集成和复用

---

## What Changes

### 新增功能/模块
- QueryConfig：配置数据模型
- QueryTemplate：查询模板定义
- QueryExecutor：查询执行器
- YAML 配置管理
- SQL 模板渲染引擎

### 修改的组件
- `pt_snap_analyzer/cli.py` - 新增查询命令
- `pt_snap_analyzer/__init__.py` - 导出查询模块

### 删除的功能
- 无

### 技术架构变更
- 引入 YAML 配置管理
- 引入模板渲染机制

---

## Impact

### 影响的规格文档
- foundation/spec.md - 依赖 Context 类

### 影响的代码模块
- `pt_snap_analyzer/query/__init__.py` - 新增：包初始化
- `pt_snap_analyzer/query/config.py` - 新增：配置管理
- `pt_snap_analyzer/query/executor.py` - 新增：查询执行器
- `pt_snap_analyzer/query/templates/` - 新增：模板目录
- `pt_snap_analyzer/query/templates/leak_detection_v2.yaml` - 新增：泄漏检测模板
- `pt_snap_analyzer/query/templates/memory_timeline_v2.yaml` - 新增：时间线模板
- `pt_snap_analyzer/query/templates/callstack_analysis_v2.yaml` - 新增：调用栈模板

### 影响的依赖
- `PyYAML>=6.0` - 已在 foundation 中定义
- `Jinja2>=3.0.0` - 新增：模板渲染

### 影响的配置
- 无环境变量变更
- 配置文件：YAML 查询模板

---

## ADDED Requirements

### Requirement: QueryConfig 配置类
系统 SHALL 定义查询配置类：

- version: 配置版本
- queries: 查询模板字典
- load_yaml(path) -> QueryConfig: 从 YAML 加载
- get_query(name) -> QueryTemplate: 获取查询模板

#### Scenario: 加载配置文件
- **GIVEN** 存在有效的 YAML 配置文件
- **WHEN** 调用 load_yaml(config_path)
- **THEN** 返回 QueryConfig 实例

### Requirement: QueryTemplate 模板类
系统 SHALL 定义查询模板类：

- name: 查询名称
- description: 查询描述
- devices: 适用设备列表
- parameters: 参数定义
- query: SQL 模板字符串
- output_schema: 输出 schema 定义

#### Scenario: 参数验证
- **GIVEN** 查询模板包含必需参数
- **WHEN** 参数未提供
- **THEN** 抛出参数缺失错误

### Requirement: QueryExecutor 执行器
系统 SHALL 实现查询执行器：

- render(template, params) -> str: 渲染 SQL 模板
- execute(query, params) -> List[Dict]: 执行查询
- execute_template(name, params) -> List[Dict]: 执行模板查询
- validate_output(result, schema) -> bool: 验证输出

#### Scenario: 执行参数化查询
- **GIVEN** 有效的查询模板和参数
- **WHEN** 调用 execute_template(name, params)
- **THEN** 返回查询结果列表

#### Scenario: 设备适配
- **GIVEN** 多设备数据库
- **WHEN** 执行查询并指定设备
- **THEN** 只查询指定设备的数据

### Requirement: SQL 模板渲染
系统 SHALL 支持 SQL 模板语法：

- 参数替换：{{ param_name }}
- 条件语法：{% if condition %}...{% endif %}
- 循环语法：{% for item in items %}...{% endfor %}
- 设备表名：{{ device_table }}

#### Scenario: 参数替换
- **GIVEN** SQL 模板包含 {{ min_size }}
- **WHEN** 提供参数 min_size=1024
- **THEN** 渲染后的 SQL 包含 1024

### Requirement: 预定义查询模板
系统 SHALL 提供预定义查询模板：

- leak_detection_v2: 泄漏检测查询
- memory_timeline_v2: 内存时间线查询
- callstack_analysis_v2: 调用栈分析查询

#### Scenario: 使用预定义模板
- **GIVEN** 预定义模板已注册
- **WHEN** 执行 leak_detection_v2
- **THEN** 返回泄漏检测结果

---

## MODIFIED Requirements
无

## REMOVED Requirements
无

---

## 1. Overview

### 1.1 Purpose
提供灵活的查询能力，支持 YAML 配置的 SQL 模板、参数化查询、设备适配和结果验证。

### 1.2 Scope
- 查询配置系统设计
- SQL 模板渲染引擎
- 查询执行器实现
- 预定义查询模板
- CLI 查询命令

---

## 2. Technical Architecture

### 2.1 File Structure
```
pt_snap_analyzer/
├── query/
│   ├── __init__.py
│   ├── config.py          # QueryConfig, QueryTemplate
│   ├── executor.py        # QueryExecutor
│   └── templates/
│       ├── leak_detection_v2.yaml
│       ├── memory_timeline_v2.yaml
│       └── callstack_analysis_v2.yaml
└── cli.py                 # 新增查询命令
```

### 2.2 Configuration Model

#### QueryParameter
**Query parameter definition**

**Attributes:**
- `name: str` - Parameter name
- `default: Any` - Default value
- `type: str` - Type ('str', 'int', 'float', 'bool')
- `description: str` - Parameter description
- `required: bool` - Whether required

#### QueryTemplate
**SQL query template**

**Attributes:**
- `name: str` - Template name
- `description: str` - Template description
- `devices: List[str]` - Applicable devices
- `parameters: Dict[str, QueryParameter]` - Parameter definitions
- `query: str` - SQL template string
- `output_schema: List[Dict[str, str]]` - Output schema

#### QueryConfig
**Query configuration**

**Attributes:**
- `version: str` - Config version
- `queries: Dict[str, QueryTemplate]` - Query templates

**Key Methods:**
- `load_yaml(path: str) -> QueryConfig` - Load from YAML
- `get_query(name: str) -> QueryTemplate` - Get template

### 2.3 Query Executor

#### QueryExecutor
**Executes queries with template rendering**

**Key Methods:**
- `render(template: QueryTemplate, params: Dict) -> str` - Render SQL
- `execute(query: str, params: Dict) -> List[Dict]` - Execute SQL
- `execute_template(name: str, params: Dict) -> List[Dict]` - Execute template
- `validate_output(result: List, schema: List) -> bool` - Validate output

### 2.4 Template Syntax

**Parameter substitution:**
- `{{ param_name }}` - Simple substitution
- `{{ param_name|upper }}` - With filter
- `{% if condition %}...{% endif %}` - Conditional
- `{% for item in items %}...{% endfor %}` - Loop

**Special variables:**
- `{{ device_table }}` - Current device table name
- `{{ device_id }}` - Current device ID

---

## 3. Implementation Requirements

### 3.1 Dependencies
- `Jinja2>=3.0.0` - 新增：模板渲染
- `PyYAML>=6.0` - 已有：YAML 解析

### 3.2 Testing Strategy
- 单元测试：配置加载、模板渲染、查询执行
- 集成测试：使用示例数据库测试查询
- 模板测试：验证预定义模板正确性
- 覆盖率目标：>80%

---

## 4. Success Criteria
- [ ] 配置系统正确实现
- [ ] 模板渲染正确
- [ ] 查询执行正确
- [ ] 参数替换正常
- [ ] 设备适配正常
- [ ] 预定义模板可用
- [ ] 所有单元测试通过
- [ ] 测试覆盖率 >80%
- [ ] 代码通过 ruff 检查
- [ ] 代码通过 black 格式化

---

## 5. Risks and Mitigations

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| SQL 注入风险 | 高 | 低 | 使用参数化查询，不直接拼接 SQL |
| 模板渲染错误 | 中 | 中 | 提供详细的错误信息和模板调试功能 |
| YAML 配置格式错误 | 中 | 中 | 严格的 schema 验证，友好的错误提示 |
| 设备适配复杂 | 中 | 中 | 抽象设备管理逻辑，提供默认实现 |
| 模板性能问题 | 低 | 低 | 模板预编译缓存，避免重复渲染 |
| Jinja2 依赖冲突 | 低 | 低 | 固定 Jinja2 版本，使用虚拟环境 |

---

## 6. Appendix

### 参考文档
- [Jinja2 文档](https://jinja.palletsprojects.com/)
- [PyYAML 文档](https://pyyaml.org/wiki/PyYAMLDocumentation)
- [SQLite 查询优化](https://www.sqlite.org/optoverview.html)

### 相关讨论
- SQL 模板设计规范
- 参数化查询最佳实践
- 设备适配策略

### 设计决策记录
1. **选择 Jinja2 而非 string.format**: Jinja2 更强大，支持条件/循环，安全性更好
2. **YAML 而非 JSON 配置**: YAML 更易读，支持注释，便于维护
3. **预编译模板缓存**: 提高性能，避免重复解析
4. **设备适配层**: 简化多设备查询逻辑

### 示例 YAML 模板
```yaml
name: leak_detection_v2
description: Detect memory leaks
devices: ["all", "0", "1"]
parameters:
  min_size:
    type: int
    default: 1024
    required: false
    description: Minimum leak size
query: |
  SELECT id, address, size, callstack
  FROM {{ device_table }}
  WHERE size >= {{ min_size }}
    AND freeEventId IS NULL
output_schema:
  - column: id
    type: int
  - column: address
    type: hex
  - column: size
    type: int
```

### 示例查询执行
```python
from pt_snap_analyzer.query import QueryExecutor

executor = QueryExecutor(config_path="templates/")
results = executor.execute_template(
    "leak_detection_v2",
    {"min_size": 2048, "device_id": 0}
)
```
