# Changelog

## [0.4.1] - 2026-10-12

相对 v0.4.0：分析对象从单库扩展为「单库 + 完整分片数据集」——新增兼容 v1 数据集的只读 focus/寻址、原创 `pt-snap-native-v2` 原生分库导入与显式 msinsight 兼容导出，并把全局内建查询、公开工作预算与私有 scratch 归约纳入同一契约；单库导入保留结构化有序帧，新增 `report memory-tree`（含交互式 HTML）与调用栈字节预算（`stack_bytes`）；同时收口峰值报告完整性、诊断 skill 行为、API 生命周期与 CI/打包审计。本段覆盖 `v0.4.0` 之后已合入 `main` 的全部用户可见变更。

### 新增

- 完整已校验数据集可作为 focus 或显式目标：兼容 v1 目录/`manifest.json` 无需原始 pickle、导入 metadata、引用或扩展表即可只读 focus；`overview.dataset` 输出格式、manifest 版本/状态、内容指纹、真实/边界事件数、逐设备分片路径/范围与能力。事件范围排除负 ID 合成行；外部数据集级 metadata 为 `unavailable` 属正常，原生/兼容导出提供整份证明后才为 `available`。路径/设备优先级不变，CLI focus 不写产物或检测布局。
- 数据集 `event` 寻址与定点归因：`query`/`SnapshotAnalyzer` 支持真实 ID 路由到所在片、闭区间 `min_id/max_id` 跨片全局筛选/排序/分页，`--slice`（API `slice_index`）限制到单片真实事件；`active_blocks_at_event`/`active_memory_callstack_at_event` 在排名/分页前解析完整跨片 alloc/free 与栈来源，原版无扩展产物同样适用。负 ID 不能作为整份数据集 selector，缺失事件不虚构 event 0。
- 数据集全局内建查询支持矩阵：`event`/`allocation` 全局合并排序分页；`memory_peak`/`allocator_gap` 使用独立选择的真实全局事件；`block`/`freed_block_lifetime`/`leak_detection` 采用去重生命周期与终片观察语义；`callstack_analysis` 按完整 canonical 来源身份合并后再做全局阈值/排名；`preexisting_live` 为所有者事件占用。数据集明确不支持 runtime override/自定义模板/任意 SQL；单库行形状不变，数据集行新增可选的 `lifecycle_id`、身份/来源证明、`source_stack_id`、`stack_kind`、`stack_event_id`、`frames_status` 等字段。
- 原生分库导入：`pt-snap import --events-per-slice N`（或显式 `--format pt-snap-native-v2`）发布 `<输出目录>/<输入文件名>.pt-snap-native-v2/`。容量按各设备真实时间顺序位置计数，保留稀疏 ID、OOM 与 workspace 事件；全部设备/分片在同级暂存、回填、关闭、写入 metadata 并校验后以独占目录 rename 发布；缓存复用校验源 SHA-256、设备选择、容量、原生格式/manifest/导入语义/扩展及 metadata 合同版本。已识别但不匹配的目标保留、须 `--force` 才替换（有短暂空档，不是单次原子 swap）；未知目录、无关文件、非法 manifest 与符号链接即使 force 也不接管。请求的项目 focus 纳入补偿，回滚自身失败会保留并报告恢复证据；`--no-focus` 完全跳过。JSON 增加 `dataset_path`、`devices`、`slice_count`、`format`、`omitted_devices`、`reused`、`rebuilt`。
- 显式 msinsight 兼容导出：`pt-snap import --format msinsight`（别名 `compatibility-v1`）生成 `<输入文件名>.msinsight/`，对齐 `Ascend/msinsight@101f65b877a267ffd5f66ea3834706057ba243e5` 固定源码的「同一原始 pickle + 邻接缓存」入口；物理内联 v1 表、metadata `import_format_version=1`，调用栈文本按每个事件复制，磁盘/暂存空间可能明显增加。兼容发布为 no-replace：即使 `--force` 也不覆盖外部/原版/用户缓存，仅完整且身份相同的 pt-snap 缓存可复用；GUI 复用为**待验收/未运行**，hash 相等不代表验收通过。
- 公开数据集工作预算：`query`、`report peak-memory`、`report memory-tree` 接受 `--max-work-rows`/`--max-work-bytes`/`--max-scratch-db-bytes`（`PT_SNAP_MAX_WORK_ROWS`/`PT_SNAP_MAX_WORK_BYTES`/`PT_SNAP_MAX_SCRATCH_DB_BYTES`），Python API 提供不可变 `QueryLimits`（构造默认与单次覆盖）。默认 100000 工作行 / 64 MiB 工作字节 / 512 MiB scratch 页；工作超限整次失败并报告已消耗行数/字节，不返回冒充完整的部分全局结论。超过 SQLite 附加上限或观察阈值的生命周期查询使用查询专属临时派生库（目录 0700、文件 0600、页数上限、源分片只读，完成/错误/取消均清理）。
- 数据集变更检测与缓存合同：默认每次对 manifest 和全部成员取内容哈希（有界进程内 LRU 仅在 generation 与完整 fingerprint 相同时复用逐行校验结果）；每次在返回行或计数前复查 generation，检测到并发变更以数据库完整性错误整体失败，不发部分结果。`PT_SNAP_DATASET_CACHE=immutable` 供受控不可变产物启用纯元数据复用（调用方责任合同，不代表工具检测文件系统能力）。
- 单库结构化帧与内存树：导入格式升级为 3，新增 `frame`/`callstack_frame`/`callstack_frame_manifest` 保留原始有序帧、重复帧与逐栈期望长度；新增 `event_frames`、`active_memory_frame_tree_at_event` 模板和 `pt-snap report memory-tree --event-id <id>`（`--format text|html`、`--json`、`--min-size`、`--include-static/--exclude-static`）。HTML 支持点击缩放、全树搜索与可键盘操作的子节点列表；每个节点满足「总占用 = 自身占用 + 直接子节点占用」，文本/HTML 渲染器拒绝不完整或不守恒的树。帧树仅支持单库格式 3，数据集目录与原生分片明确拒绝。
- 调用栈字节预算：`event` 与 `active_memory_callstack_at_event` 新增 `stack_bytes` 参数，`report peak-memory` 新增 `--stack-bytes`。默认负数保留完整文本，`0` 仅保留身份，正数返回不超过该 UTF-8 字节数的有效前缀；行内新增 `stack_id`、`stack_kind`、`stack_event_id`、`stack_bytes`、`stack_original_bytes`、`stack_truncated`。`stack_truncated` 只表示文本缩略，与行集合的 `has_more`/`truncated`/`total_is_exact` 相互独立；可用返回的 `stack_event_id` 在同一数据库/设备取回完整文本。
- `report peak-memory` 扩展：`--start-id/--end-id` 限定峰值选择（归因仍解析所选事件的完整活跃集合），`--timeout` 成为整报告递减 deadline；JSON 新增峰值 `scope`、归因 `source_coverage`、`included_bytes`、`percent_denominator`、`active_bytes_at_event`、`coverage_percent` 与 `budget_scope`。
- Agent 集成：`pt-snap-helper` 在没有 CLI 时先路由昇腾采集（采集 skill 须由宿主加载，不隐式安装包或 skill）；`pt-snap-setup` 的 `ready` 判据要求所选 Python 与 CLI shebang 解释器的规范化 `sys.executable` 和 `sys.prefix` 都一致；`skill list`/`skill install` 指南明确自定义 `--dir` 复查、范围化 `missing`/`installed` 与宿主加载状态的区别。

