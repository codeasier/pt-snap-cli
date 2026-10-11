"""Run one of exactly two exhaustive, deterministic Windows non-slow shards."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest


def validate_partition(nodeids, partitions):
    """Fail before execution if any collected test is missing, repeated, or unknown."""
    if len(nodeids) != len(set(nodeids)):
        raise pytest.UsageError("platform collection contains duplicate node IDs")
    if len(partitions) != 2 or any(not part for part in partitions):
        raise pytest.UsageError("platform partition requires exactly two nonempty shards")
    if Counter(node for part in partitions for node in part) != Counter(nodeids):
        raise pytest.UsageError("platform shards must cover every selected test exactly once")


def partition_nodeids(nodeids):
    # Alternating individual cases, rather than whole directories/files, spreads
    # expensive parameterized SQLite tests across both fixed-size CI jobs.
    ordered = sorted(nodeids)
    partitions = [ordered[0::2], ordered[1::2]]
    validate_partition(nodeids, partitions)
    return partitions


class PlatformPartition:
    def __init__(self, shard, manifest=Path("platform-partition.json")):
        if shard not in (0, 1):
            raise pytest.UsageError("platform shard must be 0 or 1")
        self.shard = shard
        self.manifest = manifest

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_collection_modifyitems(self, config, items):
        # Run after ordinary selection hooks, particularly pytest's -m filter.
        # Both jobs collect the entire suite before assigning any non-slow case.
        yield
        nodeids = [item.nodeid for item in items]
        partitions = partition_nodeids(nodeids)
        # Keep validation independent of construction so future partition changes
        # cannot silently drop/duplicate tests before modifying pytest's items.
        validate_partition(nodeids, partitions)
        selected = set(partitions[self.shard])
        omitted = [item for item in items if item.nodeid not in selected]
        items[:] = [item for item in items if item.nodeid in selected]
        config.hook.pytest_deselected(items=omitted)
        ordered = sorted(nodeids)
        self.manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "selection": "not slow",
                    "shard": self.shard,
                    "shard_count": 2,
                    "collection_sha256": hashlib.sha256(
                        "\n".join(ordered).encode("utf-8")
                    ).hexdigest(),
                    "full_collection": ordered,
                    "partitions": partitions,
                    "selected": partitions[self.shard],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", required=True, type=int, choices=(0, 1))
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args(argv)
    pytest_args = [
        "-m",
        "not slow",
        "--junitxml=platform-tests.xml",
        "-o",
        "junit_family=legacy",
    ]
    if args.collect_only:
        pytest_args.append("--collect-only")
    return pytest.main(pytest_args, plugins=[PlatformPartition(args.shard)])


if __name__ == "__main__":
    raise SystemExit(main())
