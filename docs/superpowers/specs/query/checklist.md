# Checklist: pt-snap-analyzer 查询系统

## Query Conditions
- [ ] Condition ABC 正确定义
- [ ] Equal 条件正确实现
- [ ] NotEqual 条件正确实现
- [ ] GreaterThan 条件正确实现
- [ ] LessThan 条件正确实现
- [ ] In 条件正确实现
- [ ] Like 条件正确实现
- [ ] And 条件正确实现
- [ ] Or 条件正确实现

## Query Builder
- [ ] QueryBuilder 类正确实现
- [ ] from_table() 方法正确
- [ ] where() 方法正确
- [ ] order_by() 方法正确
- [ ] limit() 方法正确
- [ ] offset() 方法正确
- [ ] build() 方法正确生成 SQL
- [ ] execute() 方法正确执行查询

## Query Registry
- [ ] 注册表正确实现
- [ ] register_query 装饰器正确
- [ ] get_query() 函数正确
- [ ] list_queries() 函数正确
- [ ] preregistered queries 正确

## Result Mapper
- [ ] ResultMapper 类正确实现
- [ ] register() 方法正确
- [ ] map() 方法正确
- [ ] map_all() 方法正确
- [ ] map_to_events() 函数正确
- [ ] map_to_blocks() 函数正确
- [ ] map_to_analysis() 函数正确

## CLI Integration
- [ ] CLI query 命令正确
- [ ] CLI list-queries 命令正确
- [ ] 查询名验证正确
- [ ] 错误处理正确

## Testing
- [ ] tests/test_conditions.py 通过（8 tests）
- [ ] tests/test_builder.py 通过（7 tests）
- [ ] tests/test_registry.py 通过（3 tests）
- [ ] tests/test_mapper.py 通过（5 tests）
- [ ] 集成测试通过
- [ ] 覆盖率 >80%

## Code Quality
- [ ] ruff check 无错误
- [ ] black 格式化完成
- [ ] isort 导入排序正确
- [ ] 类型注解完整
- [ ] 文档字符串完整

## Documentation
- [ ] 查询 API 文档
- [ ] 使用示例
- [ ] 查询名列表

## Version Control
- [ ] 所有 changes committed
- [ ] Commit message 清晰描述变更
- [ ] Git log 历史清晰
