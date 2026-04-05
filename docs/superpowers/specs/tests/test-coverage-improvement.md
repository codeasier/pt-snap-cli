# 测试覆盖率提升规格说明书

## Why
<!-- 说明为什么需要这个功能，解决什么问题，业务价值是什么 -->
当前 `pt_snap_analyzer` 项目中三个核心文件的测试覆盖率较低：
- `condition.py`: 查询条件类的 SQL 生成和组合逻辑
- `registry.py`: 查询注册表的单例模式、注册、查询、模板加载功能
- `cli.py`: 命令行接口的所有命令和选项

需要补充完整的测试用例以确保：
- 核心功能的质量可靠性
- 防止回归 bug
- 提高代码可维护性
- 满足项目的覆盖率要求

## What Changes
<!-- 详细说明需要做哪些变更 -->
### 新增测试文件
- `tests/test_condition.py`: 完整的查询条件类测试
- `tests/test_registry.py`: 完整的查询注册表测试
- `tests/test_cli.py`: 完整的 CLI 命令测试

### 修改的组件
- 无修改现有代码，仅新增测试文件

### 技术架构变更
- 使用 pytest 作为测试框架
- 使用 pytest-mock 进行 mock 测试
- 使用 typer.testing.TestRunner 进行 CLI 测试

## Impact
<!-- 分析变更范围 -->
### 影响的规格文档
- 无

### 影响的代码模块
- 新增：`tests/test_condition.py`
- 新增：`tests/test_registry.py`
- 新增：`tests/test_cli.py`

### 影响的依赖
- pytest (已存在)
- pytest-mock (需确认是否已安装)
- typer.testing (已包含在 typer 中)

### 影响的配置
- 无配置文件变更

## ADDED Requirements
<!-- 新增的需求 -->

### Requirement: condition.py 测试覆盖
系统 SHALL 覆盖所有查询条件类的测试：

- 基础条件类：Equal, NotEqual, GreaterThan, LessThan, GreaterThanOrEqual, LessThanOrEqual
- 特殊条件类：In, Like
- 组合条件类：And, Or
- 混合组合：And 和 Or 的嵌套和组合

#### Scenario: 基础条件类测试
- **GIVEN** 条件类实例已创建
- **WHEN** 调用 to_sql() 方法
- **THEN** 返回正确的 SQL 字符串和参数列表

#### Scenario: 组合条件测试
- **GIVEN** 多个条件实例
- **WHEN** 使用 & 或 | 操作符组合
- **THEN** 生成正确的复合 SQL 表达式

#### Scenario: 边界条件测试
- **GIVEN** 空列表或特殊值
- **WHEN** 创建条件或组合条件
- **THEN** 正确处理边界情况

### Requirement: registry.py 测试覆盖
系统 SHALL 覆盖查询注册表的所有功能测试：

- 单例模式：创建、重置
- 注册功能：模板注册、工厂函数注册
- 查询功能：按名称查询、列表查询
- 模板加载：YAML 文件加载
- 模块级函数：便捷函数测试

#### Scenario: 单例模式测试
- **GIVEN** 多次调用 QueryRegistry()
- **WHEN** 检查实例
- **THEN** 返回同一实例（重置前）

#### Scenario: 注册和查询测试
- **GIVEN** 模板或工厂函数已注册
- **WHEN** 调用 get() 方法
- **THEN** 返回正确的模板

#### Scenario: YAML 加载测试
- **GIVEN** YAML 模板文件存在
- **WHEN** 调用 _load_yaml_templates()
- **THEN** 模板成功加载到注册表

### Requirement: cli.py 测试覆盖
系统 SHALL 覆盖所有 CLI 命令和选项的测试：

- version 回调函数
- use 命令：数据库配置
- query 命令：查询执行
- config 命令：配置管理

#### Scenario: use 命令测试
- **GIVEN** 数据库路径（存在/不存在）
- **WHEN** 执行 use 命令
- **THEN** 正确配置数据库并显示设备信息

#### Scenario: query 命令测试
- **GIVEN** 查询模板和参数
- **WHEN** 执行 query 命令
- **THEN** 返回正确的查询结果

#### Scenario: config 命令测试
- **GIVEN** 配置存在/不存在
- **WHEN** 执行 config 命令（显示/清空/路径）
- **THEN** 正确显示或修改配置

## MODIFIED Requirements
<!-- 修改的需求 -->
无

## REMOVED Requirements
<!-- 移除的需求 -->
无

## Technical Design
<!-- 技术设计方案 -->

### 测试策略
- 单元测试：测试独立的函数和类
- 集成测试：测试组件间交互
- Mock 测试：隔离外部依赖

### 测试工具
- pytest: 测试框架
- pytest-mock: mock 功能
- typer.testing.TestRunner: CLI 测试

### 测试组织
```
tests/
├── test_condition.py    # 查询条件测试
├── test_registry.py     # 注册表测试
└── test_cli.py          # CLI 测试
```

## Risks and Mitigations
<!-- 风险分析和缓解措施 -->
| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| pytest-mock 未安装 | 中 | 低 | 提前检查并安装依赖 |
| CLI 测试依赖数据库 | 中 | 中 | 使用临时文件和 mock |
| 测试执行时间长 | 低 | 低 | 优化测试结构，并行执行 |

## Success Criteria
<!-- 成功标准 -->
- [ ] condition.py 测试覆盖率 >= 90%
- [ ] registry.py 测试覆盖率 >= 90%
- [ ] cli.py 测试覆盖率 >= 90%
- [ ] 所有测试用例通过
- [ ] 无 flaky 测试
- [ ] 测试代码符合项目规范

## Appendix
<!-- 附录 -->
- 测试文件将输出到 `/Users/test1/liuyekang/dev/code/pt-snap-cli/docs/superpowers/specs/tests/`
- 参考模板：`docs/superpowers/specs/.templates/`
