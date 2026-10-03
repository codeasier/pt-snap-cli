# Issue Forms

Parent scope: [automation](../AGENTS.md).

| File | Purpose |
| --- | --- |
| `01-bug-report.yml` | Reproduction and environment details |
| `02-feature-request.yml` | Proposed behavior and use case |
| `03-documentation.yml` | Documentation errors or improvements |
| `04-question.yml` | Usage questions |
| `config.yml` | Blank-issue policy and contact links |

Numbered filenames control chooser ordering. Preserve GitHub issue-form
`name`, `description`, and structured `body` fields; `config.yml` does not have
an `issue_templates` key. Keep prompts aligned with CLI, SnapshotDB and agent-skill
terminology in the README/docs. Contact links must lead to enabled destinations.

The PR template is `../pull_request_template.md`, outside this directory. Changes
to form names/paths or chooser schema require YAML validation and
`pytest tests/test_governance.py` from the repository root; the governance suite
checks the expected form set and supported template placement.
