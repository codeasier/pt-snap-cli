# pt-snap-cli

[![PyPI](https://img.shields.io/pypi/v/pt-snap-cli?logo=pypi&logoColor=FFE873&label=PyPI&color=3775A9)](https://pypi.org/project/pt-snap-cli/)
[![Python](https://img.shields.io/pypi/pyversions/pt-snap-cli?logo=python&logoColor=white)](https://pypi.org/project/pt-snap-cli/)
[![MIT License](https://img.shields.io/github/license/codeasier/pt-snap-cli)](LICENSE)
[![Tests](https://github.com/codeasier/pt-snap-cli/actions/workflows/test.yml/badge.svg)](https://github.com/codeasier/pt-snap-cli/actions/workflows/test.yml)

[中文文档](README_zh.md) | English

A command-line tool for analyzing PyTorch memory snapshots. Set a snapshot database, run built-in queries, and inspect memory usage, leaks, and timelines.

## Start Here

| Your input or goal | Next step |
| --- | --- |
| Existing `.db` or complete dataset | [Inspect → query → report](docs/en/quickstart.md#step-2-inspect-the-target-and-choose-a-device); no import required |
| Trusted pickle | [Default single-DB import](docs/en/quickstart.md#step-1-import-only-if-needed) |
| No snapshot yet | [Collection prerequisites and entry points](docs/en/quickstart.md#need-to-collect-a-snapshot) |
| Ask an agent to analyze | [Install → restart → verify → ask](docs/en/skills.md#first-agent-session) |

## Installation

Requires **Python 3.10+**. Offline import/analysis needs no PyTorch or accelerator;
collection uses the workload's compatible GPU/NPU environment.

```bash
python -m pip install pt-snap-cli
```

For a source checkout and contributor setup, see [Development](#development).

## Quick Start

If you already have a DB, skip import. Otherwise use only a **trusted** pickle:
its deserialization can execute arbitrary code; the `builtins` restriction does
not make `pt-snap import` a sandbox.

```bash
pt-snap import snapshot.pkl
pt-snap overview snapshot.pkl.db --json
# Replace 0 with a device returned by overview.
pt-snap query snapshot.pkl.db --device 0 --template-use memory_peak --json
pt-snap report peak-memory snapshot.pkl.db --device 0 --metric active --limit 20
```

Default import writes `snapshot.pkl.db` beside the pickle and updates project
`.pt-snap/focus.json` in the current directory. Add `--no-focus` to avoid that
focus change, not to prevent DB replacement: a standalone cache miss/`--force`
can replace an existing same-named DB; choose another `--output-dir` if needed.
The explicit-path inspection/query/report commands do not persist
focus or modify source data. The [walkthrough](docs/en/quickstart.md) explains
byte units, allocated/active/reserved counters, expected output and partial reports.

### Other Input Formats

- [Native sharded import](docs/en/quickstart.md#optional-import-a-native-sharded-dataset): opt in with `--events-per-slice`; not msinsight-compatible.
- [Explicit msinsight export](docs/en/quickstart.md#optional-export-an-msinsight-compatible-dataset): separate compatibility and no-replace rules, even with `--force`.
- [Replayable pickle splitting](docs/en/splitting.md): one split strategy and a new output directory; separate from dataset import.
- [Complete-dataset addressing](docs/en/sharded-snapshotdb.md#complete-dataset-focus-and-addressing-p1), [global built-in support](docs/en/querying.md#dataset-global-built-in-support-p3), and [recorded interoperability acceptance](docs/en/interop-acceptance.md): advanced contracts and evidence, not prerequisites for a first report.

## Commands

| Command | Description |
|---------|-------------|
| `pt-snap focus` | Set and manage analysis focus (database + device) |
| `pt-snap import <snapshot.pkl>` | Import a PyTorch memory snapshot pickle into a SnapshotDB |
| `pt-snap split <snapshot.pkl>` | Create replayable per-device snapshot slices |
| `pt-snap metadata [database.db]` | Inspect SnapshotDB import provenance and compatibility metadata |
| `pt-snap capabilities` | List CLI version, query template contracts, and bundled skills |
| `pt-snap overview [database.db]` | Read-only device list, per-device event-id bounds, and import-metadata status |
| `pt-snap query` | Run memory analysis queries |
| `pt-snap report` | Generate higher-level memory analysis reports |
| `pt-snap report memory-tree --event-id <id>` | Frame-level live-memory breakdown; `--format html` emits an interactive flamegraph |
| `pt-snap config` | Manage global configuration |
| `pt-snap skill` | List and install bundled agent skills |

`pt-snap --help` includes an agent hint: prefer `--json` on the command that supports it, start with the `pt-snap-helper` skill, use `pt-snap capabilities --json` and `pt-snap overview --json` before diagnosing, and check availability with `pt-snap skill list --json`. `focus`, `import`, `split`, `query`, `config`, `capabilities`, `overview`, `metadata`, `report peak-memory`, and `skill list/install/upgrade/uninstall` accept `--json`.

Peak reports expose attribution completeness and same-event active-byte coverage;
group percentages use included bytes after filtering and ranking. See the
[report guide](docs/en/querying.md#report-command) before interpreting a capped breakdown.

Standalone imports preserve ordered structured callstack frames. Use `event_frames` to
inspect them, or `report memory-tree --event-id 100 --format html > memory-tree.html`
to explore event-time occupancy by caller path. See
[frame memory breakdown](docs/en/querying.md#frame-memory-breakdown); older
text-only databases require re-importing the original snapshot.
`report memory-tree` also accepts `--json`. The HTML view has full-tree search and
keyboard-accessible child lists, so tiny and zero-byte frames remain reachable.

Dataset work limits are configurable with `--max-work-rows`, `--max-work-bytes`,
`--max-scratch-db-bytes`, environment variables, or immutable Python `QueryLimits`.
Defaults remain 100000 work rows / 64 MiB work bytes / 512 MiB scratch pages; see
[public dataset limits](docs/en/querying.md#public-dataset-limits) for precedence,
deep-pagination costs and all-or-error semantics.

## Agent Skills

For long diagnostic stacks, opt into `stack_bytes` on `event` or
`active_memory_callstack_at_event`, or `report peak-memory --stack-bytes 256`.
See [compact callstack text](docs/en/querying.md#compact-callstack-text) for
identity, byte-budget metadata and full-text retrieval.

Install bundled diagnostic workflows with `pt-snap skill install`. Agent integration uses skills plus the CLI; there is no MCP server. See the [Agent Skills guide](docs/en/skills.md).

Ascend NPU capture can proceed without `pt-snap` when the host has loaded
`pt-snap-ascend-npu-collect`; the helper routes collection before CLI setup.
Analysis still requires the CLI and a SnapshotDB, with trusted import as a separate decision.

## Documentation

See the [documentation index](docs/README.md) for all English and Chinese guides.

| Topic | Guide |
|-------|-------|
| Getting started | [Quick Start](docs/en/quickstart.md) |
| Managing focus | [Focus Management](docs/en/focus-management.md) |
| Running queries | [Querying](docs/en/querying.md) |
| Splitting snapshots | [Splitting Snapshots](docs/en/splitting.md) |
| Agent skills | [Agent Skills](docs/en/skills.md) |
| Database format | [SnapshotDB Schema](docs/en/database.md) |
| Sharded protocols, native import and compatibility limits | [Sharded SnapshotDB protocol](docs/en/sharded-snapshotdb.md) |
| Python API | [SnapshotAnalyzer API](docs/en/snapshot-analyzer-api.md) |
| Result mapping utility | [ResultMapper API](docs/en/result-mapper-api.md) |

## Development

Use the repository's single [Development and Checks checklist](AGENTS.md#development-and-checks):
fixture provenance, pytest, Ruff, Black, **basedpyright**, and `git diff --check`.
It also explains environment isolation, browser tests and coverage gates.

```bash
python -m pip install -e ".[dev]"
```


For the regular suite use `pytest -m 'not slow'`. Default-capacity scale and
non-editable installed exporter tests are described in the
[dataset acceptance guide](docs/en/dataset-acceptance.md).

The supplemental platform workflow runs Python 3.13 non-slow tests on macOS and
Windows. Windows uses four deterministic, disjoint shards of the full non-slow
collection; macOS runs it in one job. All five jobs retain a 20-minute limit,
with at most two running concurrently. Each Windows shard validates exhaustive
coverage before execution and uploads its full collection/partition manifest
alongside JUnit results. No tests are skipped to meet the time limit. To reproduce
one Windows partition locally, run
`python .github/scripts/run_platform_tests.py --shard 0` (choose `--shard 0` through `--shard 3`);
add `--collect-only` to inspect the partition without executing tests.

### Building distributions

Build from a fresh checkout or a new worktree at the intended commit, with no
existing `build/` or `dist/` directories. Setuptools can reuse files in `build/lib`
on repeated builds, including modules deleted from the source tree; build dependency
isolation does not clean these intermediates. Inspect old outputs before removing
them yourself, or use a fresh worktree instead.

From that checkout's root:

```bash
python -m build                  # Build sdist and wheel
python .github/scripts/audit_wheel.py --wheel dist/<built-wheel>.whl
```

Replace `<built-wheel>` with the generated filename. The read-only audit compares
Python module paths and bytes with `src/`, and separately checks query YAML,
bundled skills, and snapshot license/provenance resources against the packaging
contract. Generated distribution metadata is allowed. A mismatch fails with the
affected paths; rebuild from a fresh source tree and audit again before using the
wheel. CI audits its wheel before installed-package acceptance; release separately
audits the actual wheel it uploads for publication.
