# Checklist: pt-snap-analyzer RAG 知识库

## Data Models
- [ ] AnalysisStep dataclass 正确定义
- [ ] RAGCase dataclass 正确定义
- [ ] RAGCase.__post_init__ 正确生成 case_id 和 timestamp
- [ ] SearchMatch dataclass 正确定义
- [ ] SearchResult dataclass 正确定义

## Case Archive System
- [ ] ArchiveError 异常类定义
- [ ] CaseArchive 类正确实现
- [ ] add_case() 方法正确实现
- [ ] add_case() 方法验证 required 字段
- [ ] get_case() 方法正确实现
- [ ] list_cases() 方法正确实现
- [ ] list_cases() 支持 tag 过滤 (AND logic)
- [ ] delete_case() 方法正确实现
- [ ] _case_to_dict() 方法正确序列化
- [ ] _dict_to_case() 方法正确反序列化

## Searcher System
- [ ] Searcher 类正确实现
- [ ] search() 方法正确实现
- [ ] _score_case() 方法正确计算分数
- [ ] _normalize_text() 方法正确规范化文本
- [ ] get_tags() 方法正确返回所有标签
- [ ] top_k 参数正确限制结果数量
- [ ] tags 参数正确过滤结果

## CLI Commands
- [ ] rag 命令实现
- [ ] rag-add 命令实现
- [ ] rag-search 命令实现
- [ ] rag-list 命令实现
- [ ] rag-tags 命令实现
- [ ] JSON 输出格式正确
- [ ] 错误处理正确

## SDK Integration
- [ ] pt_snap_analyzer/__init__.py 导出正确
- [ ] pt_snap_analyzer/rag/__init__.py 导出正确
- [ ] CaseArchive 可通过 SDK 访问
- [ ] Searcher 可通过 SDK 访问
- [ ] RAGCase 可通过 SDK 访问

## Testing
- [ ] tests/test_rag_models.py 通过 (7 tests)
- [ ] tests/test_rag_archive.py 通过 (10 tests)
- [ ] tests/test_rag_searcher.py 通过 (7 tests)
- [ ] tests/test_rag_cli.py 通过 (7 tests)
- [ ] tests/test_sdk_rag.py 通过 (3 tests)
- [ ] 总测试通过 (34+ tests)
- [ ] 覆盖率 >80%

## Code Quality
- [ ] ruff check 无错误
- [ ] black 格式化完成
- [ ] isort 导入排序正确
- [ ] 类型注解完整
- [ ] 文档字符串完整

## Documentation
- [ ] README.md 更新 RAG 部分
- [ ] API 文档
- [ ] 使用示例
- [ ] 案例格式说明

## Version Control
- [ ] 所有 changes committed
- [ ] Commit message 清晰描述变更
- [ ] Git log 历史清晰
