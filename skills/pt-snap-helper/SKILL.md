---
name: pt-snap-helper
description: Use as the first pt-snap entry when the next skill is unclear. Routes by user goal and input type (existing SnapshotDB, pickle-only, missing CLI, Ascend NPU collection) to pt-snap-setup, pt-snap-ascend-npu-collect, pt-snap-memory-leak, pt-snap-memory-peak-breakdown, or pt-snap-memory-fragmentation. Prefers --json on commands that accept it.
---

# pt-snap-helper

## Overview

This is a read-only navigator. Choose the next skill from the user's goal and
input type. Do not install packages, do not copy skills into agent directories,
do not import or deserialize pickle, and do not persist focus.

Use this skill when:

- The user first asks about pt-snap and the next skill is unclear.
- The host has several pt-snap skills and needs a routing decision.
- The user has a SnapshotDB, a pickle, no CLI, or needs Ascend NPU collection.

Do not use this skill to run leak, peak, or fragmentation analysis. Hand off to
the matching diagnostic skill after routing.

## Prerequisite: check skill availability

If `pt-snap` is on PATH, inspect bundled skill status with JSON:

```bash
command -v pt-snap
pt-snap skill list --json
```

Parse `skills[].name` and `skills[].status`. Status is `installed`, `outdated`,
or `missing`.

If `pt-snap` is missing, stop routing diagnostics and hand off to
`pt-snap-setup`. Do not install the Python package from this skill.

If a needed skill is `missing` or `outdated`, tell the user how to install or
upgrade it. Do not run install or upgrade from this skill.

Install or upgrade examples the user can run after they confirm they want
the skills installed or updated. Do not run these commands from this skill:

```bash
pt-snap skill install pt-snap-helper --json
pt-snap skill install --json
pt-snap skill upgrade pt-snap-helper --json
pt-snap skill upgrade --json
```

After any install, upgrade, or uninstall that changes skill files, the host
agent must be restarted before the change is visible:

Restart the agent after install, upgrade, or uninstall so the skill change takes effect.

`pt-snap skill list` does not require a restart.

## Prefer `--json` where supported

Prefer `--json` on commands that accept it. There is no global `--json` flag
on `pt-snap`; add the option to the specific command:

- `pt-snap skill list --json`
- `pt-snap skill install --json`
- `pt-snap skill upgrade --json`
- `pt-snap skill uninstall --json`
- `pt-snap capabilities --json`
- `pt-snap overview '<db_path>' --json`
- `pt-snap metadata '<db_path>' --json`
- `pt-snap report peak-memory '<db_path>' --device <device_id> --json`
- `pt-snap focus --json`
- `pt-snap config --json`
- `pt-snap query --list --json`
- `pt-snap query --template-info <name> --json`
- `pt-snap query --template-use <name> --json`

  Execute results include `has_more` / `truncated`. Diagnostic skills keep
  listings bounded; do not treat a page as the complete matching set.
- `pt-snap import <snapshot.pkl> --json`
- `pt-snap split <snapshot.pkl> --output <dir> --slices <n> --json`

`split --json` prints the result inventory on stdout. `split --format json`
only changes slice file format; the two flags are independent.

On `--json` failure, stdout is empty, stderr is a JSON object with
`ok: false` and `error.code` / `error.message` / `error.hint`, and the
exit code is nonzero. The `pt-snap` console entry also converts Click
usage/parse errors (for example `query -n abc --json`) into
`INVALID_PARAMETER` with exit code 2, and Ctrl-C / EOF into `ERROR`
with message `Aborted!`. The console entry returns the Typer/Click
exit code (nonzero on failure). Usage-error `--json` detection is a
best-effort argv scan (exact `--json` before `--`, not an option
value; `--opt=value` and numeric tokens do not consume the next
argument). Text mode still writes `Error:` lines to stdout.

This skill itself does not run analysis queries. The diagnostic skills own
those commands. For an existing SnapshotDB, point the next skill at
`pt-snap capabilities --json` and `pt-snap overview '<db_path>' --json`
before diagnosis so it does not need per-template `--template-info` or a
separate metadata probe.

## Routing matrix

Choose one next skill. If the goal is still ambiguous after this table, ask
the user; do not start all diagnostic skills.

