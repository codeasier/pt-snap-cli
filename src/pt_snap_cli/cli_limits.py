"""Shared query/report options; resolution and validation stay in core."""

from typing import Annotated

import typer

MaxWorkRows = Annotated[
    int | None,
    typer.Option(
        "--max-work-rows",
        rich_help_panel="Dataset limits",
        help="Dataset cumulative fetched/output rows, positive integer (env: PT_SNAP_MAX_WORK_ROWS; default: 100000)",
    ),
]
MaxWorkBytes = Annotated[
    int | None,
    typer.Option(
        "--max-work-bytes",
        rich_help_panel="Dataset limits",
        help="Dataset cumulative serialized work bytes, positive integer (env: PT_SNAP_MAX_WORK_BYTES; default: 67108864); not RSS",
    ),
]
MaxScratchDBBytes = Annotated[
    int | None,
    typer.Option(
        "--max-scratch-db-bytes",
        rich_help_panel="Dataset limits",
        help="Dataset derived DB page bytes: 0 disables, otherwise 4096..4294967296 (env: PT_SNAP_MAX_SCRATCH_DB_BYTES; default: 536870912)",
    ),
]
