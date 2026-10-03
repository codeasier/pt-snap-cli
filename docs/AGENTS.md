# User Documentation and Evidence

Parent scope: [repository](../AGENTS.md).

`docs/README.md` is the topic/language index. [English](en/AGENTS.md) and
[Chinese](zh/AGENTS.md) guides share behavioral coverage; `legal/` retains evidence
referenced by the index and snapshot provenance. Agent implementation rules belong
in scoped AGENTS guides, not in user walkthroughs.

## Verify Against the Owning Implementation

| Topic | Source of truth |
| --- | --- |
| Root commands/help/JSON | `cli.py`, `cli_output.py`, `core/json_codec.py`, `core/error_codes.py` |
| Reports and skill commands | `cli_reports.py`, `cli_skills.py` and owning core services |
| API/lifecycle | `api.py`, core result models, CLI/API contract tests |
| Focus and read-only inspection | `config.py`, `context.py`, focus/overview/metadata services |
| Query parameters/semantics/completeness | YAML templates, query config/registry/executor, QueryService |
| Snapshot schema/import/split | Runtime adaptors, import metadata/backend and SplitService |
| Distribution and install | `pyproject.toml`, SkillService, authored/bundled skill parity |

Paths in this table are within `src/pt_snap_cli/` unless stated otherwise.
Commands must be checked against group modules too; not all options live in
`cli.py` after command-group separation.

## Change-Together Rules

- Public behavior changes update both language guides and relevant README entry
  points. Topic additions/moves also update `docs/README.md` navigation.
- Installation walkthroughs lead with PyPI; keep editable developer setup
  separate. Agent integration uses skills plus CLI, and host restart/loading
  must be distinguished from on-disk installation status.
- Query examples preserve sentinels, units, denominators, completeness and layout
  compatibility. API examples should show owned resource lifetimes and avoid
  implying that session focus persists like CLI focus.
- Import/split examples state pickle trust/code-execution and publication behavior.
  Snapshot schema docs describe both reader layouts and the current writer.
- Legal evidence and runtime provenance have different maintenance contracts from
  prose guides. Preserve provenance's append-only history and the fixed branding
  evidence allowlist enforced by `tests/test_governance.py`.

For documentation-only edits, verify relative links, referenced source and
existing contract tests. Run the owning executable test when an example's behavior
is in doubt; do not invoke import, install or publication just to validate prose.
