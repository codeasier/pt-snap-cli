import pickle
from pathlib import Path

import pytest

from pt_snap_cli.snapshot.util.file_util import (
    check_dir_valid,
    check_file_valid,
    load_pickle_to_dict,
    save_dict_to_pickle,
)
from tests.snapshot.helpers import FIXTURE_DIR

UNSAFE_PICKLE_PAYLOAD = {"executed": False}


def unsafe_pickle_payload() -> dict:
    UNSAFE_PICKLE_PAYLOAD["executed"] = True
    return {"pwned": True}


class UnsafeReducePayload:
    def __reduce__(self) -> tuple[object, tuple[()]]:
        return (unsafe_pickle_payload, ())


def write_unsafe_reduce_pickle(path: Path) -> Path:
    UNSAFE_PICKLE_PAYLOAD["executed"] = False
    path.write_bytes(pickle.dumps({"payload": UnsafeReducePayload()}))
    return path


def test_save_and_load_pickle_round_trip(tmp_path: Path):
    target = tmp_path / "nested" / "snapshot.pkl"
    payload = {"device_traces": [1, 2, 3]}

    save_dict_to_pickle(payload, target)

    assert target.exists()
    assert load_pickle_to_dict(target) == payload


def test_load_pickle_to_dict_rejects_non_dict_payload(tmp_path: Path):
    target = tmp_path / "list.pkl"
    with target.open("wb") as file_handle:
        pickle.dump([1, 2, 3], file_handle)

    with pytest.raises(ValueError):
        load_pickle_to_dict(target)


def test_load_pickle_to_dict_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_pickle_to_dict(tmp_path / "missing.pkl")


def test_load_pickle_to_dict_rejects_unsafe_global_without_running_payload(tmp_path: Path):
    target = write_unsafe_reduce_pickle(tmp_path / "evil.pkl")

    with pytest.raises(pickle.UnpicklingError):
        load_pickle_to_dict(target)

    assert UNSAFE_PICKLE_PAYLOAD["executed"] is False


def test_load_pickle_to_dict_rejects_corrupt_stream(tmp_path: Path):
    target = tmp_path / "corrupt.pkl"
    target.write_bytes(b"\x80\x04not a valid pickle stream")

    with pytest.raises(pickle.UnpicklingError, match="Cannot load pickle file"):
        load_pickle_to_dict(target)


@pytest.mark.parametrize(
    "fixture_name",
    (
        "snapshot_with_empty_cache.pkl",
        "snapshot_expandable.pkl",
        "snapshot_with_multi_devices.pkl",
    ),
)
def test_load_pickle_to_dict_accepts_fixture_snapshots(fixture_name: str):
    data = load_pickle_to_dict(FIXTURE_DIR / fixture_name)
    assert isinstance(data, dict)


def test_save_dict_to_pickle_rejects_non_dict(tmp_path: Path):
    with pytest.raises(TypeError):
        save_dict_to_pickle([1, 2, 3], tmp_path / "bad.pkl")


def test_check_dir_and_file_valid(tmp_path: Path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("ok", encoding="utf-8")

    assert check_dir_valid(tmp_path)
    assert check_file_valid(file_path)
    assert not check_dir_valid(file_path)
    assert not check_file_valid(tmp_path)
