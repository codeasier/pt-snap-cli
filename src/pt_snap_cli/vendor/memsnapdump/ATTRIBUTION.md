# Vendored MemSnapDump

This directory contains a vendored copy of the `dump2db` toolchain from
[`codeasier/MemSnapDump`](https://github.com/codeasier/MemSnapDump). The vendored
code is the minimum closure required to invoke
`memsnapdump.tools.adaptors.snapshot2db.run_dump_to_db` from
`pt_snap_cli.core.snapshot_import_backend`.

## Upstream metadata

| Field        | Value                                                              |
| ------------ | ------------------------------------------------------------------ |
| Repository   | https://github.com/codeasier/MemSnapDump                            |
| Pinned SHA   | `87ea207372e0985790e1a28dab499dccf3c3b9a4` (branch `master`, HEAD at vendoring time) |
| Vendored on  | 2026-06-22                                                         |
| Vendored by  | pt-snap-cli maintainers                                            |
| Closure size | 22 Python source files (5 `__init__.py` + 17 modules)              |

## License

The upstream repository does not publish a top-level `LICENSE` file. Both
`pt-snap-cli` and `MemSnapDump` are developed by the same author and pt-snap-cli
inherits the upstream code under the same MIT license terms; see [`LICENSE`](./LICENSE)
in this directory for the full text. When upstream publishes a formal license
file in a future release, the pinned SHA in this file should be updated and
the upstream license text should replace this one.

## Syncing strategy

The closure is intentionally laid out to mirror the upstream module structure
one-to-one:

```
memsnapdump/
├── __init__.py
├── base/
├── simulate/
├── tools/adaptors/database/
└── util/
```

This makes future re-syncs a matter of `diff -ru` between this tree and a fresh
upstream checkout, file by file. To resync:

1. `git fetch https://github.com/codeasier/MemSnapDump.git master`
2. For each Python file under `src/pt_snap_cli/vendor/memsnapdump/`, copy the
   upstream file from the same path, preserving the upstream license header
   (if any).
3. Update the pinned SHA in the table above.
4. Re-run `pytest` and the wheel smoke test in CI.

## Local modifications

**None.** The vendored code is intended to be byte-identical to the pinned
upstream SHA, so that re-syncing is a clean replace operation. Any local fix
or workaround that the project needs should be applied in
`src/pt_snap_cli/core/snapshot_import_backend.py` (the semantic adapter) or
in `src/pt_snap_cli/core/import_service.py`, **not** in this directory.

## Lint / format exclusion

`pyproject.toml` excludes this entire tree from `black` and `ruff` so that
upstream code is not reformatted on every lint pass. When you upgrade the
pinned SHA, run `black` and `ruff` against the new tree first to surface any
drift between the upstream style and our pinned configuration.

## Tooling

- `black` and `ruff` are configured with `extend-exclude` covering
  `src/pt_snap_cli/vendor/`.
- CI includes a wheel smoke test (`.github/workflows/test.yml`) that builds
  the package, installs the wheel, and runs `pt-snap import` against a real
  fixture. This guarantees that any packaging regression (e.g. setuptools
  dropping the vendored closure) is caught before release.
