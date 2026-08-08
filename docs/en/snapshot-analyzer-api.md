# SnapshotAnalyzer API

[中文](../zh/snapshot-analyzer-api.md) | English

`SnapshotAnalyzer` is the high-level Python facade for focus inspection,
template discovery, query execution, and SnapshotDB import metadata. Import it
from `pt_snap_cli.api`; it is not re-exported from the package root.

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
print(state.source)

state = analyzer.set_focus(
    db_path="/path/to/other.db",
    device_id=1,
)
```

`set_focus()` validates a supplied database and updates only the current
`SnapshotAnalyzer` object. It does not write `.pt-snap/focus.json`, change
`PT_SNAP_DB_PATH`, or update global config. A supplied device is validated when
a query resolves its target device.

When the analyzer has an explicit `db_path`, `get_focus()` reports its analyzer
device and does not inherit a device from project or global focus. With no
explicit `db_path`, a device-only analyzer override is applied during query
execution, while `get_focus()` continues to report the device attached to the
resolved project or global focus.

`get_focus()` returns a `FocusState` with these fields:

| Field | Meaning |
| --- | --- |
| `db_path` | Resolved database path, or `None` |
| `device_id` | Device attached to the resolved focus; see the device-only analyzer override note above |
| `source` | Resolution source such as `explicit`, `env`, `project`, `global`, or `none` |
| `available_devices` | Device IDs discovered from `trace_entry_<device>` tables |

See [Focus Management](focus-management.md) for the complete resolution and
persistence model.

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
`category`. `get_template_info()` returns full template metadata or `None` when
the template cannot be resolved.

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
| `total` | Number of rows produced before display limiting |
| `returned` | Number of rows included in `rows` |
| `device_id` | Device selected for execution |
| `rows` | Query rows as dictionaries |

Pass `device_id` to `execute_query()` to override the analyzer's device for one
call. Otherwise selection uses the analyzer device, then the device from resolved
project or global focus when no explicit analyzer database is set, then the first
discovered device. An explicit analyzer database without an analyzer device does
not inherit a configured device. `max_rows=None`, zero, or a negative value is
unlimited.

Rows contain raw SQLite values. Template `output_schema` metadata is not applied
automatically; use the optional [ResultMapper API](result-mapper-api.md) when
converted values or model mapping are required.

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
  `ValueError` for an invalid SnapshotDB schema.
- `execute_query()` raises `RuntimeError` when no database can be resolved;
  query, parameter, device, and database errors otherwise follow the shared
  service-layer exceptions.
- `get_database_metadata()` raises `RuntimeError` without a resolved database,
  `FileNotFoundError` for a missing file, and `ValueError` for an invalid schema.
- `SnapshotAnalyzer` does not import or split raw pickle snapshots and does not
  generate reports. Use the CLI commands documented in
  [Quick Start](quickstart.md), [Splitting Snapshots](splitting.md), and
  [Querying](querying.md) for those workflows.
