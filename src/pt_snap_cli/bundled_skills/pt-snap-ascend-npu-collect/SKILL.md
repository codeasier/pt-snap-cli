---
name: pt-snap-ascend-npu-collect
description: Collect Ascend NPU (torch_npu) PyTorch memory snapshots by recording allocator history and dumping a `.pkl` / `.pickle`. Use when the user needs to capture, dump, or enable snapshot collection on 昇腾 / Ascend via native `_record_memory_history` / `_dump_snapshot`, MindSpeed-MM `memory_profile`, verl `torch_memory`, MindSpeed `--record-memory-history`, or `OOM_SNAPSHOT_*`. Not for diagnosing an existing SnapshotDB and not for importing pickle.
---

# pt-snap-ascend-npu-collect

Collect an Ascend NPU memory snapshot pickle. This is a collection skill, not
an analysis skill.

## Purpose

Record Ascend NPU allocator history and dump a `.pkl` or `.pickle` file.
Collection is finished when that file exists on disk.

This skill does not import, deserialize, visualize, or diagnose the pickle.
Leak, peak, and fragmentation workflows require an existing SnapshotDB and
a separate trusted-input import decision.

torch_npu usage aligns with `torch.cuda.memory.*`, but storage fields and
structure can differ by TorchNPU version. Treat the on-disk pickle as
torch_npu output, not as a CUDA snapshot.

## Required Inputs

Obtain enough context to choose one collection route:

- The training or inference framework, or that the user will call torch_npu
  APIs directly.
- Whether the goal is a planned step window or an OOM fallback.
- An output directory and which ranks to capture.

Optional inputs:

- Step window (`start_step` / `end_step`, or an explicit step list).
- `stacks`: `python` (lower overhead) or `all`.
- `max_entries`: a positive bound; default `100000` when the user has no
  preference. Do not recommend an unbounded recorder unless the user
  explicitly asks for it.
- TorchNPU / HDK / CANN versions when the user already knows them.

Replace placeholders such as `<python_executable>`, `<output_dir>`,
`<snapshot_path>`, `<rank>`, and `<step>` with values the user supplied or
that a read-only check returned. Treat every filesystem path as untrusted
input to quoting: put it in single quotes, and reject values that contain
quotes, `$`, backticks, or other shell metacharacters instead of escaping
them.

## Prerequisite Phase

Run these checks before proposing a capture plan. Do not install packages,
switch interpreters, or start the user's training job.

### 1. Identify the active Python environment

Select one interpreter once, preferring `python` and falling back to
`python3`:

```bash
if command -v python >/dev/null 2>&1; then command -v python; else command -v python3; fi
```

If neither command exists, stop and report that no Python interpreter is
available. Save the selected command path as `<python_candidate>`, then
resolve the interpreter itself:

```bash
"<python_candidate>" -c "import sys; print(sys.executable)"
```

Preserve this path exactly as `<python_executable>` for every later Python
command. Do not pass it through `realpath`, and do not assume Conda or any
fixed environment name.

### 2. Verify torch_npu collection APIs without installing

Run:

```bash
"<python_executable>" -c "import torch_npu; from torch_npu.npu import memory; print(getattr(torch_npu, '__version__', 'unknown')); print(hasattr(memory, '_record_memory_history'), hasattr(memory, '_snapshot'), hasattr(memory, '_dump_snapshot'))"
```

Stop and report the exact failure if the import or attribute check fails.
Do not install `torch_npu`, CANN, a framework, or `pt-snap-cli` from this
skill.

Record the version string when it is available. The `OOM_SNAPSHOT_*`
environment-variable path requires TorchNPU `>= 6.0.0`. If the version is
missing or older, do not offer that path as ready.

`torch_npu.contrib.transfer_to_npu` maps
`torch.cuda.memory._record_memory_history` / `_snapshot` / `_dump_snapshot`
onto the NPU APIs. CUDA-shaped call sites may be reused, but the pickle
layout is still torch_npu's.

