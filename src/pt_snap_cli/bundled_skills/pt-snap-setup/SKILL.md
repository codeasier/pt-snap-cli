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

Before running commands, substitute placeholders such as `<python_executable>`, `<pt_snap_executable>`, and `<pt_snap_cli_source_dir>` with actual values.

## Mandatory Prerequisite Phase
Run these checks in order and report what you found.

### 1. Identify the active Python environment
Select one interpreter once, preferring `python` and falling back to `python3`:
```bash
if command -v python >/dev/null 2>&1; then command -v python; else command -v python3; fi
```
If neither command exists, stop and report that no Python interpreter is available. Save the selected command path as `<python_candidate>`, then resolve the interpreter itself:
```bash
"<python_candidate>" -c "import sys; print(sys.executable)"
```
Preserve this path exactly as `<python_executable>` for every later Python and pip command; do not pass it through `realpath` or switch between `python` and `python3`. A virtual environment may use a symlink whose location is required for Python to discover that environment.

Run:
```bash
"<python_executable>" -V
"<python_executable>" -m pip --version
"<python_executable>" -c "import sys; print(sys.executable)"
```
Record the active Python version, the pip target environment, and the Python executable path. If any of these commands fails, stop and report the exact failure; do not attempt installation with an unverified interpreter.

### 2. Check whether the CLI works and belongs to the selected Python
Run:
```bash
command -v pt-snap
pt-snap --help
```
If both commands succeed, save the first command's output as `<pt_snap_executable>` and inspect its shebang:
```bash
"<python_executable>" -c "from pathlib import Path; import sys; print(Path(sys.argv[1]).open(encoding='utf-8').readline().strip())" "<pt_snap_executable>"
```
Resolve the shebang interpreter and compare `realpath` values computed temporarily for the shebang interpreter and `<python_executable>`. For an `/usr/bin/env <name>` shebang, resolve `<name>` in the current `PATH` before comparing. Never replace `<python_executable>` with its `realpath`; canonicalization is only for this ownership comparison. Report `ready` only when `pt-snap --help` succeeds and both comparison paths identify the same interpreter.

If the shebang is missing or cannot be resolved, report `CLI ownership unverified`. If it points to another interpreter, report `CLI belongs to another Python environment`. Do not report the selected Python environment as ready and do not reinstall automatically.

### 3. If the CLI is unavailable or belongs elsewhere, check package availability
Run this check if `pt-snap --help` failed or Step 2 did not verify ownership:
```bash
"<python_executable>" -c "import pt_snap_cli; print(pt_snap_cli.__file__)"
```
If the import succeeds, also run:
```bash
"<python_executable>" -m pip show pt-snap-cli
```
This distinguishes between:
- CLI available and ready.
- CLI resolves to another Python environment while the selected Python may or may not have the package.
- Package import works but `pt-snap` is not on the current shell `PATH`.
- Package import works from a source path, but the distribution is not installed in the active environment.
- Neither the CLI nor the package is available in the active Python environment.

### 4. If no matching CLI or package is available, ask before installing
If CLI ownership is not verified and the import check fails, report `not installed`, then ask which install source the user prefers. Confirm before running any install command. If the user declines, report `installation declined` and stop.

If the import succeeds but the CLI is missing, do not reinstall automatically. Report that the package is importable but the `pt-snap` entry point is unavailable, including whether `pip show pt-snap-cli` found an installed distribution. Ask whether the user wants to repair the installation or update `PATH`.

Install choices:
- Editable install from this repository or another local checkout:
  - Standard: `"<python_executable>" -m pip install -e "<pt_snap_cli_source_dir>"`
  - With dev extras if requested: `"<python_executable>" -m pip install -e "<pt_snap_cli_source_dir>[dev]"`
- PyPI install:
  - `"<python_executable>" -m pip install pt-snap-cli`

If the user wants a local editable install but has not provided `<pt_snap_cli_source_dir>`, ask for it first.

### 5. Run the chosen install into the active Python environment
Always use `"<python_executable>" -m pip install ...` so the install targets the selected Python environment.

Examples:
```bash
"<python_executable>" -m pip install -e "<pt_snap_cli_source_dir>"
"<python_executable>" -m pip install -e "<pt_snap_cli_source_dir>[dev]"
"<python_executable>" -m pip install pt-snap-cli
```
Do not switch environments silently. Do not replace `"<python_executable>" -m pip` with plain `pip` unless the user explicitly asks for that behavior.

