---
name: pt-snap-agent-e2e
description: >
  Evaluation contract for Agent-first CLI usage from issue #136. This is not a
  shipped user skill; it grades recorded CLI tool traces against the parent
  issue's end-to-end scenarios.
---

# Agent CLI end-to-end evaluation

Adapters should expose semantic operations, not raw argv. Record structured
outputs even when the current CLI still prints text. Target fields:

| Operation | Normalized output |
| --- | --- |
| `pt_snap.help` | `{mentions_helper: true, helper_skill: "pt-snap-helper"}` when help points at the helper skill |
| `pt_snap.skill_list` | JSON listing; `json: true` in arguments |
| failed `pt_snap.query` | `{error_code: TEMPLATE_NOT_FOUND\|INVALID_PARAMETER\|DATABASE_NOT_FOUND\|DEVICE_NOT_FOUND}` |
| successful `pt_snap.query` | envelope with `db_path`, `device_id`, `returned`, `has_more`, and `rows` |
| `pt_snap.import` | `{db_path: "<published db>", focus_updated: true\|false}` |

Do not materialize pickle fixtures for these cases. Import is a semantic
operation; `pickle.access` remains forbidden.
