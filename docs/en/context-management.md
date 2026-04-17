# Context Management

[English](context-management.md) | [中文](../zh/context-management.md)

`pt-snap` supports project-scoped context so different terminals, agents, or working directories can analyze different databases without overwriting each other.

## Resolution Priority

Database context is resolved in this order:

1. **Explicit argument**: `pt-snap query <db_path>`
2. **Environment variable**: `PT_SNAP_DB_PATH`
3. **Project context**: Nearest `.pt-snap/context.json`, searching upward from current directory
4. **Legacy global config**: `~/.config/pt-snap-cli/config.json`

## Set Project Database

```bash
pt-snap use /path/to/your/snapshot.db
```

After successful validation, the database path is saved to `.pt-snap/context.json` in the current directory.

## Session-Scoped Override

When a shell or agent needs an isolated database without changing project context:

```bash
export PT_SNAP_DB_PATH=/path/to/agent-specific/snapshot.db
pt-snap query --template-use memory_summary
```

Or validate and print the export command in one step:

```bash
pt-snap use /path/to/agent-specific/snapshot.db --session
```

## View Effective Context

```bash
pt-snap use
```

This shows the resolved database path and where it came from (project context, session env, or global config).

## Override Context

Even with context configured, you can specify a different database on the command line:

```bash
# Uses this database temporarily, does not affect saved context
pt-snap query /path/to/other.db --template-use memory_summary
```

## Legacy Global Configuration

Global configuration is kept for compatibility. For concurrent workflows, prefer project or session context.

```bash
# Store in ~/.config/pt-snap-cli/config.json
pt-snap use /path/to/your/snapshot.db --global
```

### Manage Global Config

```bash
pt-snap config          # View global configuration
pt-snap config --path   # Show config file path
pt-snap config --clear  # Clear global configuration
```

## Context File Locations

| Scope | File |
|-------|------|
| Project | `.pt-snap/context.json` (git-ignored, per-project) |
| Global | `~/.config/pt-snap-cli/config.json` |

### Context File Format

```json
{
  "current_db_path": "/path/to/your/snapshot.db"
}
```

## Error Handling

**No database configured:**

```bash
pt-snap query --template-use memory_summary
# Error: No database path specified and no database configured.
# Use 'pt-snap use <database_path>' to set a project database, or provide db_path argument.
```

**Database file not found:**

```bash
pt-snap query --template-use memory_summary
# Error: Database from project context not found: /path/to/missing.db
# Use 'pt-snap use <new_database_path>' to set a new project database, or provide db_path argument.
```
