# Agent Skills

[中文](../zh/skills.md) | English

`pt-snap-cli` ships agent skills for routing (`pt-snap-helper`), setup, Ascend NPU collection, and memory diagnostics. Agents should start with `pt-snap-helper` and prefer `--json` on commands that accept it. The `pt-snap skill` commands copy those skills into the shared Agent Skills directory and into host-specific directories that Claude Code still requires.

## Collection when the CLI is missing

For Ascend NPU capture, `pt-snap-helper` routes to `pt-snap-ascend-npu-collect`
without requiring `pt-snap-setup` first. The exact collection skill must already
be loaded by the host or load successfully through its supported loader; the
collection skill owns TorchNPU/environment verification. Without the CLI,
catalog/directory status is `unchecked`, reported separately from host-loading
evidence. Readable skill source is not proof of loading.

If loading fails or is unavailable, the helper pauses collection handoff and
explains how to make the known skill directory discoverable and restart, or use
a supported loader. Acquiring a missing skill is a separate user choice; the
helper does not implicitly install packages or skills.

Existing SnapshotDB analysis with a missing CLI still routes to setup. For
capture followed by analysis, collect first, then use setup if the CLI is still
missing. Pickle-only analysis requires an independent trusted-import decision;
setup approval does not approve import. Diagnostic handoff starts only after a
SnapshotDB exists, with the normal capabilities/overview preflight.

## List skills

```bash
pt-snap skill list
pt-snap skill list --json
pt-snap skill list --target claude --user
```

Each bundled skill is shown as its own block: name, status, install locations, and a short description. Status is one of:

- `installed` — a matching copy is present in at least one inspected location
- `outdated` — a copy exists but differs from the bundled skill, or the path exists without `SKILL.md`
- `missing` — no copy was found in the inspected locations

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

### Custom-directory availability and helper handoff

After `pt-snap skill install --dir '<skills_dir>' --json`, verify that same
directory with `pt-snap skill list --dir '<skills_dir>' --json`. Pass the parent
containing the skill folders. The default `pt-snap skill list --json` checks
only built-in host locations and may still say `missing`; custom directories
are not registered automatically. JSON `locations` identifies the checked paths.

On-disk status and host loading are separate. An `installed` copy is not proof
that the host discovers the custom directory or has loaded the skill. A readable
JSON `source_dir` is the source catalog, not proof of either installation or
loading. `pt-snap-helper` may hand off to an already loaded skill (or one loaded
successfully through the host's supported loader) despite default `missing`,
without a redundant install. If loading is unavailable, it pauses the diagnostic
handoff and asks the user to configure host discovery and restart. If the active
copy is known to be outdated, upgrade and restart before diagnosis. Missing or
outdated copies in the intended custom location require an install or upgrade
with the same `--dir`; the helper only explains these commands, never runs them.
It reports inspected status and host-loading evidence separately.

### Install commands

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

Without `--target`, `--project`, or `--dir`, `uninstall` removes every bundled-skill copy that contains `SKILL.md` and that `list` would report as installed or outdated, across all built-in hosts and both user and project scopes. Each requested name with no removable copy is reported as `not_installed` at the default user-level `agents` and `claude` destinations. Omitting names requests every bundled skill.

`--target`, `--project`, and `--dir` keep narrower destinations: `--project` uses the default `agents` and `claude` project directories unless `--target` selects hosts, and `--dir` only touches that folder.

`uninstall` only deletes directories that contain `SKILL.md`. `list` also marks a same-named path without `SKILL.md` as `outdated`. Uninstall leaves that path untouched and, if any such path is among the destinations, refuses the whole operation before deleting anything. Remove or replace the stray path, then re-run uninstall.

After an install, upgrade, or uninstall that changes skill files, restart the agent so it picks up the change.

## Bundled skills

| Skill | Use when |
|-------|----------|
| `pt-snap-helper` | Choosing the next skill from the user goal and input type; for an existing SnapshotDB, start with `capabilities` then `overview` before diagnosis |
| `pt-snap-setup` | Installing or verifying `pt-snap-cli` in the active Python environment |
| `pt-snap-ascend-npu-collect` | Collecting an Ascend NPU memory snapshot pickle |
| `pt-snap-memory-leak` | Diagnosing live allocations and leak candidates in a SnapshotDB |
| `pt-snap-memory-peak-breakdown` | Explaining active memory at a peak event |
| `pt-snap-memory-fragmentation` | Diagnosing allocator gaps and reserved-pool pressure |

Skill management is CLI-only.

### Setup readiness

`pt-snap-setup` reports `ready` only after CLI help succeeds and the selected
Python and CLI shebang interpreter match on both normalized `sys.executable`
and `sys.prefix`. Matching executable realpaths alone is insufficient: different
venvs can share a base interpreter. Both probes preserve the original execution
paths; normalization is only for comparison, so directory symlink aliases of the
same environment still match. Simple `env <name>` shebangs use the current `PATH`.
Unresolved shebangs, unsupported argument/wrapper semantics (including `env -S`),
or failed identity probes leave `CLI ownership unverified`. A mismatch reports
`CLI belongs to another Python environment`; installation still requires confirmation.
