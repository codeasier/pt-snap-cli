<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# docs

## Purpose
`docs` contains end-user and API documentation for the CLI, focus management, query templates, MCP integration, snapshot database format, high-level and result mapping Python APIs, and retained legal evidence. It is split into English and Chinese language trees with a top-level README for navigation.

## Key Files
| File | Description |
|------|-------------|
| `README.md` | Documentation landing page and language/topic navigation. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `en/` | English documentation guides (see `en/AGENTS.md`). |
| `zh/` | Chinese documentation guides (see `zh/AGENTS.md`). |
| `legal/` | Governance evidence referenced by the documentation index and snapshot provenance record. |

## For AI Agents

### Working In This Directory
- Keep English and Chinese docs synchronized when changing user-visible behavior.
- Verify command names, options, template names, and MCP tool names against source code before updating docs.
- Prefer updating existing guides over creating new documentation pages.

### Testing Requirements
- For documentation-only changes, review rendered Markdown structure and verify referenced commands/options exist.
- If examples depend on behavior changes, run the matching CLI or service tests.

### Common Patterns
- The two language trees mirror the same topics: quick start, focus management, querying, snapshot splitting, MCP, database schema, SnapshotAnalyzer API, and result mapper API.

## Dependencies

### Internal
- `src/pt_snap_cli/cli.py` defines documented CLI commands and options.
- `src/pt_snap_cli/mcp/server.py` defines documented MCP tools, resource, and prompt.
- `src/pt_snap_cli/query/templates/` defines documented built-in template names and parameters.

### External
- Markdown is the only documentation format used here.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