### 3. Choose exactly one collection route

Ask the user when the framework or goal is ambiguous. Do not combine routes
in one plan.

| Situation | Route |
| --- | --- |
| Custom script or the user will edit training code | `native-api` |
| MindSpeed-MM | `mindspeed-mm` |
| verl, including 昇腾 / Ascend recipes; MindSpeed-RL | `verl` |
| MindSpeed Core / Megatron with `--record-memory-history` | `mindspeed-core` |
| vllm-ascend, or any job that must not change code | `oom-env` |
| User wants an OOM fallback in addition to a planned window | Keep the planned route; mention `oom-env` only as a separate optional fallback |

MindSpeed-RL inherits the verl profiler and is no longer adding features.
Route it as `verl` and point new work at the verl Ascend recipe. vllm-ascend
has no built-in `_dump_snapshot` / `_record_memory_history` integration;
`memory_snapshot()` in that tree is a mempool check, not a capture API.

## Collection Workflow

Propose the snippet or config for the chosen route. Apply edits to the
user's training repository only when they asked to change that code. Do not
launch training or inference unless the user explicitly asked to run it.

After a capture the user already ran, inventory artifacts with `ls` / `find`
on the output directory. Never open, unpickle, or inspect the file contents.

### Route `native-api`

Start recording before the first large allocation. Use a bounded
`max_entries` and prefer `stacks="python"` unless the user asked for C++
frames. Dump at a fixed step or phase, then disable recording:

```python
import torch_npu

torch_npu.npu.memory._record_memory_history(
    enabled="all",
    context="all",
    stacks="python",
    max_entries=100_000,
)

run_your_code()

torch_npu.npu.memory._dump_snapshot("snapshot.pickle")
torch_npu.npu.memory._record_memory_history(enabled=None)
```

API notes:

- `_record_memory_history(enabled="all", context="all", stacks="all", max_entries=sys.maxsize, device=None)`:
  `enabled=None` stops recording; `state` keeps current allocations only;
  `all` includes history. `stacks` is `python` or `all`.
- `_snapshot(device=None, augment_with_fx_traces=False)` returns the Snapshot
  dict (`segments` / `device_traces`). Use this when a framework must
  serialize the dict itself.
- `_dump_snapshot(filename="dump_snapshot.pickle", augment_with_fx_traces=False)`
  writes the pickle.
- `_save_segment_usage()` / `_save_memory_usage()` write SVG views. They are
  not SnapshotDB input.
- `memory_snapshot(mempool_id=None)` returns current allocator segments
  only. Do not treat it as a history capture.

Expected artifact: a `.pickle` or `.pkl` file. An OOM during the same run
may also write CSV next to the pickle; CSV is not importable.

### Route `oom-env`

Use this when the user cannot change code, or as an explicit OOM fallback.
It does not replace a planned step window.

```bash
export OOM_SNAPSHOT_ENABLE=1
export OOM_SNAPSHOT_PATH='<output_dir>'
```

| Variable | Values | Meaning |
| --- | --- | --- |
| `OOM_SNAPSHOT_ENABLE` | `0` / `1` / `2` | `0` off; `1` current plus history; `2` current only |
| `OOM_SNAPSHOT_PATH` | directory | Snapshot and CSV output directory; defaults to the current working directory |
| `TASK_QUEUE_ENABLE` | `2` | Optional. With OOM snapshots, can show TaskQueue workspace occupancy |

Offer this route only when TorchNPU `>= 6.0.0` was verified or the user
states that version. The extra per-component `curMemSize` /
`memPeakSize` CSV files require HDK `>= 25.5.0` and CANN `>= 8.5.0`; if
those versions are unknown, list CSV availability as unknown.

Do not present `TASK_QUEUE_ENABLE=2` as required for a usable pickle.

### Route `mindspeed-mm`

Prefer `tools.json` `memory_profile` over hand-edited training loops.

