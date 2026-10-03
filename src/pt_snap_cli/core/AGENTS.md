# Product Services

Parent scope: [package runtime](../AGENTS.md).

Core owns product semantics over config, Context, queries and snapshot mechanisms.
CLI/API adapters consume its results and errors; presentation stays in adapters.

## Service Boundaries

| Files | Responsibility |
| --- | --- |
| `focus_service.py` | Resolve/validate database and device; explicit project/global focus writes |
| `context_cache.py` | Bounded persistent Context LRU with resolved-path and file-signature invalidation |
| `query_service.py` | Catalog contracts, focus/device selection, executor reuse, completeness and timeout budget |
| `capability_service.py`, `overview_service.py` | Full catalog and read-only database/device/event-bound/import-metadata probes |
| `report_service.py` | Compose named queries into peak-memory reports rather than duplicate SQL |
| `import_service.py`, `import_metadata.py` | Trusted-input import validation, source/cache identity, metadata, optional focus |
| `snapshot_import_backend.py` | Runtime adapter, temporary database, publication and rollback resources |
| `split_service.py` | Strategy/device validation, staging, replay validation and exclusive directory publication |
| `skill_service.py` | Skill discovery, status, install/upgrade/uninstall destination policy |
| `models.py`, `errors.py` | Shared dataclass results and normalized domain failures |
| `error_codes.py`, `json_codec.py` | Stable JSON error classification/hints and serializable envelopes |

## Ownership and Query Lifetime

- A caller-supplied `ContextCache` is borrowed. Check `is not None`, since an
  empty cache is falsy. `QueryService` and `OverviewService` close only owned
  caches; `ReportService` owns and closes its internally constructed query service.
- `QueryService.close()` releases its executor references and owned cache but
  allows reuse. This differs from terminal `SnapshotAnalyzer.close()`.
- Cache keys are resolved paths; the signature is `(mtime_ns, inode, size)`.
  Replacement or eviction closes the old Context. Executor reuse follows the
  actual Context instance; invalidation must not reuse an executor bound to an
  evicted connection.
- Finite trailing pages probe one extra row. A full inner `top_n` window is
  conservatively incomplete too. Keep `has_more`, `truncated`, `total`, and
  `total_is_exact` consistent; exact totals are opt-in and share the page query's
  timeout budget. `PT_SNAP_QUERY_TIMEOUT` is a time bound, not a row limit.

## Import and Split Transactions

Import runs the backend in a temporary directory, then writes/validates metadata
before replacing the destination. When focus is requested and a destination
already exists, rollback uses a copied backup held by a secure file descriptor
until the post-publication action succeeds. This is a backup copy, not a hard link.
Handle short/zero writes and close descriptors on every failure path.

Normal post-publication failure restores the previous destination (or removes a
new one). If rollback itself fails, preserve recovery evidence and report that
failure explicitly; never claim unconditional atomic restoration after I/O failure.
See `tests/core/test_import_backend_failures.py` and `test_import_service.py`.

Split requires exactly one positive `slices`/`max_entries` strategy and an absent
destination. It validates selected-device slices by replay before publication;
concurrent destination creation must fail rather than replace another result.

## Skill Catalog and Mutation

- Default catalog precedence: `PT_SNAP_SKILLS_DIR`, repository `skills/`, then
  packaged `bundled_skills/`; an explicit service `catalog_dir` overrides this.
- Default install targets shared `~/.agents/skills` and independent Claude
  skills (`~/.claude/skills` or `$CLAUDE_CONFIG_DIR/skills`). Explicit Cursor/Codex
  targets retain their native extras; `--dir` is a separate custom destination.
- List reports `installed`, `outdated`, `missing` across selected locations;
  filesystem status does not prove the current host loaded the skill.
- Unfiltered CLI uninstall discovers all built-in hosts and both scopes, removing
  installed/outdated copies containing `SKILL.md`. A same-named non-skill path
  aborts the entire operation before deletion. Explicit target/project/directory
  filters retain narrower destinations.
- `uninstall_skills(all_locations=True)` rejects `hosts`, `dest_dir`, and scope
  other than `user`. Keep this service constraint aligned with `cli_skills.py`.

## Change Together

Use [service tests](../../../tests/core/AGENTS.md) for the owning suite. Shared
result/error changes also require `tests/test_contract_cli_api.py` and JSON
contracts; template metadata must flow through `template_info_to_dict` to both
adapters. Keep the `models.py` Any/Unknown type gates intact. Runtime changes
also follow [snapshot guidance](../snapshot/AGENTS.md), and skill content changes
follow [authoring/evaluation](../../../skills/AGENTS.md).
