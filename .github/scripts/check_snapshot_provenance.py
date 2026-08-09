from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Sequence

SNAPSHOT_PREFIX = "src/pt_snap_cli/snapshot/"
PROVENANCE_PATH = f"{SNAPSHOT_PREFIX}PROVENANCE.md"
DECISION_LABEL = "Snapshot provenance decision"
REASON_LABEL = "Snapshot provenance no-update reason"
_DECLARATION = re.compile(
    rf"^[ \t]*(?P<label>{re.escape(DECISION_LABEL)}|{re.escape(REASON_LABEL)})"
    r":[ \t]*(?P<value>.*?)[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_PLACEHOLDERS = {
    "n/a",
    "na",
    "none",
    "no reason",
    "not applicable",
    "placeholder",
    "required only for no-update",
    "tbd",
    "todo",
}


class GuardError(ValueError):
    pass


def changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", base, head, "--"],
        check=True,
        capture_output=True,
    )
    return [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def git_blob(ref: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        check=False,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def validate_append_only(base: bytes | None, head: bytes | None) -> list[bytes]:
    """Return inserted lines while rejecting changes to existing provenance lines."""
    if head is None:
        raise GuardError(f"Append-only provenance file was deleted: {PROVENANCE_PATH}.")

    base_lines = [] if base is None else base.splitlines(keepends=True)
    head_lines = head.splitlines(keepends=True)
    base_index = 0
    inserted: list[bytes] = []
    for line in head_lines:
        if base_index < len(base_lines) and line == base_lines[base_index]:
            base_index += 1
        else:
            inserted.append(line)

    if base_index != len(base_lines):
        raise GuardError(
            f"{PROVENANCE_PATH} is append-only; existing lines may not be deleted, "
            "rewritten, truncated, or reordered."
        )
    return inserted


def _declarations(body: str) -> dict[str, list[str]]:
    declarations = {DECISION_LABEL.lower(): [], REASON_LABEL.lower(): []}
    for match in _DECLARATION.finditer(body):
        label = match.group("label").lower()
        value = _HTML_COMMENT.sub("", match.group("value")).strip()
        declarations[label].append(value)
    return declarations


def validate_provenance(
    changes: Sequence[str],
    body: str,
    inserted_lines: Sequence[bytes] = (),
) -> str:
    snapshot_changes = [path for path in changes if path.startswith(SNAPSHOT_PREFIX)]
    if not snapshot_changes:
        return "No snapshot runtime changes detected."

    declarations = _declarations(body)
    decisions = declarations[DECISION_LABEL.lower()]
    if len(decisions) != 1:
        raise GuardError(f"Provide exactly one '{DECISION_LABEL}:' declaration in the PR body.")
    decision = decisions[0].lower()
    if decision not in {"updated", "no-update"}:
        raise GuardError(
            f"'{DECISION_LABEL}' must be exactly 'updated' or 'no-update', not {decisions[0]!r}."
        )

    reasons = declarations[REASON_LABEL.lower()]
    if len(reasons) > 1:
        raise GuardError(f"Provide at most one '{REASON_LABEL}:' declaration in the PR body.")

    if decision == "updated":
        if PROVENANCE_PATH not in changes:
            raise GuardError(f"The 'updated' decision requires a change to {PROVENANCE_PATH}.")
        if not any(line.strip() for line in inserted_lines):
            raise GuardError(f"The 'updated' decision requires new content in {PROVENANCE_PATH}.")
        return f"Snapshot provenance updated in {PROVENANCE_PATH}."

    if PROVENANCE_PATH in changes:
        raise GuardError(f"The 'no-update' decision cannot include a change to {PROVENANCE_PATH}.")
    if len(reasons) != 1:
        raise GuardError(f"The 'no-update' decision requires one '{REASON_LABEL}:' declaration.")
    reason = reasons[0]
    normalized_reason = " ".join(reason.lower().split())
    if (
        not reason
        or normalized_reason in _PLACEHOLDERS
        or not any(char.isalpha() for char in reason)
    ):
        raise GuardError("The no-update reason must be a specific, non-placeholder explanation.")
    return f"Snapshot provenance evaluated with no update: {reason}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Base commit SHA")
    parser.add_argument("--head", required=True, help="Head commit SHA")
    parser.add_argument(
        "--require-decision",
        action="store_true",
        help="Require the PR provenance declaration in PR_BODY",
    )
    args = parser.parse_args()

    try:
        changes = changed_paths(args.base, args.head)
        inserted_lines: Sequence[bytes] = ()
        if PROVENANCE_PATH in changes:
            inserted_lines = validate_append_only(
                git_blob(args.base, PROVENANCE_PATH),
                git_blob(args.head, PROVENANCE_PATH),
            )
        if args.require_decision:
            message = validate_provenance(
                changes,
                os.getenv("PR_BODY", ""),
                inserted_lines,
            )
        elif PROVENANCE_PATH in changes:
            message = f"Append-only snapshot provenance validated in {PROVENANCE_PATH}."
        else:
            message = "No snapshot provenance content changes detected."
    except (GuardError, subprocess.CalledProcessError) as exc:
        print(f"Snapshot provenance guard failed: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
