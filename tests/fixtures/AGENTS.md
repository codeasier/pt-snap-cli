<!-- Parent: ../AGENTS.md -->

# fixtures

## Purpose
`tests/fixtures` owns committed test inputs. Snapshot pickle files are executable
inputs with a separate acceptance lifecycle; they are not trusted merely because
they are tracked by Git.

## Snapshot Acceptance
- `snapshots/PROVENANCE.md` records source evidence, review limits, introduction commits, sizes, and exact SHA-256 values.
- `snapshots/SHA256SUMS` is the machine-readable allowlist enforced by `tests/test_fixture_provenance.py` without deserialization.
- Git LFS pointers are acceptable in checkouts only when their OID and declared size match the reviewed object.
- Before adding or changing a pickle, document its source, rights/privacy review, sanitization evidence, purpose, introduction decision, size, checksum, and static opcode review.
- Existing objects may rely only on a historical exception explicitly recorded in `snapshots/PROVENANCE.md`; that exception does not waive evidence requirements for replacements or additions.
- Do not deserialize a new or changed fixture to inspect it. Complete provenance and non-executing static review first, obtain explicit maintainer approval, then update the manifest and tests.

## Verification
- Run `pytest tests/test_fixture_provenance.py` before import, split, benchmark, or snapshot suites that load committed pickles.
- Changes to fixture trust records require `git diff --check` and review of `.gitattributes`/`.gitignore` when Git LFS or sensitive-data rules are affected.