| User goal | Existing SnapshotDB | Only pickle | `pt-snap` missing | Need Ascend NPU capture |
| --- | --- | --- | --- | --- |
| Install or verify the CLI | `pt-snap-setup` | `pt-snap-setup` | `pt-snap-setup` | `pt-snap-setup` |
| Collect an Ascend NPU pickle | `pt-snap-ascend-npu-collect` | `pt-snap-ascend-npu-collect` | `pt-snap-setup` first | `pt-snap-ascend-npu-collect` |
| Leak / live allocations at end of trace | `pt-snap-memory-leak` | Trusted import first, then leak | `pt-snap-setup` first | Collect first, then trusted import, then leak |
| What was live at a peak event | `pt-snap-memory-peak-breakdown` | Trusted import first, then peak | `pt-snap-setup` first | Collect first, then trusted import, then peak |
| Allocator gaps / reserved-pool pressure | `pt-snap-memory-fragmentation` | Trusted import first, then fragmentation | `pt-snap-setup` first | Collect first, then trusted import, then fragmentation |

Exact next-skill names:

- `pt-snap-setup`
- `pt-snap-ascend-npu-collect`
- `pt-snap-memory-leak`
- `pt-snap-memory-peak-breakdown`
- `pt-snap-memory-fragmentation`

CSV, SVG, and other visualization files are not SnapshotDB input. If the user
only has those, stop and ask for a `.db` or a trusted pickle.

### Existing SnapshotDB

A SnapshotDB is a pt-snap SQLite database (typically `.db`) with a
`dictionary` table. When the user already has one:

1. Confirm the goal is leak, peak, or fragmentation.
2. Tell the next skill to start with `pt-snap capabilities --json` and
   `pt-snap overview '<db_path>' --json` (overview first, then diagnose).
   Pass the database path and device if the user supplied them.
3. Hand off to the matching diagnostic skill. Do not run leak, peak, or
   fragmentation query templates from this helper.
4. Do not run `pt-snap focus <database_path>` to persist a new focus from this
   skill. Diagnostic skills may read the current focus with no arguments.

This helper may mention that `pt-snap overview '<db_path>' --json` and
`pt-snap capabilities --json` exist. Running those orientation commands
belongs to the diagnostic skill. Do not import pickle or persist focus.

### Only pickle

A `.pkl` / `.pickle` file is not a SnapshotDB. Pickle import is trusted-code
execution, not a sandbox.

From this skill:

- Do not open, import, inspect, or deserialize pickle input.
- Do not run `pt-snap import`.
- Do not run `pt-snap split`.
- Do not run `pt-snap focus` with a database path.

Tell the user that import is an independent trusted-input decision. If they
confirm the pickle is trusted and they want a SnapshotDB, they can run:

```bash
pt-snap import <snapshot.pkl> --json
```

Import may update focus unless they pass `--no-focus`. This helper must not run that command or change focus.

After the user has a SnapshotDB, route to the matching diagnostic skill.

If they need to capture a pickle on Ascend NPU first, hand off to
`pt-snap-ascend-npu-collect` instead of importing.

### `pt-snap` missing

Hand off to `pt-snap-setup`. That skill owns interpreter selection, ownership
checks, and install approval. This helper must not run `pip` or assume Conda.

### Need Ascend NPU collection

Hand off to `pt-snap-ascend-npu-collect`. Collection ends when a pickle exists
on disk. It does not import or diagnose.

## Boundaries

- Keep this skill read-only. Do not install Python packages, and do not write files.
- Do not run `pt-snap skill install` / `upgrade` / `uninstall`.
- Do not persist focus or edit configuration.
- Do not start leak, peak, fragmentation, or OOM-root-cause analysis here.
- Do not classify allocations or allocator gaps.
- Use the five skill names above exactly; do not invent aliases.

## Output

Report:

- `Goal`
- `Input type` (`snapshotdb`, `pickle`, `missing-cli`, or `npu-collect`)
- `Needed skills` and their `pt-snap skill list --json` status when available
- `Next skill` (one of the five names)
- `Install/restart notes` when a skill is missing or outdated
- `Trusted import notes` when the user only has pickle
- `Unknowns`
