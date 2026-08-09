# Snapshot Fixture Provenance

These files are Python pickle inputs. Deserializing a pickle can execute code, so
repository presence alone is not a trust decision. Tests may deserialize only
the exact objects listed in `SHA256SUMS` after `tests/test_fixture_provenance.py`
passes.

## Review Decision

- Decision date: 2026-08-09.
- Approval authority: repository owner; decision tracked by issue #94.
- Scope: the seven exact SHA-256 objects listed below are approved for this
  repository's tests and benchmarks. Any byte change or new pickle requires a
  new provenance review and manifest update before deserialization.
- Static review: all seven objects parse as pickle protocol 4. A `pickletools`
  opcode scan found no `GLOBAL`, `STACK_GLOBAL`, `REDUCE`, `BUILD`, `OBJ`,
  `INST`, `NEWOBJ`, `NEWOBJ_EX`, extension, or persistent-ID opcodes. This scan
  reduces risk but is not a general pickle sandbox.
- Privacy and rights: the five small fixtures are test-corpus inputs from the
  upstream source and commit already identified in
  `src/pt_snap_cli/snapshot/PROVENANCE.md`. The two large fixtures were committed
  as sanitized benchmark baselines; repository history does not retain their
  original capture or sanitization procedure. They are approved only as the
  exact repository test objects below, not as evidence that arbitrary related
  captures are safe to publish. Their continued use is an explicit historical
  exception based on repository history, exact-object hashing, and static opcode
  review; a replacement or additional large capture requires complete source and
  sanitization evidence.

## Accepted Objects

| Fixture | Bytes | Repository introduction | Recorded source | SHA-256 |
| --- | ---: | --- | --- | --- |
| `snapshot_1768383987920985470.pkl` | 573970 | `717e3ca` | Pinned upstream test corpus | `bf83ff68b529d9bd4152d4152b3197e88a6bd2ff8796c81d6709f82993260b5a` |
| `snapshot_expandable.pkl` | 581140 | `717e3ca` | Pinned upstream test corpus | `3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40` |
| `snapshot_import_131k_sanitized.pickle` | 43140853 | `717e3ca` (accepted from pre-squash baseline work) | Repository-maintainer sanitized benchmark baseline; original capture not retained | `26b8d9280e7647fd4e086610c68420d5560278ff40f379f463b51b96f69e1b4d` |
| `snapshot_import_628k_sanitized.pickle` | 175057085 | `717e3ca` (accepted from pre-squash baseline work) | Repository-maintainer sanitized benchmark baseline; original capture not retained | `40634062b399d232a4dd0ca055dbec8479ec6360fd92d8839864f58be217b67a` |
| `snapshot_with_empty_cache_expandable.pkl` | 614145 | `717e3ca` | Pinned upstream test corpus | `e23b9055c2ca73183ee55119180ce06fb9d4b6d4af1b0ecc081b31739e4442aa` |
| `snapshot_with_empty_cache.pkl` | 617060 | `7a40d5c` | Pinned upstream test corpus | `d5cb93fa1e1689f0debb31cbc064d1cbc13f2f44204b9c76dd2c47aa8ba85b3f` |
| `snapshot_with_multi_devices.pkl` | 1355829 | `7a40d5c` | Pinned upstream test corpus | `6f14009de2c4ca42bf9155e358dcc1e37926a2b113705fb7fd2e4ef2545e3aba` |

The two large objects are stored through Git LFS. Their LFS OIDs and declared
sizes must match this table when the object bodies are not present locally.