```json
{
  "memory_profile": {
    "enable": true,
    "start_step": 0,
    "end_step": 2,
    "save_path": "./memory_snapshot",
    "dump_ranks": [0],
    "stacks": "all",
    "max_entries": 100000
  }
}
```

`start_step` `0` includes initialization. Keep `dump_ranks` to the ranks
under investigation; capturing every rank multiplies file size and overhead.
If the user insists on no bound, `max_entries` may be `null`; record that as
an explicit unbounded choice.

Custom loop hook, only when `tools.json` cannot drive the job:

```python
from megatron.training import get_args
from mindspeed_mm.tools.mem_profiler import memory_profiler

args = get_args()
memory_profiler.reset(args.mm.tool.memory_profile)
while iteration < args.train_iters:
    memory_profiler.step()
    train_one_step()
memory_profiler.stop()
```

One-off script helper:

```python
from mindspeed_mm.tools.mem_profiler import _record, _dump, _stop
_record(); code_to_record(); _dump(); _stop()
```

Expected artifact: `snapshot_{timestamp}_{rank}.pickle` under `save_path`.

### Route `verl`

Use the packaged profiler. Do not add native `_dump_snapshot` calls beside
it. On NPU, verl snapshots with `_snapshot()` plus its own pickle write,
clears history after each dump, and can attach
`torch_npu._C._npu_attach_out_of_memory_observer` for OOM.

```bash
python3 -m verl.trainer.main_ppo ... \
  trainer.device=npu \
  global_profiler.tool=torch_memory \
  actor_rollout_ref.actor.profiler.enable=True \
  actor_rollout_ref.actor.profiler.ranks='[0]' \
  global_profiler.steps=[1,2,3,4,5,6,7,8,9,10] \
  global_profiler.save_path=./mem_snapshots \
  global_profiler.global_tool_config.torch_memory.trace_alloc_max_entries=100000 \
  global_profiler.global_tool_config.torch_memory.stack_depth=32
```

Keep the step list short. Use `profiler.ranks='[0,1]'` for selected ranks
and `profiler.all_ranks=True` only for a short window. Expected artifacts
are per-step files named `torch_memory_rank{N}_pid{pid}.pickle`.

MindSpeed-RL uses the same profiler. For new 昇腾 / Ascend recipes, point at
https://github.com/verl-project/verl-ascend-recipe rather than adding
MindSpeed-RL-only capture code.

### Route `mindspeed-core`

Enable Megatron `--record-memory-history`. `transfer_to_npu` maps that path
onto NPU. Use `oom-env` as a separate fallback when the user needs OOM
coverage. Expected artifact: a pickle from the Megatron / torch_npu dump
path the user's build already uses.

### Route `oom-env` for vllm-ascend

Do not invent a vllm-ascend snapshot flag. Use `OOM_SNAPSHOT_ENABLE` /
`OOM_SNAPSHOT_PATH` as in Route `oom-env`. Service profiling through
msprof, `torch_npu.profiler`, or msprobe is outside this skill.

## After Artifacts Appear

When the user says capture finished, or when they already have files:

1. List the output directory and record each `.pkl` / `.pickle` path, size,
   and rank or step in the file name when present.
2. List sibling CSV files separately. Label them `OOM component CSV`, not
   snapshot input.
3. Ignore SVG files from `_save_segment_usage` / `_save_memory_usage`.
4. Stop. Do not open the pickle, run `pt-snap import`, run `pt-snap split`,
   persist focus, or start a diagnostic skill.

A collected pickle is not a SnapshotDB. `pt-snap` import accepts only
trusted `.pkl` / `.pickle` input, is not a sandbox, and is a separate
user decision. After a SnapshotDB exists, route by question:

- live allocations at the end of a trace → `pt-snap-memory-leak`
- what was live at an active, allocated, or reserved peak →
  `pt-snap-memory-peak-breakdown`
