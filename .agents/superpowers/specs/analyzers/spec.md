# Spec: pt-snap-analyzer 分析器模块

**Goal:** 实现核心分析器模块：泄漏检测、峰值分析、趋势分析、调用栈分析

**Architecture:** 基于 AnalyzerBase 抽象基类，每个分析器实现独立的 analyze() 方法，返回结构化结果

**Tech Stack:** Python 3.10+, SQLite3, Pydantic

---

## Why

### 当前痛点
- 开发者无法快速识别内存泄漏问题，需要人工逐行分析事件日志
- 内存峰值出现时无法定位原因，缺少系统化的分析工具
- 内存使用趋势不明朗，无法预测潜在的内存风险
- 调用栈信息分散，难以关联到具体的代码位置

### 需要解决的问题
- 实现自动化的泄漏检测算法，识别异常的内存分配模式
- 分析内存峰值时刻的上下文信息，定位峰值原因
- 统计内存使用趋势，提供预警机制
- 聚合调用栈信息，关联到具体的代码位置

### 预期的业务价值
- 内存泄漏检测时间从数小时降低到分钟级别
- 峰值分析效率提升 70% 以上
- 提前发现 80% 以上的内存风险
- 减少人工分析工作量，提高开发效率

---

## What Changes

### 新增功能/模块
- AnalyzerBase 抽象基类：定义分析器接口
- LeakDetector：泄漏检测分析器
- PeakAnalyzer：峰值分析分析器
- TrendAnalyzer：趋势分析分析器
- StackAnalyzer：调用栈分析分析器
- AnalysisResult 基类：分析结果数据结构
- LeakResult/PeakResult/TrendResult/StackResult：专用结果类型

### 修改的组件
- `pt_snap_analyzer/cli.py` - 新增分析命令
- `pt_snap_analyzer/models/__init__.py` - 导出新的结果模型

### 删除的功能
- 无

### 技术架构变更
- 引入抽象基类模式
- 分析器插件化架构

---

## Impact

### 影响的规格文档
- foundation/spec.md - 依赖 Context 类

### 影响的代码模块
- `pt_snap_analyzer/analyzers/__init__.py` - 新增：包初始化
- `pt_snap_analyzer/analyzers/base.py` - 新增：分析器基类
- `pt_snap_analyzer/analyzers/leak_detector.py` - 新增：泄漏检测
- `pt_snap_analyzer/analyzers/peak_analyzer.py` - 新增：峰值分析
- `pt_snap_analyzer/analyzers/trend_analyzer.py` - 新增：趋势分析
- `pt_snap_analyzer/analyzers/stack_analyzer.py` - 新增：调用栈分析
- `pt_snap_analyzer/models/result.py` - 新增：分析结果基类
- `pt_snap_analyzer/models/leak.py` - 新增：泄漏结果
- `pt_snap_analyzer/models/peak.py` - 新增：峰值结果
- `pt_snap_analyzer/models/trend.py` - 新增：趋势结果
- `pt_snap_analyzer/models/stack.py` - 新增：调用栈结果

### 影响的依赖
- 无新增依赖（使用 foundation 已有依赖）

### 影响的配置
- 无环境变量变更
- 无配置文件变更

---

## ADDED Requirements

### Requirement: AnalyzerBase 抽象基类
系统 SHALL 定义分析器抽象基类：

- name: 分析器名称
- description: 分析器描述
- context: 分析上下文
- analyze(**kwargs) -> AnalysisResult: 执行分析
- validate_context(context) -> bool: 验证上下文

#### Scenario: 继承分析器
- **GIVEN** AnalyzerBase 基类已定义
- **WHEN** 创建子类并实现 analyze() 方法
- **THEN** 可以正常实例化并执行分析

### Requirement: LeakDetector 泄漏检测
系统 SHALL 实现泄漏检测分析器：

- 检测未释放的内存块
- 识别重复分配模式
- 定位泄漏源（调用栈）
- 返回泄漏统计信息

#### Scenario: 检测内存泄漏
- **GIVEN** 数据库包含未释放的内存块
- **WHEN** 执行 LeakDetector.analyze()
- **THEN** 返回泄漏块列表和调用栈信息

### Requirement: PeakAnalyzer 峰值分析
系统 SHALL 实现峰值分析分析器：

- 识别内存峰值时刻
- 分析峰值时的活跃块
- 统计峰值贡献者
- 返回峰值详情

#### Scenario: 分析内存峰值
- **GIVEN** 数据库包含完整的事件历史
- **WHEN** 执行 PeakAnalyzer.analyze()
- **THEN** 返回峰值时间、峰值大小、主要贡献者

### Requirement: TrendAnalyzer 趋势分析
系统 SHALL 实现趋势分析分析器：

- 计算内存使用趋势
- 识别异常增长点
- 预测未来趋势
- 返回趋势统计

#### Scenario: 分析内存趋势
- **GIVEN** 数据库包含长时间跨度的事件
- **WHEN** 执行 TrendAnalyzer.analyze()
- **THEN** 返回趋势线、增长率、异常点

### Requirement: StackAnalyzer 调用栈分析
系统 SHALL 实现调用栈分析分析器：

- 聚合调用栈信息
- 统计各栈的内存使用
- 识别高频分配位置
- 返回调用栈统计

#### Scenario: 分析调用栈
- **GIVEN** 数据库包含调用栈信息
- **WHEN** 执行 StackAnalyzer.analyze()
- **THEN** 返回调用栈排名和内存使用统计

### Requirement: AnalysisResult 结果类
系统 SHALL 定义分析结果基类：

- metadata: 元数据
- to_dict() -> Dict: 转换为字典
- to_json() -> str: 转换为 JSON