### 性能

- 数据集 `event`/`allocation` 按 `id` 排序的深分页改为按逐片匹配行数跳过整片，只在落点片使用局部 SQL OFFSET 再补满窗口；原生稀疏 ID 按实际行数计数，仅最终选中的行解析来源文本与有序帧。减少的是取入 Python 的工作量，不降低数据集校验成本或 SQLite 内部扫描量。
- 小规模 block/leak/lifetime 查询保持只读 ATTACH 归约（先证明身份、检测冲突、选最新观察再分页）；超过附加上限或启用 scratch 时改用查询专属派生库一次归约，汇总、分页与时长桶复用同一归约表；`active_*_at_event` 先在 SQL 中预归约再补充有界详情。
- 数据集校验增加进程内复用：完整校验结果按 generation + 完整 fingerprint 复用，跳过重复逐行校验但仍对 manifest/全部成员取内容哈希；`report peak-memory` 只检查一次数据集并在步骤之间复查同一 fingerprint。

### 修复

- 峰值报告保留归因完整性与 active 覆盖：JSON 返回归因 `has_more`/`truncated`/`total_is_exact` 与 `effective_params`，分组百分比以筛选、排名后的 `included_bytes` 为分母；`active_bytes_at_event` 是所选 metric 对应事件的 active counter，`coverage_percent` 在 counter 缺失/非正/无事件时为 `null`（unknown）。覆盖率不是完整性标志：`--exclude-static` 可在无截断时降低覆盖率，满窗口即使 100% 也可能不完整；空 trace 返回空分组、零 included bytes 与未知覆盖率。动态分组填满 `top_n` 窗口时文本输出标记 partial。
- `active_memory_callstack_at_event` 完整性收敛：零大小内部排名窗口（`top_n=0`）保守标记 `has_more`/`truncated`/非精确（单库与数据集一致）；`static`/`preexisting_live_at_event` 不受动态 `top_n` 限制，但外层 `-n` 仍可裁掉特殊组，有限 `top_n=N` 且包含静态组时建议 `-n N+2`。固定 `top_n` 时增大 `-n` 不改变共有行及其百分比，增大 `top_n` 可能改变分母。
- 单库 `memory_peak`/`allocator_gap` 语义版本升为 2：仅真实事件（`id >= 0`）参与峰值与同事件计数器，负 ID 合成边界行不再可能成为峰值或参与 gap 计算。
- `callstack_analysis` 语义版本升为 2：按完整采集文本分组（两种单库布局一致，不再按局部去重 ID 或显示标签），统计全部带栈真实 action（含 free/segment/workspace），负边界排除；v2 布局下缺失/NULL joined 文本保留为独立 missing 组，空文本独立计数组。`alloc_count` 保留字段名但不是分配次数，`avg_size` 不是分片平均值。
- `leak_detection` 补齐作用域说明与完整窗口流程：单库 SQL 仅检查 `allocEventId >= 0` 与 NULL/负 `freeEventId`；数据集要求已证明的真实分配 + 终片 `state IN (0,1)`，排除 inactive、较早分片和未证明观察。模板无 `offset`；需要完整候选集时先 `--exact-total` 计数，再以正 `-n <total>` 单次替换窗口，不拼接/累加重叠窗口。
- 查询失败保真：类型化 query/timeout 错误跨执行器边界保留原类型；未知异常只包装一次，保留可操作的 domain 消息与 cause。compatibility 导出器的事件 ID 校验改为按片 count/min/max 连续性检查，不再物化全部 ID 集合。
- `SnapshotAnalyzer` 生命周期显式化：`close()` 幂等且终结操作（关闭后 focus/发现/metadata/概览/查询与再次进入 `with` 抛 `RuntimeError("SnapshotAnalyzer is closed.")`）；`close()`/`with` 会释放自身缓存，注入的 `context_cache` 为借用、由调用方关闭；显式失效后未关闭的 analyzer 可重新填充缓存。
- 导入回滚加固：回滚自身失败时保留并报告恢复路径与 checkpoint，不再静默吞掉；补全与查询路径持有的数据库句柄在 teardown 时确定性关闭；`T | None`（PEP 604）与 `Optional[T]` 同样映射到正确的 SQLite affinity。
- 诊断 skill 修复：峰值/终块按完整身份匹配；leak 候选使用有界替换窗口并要求迭代证据；碎片归因限定所选范围；峰值归因按 `top_n+2` 为 `static`/preexisting 预留特殊行；前置探测统一为 `capabilities` + `overview`；setup 保留原始执行路径、仅对比较做规范化；verl 采集示例保留所选 Python。

