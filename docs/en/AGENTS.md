<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# en

## Purpose
`docs/en` contains the English documentation set for installing and using `pt-snap-cli`, managing focus, querying and splitting snapshots, installing bundled agent skills, understanding the SQLite schema, and using the high-level and result mapping Python APIs.

## Key Files
| File | Description |
|------|-------------|
| `quickstart.md` | End-to-end installation and first-query walkthrough. |
| `focus-management.md` | Focus resolution, project focus files, environment variables, and global config behavior. |
| `querying.md` | Query listing, template info, parameter usage, result limits, and built-in templates. |
| `splitting.md` | Snapshot slicing strategies, output formats, replay validation, and publication guarantees. |
| `skills.md` | Bundled agent-skill listing, helper entry, install destinations, and status meanings. |
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
- `skills.md` documents `pt-snap skill list` / `install` / `upgrade` / `uninstall`, built-in and `--dir` destinations, and must stay aligned with `SkillService`.

## Dependencies

### Internal
- CLI, query template, and schema details should be checked against `src/pt_snap_cli/` before editing.

### External
- Markdown only.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
