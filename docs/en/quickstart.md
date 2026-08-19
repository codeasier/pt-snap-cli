# Quick Start

[中文](../zh/quickstart.md) | English

Get up and running with `pt-snap-cli` in a few minutes.

## Installation

From a source checkout:

```bash
pip install -e .
```

## Your First Analysis

### Optional: Import a PyTorch Snapshot

If you have a raw `.pkl` memory snapshot, import it first with the built-in backend:

> **Security warning:** Use trusted pickle input only. Deserializing a pickle can
> execute arbitrary code. The loader rejects non-`builtins` global objects, but
> `pt-snap import` is not a sandbox.

```bash
pt-snap import snapshot.pkl
pt-snap metadata snapshot.pkl.db
pt-snap query --list
```

The import command stores a SHA-256 source fingerprint and import compatibility metadata inside the
generated database. Repeating the same import with the same device selection reuses the existing DB.
Use `--force` when you intentionally need to rebuild it:

```bash
pt-snap import snapshot.pkl --force
```

Import currently loads the entire pickle before processing it, so peak memory can be
substantially larger than the input file depending on its object graph and frame count.
Run large imports with sufficient memory headroom. `--device` limits subsequent replay
and database writes, but does not reduce the initial pickle-loading memory peak.

During import, pt-snap replays the selected device's allocator history instead of
copying raw events directly. The resulting SnapshotDB records event-by-event
`allocated`, `active`, and `reserved` totals plus block lifecycles, which makes it
the supported input for `pt-snap query` and `pt-snap report`. This replay behavior
is part of the command workflow; snapshot runtime Python modules are not a public API.

### Optional: Split a Snapshot

Use `pt-snap split` when you need smaller, independently replayable files. Split
does not read or change focus:

```bash
pt-snap split snapshot.pkl --max-entries 50000 --output snapshot-slices
```

Use exactly one of `--slices` and `--max-entries`. See
[Splitting Snapshots](splitting.md) for all-device behavior, formats, names, and
atomic publication guarantees.

### Step 1: Set the Snapshot Database and Device

Point `pt-snap` to your SQLite snapshot database file:

```bash
pt-snap focus snapshot.pkl.db --device 0
```

This validates the database and saves the path and device ID to `.pt-snap/focus.json` in your current directory, so you don't need to repeat it.

If you only want to set the database (no device yet):

```bash
pt-snap focus snapshot.pkl.db
```

### Step 2: List Available Queries

```bash
pt-snap query --list
```

### Step 3: Run a Query

```bash
pt-snap query --template-use memory_peak
```

### Step 4: Try Advanced Queries

```bash
# Detect potential memory leaks
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'

# Query automatically uses the focused device, or you can override it
pt-snap query --template-use block --device 0 --params '{"min_size": 1048576}'
```

## What's Next

- [Focus Management](focus-management.md) — Learn how to manage database and device focus across projects and sessions
- [Querying](querying.md) — Query workflows, template discovery, parameters, and output
- [Splitting Snapshots](splitting.md) — Create independently replayable per-device slices
- [MCP Server](mcp.md) — Use the MCP server for AI agent integration
- [Database Schema](database.md) — Understand the SnapshotDB format
- [SnapshotAnalyzer API](snapshot-analyzer-api.md) — Query SnapshotDB files from Python
