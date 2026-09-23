---
name: pt-snap-agent-e2e
description: >
  Evaluation contract for Agent-first CLI usage from issue #136. This is not a
  shipped user skill; it grades recorded CLI tool traces against the parent
  issue's end-to-end scenarios.
---

# Agent CLI end-to-end evaluation

Adapters should expose semantic operations, not raw argv. Every machine-readable
call must request JSON and preserve the complete success or error envelope.
Target fields:

| Operation | Normalized output |
| --- | --- |
| `pt_snap.help` | `{mentions_helper: true, helper_skill: "pt-snap-helper", install_command, restart_required}` when help provides helper onboarding |
| `pt_snap.skill_list` | JSON listing; `json: true` in arguments |
| failed `pt_snap.query` | `{error_code: TEMPLATE_NOT_FOUND\|INVALID_PARAMETER\|DATABASE_NOT_FOUND\|DEVICE_NOT_FOUND}` |
| successful `pt_snap.query` | envelope with `db_path`, `device_id`, `returned`, `has_more`, and `rows` |
| `pt_snap.import` | `{db_path: "<published db>", focus_state, focus_source}`; non-null `focus_state` means focus changed |

Do not materialize pickle fixtures for these cases. Import is a semantic
operation; `pickle.access` remains forbidden.
