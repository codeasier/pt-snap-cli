# Changelog

## [0.1.1] - 2026-06-22

本次发布将 pt-snap-cli 从早期查询工具推进为面向 PyTorch 内存快照分析的 CLI + MCP 双入口工具。核心变化集中在三方面：导入链路补齐、面向 Agent 的 MCP 集成，以及更实用的内存峰值分析与查询体验。由于仓库当前没有历史发布 tag，本条目以现有 `origin/main` 全量历史和已合并 PR 元数据为依据整理。

### 新增

- 集成 MemSnapDump dump2db 后端，支持将 PyTorch memory snapshot pickle 转换为 SnapshotDB，补齐从快照到 SQLite 分析库的导入链路。
- 新增 MCP server 与共享核心服务，使 CLI 能力可被 Agent 通过 MCP 调用，并补充 CLI/MCP 合约覆盖。
- 新增峰值内存归因相关报告与查询模板，帮助定位内存峰值来源。
- 增强 query template 体系，支持按目录组织、动态分类发现、分类过滤，以及更完整的查询构建能力。
- 增加 shell completion，改善命令行补全体验。

### 改进

- 将数据库选择命令从 `use` 重命名为 `focus`，并支持持久化 device 选择，使项目级焦点配置更清晰。
- 重构基础查询模板为更接近资源化的分页查询形式，并移除查询输出中硬编码的 10 行限制，改由 `-n` 控制。
- 迁移到 `src` layout，整理测试目录结构，并完善中英文文档组织。
- 增加 GitHub CI/CD、basedPyright 检查和更多测试覆盖，提升发布前质量门槛。

### 修复

- 修复模板加载、布尔参数转换、shell completion KeyError、分类列表触发、文档链接等问题。
- 收窄过宽异常处理，移除未使用依赖和冗余目录，降低维护成本。
