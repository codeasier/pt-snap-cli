# Focus 管理

[English](../en/focus-management.md) | 中文

`pt-snap` 支持项目级 focus。解析到同一个最近 `.pt-snap/focus.json` 的进程会共享
该 focus，不同项目目录则可以选择不同数据库和设备。同一项目内的终端或 Agent 需要
相互隔离时，应使用 session 覆盖。

## 解析优先级

焦点按以下顺序解析：

1. **显式参数**: `pt-snap query <db_path>`
2. **环境变量**: `PT_SNAP_DB_PATH`
3. **项目焦点**: 从当前目录向上查找最近的 `.pt-snap/focus.json`
4. **Legacy 全局配置**: `~/.config/pt-snap-cli/config.json`

## 设置项目数据库和设备

```bash
# 设置数据库
pt-snap focus /path/to/your/snapshot.db

# 同时设置数据库和设备
pt-snap focus /path/to/your/snapshot.db --device 0

# 仅切换设备（保持当前数据库）
pt-snap focus --device 1
```

验证成功后，数据库路径和设备 ID 会保存到当前目录的 `.pt-snap/focus.json`。

## Session 级覆盖

当某个 shell 或 Agent 需要独立数据库且不想修改项目 focus 时：

```bash
export PT_SNAP_DB_PATH=/path/to/agent-specific/snapshot.db
pt-snap query --template-use memory_peak
```

或在验证数据库的同时输出 export 命令：

```bash
pt-snap focus /path/to/agent-specific/snapshot.db --session
```

Session focus 只导出 `PT_SNAP_DB_PATH`，因此 `--session` 不能与 `--device` 或
`--global` 组合。设备应在每次查询时传入；只有取消 session 覆盖后，项目 focus 及其设备
设置才会重新生效。

## 查看当前焦点

```bash
pt-snap focus
```

显示已解析的数据库路径、设备 ID 及其来源（项目 focus、session 环境变量或全局配置）。`pt-snap focus`、`pt-snap focus <db>`、`pt-snap focus --global` 和 `pt-snap focus --device` 在识别到调用栈 schema 时还会打印 `Callstack layout: v1 (inline text)` 或 `v2 (deduplicated)`；布局冲突时打印警告。`pt-snap focus --session` 只输出 `export PT_SNAP_DB_PATH=...`，以便被 shell 直接执行。该信息从数据库只读识别，不会写入 `.pt-snap/focus.json`。

`--json` 覆盖读取、设置、仅改设备、`--global` 与 `--session`。成功对象包含 `schema_version`、`ok`、`action`、`configured`、`db_path`、`focus_source`、`focus_file`、`device_id`、`available_devices`、`callstack_layout`、`callstack_layout_error` 和 `db_exists`。未提供数据库路径时，`focus --json` 仍读取当前 focus 并报告 `action: "read"`；同时带 `--session` 或 `--global` 也一样，与文本模式一致。`focus --session <db> --json` 只验证数据库，并返回 `session_applied: false` 以及 `env.name` / `env.value` / `env.export`；不会打印可直接 eval 的裸 shell 行，也不表示已修改父 shell。

## 覆盖焦点

即使已配置 focus，仍可在命令行中临时指定不同的数据库或设备：

```bash
# 仅本次查询使用该数据库，不影响已保存的 focus
pt-snap query /path/to/other.db --template-use memory_peak

# 覆盖设备（忽略 focus 中的 device_id）
pt-snap query --template-use memory_peak --device 2
```

## Legacy 全局配置

全局配置用于兼容旧版本。并发工作流中推荐使用项目 focus 或 session 覆盖。

```bash
# 保存到 ~/.config/pt-snap-cli/config.json
pt-snap focus /path/to/your/snapshot.db --global
```

### 管理全局配置

```bash
pt-snap config          # 查看全局配置
pt-snap config --path   # 显示配置文件路径
pt-snap config --clear  # 清除全局配置
pt-snap config --json   # 同一组操作用机器可读 JSON 输出
```

`config` 仍然只管理 legacy 全局配置文件。`--json` 增加 `action`（`show` / `path` / `clear`）、`path`，以及 `config` 或 `cleared`。

## Focus 文件位置

| 范围 | 文件 |
|------|------|
| 项目 | `.pt-snap/focus.json`（项目作用域内的进程共享） |
| 全局 | `~/.config/pt-snap-cli/config.json` |

项目 focus 可能包含本地数据库的绝对路径。需要保持为本地文件时，请将 `.pt-snap/`
加入项目的 `.gitignore`；pt-snap 不会自动修改忽略规则。

### Focus 文件格式

```json
{
  "db_path": "/path/to/your/snapshot.db",
  "device_id": 0
}
```

## 完整数据集 focus 与导入补偿

完整兼容 v1 数据集或已发布 `pt-snap-native-v2` 目录/`manifest.json` 可以按相同的
优先级和设备规则 focus：

```bash
pt-snap focus captures/snapshot.pkl.pt-snap-native-v2 --device 0 --json
pt-snap query --template-use event --slice 0 --json
```

原生布局为 `v2`，兼容布局为 `v1`；写 focus 前校验全部声明成员，不修复产物，不保存
布局信息。原生稀疏 ID 按原始 ID 寻址，不当成位置计数。数据集 focus 只支持有界
`event`，聚合/生命周期及跨片请求明确失败。API 会话 focus 只读，`SnapshotAnalyzer`
不承担 import/split。

导入把项目 focus 写入**当前目录**，不是输出目录；`--no-focus` 跳过。原生数据集导入 focus 失败
（包括先修改再抛错）在普通补偿下恢复旧产物与旧 focus 原始字节及内存 config 状态，
或者恢复原先不存在。恢复失败时，错误指明保留的 `.focus.pt-snap-*.recovery` checkpoint
及/或数据集恢复目录。若 checkpoint 为空且 `prior focus existed: False`，它记录原先
不存在，不是有效 focus JSON。请保留证据供人工恢复；不承诺任意 I/O/崩溃原子性或并发
writer 锁。详见[原生导入](quickstart.md#可选导入原生分库数据集)。

显式兼容导入（`--format msinsight`）采用相同的请求 focus 补偿，但即使 force 也
**不替换**已有兼容输出。仅整体证明完整、身份相同的 pt-snap 缓存可复用，否则换新输出。
GUI 仍要求同一原始 pickle 与邻接缓存，pt-snap focus 只需完整产物。首个 SQLite 打开
之前检查全部兼容成员的别名及存活/悬空 sidecar；裸校验和缓存查询对已关闭最终化成员
使用 `mode=ro&immutable=1`，保留原版 checkpoint WAL 的字节与目录清单。这不是 live
writer 锁，原生非 WAL 检查与单库默认不变。


## 错误处理

**未设置焦点时查询：**

```bash
pt-snap query --template-use memory_peak
# Error: No database path specified and no database configured.
# Use 'pt-snap focus <database_path>' to set a project database, or provide db_path argument.
```

**数据库文件不存在：**

```bash
pt-snap query --template-use memory_peak
# Error: Database from project focus not found: /path/to/missing.db
# Use 'pt-snap focus <new_database_path>' to set a new project database, or provide db_path argument.
```
