# Agent Skills

[English](../en/skills.md) | 中文

`pt-snap-cli` 附带用于环境安装、昇腾 NPU 采集和内存诊断的 agent skill。`pt-snap skill` 命令会把这些 skill 复制到共享的 Agent Skills 目录，以及 Claude Code 仍然需要的独立目录。

## 列出 skill

```bash
pt-snap skill list
pt-snap skill list --json
pt-snap skill list --target claude --user
```

每个随包 skill 单独一块显示：名称、状态、安装位置，以及一句简短说明。状态为以下之一：

- `installed` — 至少一个检查位置存在内容匹配的副本
- `outdated` — 已有副本，但与随包版本不同
- `missing` — 未找到副本

`--target` 接受逗号分隔的 `agents`、`claude`、`cursor`、`codex`。`--user` 和 `--project` 分别只检查用户级或当前项目目录。不传这些选项时，`list` 会同时检查两个范围。

## 安装位置

Cursor、OpenCode、Codex 以及多个 Agent Skills 宿主会读取共享目录。Claude Code 不会，它只读自己的目录树。CLI 使用 `Path.home()`，因此同一组命令可用于 Windows、macOS 和 Linux。

| `--target` | 用户级目录 | 项目目录 | 谁会读取 |
|------------|------------|----------|----------|
| `agents`（默认） | `~/.agents/skills` | `.agents/skills` | Cursor、OpenCode、Codex（当前官方用户/仓库路径）、Cline 及其他 Agent Skills 宿主 |
| `claude`（默认） | `~/.claude/skills` | `.claude/skills` | Claude Code。Cursor 和 OpenCode 也会兼容读取这棵目录树。 |
| `cursor` | `~/.cursor/skills` | `.cursor/skills` | Cursor 原生目录。Cloud Agents 只同步这个用户目录，不同步 `~/.agents/skills`。 |
| `codex` | `~/.codex/skills` | `.codex/skills` | Codex 旧版用户目录（`$CODEX_HOME/skills`）。Codex 仍会扫描；新的用户 skill 应写入 `agents`。 |

Windows 上用 `%USERPROFILE%` 代替 `~`。如果设置了 `CLAUDE_CONFIG_DIR`，用户级 Claude skill 会写到 `$CLAUDE_CONFIG_DIR/skills`。如果设置了 `CODEX_HOME`，`--target codex` 会写到 `$CODEX_HOME/skills`。设置 `PT_SNAP_SKILLS_DIR` 指向包含 `*/SKILL.md` 子目录的目录，会用该目录作为 skill 目录源，覆盖仓库 `skills/` 或随包副本；它不会改变安装目标路径。

OpenCode 还有原生目录 `~/.config/opencode/skills` 和 `.opencode/skills`。它已经会读取 `agents` 和 `claude`，因此不需要单独的 OpenCode 目标。原生目录、Windsurf 或其他自定义文件夹用 `--dir`。`--dir` 不能与 `--target`、`--user` 或 `--project` 同时使用。

```bash
pt-snap skill install --dir C:\Users\you\custom-skills
pt-snap skill list --dir C:\Users\you\custom-skills
pt-snap skill upgrade --dir C:\Users\you\custom-skills
pt-snap skill uninstall --dir C:\Users\you\custom-skills
```

## 安装 skill

```bash
pt-snap skill install
pt-snap skill install pt-snap-setup --target claude
pt-snap skill install --project --target agents
```

省略 skill 名称时会安装全部随包 skill。默认写入共享的用户级 `agents` 目录以及 Claude 目录。用 `--target` 选择宿主，用 `--project` 写入当前工作目录，或用 `--dir` 写入自定义 skill 目录。

如果目标目录已存在且内容不同，必须加上 `--force` 才会覆盖。内容相同的副本会保持不变。

## 升级 skill

```bash
pt-snap skill upgrade
pt-snap skill upgrade pt-snap-setup --target claude
```

`upgrade` 会用随包版本替换已经过期的副本。尚未安装的 skill 保持未安装；内容已是最新的副本不会改动。

## 卸载 skill

```bash
pt-snap skill uninstall
pt-snap skill uninstall pt-snap-setup --target claude
pt-snap skill uninstall --project --target cursor
```

`uninstall` 会从选定宿主的 skill 目录删除随包 skill。未安装的 skill 会报告为 `not_installed`。

仅在 install、upgrade 或 uninstall 实际改动 skill 之后，才需要重启 agent 让变更生效。`list` 不会提示重启。

## 随包 skill

| Skill | 适用场景 |
|-------|----------|
| `pt-snap-setup` | 在当前 Python 环境安装或验证 `pt-snap-cli` |
| `pt-snap-ascend-npu-collect` | 采集昇腾 NPU 内存快照 pickle |
| `pt-snap-memory-leak` | 在 SnapshotDB 中诊断仍存活分配和泄漏候选 |
| `pt-snap-memory-peak-breakdown` | 解释峰值事件上的 active 内存 |
| `pt-snap-memory-fragmentation` | 诊断分配器空洞和 reserved 池压力 |

Skill 管理只通过 CLI 提供。MCP 服务器不负责安装、升级或卸载 skill。
