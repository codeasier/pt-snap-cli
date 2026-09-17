<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-24 -->

# en

Parent scope: [docs](../AGENTS.md)

## Purpose
`docs/en` contains the English documentation set for installing and using `pt-snap-cli`, managing focus, querying and splitting snapshots, running the MCP server, understanding the SQLite schema, and using the high-level and result mapping Python APIs.

## Key Files
| File | Description |
|------|-------------|
| `quickstart.md` | End-to-end installation and first-query walkthrough. |
| `focus-management.md` | Focus resolution, project focus files, environment variables, and global config behavior. |
| `querying.md` | Query listing, template info, parameter usage, result limits, and built-in templates. |
| `splitting.md` | Snapshot slicing strategies, output formats, replay validation, and publication guarantees. |
| `mcp.md` | MCP server setup, tools, resources, prompts, and agent usage. |
| `database.md` | Snapshot SQLite table/schema reference. |
| `snapshot-analyzer-api.md` | High-level Python API for focus, template discovery, queries, and import metadata. |
| `result-mapper-api.md` | Result mapping API documentation. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | English docs are flat topic files. |

## For AI Agents

### Working In This Directory
- Keep examples executable against current CLI options and template names.
- Mirror user-visible changes in `../zh/` when appropriate.

### Testing Requirements
- Verify referenced commands and options against `src/pt_snap_cli/cli.py`.
- Verify template details against `src/pt_snap_cli/query/templates/`.

### Common Patterns
- Topic files correspond to major product areas rather than source modules.

## Dependencies

### Internal
- CLI, MCP, query template, and schema details should be checked against `src/pt_snap_cli/` before editing.

### External
- Markdown only.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