### 稳定性与工程

- CLI 模块拆分：`cli_output.py`/`cli_reports.py`/`cli_skills.py`/`cli_limits.py` 从 `cli.py` 分离，根命令与组命令继续共用同一 JSON/错误路径；`TemplateSummaryPayload`/`QueryResultPayload` 与 `object` 动态值使 API/快照边界显式化，不转换值或改变结果键。
- wheel 审计进入 CI 与 release：新增只读 `.github/scripts/audit_wheel.py`，将 Python 模块的路径与字节内容与 `src/` 比对，并独立检查查询 YAML、内置技能、snapshot 许可证/来源资源；CI 在安装验收前审计 wheel，release 审计实际上传用于发布的 wheel；README 增加「从全新 checkout/worktree 构建」说明。
- CI 分层与平台覆盖：新增 `platform.yml`（macOS 1 任务 + Windows 4 个确定性分区、Python 3.13、非 slow、20 分钟上限、最多并行 2、执行前验证分区无遗漏/重复并上传分片清单）；`test.yml` 增加 Chromium 浏览器回归（memory-tree HTML）与定时 `dataset-acceptance` 作业，clean-wheel Agent 验收扩展多格式多分片与 `--events-per-slice`；常规套件可用 `pytest -m 'not slow'`。
- 数据集验收证据落地：新增中英文 `sharded-snapshotdb.md`、`dataset-acceptance.md`、`interop-acceptance.md` 与 JSON 基准记录，覆盖固定目标双向互操作、200-seed 配对差分、150 万事件合成容量、便携三片 fixture 与离线多分片 wheel/技能验收；skill 评测新增最低最终答案有效性门槛。
- Agent 指南与文档重建：按当前架构重写 AGENTS 层级与 `docs/README.md` 导航，`README`/`README_zh` 增补数据集、内存树、预算与构建审计入口。