### 6. Re-verify after install
Run the CLI path, help, ownership, import, and distribution checks again after any confirmed install command. Step 6 always re-runs all checks post-install by design:
```bash
command -v pt-snap
pt-snap --help
"<python_executable>" -c "import pt_snap_cli; print(pt_snap_cli.__file__)"
"<python_executable>" -m pip show pt-snap-cli
```
Repeat the shebang comparison from Step 2 when `command -v pt-snap` and `pt-snap --help` succeed. Then report the final state using the result categories in the output template.

If installation succeeds but `pt-snap --help` still fails while the import succeeds, report `CLI missing but import works` and explain that the executable directory is not on the current shell `PATH`. Do not run another install automatically.

If `pt-snap` still resolves to another interpreter, report `CLI belongs to another Python environment`, even when the selected Python can import the package. Do not report `ready` until CLI ownership matches.

### 7. Stop if verification still fails
If verification still fails after the confirmed install command, stop and report the exact failure. Do not guess another environment, do not try a different interpreter automatically, and do not keep running more install commands without user confirmation.

## Output Template
Report results in this structure:

- Active Python info:
  - Selected command: `<python or python3>`
  - `<python_executable> -V`: `<version output>`
  - `<python_executable> -m pip --version`: `<pip output>`
  - `<python_executable> -c "import sys; print(sys.executable)"`: `<preserved python path>`
- Detected availability:
  - `command -v pt-snap`: `<executable path, failed, or not run>`
  - `pt-snap --help`: `<worked or failed>`
  - CLI shebang interpreter: `<canonical interpreter path, unresolved, or not run>`
  - CLI ownership: `<matches selected Python, belongs elsewhere, unresolved, or not run>`
  - `<python_executable> -c "import pt_snap_cli; print(pt_snap_cli.__file__)"`: `<worked, failed, or not run>`
  - `<python_executable> -m pip show pt-snap-cli`: `<found, not found, failed, or not run>`
- Install command used:
  - `<none, or exact <python_executable> -m pip install ... command>`
- Install outcome:
  - `<success, declined, or failure summary>`
- Final verification result:
  - `<ready / CLI belongs to another Python environment / CLI ownership unverified / CLI missing but import works / not installed / installation declined / install failed>`

Use these categories consistently before and after installation:
- `ready`: CLI help succeeds and the CLI shebang resolves to the selected Python.
- `CLI belongs to another Python environment`: CLI help succeeds, but its shebang resolves to a different interpreter.
- `CLI ownership unverified`: CLI help succeeds, but its shebang is missing or cannot be resolved.
- `CLI missing but import works`: the selected Python imports the package, but no matching CLI is available.
- `not installed`: neither a matching CLI nor a package import is available and no install was attempted.
- `installation declined`: installation was offered and the user declined it.
- `install failed`: a confirmed install command or its post-install package verification failed.

## Guardrails
- Do not assume conda or any fixed environment name.
- Do not silently switch the user's environment.
- Confirm with the user before any `pip install`.
- Select `python` or `python3` once and preserve its `sys.executable` path for every Python and pip command.
- Use canonical paths only for CLI ownership comparison, never to execute Python or pip.
- Verify that the resolved `pt-snap` shebang belongs to the selected Python before reporting `ready`.
- Do not write report files.
- Do not modify user config beyond what `pip install` requires.

## Verification Checklist
- `python` or `python3` selected once and its uncanonicalized `sys.executable` path used consistently.
- Active Python environment identified with `<python_executable> -V`, `<python_executable> -m pip --version`, and `sys.executable`.
- `command -v pt-snap` and `pt-snap --help` checked in the current shell.
- Resolved CLI shebang interpreter compared with the selected Python before reporting `ready`.
- Package import checked if the CLI is unavailable or its ownership is not verified.
- `<python_executable> -m pip show pt-snap-cli` checked when the package import succeeds but the CLI is unavailable or belongs elsewhere.
- User confirmation obtained before any `<python_executable> -m pip install ...` command.
- Exact install command recorded if one was run.
- Post-install verification re-run.
- `not installed`, `installation declined`, and `install failed` reported as distinct states.
- If verification failed, failure reported without guessing another environment.
