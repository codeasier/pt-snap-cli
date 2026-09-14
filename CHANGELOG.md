# Changelog

## [0.3.0] - 2026-09-17

本次发布聚焦 Agent 诊断技能与查询/导入性能：新增内存泄漏、碎片、峰值拆解与 Ascend NPU 采集等诊断 skill、`pt-snap skill` 共享安装命令及本地 skill 评测框架；SnapshotDB 采用去重 callstack 存储，叠加查询执行层优化，使导入、拆分与查询获得数量级加速，同时只读兼容 v1/v2 两种 callstack 布局；pickle 加载收敛到内建类型白名单，进一步降低反序列化风险。

### 新增

- 新增内存泄漏归因、分配器碎片取证、内存峰值拆解三个只读诊断 skill，Agent 可直接基于 SnapshotDB 完成常见内存分析工作流。
- 新增 Ascend NPU 快照采集 skill，覆盖华为昇腾环境下的快照获取流程。
- 新增 `pt-snap skill` 命令，支持对内置 skill 的安装、列出、升级与卸载，统一写入共享 `~/.agents/skills` 及 Claude 独立目录；安装/升级/卸载均先校验目标目录，拒绝覆盖或删除非 skill 路径，发布失败可回滚。
- 新增本地 skill 评测框架，用于诊断 skill 的回归验证与质量评估。
- SnapshotDB callstack 查询只读兼容 v1/v2 双布局：旧版 inline callstack 数据库无需重建即可继续 focus、查看元数据和执行查询，按布局自动选择 SQL。
- 快照 pickle 加载改经 `SafeUnpickler` 白名单限制为内建类型，降低加载不可信快照时的任意代码执行风险。

### 性能

- `trace_entry_<device>` 改为整数引用共享 `callstack` 表存储去重后的 callstack：基准样本（62.8 万事件）导入耗时 29.1s 降至 8.6s，数据库体积 5.95 GB 降至 177 MB，callstack 与聚合类查询提速 2.9x 至 184x。
- `max_rows` 下沉为 SQL `LIMIT`，Jinja 模板按名称缓存编译结果；新增 mtime 感知的 `ContextCache`（LRU，默认 4 项），MCP server 与 `SnapshotAnalyzer` 跨查询复用只读 SQLite 连接并跳过逐次 schema 校验。
- 拆分回放复用原始帧、跳过 `Frame` 重建，基准样本 4 分片拆分耗时 12.5s 降至 2.5s，分片规范化哈希保持不变。

### 修复

- 修复缺少 `addr` 字段的 OOM 快照导入失败的问题。
- 恢复 dump 时 torch-npu workspace 快照校正，保证 NPU 工作区块在导入与拆分后仍保留帧信息。
- callstack 布局冲突的外部数据库不再阻断 focus、metadata 与非 callstack 查询，仅在执行 callstack 变体模板时报错。
- 移除 `leak_detection` 模板未使用的 `device_id` 参数；对齐仓库安全契约与文档描述和实际运行时行为。

### 稳定性与工程

- basedpyright 类型检查覆盖整个 `src/pt_snap_cli` 并设为零 error 门槛，修复 core/query 既有类型问题；snapshot 目录暂以 warning 过渡，后续版本逐步收紧。
- 对齐 MCP `execute_query` 文档与 `max_rows` 默认值及结果截断语义；改进 fixture 溯源守卫与测试环境的本地隔离。

### 兼容性提示

- 导入格式版本升级为 2，新导入的 SnapshotDB 采用去重 callstack 布局；v1 与 v2 布局均可只读查询，无需重新导入或迁移。
- 依赖非内建类型的第三方 pickle 快照将无法直接加载，需先在来源侧完成序列化收敛。

## [0.2.0] - 2026-08-08

本次发布重点补齐大型 PyTorch 内存快照的拆分与可追溯导入能力，并将快照运行时转为项目首方维护。导入和回放链路同时获得显著的时间与内存优化，SnapshotDB 查询性能和失败安全性也进一步提升。

### 新增

- 新增 `pt-snap split`，支持按设备使用 `--slices` 或 `--max-entries` 拆分快照，输出可独立回放的 pickle 或规范化 JSON 切片，并在发布前逐一执行回放验证。
- 为导入生成的 SnapshotDB 写入 `pt_snap_metadata`，记录源文件 SHA-256、设备选择、格式版本、导入器版本和完成时间；匹配的数据库可直接复用，`--force` 可强制重建。
- 新增 `pt-snap metadata`、`SnapshotAnalyzer.get_database_metadata()` 和 MCP `get_database_metadata`，统一查看数据库来源与兼容性信息。
- 新增安全的 pt-snap 环境安装与校验 skill，避免在错误的 Python 环境中安装或执行分析。

### 性能

- 优化 SQLite 导入事务、缓存和同步设置，并为常用 trace、block 查询列增加索引。
- 使用二分查找和已发现索引复用优化快照回放，同时保持 segment 顺序和边界行为。
- 数据库导入不再为每个 frame 引用构造 `Frame` 对象；基准样本显示耗时降低 58% 到 63%，峰值 RSS 降低 84% 到 87%，数据库结果保持一致。

### 稳定性与工程

- 将原 vendored snapshot runtime 迁移到首方 `pt_snap_cli.snapshot`，补充许可证、来源记录、变更治理和完整的回放/导入基线测试。
- 导入先在临时数据库中写入并校验 metadata，再原子发布；源快照在导入期间发生变化或导入失败时保留已有目标数据库。
- 拆分使用同文件系统 staging 目录和 no-replace 原子发布，失败时不覆盖或合并既有输出，也不遗留部分结果。
- 完善中英文拆分、数据库和快速入门文档，并使 GitHub Release 标题与发布标签一致。

### 兼容性提示

- 旧版或外部生成且没有 `pt_snap_metadata` 的兼容 SnapshotDB 仍可查询；再次导入时会重建一次后再参与缓存复用。
- `pt-snap import` 在缓存命中时输出 `Reused:`，重建时可能额外输出 `Cache miss:`；依赖精确终端文本的调用方需要相应调整。
- MCP 依赖范围收窄为 `mcp>=1.0.0,<2`。原内部 vendor 命名空间已随首方 runtime 迁移移除。

## [0.1.1] - 2026-06-22

本次发布将 pt-snap-cli 从早期查询工具推进为面向 PyTorch 内存快照分析的 CLI + MCP 双入口工具。核心变化集中在三方面：导入链路补齐、面向 Agent 的 MCP 集成，以及更实用的内存峰值分析与查询体验。由于仓库当前没有历史发布 tag，本条目以现有 `origin/main` 全量历史和已合并 PR 元数据为依据整理。

### 新增

- 集成内建快照导入能力，支持将 PyTorch memory snapshot pickle 转换为 SnapshotDB，补齐从快照到 SQLite 分析库的导入链路。
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
