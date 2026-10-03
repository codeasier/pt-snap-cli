# Chinese User Guides

Parent scope: [documentation](../AGENTS.md).
Topic reference: [English guide map](../en/AGENTS.md).

The same-named Markdown topics mirror the English guides. Translate explanatory
prose while preserving executable identifiers: CLI flags, template names, JSON
keys, Python APIs, schema columns and paths must stay exact.

## Translation Contracts

- Preserve differences between session focus and persisted project/global focus,
  catalog content and installed/host-loaded skills, and trusted collection/import
  versus read-only diagnosis.
- Keep units, denominators, sentinels, event ranges, and incomplete-query caveats
  explicit. Translate leak/fragmentation candidates conservatively rather than
  upgrading them into confirmed causes.
- `database.md` and `querying.md` describe v1/v2 layout behavior consistently with
  their English counterparts; semantics version is a separate contract.
- `snapshot-analyzer-api.md` retains context-manager/close examples and borrowed
  cache ownership. `splitting.md` retains exactly-one-strategy and no-replace
  destination requirements as well as pickle security language.
- `skills.md` follows the authored skills and SkillService for shared/native/custom
  destinations, restart requirements and installation status meanings.

After behavior edits, compare commands/examples with the English topic and source,
then check `README_zh.md` and `docs/README.md` navigation. Use the parent's
implementation/test map; translation-only wording changes do not need a package
install or snapshot import to validate them.
