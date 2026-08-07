<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# mcp

## Purpose
`mcp` exposes `pt-snap-cli` functionality as a FastMCP server so agents and MCP clients can inspect or set focus, list templates, fetch template metadata, execute queries, and use a memory-leak analysis prompt.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | MCP package marker. |
| `server.py` | FastMCP app, tools, resource, prompt, and `pt-snap-mcp` entrypoint. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | MCP implementation is contained in `server.py`. |

## For AI Agents

### Working In This Directory
- Keep MCP tool behavior aligned with `SnapshotAnalyzer` rather than duplicating CLI-specific logic.
- Use JSON-serializable return values for tools and resources.
- Update docs in `docs/*/mcp.md` and tests when adding or changing MCP tools.

### Testing Requirements
- Run `pytest tests/test_mcp_server.py` for MCP changes.
- Run API tests if MCP changes require `SnapshotAnalyzer` changes.

### Common Patterns
- A module-level `SnapshotAnalyzer` backs all MCP tools.
- `focus://current` mirrors the current focus tool response.

## Dependencies

### Internal
- `pt_snap_cli.api.SnapshotAnalyzer` provides the server-facing API.

### External
- `mcp.server.fastmcp.FastMCP` provides tool/resource/prompt registration and server execution.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