### 兼容性提示

- 新导入的单库为格式 3；格式 2 文本库继续支持原有查询，但 `event_frames`、`active_memory_frame_tree_at_event` 与 `report memory-tree` 需从原始快照重新导入，分析器不会从显示文本猜测原始帧，也不迁移数据库（缓存按格式变化自动重建）。
- `memory_peak`/`allocator_gap` 语义版本 2 与 `callstack_analysis` 语义版本 2 会改变部分结果：负合成行不再参与；`callstack_analysis` 的 `alloc_count` 不再是分配次数、按完整文本分组、missing/空文本为独立组。依赖旧结果或旧字段解释的调用方需重新评估。
- `report peak-memory` 文本新增 partial 标记，JSON 新增字段（原有 `callstack_groups` 与 `percent_of_active_blocks` 数值不变）；`active_memory_callstack_at_event` 的完整性标志更保守。`stack_bytes` 限制的是 UTF-8 文本前缀，不是模型 token 预算或整包输出硬上限；`stack_truncated` 与行集合完整性独立。
- 数据集工作预算默认生效且没有「无限」档：`limit`/`-n`/`stack_bytes`/`--timeout` 不提高预算，无界输出、大 offset 或禁用 scratch 的来源读取会明确失败；scratch 设为 0 只禁用派生库，不禁用工作预算。非法预算在访问数据库前失败。
- 原生数据集 `--force` 会替换已识别的旧产物（发布期间路径有短暂空档）；兼容导出对已有目标 no-replace；`PT_SNAP_DATASET_CACHE=immutable` 是显式调用方合同；数据集不支持自定义 SQL/override 与逐片拼接的全局生命周期结论；原版无扩展数据集的导入 metadata 为 `unavailable` 属正常。GUI 互操作为待验收事项。
- `import`/`overview`/`capabilities`/`--template-info` 的 JSON 新增数据集相关字段与 `dataset_support`（含生效工作上限）；已发布命令名与既有 JSON 成功/失败信封保持不变。

## [0.4.0] - 2026-09-24

相对 v0.3.0：关闭 MCP 产品面，Agent 集成入口收敛到 bundled skills 与 CLI；并一次落地 helper、查询参数白名单、字段语义、全命令 `--json`、查询完整性协议，以及 `capabilities` / `overview`。本段覆盖 `v0.3.0` 之后已合入 `main` 的全部用户可见变更。

### 破坏性变更

- 移除 `pt-snap-mcp` 控制台入口、`src/pt_snap_cli/mcp/` 与核心依赖 `mcp`。安装 `pt-snap-cli`（无 extra）后依赖树不再包含 `mcp`、`starlette` 或 `uvicorn`；发布的 console script 只剩 `pt-snap`。
- Agent 集成改为 skills + `pt-snap` CLI。`SnapshotAnalyzer` Python API 保留；`execute_query()` 默认仍为 `max_rows=None`（不截断），缺模板时 `get_template_info()` 仍返回 `None`。
- 删除从未被代码使用的可选依赖组 `rag`（`chromadb` / `langchain`）。`dev` 现在是唯一 extra；`pip install "pt-snap-cli[rag]"` 不再有效。

