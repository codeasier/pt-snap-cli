# Quick Start

[English](quickstart.md) | [中文](../zh/quickstart.md)

Get up and running with `pt-snap-cli` in a few minutes.

## Installation

```bash
pip install -e .
```

## Your First Analysis

### Step 1: Set the Snapshot Database

Point `pt-snap` to your SQLite snapshot database file:

```bash
pt-snap use examples/snapshot_expandable.pkl.db
```

This validates the database and saves the path to `.pt-snap/context.json` in your current directory, so you don't need to repeat it.

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

# View active memory blocks on device 0
pt-snap query --template-use active_blocks --device 0
```

## What's Next

- [Context Management](context-management.md) — Learn how to manage multiple databases across projects and sessions
- [Querying](querying.md) — Full guide to all query templates, parameters, and output
- [Database Schema](database.md) — Understand the SnapshotDB format
