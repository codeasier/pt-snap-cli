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

## View Current Focus

```bash
pt-snap focus
```

This shows the resolved database path, device ID, and where they came from (project focus, session env, or global config).

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
```

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
