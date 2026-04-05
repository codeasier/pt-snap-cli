# Tasks: pt-snap-analyzer 分析器模块

---

## Task List

- [ ] Task 1: 分析器基类和数据模型
  - [ ] Step 1: 创建 analysis 数据模型 (AnalysisResult, MemoryStats, BlockStats)
  - [ ] Step 2: 创建 AnalyzerBase 抽象基类
  - [ ] Step 3: 创建 models 初始化文件
  - [ ] Step 4: 创建测试文件
  - [ ] Step 5: 运行测试
  - [ ] Step 6: Commit

- [ ] Task 2: 泄漏检测分析器
  - [ ] Step 1: 创建泄漏数据模型 (LeakInfo, LeakResult)
  - [ ] Step 2: 创建泄漏检测分析器
  - [ ] Step 3: 创建测试文件
  - [ ] Step 4: 运行测试
  - [ ] Step 5: Commit

- [ ] Task 3: 峰值分析器
  - [ ] Step 1: 创建峰值数据模型 (PeakInfo, PeakResult)
  - [ ] Step 2: 创建峰值分析器
  - [ ] Step 3: 创建测试文件
  - [ ] Step 4: 运行测试
  - [ ] Step 5: Commit

- [ ] Task 4: 块生命周期分析器
  - [ ] Step 1: 创建生命周期分析器
  - [ ] Step 2: 创建测试文件
  - [ ] Step 3: 运行测试
  - [ ] Step 4: Commit

- [ ] Task 5: CLI 集成和 SDK
  - [ ] Step 1: 扩展 CLI 命令
  - [ ] Step 2: 更新 SDK 导出
  - [ ] Step 3: 创建集成测试
  - [ ] Step 4: 运行测试
  - [ ] Step 5: Commit

## Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