### 新增

- 新增 `pt-snap-helper` 引导技能，并在 `pt-snap --help` 末尾加入 Agent 提示（优先使用已支持的 `--json`，无技能时可用 `pt-snap skill install pt-snap-helper --json` 安装并重启 Agent，用 `pt-snap skill list --json` 检查技能）。helper 只读路由，不自动安装包、导入 pickle 或改写 focus；随包分发走 `pt-snap skill`。
- helper 与泄漏/碎片/峰值诊断 skill 补充 focus 目标缺失但同目录或当前目录存在候选 `.db` 时的恢复规则：不按名称/大小/时间自动选库（即使只有一个候选也需用户确认），确认前不诊断、不用 Python/`sqlite3` 绕过 CLI，确认后先执行 `pt-snap metadata` 再继续原有预检；合法旧库的 `unavailable` / `metadata_missing` 不强制重新 import，换库不继承旧 device，且不持久化 focus、不代跑 import。
- `--template-info` 与 `get_template_info()` 展示参数 `choices`。`order_by` / `order_dir` 等会写入 SQL 标识符或关键字的参数必须声明封闭取值列表；字符串 `choices` 大小写不敏感，并规范化为声明拼写（如 `desc` → `DESC`）。
- `output_schema` 可声明字段语义（`units`、`metric_semantics`、`scope`、`denominator`、`sentinel`、`interpretation_limits`），查询级可声明 `semantics_version` 与解释限制。`--template-info` 与 `get_template_info()` 透出同一份契约。`execute_query()` 结果增加 `template` 与 `semantics_version`，行数据仍为原始 SQLite 值。优先覆盖 `leak_detection`、`memory_peak`、`allocator_gap`、`active_memory_callstack_at_event`。
- `leak_detection` 的对外描述改为「捕获范围内无释放完成记录的候选」，不再写成已确认泄漏。
- `focus`、`import`、`split`、`query`、`config` 支持 `--json`。成功结果带 `schema_version` / `ok` 信封，以及 `db_path`、`focus_source`、`device_id`、`template`、`effective_params` 等上下文。`query --list` / `--template-info` / 执行共用该选项；`--template-info --json` 透出字段语义。
- JSON 模式失败时 stdout 为空，stderr 为带稳定错误码的结构化对象（如 `TEMPLATE_NOT_FOUND`、`INVALID_PARAMETER`、`DATABASE_NOT_FOUND`、`DEVICE_NOT_FOUND`），退出码非零。`pt-snap` 控制台入口返回 Typer/Click 的退出码（不再丢弃非 standalone 返回值），在检测到 `--json` 时也会把 Click 用法/解析错误写成 `INVALID_PARAMETER` 信封（退出码 2），并把 Ctrl-C / EOF 写成 `ERROR` / `Aborted!`。解析失败时的 `--json` 判定是 argv 词法扫描（best-effort）：忽略 `--` 之后的词，`--opt=value` 与数字词不吞后续参数。`query --json` 的 `effective_params.limit` 是尾部 SQL `LIMIT`（模板 `limit` 与 `-n` 的合并，或追加的 `-n`）；CTE 内的 `top_n` 仍是独立参数。
- `split --json` 只控制 stdout 清单，与 `--format json` 的分片文件格式相互独立。`focus --session --json` 返回验证结果与 `PT_SNAP_DB_PATH` 赋值信息，不暗示已修改父 shell。
- 查询结果增加完整性与分页字段：`has_more` / `truncated` / `total_is_exact`。默认 `total` 等于本页 `returned`；`--exact-total`（API `exact_total=True`）才对匹配集合做 `COUNT`。有限 `LIMIT` 时多取一行判断是否还有后续，不再在触达 `-n` 时自动计数。CTE 内有限 `top_n` 在窗口已满时也置 `has_more` / `truncated`，续页靠增大 `top_n` 而不是 `offset` / `-n`。`event` / `block` / `allocation` / `leak_detection` 用 `id` 做稳定分页次序。`--timeout` 与 `PT_SNAP_QUERY_TIMEOUT` 是一次 `QueryService` 调用的共享时限（页面查询与可选 COUNT 共用），并作用于所有模板查询（含 `report peak-memory`）；非法环境变量归为 `INVALID_PARAMETER`。诊断 skill 默认有界查询，并按 `has_more` / `truncated` 续页。
- 新增 `pt-snap capabilities`：一次输出 CLI 版本、全部查询模板/参数契约（含字段语义）和技能清单。`--json` 使用同一成功信封，替代逐个 `--template-info` 探测。
- 新增 `pt-snap overview`：只读输出设备列表、各设备首/末 event id，以及导入 metadata 状态。`--json` 使用同一信封；分析路径不写数据库、不持久化 focus。
- 新增 `preexisting_live` 与 `freed_block_lifetime` 查询模板，泄漏技能不再依赖 `sqlite3` CLI 回退。`preexisting_live` 排除 `freeEventId = -1` 的 static 块，与 `active_memory_callstack_at_event` 的 `[preexisting live]` 分组一致。诊断前置探测从 7 次（`metadata` + 六个 `--template-info`）降为 2 次（`capabilities` + `overview`）。helper 引导「先概览、再诊断」。

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
- Agent CLI 端到端评估补齐参数纠错、无设备数据库、真实竞争数据库、模板语义与 import focus 信封；post-change 契约任务成功率由 0 提升至 1，错误结论率由 0.8 降至 0，并约束调用与输出预算。
- CI 与 release gate 新增干净 wheel Agent 验收：在隔离 venv 中确认包与 helper 来自 wheel，并仅用结构化输出完成 helper 安装、trusted snapshot import、capabilities、overview 与 peak query。
- basedpyright 对 `src/pt_snap_cli/snapshot/` 与其余包路径同一套 error 门槛：补齐注解后移除 snapshot `executionEnvironments` 降级列表（#122 阶段 3）。

