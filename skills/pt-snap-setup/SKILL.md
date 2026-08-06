---
name: pt-snap-setup
description: Use when installing or verifying pt-snap-cli in the current Python environment. Does not assume conda; for first-time install, PyPI, editable install, or pre-flight before fragmentation/leak analysis when pt-snap is missing.
---

# pt-snap-setup

## Overview
Use this skill to verify whether `pt-snap-cli` is available in the current Python environment, or to guide a safe install into that same environment when it is missing.

Use it when:
- Installing `pt-snap-cli` for the first time.
- Verifying whether the current shell is ready to run `pt-snap`.
- Doing pre-flight setup before fragmentation or leak analysis when `pt-snap` is missing.

Do not assume conda, any fixed environment name, or that a different shell has the right Python. Work only with the environment that is active in the current shell unless the user explicitly changes it.

## Required Inputs
No inputs are required.

Optional inputs:
- `<pt_snap_cli_source_dir>`: absolute or user-provided path to a local `pt-snap-cli` checkout for editable install.
- Install source preference: `editable` or `pypi`.
- Whether dev extras are wanted for a local editable install.

Before running commands, substitute placeholders such as `<pt_snap_cli_source_dir>` with actual values.

## Mandatory Prerequisite Phase
Run these checks in order and report what you found.

### 1. Identify the active Python environment
Run:
```bash
python -V
python -m pip --version
python -c "import sys; print(sys.executable)"
```
Record the active Python version, the pip target environment, and the Python executable path. If any of these commands fails, stop and report the exact failure; do not attempt installation with an unverified interpreter.

### 2. Check whether the CLI already works
Run:
```bash
pt-snap --help
```
If this succeeds, report that `pt-snap` is available in the current shell.

### 3. If the CLI is unavailable, check package importability and installation metadata
Run this check only if `pt-snap --help` failed in Step 2:
```bash
python -c "import pt_snap_cli; print(pt_snap_cli.__file__)"
```
If the import succeeds, also run:
```bash
python -m pip show pt-snap-cli
```
This distinguishes between:
- CLI available and ready.
- Package import works but `pt-snap` is not on the current shell `PATH`.
- Package import works from a source path, but the distribution is not installed in the active environment.
- Neither the CLI nor the package is available in the active Python environment.

### 4. If both checks fail, ask for install source and confirm first
If `pt-snap --help` fails and the import check fails, stop and ask the user which install source they prefer. Confirm before running any install command.

If the import succeeds but the CLI is missing, do not reinstall automatically. Report that the package is importable but the `pt-snap` entry point is unavailable, including whether `pip show pt-snap-cli` found an installed distribution. Ask whether the user wants to repair the installation or update `PATH`.

Install choices:
- Editable install from this repository or another local checkout:
  - Standard: `python -m pip install -e "<pt_snap_cli_source_dir>"`
  - With dev extras if requested: `python -m pip install -e "<pt_snap_cli_source_dir>[dev]"`
- PyPI install:
  - `python -m pip install pt-snap-cli`

If the user wants a local editable install but has not provided `<pt_snap_cli_source_dir>`, ask for it first.

### 5. Run the chosen install into the active Python environment
Always use `python -m pip install ...` so the install targets the active Python environment.

Examples:
```bash
python -m pip install -e "<pt_snap_cli_source_dir>"
python -m pip install -e "<pt_snap_cli_source_dir>[dev]"
python -m pip install pt-snap-cli
```
Do not switch environments silently. Do not replace `python -m pip` with plain `pip` unless the user explicitly asks for that behavior.

### 6. Re-verify after install
Run both checks again after any confirmed install command, even if Step 3 was the only check that failed earlier. Step 6 always re-runs both checks post-install by design:
```bash
pt-snap --help
python -c "import pt_snap_cli; print(pt_snap_cli.__file__)"
```
Then report the final state using the same result categories as the output template: `ready`, `CLI missing but import works`, or `install failed`.

If installation succeeds but `pt-snap --help` still fails while the import succeeds, report `CLI missing but import works` and explain that the executable directory is not on the current shell `PATH`. Do not run another install automatically.

### 7. Stop if verification still fails
If verification still fails after the confirmed install command, stop and report the exact failure. Do not guess another environment, do not try a different interpreter automatically, and do not keep running more install commands without user confirmation.

## Output Template
Report results in this structure:

- Active Python info:
  - `python -V`: `<version output>`
  - `python -m pip --version`: `<pip output>`
  - `python -c "import sys; print(sys.executable)"`: `<python path>`
- Detected availability:
  - `pt-snap --help`: `<worked or failed>`
  - `python -c "import pt_snap_cli; print(pt_snap_cli.__file__)"`: `<worked, failed, or not run>`
  - `python -m pip show pt-snap-cli`: `<found, not found, failed, or not run>`
- Install command used:
  - `<none, or exact python -m pip install ... command>`
- Install outcome:
  - `<success, declined, or failure summary>`
- Final verification result:
  - `<ready / CLI missing but import works / install failed>`

## Guardrails
- Do not assume conda or any fixed environment name.
- Do not silently switch the user's environment.
- Confirm with the user before any `pip install`.
- Use `python -m pip` so install targets the active Python environment.
- Do not write report files.
- Do not modify user config beyond what `pip install` requires.

## Verification Checklist
- Active Python environment identified with `python -V`, `python -m pip --version`, and `python -c "import sys; print(sys.executable)"`.
- `pt-snap --help` checked in the current shell.
- `python -c "import pt_snap_cli; print(pt_snap_cli.__file__)"` checked if needed.
- `python -m pip show pt-snap-cli` checked when the package import succeeds but the CLI is unavailable.
- User confirmation obtained before any `python -m pip install ...` command.
- Exact install command recorded if one was run.
- Post-install verification re-run.
- If verification failed, failure reported without guessing another environment.