#### Scenario: 结果序列化
- **GIVEN** 分析结果实例
- **WHEN** 调用 to_json() 方法
- **THEN** 返回有效的 JSON 字符串

---

## MODIFIED Requirements
无

## REMOVED Requirements
无

---

## 1. Overview

### 1.1 Purpose
实现 pt-snap-analyzer 的核心分析功能，提供对 PyTorch 内存快照的深度分析能力。

### 1.2 Scope
- 分析器框架设计与实现
- 泄漏检测分析器
- 峰值分析分析器
- 趋势分析分析器
- 调用栈分析分析器
- 分析结果模型定义

---

## 2. Technical Architecture

### 2.1 File Structure
```
pt_snap_analyzer/
├── analyzers/
│   ├── __init__.py
│   ├── base.py            # AnalyzerBase 抽象基类
│   ├── leak_detector.py   # 泄漏检测
│   ├── peak_analyzer.py   # 峰值分析
│   ├── trend_analyzer.py  # 趋势分析
│   └── stack_analyzer.py  # 调用栈分析
├── models/
│   ├── result.py          # AnalysisResult 基类
│   ├── leak.py            # LeakResult
│   ├── peak.py            # PeakResult
│   ├── trend.py           # TrendResult
│   └── stack.py           # StackResult
└── cli.py                 # 新增分析命令
```

### 2.2 Analyzer Pattern

#### AnalyzerBase (ABC)
**Abstract Base Class for Analysers**

**Key Methods:**
- `analyze(**kwargs) -> AnalysisResult` - Execute analysis
- `validate_context(context: Context) -> bool` - Validate context

**Attributes:**
- `name: str` - Analyzer name
- `description: str` - Analyzer description
- `context: Context` - Analysis context

#### AnalysisResult
**Base class for analysis results**

**Key Methods:**
- `to_dict() -> Dict[str, Any]` - Convert to dictionary
- `to_json() -> str` - Convert to JSON string

**Attributes:**
- `metadata: Dict[str, Any]` - Analysis metadata

### 2.3 Analyzer Implementations

#### LeakDetector
**Detects memory leaks**

**Key Methods:**
- `analyze(min_size=0, top_n=10) -> LeakResult` - Detect leaks
- `_find_unreleased_blocks()` - Find unreleased blocks
- `_identify_leak_patterns()` - Identify leak patterns

#### PeakAnalyzer
**Analyzes memory peaks**

**Key Methods:**
- `analyze(top_k=5) -> PeakResult` - Analyze peaks
- `_find_peak_moments()` - Find peak moments
- `_analyze_peak_contributors()` - Analyze contributors

#### TrendAnalyzer
**Analyzes memory usage trends**

**Key Methods:**
- `analyze(window_size=100) -> TrendResult` - Analyze trends
- `_calculate_moving_average()` - Calculate MA
- `_detect_anomalies()` - Detect anomalies

#### StackAnalyzer
**Analyzes call stacks**

**Key Methods:**
- `analyze(min_count=1) -> StackResult` - Analyze stacks
- `_aggregate_stacks()` - Aggregate call stacks
- `_rank_by_frequency()` - Rank by frequency

---

## 3. Implementation Requirements

### 3.1 Dependencies
无新增依赖，使用 foundation 模块的依赖。

### 3.2 Testing Strategy
- 单元测试：每个分析器独立测试
- 集成测试：使用示例数据库测试
- 边界测试：空数据库、无事件、无泄漏等场景
- 覆盖率目标：>80%

---

## 4. Success Criteria
- [ ] 所有分析器正确实现
- [ ] 泄漏检测准确
- [ ] 峰值分析正确
- [ ] 趋势分析合理
- [ ] 调用栈分析完整
- [ ] 所有单元测试通过
- [ ] 测试覆盖率 >80%
- [ ] 代码通过 ruff 检查
- [ ] 代码通过 black 格式化

---

## 5. Risks and Mitigations

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 泄漏检测算法误判 | 高 | 中 | 提供可配置的阈值，支持人工确认 |
| 峰值分析性能问题 | 中 | 中 | 使用 SQL 聚合查询，避免 Python 层计算 |
| 趋势分析准确性 | 中 | 中 | 使用多种算法对比，提供置信度指标 |
| 调用栈信息缺失 | 高 | 低 | 优雅降级，返回部分分析结果 |
| 分析器耦合 | 中 | 低 | 严格遵守抽象基类接口，保持独立性 |
| 结果格式化复杂 | 低 | 中 | 使用统一的 to_dict() 方法，便于序列化 |

---

## 6. Appendix

### 参考文档
- [Python ABC](https://docs.python.org/3/library/abc.html)
- [SQLite 聚合函数](https://www.sqlite.org/lang_aggfunc.html)
- [统计分析算法](https://en.wikipedia.org/wiki/Statistical_analysis)

### 相关讨论
- 泄漏检测算法设计
- 峰值定义和识别策略
- 趋势分析方法选择

### 设计决策记录
1. **使用抽象基类而非 Protocol**: 更清晰的继承关系，便于扩展
2. **分析器独立实现**: 每个分析器专注于单一职责，便于测试和维护
3. **结果统一序列化**: 所有结果支持 to_dict() 和 to_json()，便于 CLI 输出
4. **可配置参数**: 每个分析器支持参数调整，适应不同场景

### 示例输出
```json
{
  "analyzer": "LeakDetector",
  "timestamp": "2026-04-04T10:00:00Z",
  "metadata": {
    "total_leaks": 5,
    "leaked_bytes": 1048576
  },
  "leaks": [
    {
      "address": "0x1000",
      "size": 262144,
      "stack": "train.py:42"
    }
  ]
}
```