### 兼容性提示

- 已配置 `pt-snap-mcp` 或 MCP 客户端的调用方需改用 CLI、bundled skills 或 Python API。历史 CHANGELOG 中的 MCP 条目仅作记录，不再对应已发布入口。
- 依赖 `pt-snap-cli[rag]` 的安装命令会失败；该 extra 从未启用任何功能。
- 拼错或多余的查询参数、以及不在 `choices` 内的 `order_by` / `order_dir` 现在会报错，而不再静默得到错误结果或 SQLite 语法错误。
- 用户自写查询模板若在 `output_schema` 列上使用未登记键，加载会失败；仅含 `column`/`type` 的旧模板仍然有效。`execute_query()` 返回字典新增 `template`、`semantics_version` 键。
- 不带 `--target` / `--project` / `--dir` 的 `pt-snap skill uninstall` 现在会删除 `skill list` 看到的、含有 `SKILL.md` 的全部已安装副本，而不再只检查默认的用户级 `agents` 与 `claude` 目录。需要窄范围卸载时请显式传这些选项。同名但缺少 `SKILL.md` 的路径会让整次卸载失败且零删除。
- 文本模式保持原样：人类可读输出不变，`_error()` 与查询/报告说明行仍写 stdout。缺失模板的 `query --template-info` 改为退出码 1。数据库无设备时，文本模式查询仍退出 0；JSON 模式改为 `DEVICE_NOT_FOUND` 且退出码非零。
- 已有 `metadata --json`、`report peak-memory --json` 与 `skill list/install/upgrade/uninstall --json` 成功字段保持兼容，不包进新信封。它们在 `--json` 失败时改走 stderr 错误信封。新的 `focus` / `import` / `split` / `query` / `config` / `capabilities` / `overview` 的 `--json` 使用成功/失败信封。`capabilities` 在技能目录不可读时走 `SKILL_ERROR`；`overview` 把损坏的设备表/边界查询翻译为 `DATABASE_SCHEMA_INVALID`，并把损坏的 focus 文件翻译为 `FOCUS_FILE_INVALID`。
- 查询默认 `total` 不再在触达 `-n` 时自动变成匹配集合 `COUNT`。依赖该旧语义的调用方必须显式传 `--exact-total` / `exact_total=True`。

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
