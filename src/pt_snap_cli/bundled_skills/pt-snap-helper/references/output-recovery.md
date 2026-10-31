# Recover complete JSON after tool truncation

Read this only when the host tool omitted command output. Only retry probes
that the calling skill is allowed to execute: the helper passes this procedure
to the selected diagnostic skill; it does not run diagnostic preflight itself. Transport truncation
is different from query `has_more` / `truncated` or `stack_truncated`; retrieving
the full JSON does not make a capped evidence set complete.

1. Keep the exact command, CLI/Python environment, resolved target/device and
   dataset fingerprint. Wait for the process to finish; retain exit status,
   stdout and stderr separately. Partial live output is not a successful result.
2. If the host retains complete output, use its output-reading/continuation tool
   to read every byte range from that same invocation, with no gaps or overlaps.
   Reassemble in host memory and parse the **whole** stdout with `json.loads`;
   reject missing/trailing bytes. Do not mix chunks from different invocations.
3. If the host discarded bytes, rerun only the missing/stale read-only probe
   with a larger output budget. There is no pt-snap flag to increase a host's
   output budget. Optionally remove JSON whitespace in memory using the code
   below in the already selected Python environment. This preserves every key,
   template, schema, value and completeness flag; it is not a catalog summary.
4. Check exit status and stderr, then apply the skill's full preflight to the
   complete object: `ok`, CLI version, all required template contracts, resolved
   absolute path/device, `overview.import_metadata.status` and dataset identity
   when applicable. A successfully parsed JSON object alone is not admission.
   Revalidate identity/freshness after a retry. Do not reuse a summary or a
   truncated display as though it were the original complete object.
5. If the host still cannot expose the complete result, stop diagnosis and state
   which probe is incomplete; ask for a tool/output-budget change. Do not use
   `head`, `grep`, template-info substitution, raw SQL, file redirection or `tee`
   to bypass the full-result requirement. Do not write scratch/report files.

Run this as a Python snippet through the host's in-memory execution support
(or `python -c` with the same code); do not save it as a script. The default
command retries capabilities. To retry overview instead, replace `command`
with `["pt-snap", "overview", validated_absolute_db_path, "--json"]`, using an
already validated path string, not shell interpolation. Do not switch Python
or CLI installations. The caller must still request enough output budget or
retrieve every retained chunk of the final, minified JSON.

```python
import json
import subprocess
import sys

command = ["pt-snap", "capabilities", "--json"]
result = subprocess.run(command, capture_output=True, text=True, check=False)
sys.stderr.write(result.stderr)
if result.returncode:
    raise SystemExit(result.returncode)
payload = json.loads(result.stdout)
print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
```

This buffers the complete probe in memory; it is not streaming and has no fixed
memory/output-byte ceiling. It does not reduce semantic data, query work or
result-row caps. Never apply it to import/install/collection to obtain a retry.
