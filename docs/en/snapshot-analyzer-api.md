# SnapshotAnalyzer API

[中文](../zh/snapshot-analyzer-api.md) | English

`SnapshotAnalyzer` is the high-level Python facade for focus inspection,
template discovery, capability listing, database overview, query execution, and
SnapshotDB import metadata. Import it from `pt_snap_cli.api`; it is not
re-exported from the package root.

## Create an Analyzer

```python
from pathlib import Path

from pt_snap_cli.api import SnapshotAnalyzer

analyzer = SnapshotAnalyzer(
    db_path=Path("/path/to/snapshot.db"),
    device_id=0,
)
```

The constructor `db_path` is an explicit database for that analyzer instance,
and `device_id` is its default explicit query-device override. When `db_path` is
omitted, the database uses the same resolution order as the CLI:
`PT_SNAP_DB_PATH`, the nearest `.pt-snap/focus.json`, then legacy global config.

## Inspect and Change Focus

```python
state = analyzer.get_focus()
print(state.db_path)
print(state.device_id)
print(state.available_devices)
print(state.callstack_layout)
print(state.source)

state = analyzer.set_focus(
    db_path="/path/to/other.db",
    device_id=1,
)
```

`set_focus()` validates a supplied database and updates only the current
`SnapshotAnalyzer` object. It does not write `.pt-snap/focus.json`, change
`PT_SNAP_DB_PATH`, or update global config. A supplied device is validated
immediately against the supplied or currently resolved database; a failed update
leaves the analyzer unchanged.

Supplying a new `db_path` without `device_id` clears the analyzer's previous
device override, matching a CLI focus change that omits `--device`.

When the analyzer has an explicit `db_path`, `get_focus()` reports its analyzer
device and does not inherit a device from project or global focus. With no
explicit `db_path`, a validated device-only analyzer override is reported by
`get_focus()` and applied during query execution.

`get_focus()` returns a `FocusState` with these fields:

| Field | Meaning |
| --- | --- |
| `db_path` | Resolved database path, or `None` |
| `device_id` | Analyzer device override, or the device attached to the resolved focus |
| `source` | Resolution source such as `explicit`, `env`, `project`, `global`, or `none` |
| `available_devices` | Device IDs discovered from `trace_entry_<device>` tables |
| `callstack_layout` | `"v1"` for inline callstack text, `"v2"` for deduplicated `callstackId`, or `None` when unrecognized or conflicting |
| `callstack_layout_error` | Conflict reason when the layout cannot be used, otherwise `None` |

See [Focus Management](focus-management.md) for the complete resolution and
persistence model.

## List Capabilities

```python
catalog = analyzer.list_capabilities()
print(catalog["cli_version"])
print([item["name"] for item in catalog["templates"]])
print([item["name"] for item in catalog["skills"]])
```

`list_capabilities()` returns the same catalog as `pt-snap capabilities --json`
without the CLI envelope: `cli_version`, full template contracts (matching
`get_template_info()`), and bundled skill listings.

## Discover Templates

```python
templates = analyzer.list_templates()
basic_templates = analyzer.list_templates(category="basic")

info = analyzer.get_template_info("memory_peak")
if info is not None:
    print(info["parameters"])
    print(info["output_schema"])
```

`list_templates()` returns dictionaries containing `name`, `description`, and
`category`. `get_template_info()` returns full template metadata or `None` only
when the named template does not exist; registry failures are propagated. The
payload includes `parameters`, `output_schema`, `semantics_version`, and
`interpretation_limits`. `semantics_version` is the field-interpretation
contract and is distinct from YAML `version` and the SnapshotDB schema /
callstack layout. Unannotated templates use `semantics_version: null` and
`column`/`type` only; annotated columns may also declare `units`,
`metric_semantics`, `scope`, `denominator`, `sentinel`, and per-field
`interpretation_limits`. The dict is JSON-serializable.

## Execute Queries

