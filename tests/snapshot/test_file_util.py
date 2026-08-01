import pickle
from pathlib import Path

import pytest

from pt_snap_cli.snapshot.util.file_util import (
    check_dir_valid,
    check_file_valid,
    load_pickle_to_dict,
    save_dict_to_pickle,
)


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
