# Tasks: pt-snap-analyzer RAG 知识库

---

## Task List

- [ ] Task 1: RAG 数据模型
  - [ ] Step 1: 创建数据模型 (AnalysisStep, RAGCase, SearchMatch, SearchResult)
  - [ ] Step 2: 创建测试文件
  - [ ] Step 3: 运行测试
  - [ ] Step 4: Commit

- [ ] Task 2: 案例归档系统
  - [ ] Step 1: 创建归档器 (CaseArchive)
  - [ ] Step 2: 实现 CRUD 方法 (add_case, get_case, list_cases, delete_case)
  - [ ] Step 3: 实现序列化方法 (_case_to_dict, _dict_to_case)
  - [ ] Step 4: 创建测试文件
  - [ ] Step 5: 运行测试
  - [ ] Step 6: Commit

- [ ] Task 3: 案例检索系统
  - [ ] Step 1: 创建检索器 (Searcher)
  - [ ] Step 2: 实现 search() 方法
  - [ ] Step 3: 实现评分方法 (_score_case, _normalize_text)
  - [ ] Step 4: 实现 get_tags() 方法
  - [ ] Step 5: 创建测试文件
  - [ ] Step 6: 运行测试
  - [ ] Step 7: Commit

- [ ] Task 4: CLI 集成
  - [ ] Step 1: 添加 rag 命令到 CLI
  - [ ] Step 2: 实现 rag-add 命令
  - [ ] Step 3: 实现 rag-search 命令
  - [ ] Step 4: 实现 rag-list 命令
  - [ ] Step 5: 实现 rag-tags 命令
  - [ ] Step 6: 创建 CLI 测试文件
  - [ ] Step 7: 运行测试
  - [ ] Step 8: Commit

- [ ] Task 5: 完整的 SDK 集成
  - [ ] Step 1: 更新包初始化
  - [ ] Step 2: 创建 rag 包初始化
  - [ ] Step 3: 创建 SDK 测试
  - [ ] Step 4: 运行测试
  - [ ] Step 5: 运行完整测试
  - [ ] Step 6: Commit

## Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
