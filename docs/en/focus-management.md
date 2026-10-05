# Focus Management

[中文](../zh/focus-management.md) | English

`pt-snap` supports project-scoped focus. Processes that resolve the same nearest
`.pt-snap/focus.json` share that focus, while different project directories can
select different databases and devices. Use a session override when terminals or
agents in the same project must remain isolated.

## Resolution Priority

Focus is resolved in this order:

1. **Explicit argument**: `pt-snap query <db_path>`
2. **Environment variable**: `PT_SNAP_DB_PATH`
3. **Project focus**: Nearest `.pt-snap/focus.json`, searching upward from current directory
4. **Legacy global config**: `~/.config/pt-snap-cli/config.json`

## Set Project Database and Device

```bash
# Set database only
pt-snap focus /path/to/your/snapshot.db

# Set database and device together
pt-snap focus /path/to/your/snapshot.db --device 0

# Change device only (keeps current database)
pt-snap focus --device 1
```

After successful validation, the database path and device ID are saved to `.pt-snap/focus.json` in the current directory.

## Session-Scoped Override

When a shell or agent needs an isolated database without changing project focus:

```bash
export PT_SNAP_DB_PATH=/path/to/agent-specific/snapshot.db
pt-snap query --template-use memory_peak
```

Or validate and print the export command in one step:

```bash
pt-snap focus /path/to/agent-specific/snapshot.db --session
```

Session focus exports only `PT_SNAP_DB_PATH`; combine `--session` with neither
`--device` nor `--global`. Pass the device to each query; project focus, including
its device, becomes effective again only after the session override is unset.

## View Current Focus

```bash
pt-snap focus
```

This shows the resolved database path, device ID, and where they came from (project focus, session env, or global config). `pt-snap focus`, `pt-snap focus <db>`, `pt-snap focus --global`, and `pt-snap focus --device` also print `Callstack layout: v1 (inline text)` or `v2 (deduplicated)` when the schema is recognized, or a warning when the layout conflicts. `pt-snap focus --session` prints only the `export PT_SNAP_DB_PATH=...` line so it can be evaluated by the shell. The layout is detected read-only from the database; it is not stored in `.pt-snap/focus.json`.

`--json` covers read, set, device-only, `--global`, and `--session`. The success object includes `schema_version`, `ok`, `action`, `configured`, `db_path`, `focus_source`, `focus_file`, `device_id`, `available_devices`, `callstack_layout`, `callstack_layout_error`, and `db_exists`. Without a database path, `focus --json` still reads the current focus and reports `action: "read"`, including when `--session` or `--global` is also passed; that matches text mode. `focus --session <db> --json` validates the database and returns `session_applied: false` plus `env.name` / `env.value` / `env.export`. It does not print a bare shell line and does not change the parent shell.

## Override Focus

Even with focus configured, you can temporarily specify a different database or device on the command line:

```bash
# Uses this database temporarily, does not affect saved focus
pt-snap query /path/to/other.db --template-use memory_peak

# Override device (ignores focused device_id)
pt-snap query --template-use memory_peak --device 2
```

## Legacy Global Configuration

Global configuration is kept for compatibility. For concurrent workflows, prefer project focus or session overrides.

```bash
# Store in ~/.config/pt-snap-cli/config.json
pt-snap focus /path/to/your/snapshot.db --global
```

### Manage Global Config

```bash
pt-snap config          # View global configuration
pt-snap config --path   # Show config file path
pt-snap config --clear  # Clear global configuration
pt-snap config --json   # Same actions as machine-readable JSON
```

`config` still manages only the legacy global file. `--json` adds `action` (`show` / `path` / `clear`), `path`, and either `config` or `cleared`.

## Focus File Locations

| Scope | File |
|-------|------|
| Project | `.pt-snap/focus.json` (shared by processes in the project scope) |
| Global | `~/.config/pt-snap-cli/config.json` |

Project focus can contain an absolute local database path. Add `.pt-snap/` to the
project's `.gitignore` when the file should remain local; pt-snap does not modify
ignore rules automatically.

### Focus File Format

```json
{
  "db_path": "/path/to/your/snapshot.db",
  "device_id": 0
}
```

## Complete Dataset Focus and Import Compensation

A complete compatibility-v1 dataset or published `pt-snap-native-v2` directory/
`manifest.json` can be focused with the same precedence and device rules:

```bash
pt-snap focus captures/snapshot.pkl.pt-snap-native-v2 --device 0 --json
pt-snap query --template-use event --slice 0 --json
```

Native layout is `v2`; compatibility layout is `v1`. All declared members are
validated before writing focus, with no artifact repairs or layout persistence.
Native sparse IDs are addressed as original IDs, not positional counts. Only
bounded `event` queries are supported through dataset focus; aggregate/lifecycle
and cross-slice requests fail explicitly. API session focus is read-only and
`SnapshotAnalyzer` has no import/split facade.

Import writes project focus in the **current directory**, not the output directory.
`--no-focus` skips it. A native dataset import focus failure, including mutation before an error,
restores the old artifact plus exact prior focus bytes and in-memory config state
(or prior absence) on ordinary compensation. If restoration fails, the error
identifies the retained `.focus.pt-snap-*.recovery` checkpoint and/or dataset
recovery directory. An empty checkpoint with `prior focus existed: False` records
prior absence, not a valid focus JSON. Preserve evidence for manual recovery;
no unconditional I/O/crash atomicity or concurrent-writer lock is promised.
See [native import](quickstart.md#optional-import-a-native-sharded-dataset).

## Error Handling

**No focus configured:**

```bash
pt-snap query --template-use memory_peak
# Error: No database path specified and no database configured.
# Use 'pt-snap focus <database_path>' to set a project database, or provide db_path argument.
```

**Database file not found:**

```bash
pt-snap query --template-use memory_peak
# Error: Database from project focus not found: /path/to/missing.db
# Use 'pt-snap focus <new_database_path>' to set a new project database, or provide db_path argument.
```
