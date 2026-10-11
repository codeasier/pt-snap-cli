# Three-shard free-requested fixture

[Provenance and exact generation identity](PROVENANCE.md) ·
[File sizes and SHA256](checksums.json)

The committed compatibility-v1 dataset is
`three_shard_free_requested.pkl.msinsight/manifest.json`. Device 0 has exactly
three one-event shards: allocation 0, free-requested 1, completed-free 2.
Read it without changing its bytes. The source is synthetic JSON; no executable
pickle is committed.

Run the producer checks from the repository root:

```bash
PYTHONPATH="$PWD/src" python -m pytest tests/test_fixture_provenance.py
PYTHONPATH="$PWD/src" python -m pytest tests/test_interop_three_shard.py
```

To prepare a new isolated bundle for a separately authorized consumer retest:

```bash
PYTHONPATH="$PWD/src" python tests/fixtures/interop/generate_three_shard.py \
  --output /tmp/NEW-three-shard-interop
```

Use an absent destination. This generates a new local synthetic pickle and both
real CLI exports, with `--device 0 --events-per-slice 1 --no-focus`; it uses no
network, GPU/NPU, model sessions or original producer. The generator does not
launch a GUI and will not replace an existing output directory.

The GUI's original-source entry requires the **generated**
`three_shard_free_requested.pkl`, adjacent to its generated `.msinsight` directory.
Do not open the committed fixture directly in a consumer that modifies its DBs,
and do not transplant its manifest over another cache. Use the new bundle for
that separate run. Native-v2 output is for pt-snap's reader; it is not a claimed
msinsight input. Record consumer revision and actual observed Free Requested
panel behavior for all three shards before claiming a fix.

The tests demonstrate the current-shard-only lookup limitation and independently
verify bounded manifest-wide association, including separate address reuse and
open-ended cases in both layouts. See the bilingual
[English acceptance guide](../../../docs/en/interop-acceptance.md#three-shard-free-requested-fixture)
and [Chinese acceptance guide](../../../docs/zh/interop-acceptance.md#三片-free-requested-fixture).
