"""Opt-in text summaries; row selection and attribution are left intact."""

from __future__ import annotations

import hashlib


def summarize_stacks(rows: list[dict[str, object]], budget: int, layout: str | None) -> None:
    """Summarize each stack in place using UTF-8 bytes, not model tokens.

    SQL supplies the attribution kind, v2 ID and a representative event before
    display text is shortened. IDs are scoped to the same database/device.
    v1 groups by full text; v2 must never be identified by a text digest.
    """
    for row in rows:
        text = row.get("callstack")
        kind = row["stack_kind"]
        if kind == "captured":
            if layout == "v2":
                row["stack_id"] = f"v2:id:{row['stack_id']}"
            else:
                assert isinstance(text, str)
                row["stack_id"] = "v1:sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        else:
            row["stack_id"] = f"category:{kind}"
        encoded = text.encode("utf-8") if isinstance(text, str) else b""
        row["stack_bytes"] = budget
        row["stack_original_bytes"] = len(encoded)
        row["stack_truncated"] = len(encoded) > budget
        if len(encoded) > budget:
            # Dropping an incomplete final code point preserves valid Unicode.
            # No ellipsis is appended: the flag, not an ambiguous label, marks loss.
            row["callstack"] = encoded[:budget].decode("utf-8", errors="ignore")
