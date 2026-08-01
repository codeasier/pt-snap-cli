import os.path
from pathlib import Path

from ...representation import load_snapshot_representation, replay_snapshot
from ...util import get_logger
from .hooker import SliceDumpHooker

dump_logger = get_logger("DUMP")


def run_slice_dump(
    snapshot_file: str,
    device: int = 0,
    slices: int = 4,
    max_entries: int = 15000,
    dump_dir: str = "",
    dump_type: str = "pkl",
):
    resolved_dump_dir = dump_dir or os.path.dirname(snapshot_file)
    dump_logger.info(f"Start to dump snapshot slice, reading pickle file '{snapshot_file}'.")
    df = load_snapshot_representation(Path(snapshot_file), "pickle")
    if "segments" not in df or "device_traces" not in df or not df["device_traces"]:
        dump_logger.warning(
            "Snapshot files with no event records cannot be replayed or split. You may have disabled "
            "history event recoding during collection."
        )
        return
    if device < 0 or len(df["device_traces"]) <= device or not df["device_traces"][device]:
        dump_logger.warning(
            f"The snapshot file did not record any event data for the specified device {device}."
        )
        return
    dump_logger.info(
        f"Start loading snapshot with {len(df['segments'])} segments, "
        f"{len(df['device_traces'][device])} events"
    )
    dump_logger.info("Successfully loaded snapshot, starting to replay and dump.")
    slice_dump_hooker = SliceDumpHooker(
        dump_dir=resolved_dump_dir,
        num_of_slices=slices,
        max_entries=max_entries,
        dump_type=dump_type,
    )
    _, _ = replay_snapshot(df, device, hooker=slice_dump_hooker)
    dump_logger.info("Successfully replay and dump snapshot.")
