# Context 管理

[English](../en/context-management.md) | 中文

`pt-snap` 支持项目级上下文，避免不同终端、Agent 或工作目录分析不同数据库时互相覆盖。

## 解析优先级

数据库上下文按以下顺序解析：

1. **显式参数**: `pt-snap query <db_path>`
2. **环境变量**: `PT_SNAP_DB_PATH`
3. **项目上下文**: 从当前目录向上查找最近的 `.pt-snap/context.json`
4. **Legacy 全局配置**: `~/.config/pt-snap-cli/config.json`

## 设置项目数据库

```bash
pt-snap use /path/to/your/snapshot.db
```

验证成功后，数据库路径会保存到当前目录的 `.pt-snap/context.json`。

## Session 级覆盖

当某个 shell 或 Agent 需要独立数据库且不想修改项目 context 时：

```bash
export PT_SNAP_DB_PATH=/path/to/agent-specific/snapshot.db
pt-snap query --template-use memory_summary
```

或在验证数据库的同时输出 export 命令：

```bash
pt-snap use /path/to/agent-specific/snapshot.db --session
```

## 查看当前生效的 Context

```bash
pt-snap use
```

显示已解析的数据库路径及其来源（项目 context、session 环境变量或全局配置）。

## 覆盖 Context

即使已配置 context，仍可在命令行中临时指定不同的数据库：

```bash
# 仅本次查询使用该数据库，不影响已保存的 context
pt-snap query /path/to/other.db --template-use memory_summary
```

## Legacy 全局配置

全局配置用于兼容旧版本。并发工作流中推荐使用项目 context 或 session 覆盖。

```bash
# 保存到 ~/.config/pt-snap-cli/config.json
pt-snap use /path/to/your/snapshot.db --global
```

### 管理全局配置

```bash
pt-snap config          # 查看全局配置
pt-snap config --path   # 显示配置文件路径
pt-snap config --clear  # 清除全局配置
```

## Context 文件位置

| 范围 | 文件 |
|------|------|
| 项目 | `.pt-snap/context.json`（git-ignored，项目级） |
| 全局 | `~/.config/pt-snap-cli/config.json` |

### Context 文件格式

```json
{
  "current_db_path": "/path/to/your/snapshot.db"
}
```

## 错误处理

**未配置数据库时查询：**

```bash
pt-snap query --template-use memory_summary
# Error: No database path specified and no database configured.
# Use 'pt-snap use <database_path>' to set a project database, or provide db_path argument.
```

**数据库文件不存在：**

```bash
pt-snap query --template-use memory_summary
# Error: Database from project context not found: /path/to/missing.db
# Use 'pt-snap use <new_database_path>' to set a new project database, or provide db_path argument.
```