```python
result = analyzer.execute_query(
    "leak_detection",
    params={"min_size": 1024},
    max_rows=20,
)

print(result["device_id"])
print(result["total"])
print(result["returned"])
for row in result["rows"]:
    print(row)
```

The result contains:

| Key | Meaning |
| --- | --- |
| `total` | Matching-row `COUNT` when `exact_total=True`; otherwise the returned-row count |
| `returned` | Number of rows included in `rows` |
| `has_more` | True when a later page exists (extra-row probe on a trailing `LIMIT`, or a full inner `top_n` window) |
| `truncated` | True when this response is not the complete matching set |
| `total_is_exact` | True when `total` is a `COUNT`, or when the page is the complete matching set |
| `timeout_s` | Effective execution timeout in seconds, or `None` when unbounded |
| `device_id` | Device selected for execution |
| `rows` | Query rows as dictionaries (raw SQLite values, without long field explanations) |
| `template` | Template that produced the rows |
| `semantics_version` | Interpretation contract to look up via `get_template_info()`, or `None` |

Pass `device_id` to `execute_query()` to override the analyzer's device for one
call. Otherwise selection uses the analyzer device, then the device from resolved
project or global focus when no explicit analyzer database is set, then the first
discovered device. An explicit analyzer database without an analyzer device does
not inherit a configured device. `max_rows=None`, zero, or a negative value is
unlimited. Pass `exact_total=True` for a matching-row `COUNT`. `timeout_s`
is a wall-clock budget for one `execute_query()` call in seconds (or
`PT_SNAP_QUERY_TIMEOUT`); the page query and optional COUNT share it. The
same environment variable applies to every template query, including
`report peak-memory`. It does not change the row cap. Continue
`active_memory_callstack_at_event` by increasing `top_n`; `-n` cannot
raise that CTE cap.

Rows contain raw SQLite values. Template `output_schema` metadata is not applied
automatically; use the optional [ResultMapper API](result-mapper-api.md) when
converted values or model mapping are required.

## Inspect Database Overview

```python
overview = analyzer.get_database_overview()
print(overview["devices"])
print(overview["import_metadata"]["status"])
```

`get_database_overview()` is the read-only orientation used by
`pt-snap overview`: device list, per-device first/last event id, and import
metadata status. It does not persist focus or write the database. Missing
focus raises `RuntimeError`; a missing file raises `FileNotFoundError`; an
invalid SnapshotDB schema or a damaged `.pt-snap/focus.json` raises
`ValueError`.

## Inspect Import Metadata

```python
metadata = analyzer.get_database_metadata()

# Inspect another database without changing this analyzer's explicit focus.
other_metadata = analyzer.get_database_metadata("/path/to/other.db")
```

First-party imports return `status="available"` and a metadata object. Compatible
legacy or external databases without `pt_snap_metadata` return
`status="unavailable"` with a reason. Malformed metadata or an unsupported
metadata schema version returns `status="invalid"`.

## Errors and Scope

- `set_focus()` raises `FileNotFoundError` for a missing database and
  `ValueError` for an invalid SnapshotDB schema. Device validation uses the shared
  `InvalidDeviceError`; selecting a device without any resolvable database raises
  `RuntimeError`.
- `execute_query()` raises `RuntimeError` when no database can be resolved;
  query, parameter, device, and database errors otherwise follow the shared
  service-layer exceptions.
- `get_database_overview()` raises `RuntimeError` without a resolved database,
  `FileNotFoundError` for a missing file, and `ValueError` for an invalid schema
  or an invalid `.pt-snap/focus.json`.
- `get_database_metadata()` raises `RuntimeError` without a resolved database,
  `FileNotFoundError` for a missing file, and `ValueError` for an invalid schema.
- `SnapshotAnalyzer` does not import or split raw pickle snapshots and does not
  generate reports. Use the CLI commands documented in
  [Quick Start](quickstart.md), [Splitting Snapshots](splitting.md), and
  [Querying](querying.md) for those workflows.
