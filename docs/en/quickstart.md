# Quick Start

[中文](../zh/quickstart.md) | English

Get up and running with `pt-snap-cli` in a few minutes.

## Installation

```bash
pip install -e .
```

## Your First Analysis

### Step 1: Set the Snapshot Database and Device

Point `pt-snap` to your SQLite snapshot database file:

```bash
pt-snap focus examples/snapshot_expandable.pkl.db --device 0
```

This validates the database and saves the path and device ID to `.pt-snap/focus.json` in your current directory, so you don't need to repeat it.

If you only want to set the database (no device yet):

```bash
pt-snap focus examples/snapshot_expandable.pkl.db
```

### Step 2: List Available Queries

```bash
pt-snap query --list
```

### Step 3: Run a Query

```bash
pt-snap query --template-use memory_summary
```

### Step 4: Try Advanced Queries

```bash
# Detect potential memory leaks
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'

# Query automatically uses the focused device, or you can override it
pt-snap query --template-use active_blocks --device 1
```

## What's Next

- [Focus Management](focus-management.md) — Learn how to manage database and device focus across projects and sessions
- [Querying](querying.md) — Full guide to all query templates, parameters, and output
- [Database Schema](database.md) — Understand the SnapshotDB format
