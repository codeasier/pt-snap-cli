# Agent Skills

[中文](../zh/skills.md) | English

`pt-snap-cli` ships agent skills for routing (`pt-snap-helper`), setup, Ascend NPU collection, and memory diagnostics. Agents should start with `pt-snap-helper` and prefer `--json` on commands that currently support it. The `pt-snap skill` commands copy those skills into the shared Agent Skills directory and into host-specific directories that Claude Code still requires.

## List skills

```bash
pt-snap skill list
pt-snap skill list --json
pt-snap skill list --target claude --user
```

Each bundled skill is shown as its own block: name, status, install locations, and a short description. Status is one of:

- `installed` — a matching copy is present in at least one inspected location
- `outdated` — a copy exists but differs from the bundled skill
- `missing` — no copy was found

`--target` accepts a comma-separated list of `agents`, `claude`, `cursor`, and `codex`. `--user` and `--project` limit the scan to user-level or project-local directories. Without those flags, `list` inspects both scopes.

## Destinations

Cursor, OpenCode, Codex, and several other Agent Skills hosts read the shared directories. Claude Code does not; it only reads its own tree. The same commands work on Windows, macOS, and Linux because the CLI uses `Path.home()`.

| `--target` | User directory | Project directory | Who reads it |
|------------|----------------|-------------------|--------------|
| `agents` (default) | `~/.agents/skills` | `.agents/skills` | Cursor, OpenCode, Codex (current official user/repo path), Cline, and other Agent Skills hosts |
| `claude` (default) | `~/.claude/skills` | `.claude/skills` | Claude Code. Cursor and OpenCode also load this tree for compatibility. |
| `cursor` | `~/.cursor/skills` | `.cursor/skills` | Cursor-native extra. Cloud Agents sync only this user directory, not `~/.agents/skills`. |
| `codex` | `~/.codex/skills` | `.codex/skills` | Codex legacy user home (`$CODEX_HOME/skills`). Codex still scans it; new user skills belong in `agents`. |

Windows equivalents use `%USERPROFILE%` instead of `~`. If `CLAUDE_CONFIG_DIR` is set, user-level Claude skills go to `$CLAUDE_CONFIG_DIR/skills`. If `CODEX_HOME` is set, `--target codex` writes `$CODEX_HOME/skills`. Set `PT_SNAP_SKILLS_DIR` to a directory of `*/SKILL.md` folders to load a custom catalog instead of the repository `skills/` tree or the packaged copies; it does not change install destinations.

OpenCode also has a native tree at `~/.config/opencode/skills` and `.opencode/skills`. It already reads `agents` and `claude`, so a separate OpenCode target is not required. Use `--dir` for that native tree, Windsurf, or any other custom folder. `--dir` cannot be combined with `--target`, `--user`, or `--project`.

```bash
pt-snap skill install --dir C:\Users\you\custom-skills
pt-snap skill list --dir C:\Users\you\custom-skills
pt-snap skill upgrade --dir C:\Users\you\custom-skills
pt-snap skill uninstall --dir C:\Users\you\custom-skills
```

## Install skills

```bash
pt-snap skill install
pt-snap skill install pt-snap-setup --target claude
pt-snap skill install --project --target agents
```

Omitting skill names installs every bundled skill. The default destination is the shared user-level `agents` directory plus Claude. Use `--target` to choose hosts, `--project` to write into the current working directory, or `--dir` for a custom skills folder.

If a destination already exists and its contents differ, install refuses unless you pass `--force`. Identical copies are left unchanged. When more than one host is selected, every destination is checked before any copy is written.

## Upgrade skills

```bash
pt-snap skill upgrade
pt-snap skill upgrade pt-snap-setup --target claude
```

`upgrade` replaces outdated copies that already contain `SKILL.md`. Missing skills are left missing; current copies are left unchanged. A same-named path that exists without `SKILL.md` is left untouched; use `install --force` to replace it.

## Uninstall skills

```bash
pt-snap skill uninstall
pt-snap skill uninstall pt-snap-setup
pt-snap skill uninstall pt-snap-setup --target claude
pt-snap skill uninstall --project --target cursor
```

Without `--target`, `--project`, or `--dir`, `uninstall` removes every bundled-skill copy that `list` would report as installed or outdated, across all built-in hosts and both user and project scopes. If no copy exists anywhere, it reports `not_installed` at the default user-level `agents` and `claude` destinations.

`--target`, `--project`, and `--dir` keep narrower destinations: `--project` uses the default `agents` and `claude` project directories unless `--target` selects hosts, and `--dir` only touches that folder.

`uninstall` removes bundled skill directories that contain `SKILL.md`. A same-named path that exists without `SKILL.md` is left untouched.

After an install, upgrade, or uninstall that changes skill files, restart the agent so it picks up the change.

## Bundled skills

| Skill | Use when |
|-------|----------|
| `pt-snap-helper` | Choosing the next skill from the user goal and input type |
| `pt-snap-setup` | Installing or verifying `pt-snap-cli` in the active Python environment |
| `pt-snap-ascend-npu-collect` | Collecting an Ascend NPU memory snapshot pickle |
| `pt-snap-memory-leak` | Diagnosing live allocations and leak candidates in a SnapshotDB |
| `pt-snap-memory-peak-breakdown` | Explaining active memory at a peak event |
| `pt-snap-memory-fragmentation` | Diagnosing allocator gaps and reserved-pool pressure |

Skill management is CLI-only.
