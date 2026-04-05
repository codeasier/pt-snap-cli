# Tasks: pt-snap-analyzer 查询系统

---

## Task List

- [ ] Task 1: 查询条件实现
  - [ ] Step 1: 创建条件基类
  - [ ] Step 2: 实现条件类型 (Equal, NotEqual, GreaterThan, LessThan, In, Like)
  - [ ] Step 3: 实现组合条件 (And, Or)
  - [ ] Step 4: 创建测试文件
  - [ ] Step 5: 运行测试
  - [ ] Step 6: Commit

- [ ] Task 2: 查询构建器实现
  - [ ] Step 1: 创建查询构建器 (QueryBuilder)
  - [ ] Step 2: 实现 fluent API 方法 (from_table, where, order_by, limit, offset, columns)
  - [ ] Step 3: 实现 build() 方法
  - [ ] Step 4: 实现 execute() 方法
  - [ ] Step 5: 创建测试文件
  - [ ] Step 6: 运行测试
  - [ ] Step 7: Commit

- [ ] Task 3: 查询注册表和 CLI 集成
  - [ ] Step 1: 创建查询注册表
  - [ ] Step 2: 注册预定义查询 (active_blocks, events_by_type, memory_by_device, blocks_by_size)
  - [ ] Step 3: 扩展 CLI 查询命令
  - [ ] Step 4: 创建测试文件
  - [ ] Step 5: 运行测试
  - [ ] Step 6: Commit

- [ ] Task 4: 结果映射器
  - [ ] Step 1: 创建结果映射器 (ResultMapper)
  - [ ] Step 2: 实现类型映射 (map, map_all)
  - [ ] Step 3: 实现便捷函数 (map_to_events, map_to_blocks, map_to_analysis)
  - [ ] Step 4: 创建测试文件
  - [ ] Step 5: 运行测试
  - [ ] Step 6: Commit

- [ ] Task 5: 集成测试
  - [ ] Step 1: 运行所有测试
  - [ ] Step 2: 代码质量检查
  - [ ] Step 3: 手动测试 CLI
  - [ ] Step 4: 最终 Commit

## Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
