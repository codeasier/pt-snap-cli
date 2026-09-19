# Changelog

## [0.5.0] - Unreleased

### 新增

- `focus`、`import`、`split`、`query`、`config` 支持 `--json`。成功结果带 `schema_version` / `ok` 信封，以及 `db_path`、`focus_source`、`device_id`、`template`、`effective_params` 等上下文。`query --list` / `--template-info` / 执行共用该选项；`--template-info --json` 透出 #147 字段语义。
- JSON 模式失败时 stdout 为空，stderr 为带稳定错误码的结构化对象（如 `TEMPLATE_NOT_FOUND`、`INVALID_PARAMETER`、`DATABASE_NOT_FOUND`、`DEVICE_NOT_FOUND`），退出码非零。`pt-snap` 控制台入口返回 Typer/Click 的退出码（不再丢弃非 standalone 返回值），在检测到 `--json` 时也会把 Click 用法/解析错误写成 `INVALID_PARAMETER` 信封（退出码 2），并把 Ctrl-C / EOF 写成 `ERROR` / `Aborted!`。解析失败时的 `--json` 判定是 argv 词法扫描（best-effort）：忽略 `--` 之后的词，`--opt=value` 与数字词不吞后续参数。`query --json` 的 `effective_params.limit` 是尾部 SQL `LIMIT`（模板 `limit` 与 `-n` 的合并，或追加的 `-n`）；CTE 内的 `top_n` 仍是独立参数。
- `split --json` 只控制 stdout 清单，与 `--format json` 的分片文件格式相互独立。`focus --session --json` 返回验证结果与 `PT_SNAP_DB_PATH` 赋值信息，不暗示已修改父 shell。
- 查询结果增加完整性与分页字段：`has_more` / `truncated` / `total_is_exact`。默认 `total` 等于本页 `returned`；`--exact-total`（API `exact_total=True`）才对匹配集合做 `COUNT`。有限 `LIMIT` 时多取一行判断是否还有后续，不再在触达 `-n` 时自动计数。CTE 内有限 `top_n` 在窗口已满时也置 `has_more` / `truncated`，续页靠增大 `top_n` 而不是 `offset` / `-n`。`event` / `block` / `allocation` / `leak_detection` 用 `id` 做稳定分页次序。`--timeout` 与 `PT_SNAP_QUERY_TIMEOUT` 是一次 `QueryService` 调用的共享时限（页面查询与可选 COUNT 共用），并作用于所有模板查询（含 `report peak-memory`）；非法环境变量归为 `INVALID_PARAMETER`。诊断 skill 默认有界查询，并按 `has_more` / `truncated` 续页。

### 兼容性提示

- 文本模式保持原样：人类可读输出不变，`_error()` 与查询/报告说明行仍写 stdout。缺失模板的 `query --template-info` 已在 0.4.0 以退出码 1 失败。数据库无设备时，文本模式查询仍退出 0；JSON 模式改为 `DEVICE_NOT_FOUND` 且退出码非零。
- 已有 `metadata --json`、`report peak-memory --json` 与 `skill list/install/upgrade/uninstall --json` 成功字段保持兼容，不包进新信封。它们在 `--json` 失败时改走 stderr 错误信封。
- 查询默认 `total` 不再在触达 `-n` 时自动变成匹配集合 `COUNT`。依赖该旧语义的调用方必须显式传 `--exact-total` / `exact_total=True`。

## [0.4.0] - Unreleased

相对 v0.3.0：关闭 MCP 产品面，Agent 集成入口收敛到 bundled skills 与 CLI；并补上 helper 引导技能、查询参数白名单，以及易误读字段的语义元数据。本段覆盖 `v0.3.0` 之后已合入 `main` 的全部用户可见变更。

### 破坏性变更

- 移除 `pt-snap-mcp` 控制台入口、`src/pt_snap_cli/mcp/` 与核心依赖 `mcp`。安装 `pt-snap-cli`（无 extra）后依赖树不再包含 `mcp`、`starlette` 或 `uvicorn`；发布的 console script 只剩 `pt-snap`。
- Agent 集成改为 skills + `pt-snap` CLI。`SnapshotAnalyzer` Python API 保留；`execute_query()` 默认仍为 `max_rows=None`（不截断），缺模板时 `get_template_info()` 仍返回 `None`。
- 删除从未被代码使用的可选依赖组 `rag`（`chromadb` / `langchain`）。`dev` 现在是唯一 extra；`pip install "pt-snap-cli[rag]"` 不再有效。

### 新增

