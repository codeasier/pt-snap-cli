# English User Guides

Parent scope: [documentation](../AGENTS.md).
Translation counterpart: [Chinese guides](../zh/AGENTS.md).

## Topic Ownership

| Guide | Required behavior coverage |
| --- | --- |
| `quickstart.md` | PyPI/source setup, trusted import, focus and first query |
| `focus-management.md` | Explicit/environment/project/global resolution and persistence |
| `querying.md` | Template discovery, params, semantics, pagination/completeness and timeout |
| `splitting.md` | Strategy/device/format, original event IDs, replay validation and absent-destination publication |
| `skills.md` | Helper entry, catalog versus loaded skills, host/custom destinations and mutation commands |
| `database.md` | Snapshot tables, v1/v2 callstack layout, metadata and sentinel meanings |
| `snapshot-analyzer-api.md` | Session focus, typed query results, inspection and close/context-manager ownership |
| `result-mapper-api.md` | Type converters and model factories, separate from high-level analysis |

Keep English examples usable as copyable commands and Python snippets. Explain
placeholders and separate read-only inspection from focus/install/import writes.
Check the same-named Chinese topic when editing behavior, and keep both README
links and `docs/README.md` aligned when topics change.

Use exact public command, JSON field and template names from the implementation
map in the parent guide. A CLI result's `total` need not be an exact full count;
do not erase the completeness flags when simplifying examples. A reserved or
allocated metric peak does not make active-block attribution a decomposition of
every byte in that selected metric.
