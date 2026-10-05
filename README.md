# pt-snap-cli

[中文文档](README_zh.md) | English

A command-line tool for analyzing PyTorch memory snapshots. Set a snapshot database, run built-in queries, and inspect memory usage, leaks, and timelines.

## Installation

```bash
pip install pt-snap-cli
```

For a source checkout and contributor setup, see [Development](#development).

## Quick Start

To start from a raw PyTorch memory snapshot, import the pickle into a SnapshotDB with pt-snap's built-in snapshot support, then list the available query templates:

> **Security warning:** Import only pickle snapshots from a trusted source. Pickle
> deserialization can execute arbitrary code. The loader rejects non-`builtins`
> global objects, but `pt-snap import` is not a sandbox.

```bash
pt-snap import snapshot.pkl
pt-snap metadata snapshot.pkl.db
pt-snap query --list
```

```bash
# Set the snapshot database and device
pt-snap focus snapshot.pkl.db --device 0

# List available queries
pt-snap query --list

# Run a query (automatically uses the focused device)
pt-snap query --template-use memory_peak

# Detect potential memory leaks
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

To divide a large snapshot into independently replayable files before import,
use exactly one split strategy and an output directory that does not exist:

```bash
pt-snap split snapshot.pkl --slices 4 --output snapshot-slices
```

See [Splitting Snapshots](docs/en/splitting.md) for device selection, JSON output,
deterministic names, replay validation, and failure-safe publication.

See the [full quick start guide](docs/en/quickstart.md) for a walkthrough.

Complete compatibility-v1 sharded artifacts can be focused by directory or
`manifest.json`, without the archived pickle. See [dataset focus and addressing](docs/en/sharded-snapshotdb.md#complete-dataset-focus-and-addressing-p1)
for read-only overview, event routing, `--slice`, and explicit cross-slice limits.

Opt into a **native, not msinsight-compatible** dataset with
`pt-snap import snapshot.pkl --events-per-slice 50000 --output-dir captures --json`.
The output is `captures/snapshot.pkl.pt-snap-native-v2/`; default standalone import
is unchanged. Reuse validates all shards and content/options/semantic versions.
Nonmatching recognized targets require `--force`; unknown targets are preserved.
Publication/focus failures are compensated, with explicit recovery evidence if
rollback fails (force is not a single crash-atomic swap). See the
[native import guide](docs/en/quickstart.md#optional-import-a-native-sharded-dataset).
Only bounded dataset `event` queries are currently supported.

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
| `pt-snap config` | Manage global configuration |
| `pt-snap skill` | List and install bundled agent skills |

`pt-snap --help` includes an agent hint: prefer `--json` on the command that supports it, start with the `pt-snap-helper` skill, use `pt-snap capabilities --json` and `pt-snap overview --json` before diagnosing, and check availability with `pt-snap skill list --json`. `focus`, `import`, `split`, `query`, `config`, `capabilities`, `overview`, `metadata`, `report peak-memory`, and `skill list/install/upgrade/uninstall` accept `--json`.

Peak reports expose attribution completeness and same-event active-byte coverage;
group percentages use included bytes after filtering and ranking. See the
[report guide](docs/en/querying.md#report-command) before interpreting a capped breakdown.

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

```bash
pip install -e ".[dev]"         # Install development dependencies
pytest                           # Run all tests
black --check . && ruff check .  # Check formatting and lint
```

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