- 新增 `pt-snap-helper` 引导技能，并在 `pt-snap --help` 末尾加入 Agent 提示（优先使用已支持的 `--json`，用 `pt-snap skill list --json` 检查技能）。helper 只读路由，不自动安装包、导入 pickle 或改写 focus；随包分发走 `pt-snap skill`。
- `--template-info` 与 `get_template_info()` 展示参数 `choices`。`order_by` / `order_dir` 等会写入 SQL 标识符或关键字的参数必须声明封闭取值列表；字符串 `choices` 大小写不敏感，并规范化为声明拼写（如 `desc` → `DESC`）。
- `output_schema` 可声明字段语义（`units`、`metric_semantics`、`scope`、`denominator`、`sentinel`、`interpretation_limits`），查询级可声明 `semantics_version` 与解释限制。`--template-info` 与 `get_template_info()` 透出同一份契约。`execute_query()` 结果增加 `template` 与 `semantics_version`，行数据仍为原始 SQLite 值。优先覆盖 `leak_detection`、`memory_peak`、`allocator_gap`、`active_memory_callstack_at_event`。
- `leak_detection` 的对外描述改为「捕获范围内无释放完成记录的候选」，不再写成已确认泄漏。

### 修复

- `pt-snap skill uninstall` 在不带 `--target` / `--project` / `--dir` 时，会删除 `skill list` 报告的、且含有 `SKILL.md` 的每一份已安装或过期副本（全部内置宿主、用户级与项目级）。此前只检查默认的用户级 `agents` 与 `claude` 目录，因此 `cursor:user` 或 `--project` 副本会留下并继续显示为 `installed`。`--target` / `--project` / `--dir` 仍只作用于指定目标。同名但缺少 `SKILL.md` 的路径不会删除，并且会让整次卸载在动手前失败。部分名称未安装时，会在默认用户级 `agents` 与 `claude` 上报告 `not_installed`。
- `query --template-info` 在模板不存在时走与其他 CLI 失败相同的 `_error()` 路径，退出码为 1（此前 `typer.Exit()` 默认 0）。
- 未声明的 `--params` 键不再静默进入渲染上下文（例如 `min_sze` 不再当成未过滤结果）；查询在渲染 SQL 前失败，并列出已接受参数名。
- `allocation` / `block` / `event` / `active_blocks_at_event` 的 `order_by`、`order_dir` 不再接受任意 SQL 片段；非法取值在进数据库前被拒绝，而不再以 SQLite syntax error 暴露。

### 移除

- 删除 `QueryExecutor` 中从未匹配到分类子目录模板的非递归加载路径；打包 YAML 只由 `query.registry` 递归加载。运行时仍可用 `load_config()` / `register_template()` 显式挂模板。

### 稳定性与工程

- 增加 Agent CLI 端到端评估基线（`tests/skills/suites/pt-snap-agent-e2e`），记录当前 CLI 行为，供后续改造对比；不改变产品 CLI/API。
- 原 CLI/MCP 跨表面契约测试改写为 CLI ↔ `SnapshotAnalyzer`，文件名为 `tests/test_contract_cli_api.py`。

### 兼容性提示

- 已配置 `pt-snap-mcp` 或 MCP 客户端的调用方需改用 CLI、bundled skills 或 Python API。历史 CHANGELOG 中的 MCP 条目仅作记录，不再对应已发布入口。
- 依赖 `pt-snap-cli[rag]` 的安装命令会失败；该 extra 从未启用任何功能。
- 拼错或多余的查询参数、以及不在 `choices` 内的 `order_by` / `order_dir` 现在会报错，而不再静默得到错误结果或 SQLite 语法错误。
- 用户自写查询模板若在 `output_schema` 列上使用未登记键，加载会失败；仅含 `column`/`type` 的旧模板仍然有效。`execute_query()` 返回字典新增 `template`、`semantics_version` 键。
- 不带 `--target` / `--project` / `--dir` 的 `pt-snap skill uninstall` 现在会删除 `skill list` 看到的、含有 `SKILL.md` 的全部已安装副本，而不再只检查默认的用户级 `agents` 与 `claude` 目录。需要窄范围卸载时请显式传这些选项。同名但缺少 `SKILL.md` 的路径会让整次卸载失败且零删除。
- 本版本未扩展 `--json` 覆盖面。当前支持 `--json` 的是 `metadata`、`report peak-memory`，以及 `skill list` / `install` / `upgrade` / `uninstall`。`query`、`focus`、`import`、`split`、`config` 仍无 `--json`；`--template-info` 的机器可读形态仍是结构化 API dict 与 CLI 文本。

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