- reserved-vs-active gaps or segment churn → `pt-snap-memory-fragmentation`

If `pt-snap` is missing when the user asks to analyze an already imported
database, stop and direct them to `pt-snap-setup`. Missing `pt-snap` does
not block collection.

Optional user-facing viewers (not part of this workflow): PyTorch
[memory_viz](https://pytorch.org/memory_viz) for small local pickles, and
MindStudio Insight memory tuning for large traces. Do not run those tools
from this skill.

## Output Template

Report results in this order:

1. `Collection scope`: framework or native script, planned window versus
   OOM fallback, ranks, output directory, and `stacks` / `max_entries`.
2. `Environment`: preserved `<python_executable>`, torch_npu version, and
   whether `_record_memory_history`, `_snapshot`, and `_dump_snapshot`
   exist.
3. `Route`: one of `native-api`, `mindspeed-mm`, `verl`, `mindspeed-core`,
   or `oom-env`, plus the exact snippet, config, or environment variables.
4. `Version limits`: TorchNPU requirement for `OOM_SNAPSHOT_*`; HDK/CANN
   requirement for OOM CSV, or `unknown`.
5. `Artifacts`: pickle paths that were found or that the plan will write;
   CSV and SVG listed separately or as `none`.
6. `Compatibility notes`: CUDA API mapping through `transfer_to_npu`
   does not make the pickle CUDA-shaped; field layout follows TorchNPU.
7. `Handoff`: import is a separate trusted-input decision; name the
   diagnostic skill only when a SnapshotDB already exists.
8. `Unknowns`: missing framework, version, rank, step window, or whether
   capture has actually run.

Use these result categories:

- `native-api-plan`: a native recorder/dump snippet is ready and APIs exist.
- `framework-config-plan`: a MindSpeed-MM, verl, or MindSpeed Core config
  is ready.
- `oom-env-plan`: environment variables are ready and TorchNPU meets the
  OOM-snapshot version floor.
- `unsupported-framework`: the framework has no built-in capture; the
  report gives the fallback (`oom-env` for vllm-ascend, verl for
  MindSpeed-RL) without inventing flags.
- `collection-complete`: pickle artifacts were inventoried and no import
  or diagnosis was performed.
- `blocked`: interpreter, torch_npu import, required APIs, or a required
  user choice is missing.

## Guardrails

- Do not install packages or switch Python environments.
- Do not assume Conda or a fixed environment name.
- Preserve the selected `sys.executable` path for every Python command.
- Never open, import, inspect, or deserialize pickle input.
- Never run `pt-snap import`, `pt-snap split`, or `pt-snap focus` with a
  database or device.
- Never persist focus, write reports, exports, scratch databases, or
  readiness files.
- Never start leak, peak, fragmentation, or OOM-root-cause analysis.
- Never treat CSV, SVG, or `memory_snapshot()` output as SnapshotDB input.
- Never claim CUDA and torch_npu pickle layouts are the same.
- Never recommend unbounded `max_entries` unless the user asked for it.
- Never invent a vllm-ascend snapshot integration.
- Keep visualization tools and `pt-snap-setup` as handoffs, not steps in
  this workflow.

## Verification Checklist

- Active interpreter was selected once and its uncanonicalized
  `sys.executable` was reused.
- torch_npu import and the three collection APIs were checked without
  installing anything.
- Exactly one collection route was chosen.
- Planned captures used a bounded `max_entries` unless the user opted out.
- `OOM_SNAPSHOT_*` was offered only when the TorchNPU version floor was
  met or explicitly stated.
- Framework snippets matched MindSpeed-MM, verl, or MindSpeed Core;
  vllm-ascend used OOM environment variables only.
- After capture, only file names and sizes were recorded.
- No pickle was opened and no `pt-snap import` / focus write occurred.
- Diagnostic skills were named only as a post-import handoff.
- Result category, artifacts, version limits, and unknowns were reported.
