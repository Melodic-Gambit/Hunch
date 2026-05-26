import os
import time
from unittest.mock import patch
import pytest
from setup_dirs import _cleanup_stale_tmp, _TMP_MAX_AGE_SECONDS


def _make_stale(path):
    old_time = time.time() - _TMP_MAX_AGE_SECONDS - 5
    os.utime(str(path), (old_time, old_time))


def test_cleanup_removes_stale_tmp(tmp_path):
    tmp_file = tmp_path / "stale.tmp"
    tmp_file.write_text("data")
    _make_stale(tmp_file)
    _cleanup_stale_tmp(str(tmp_path))
    assert not tmp_file.exists()


def test_cleanup_nonexistent_dir_no_error(tmp_path):
    missing = str(tmp_path / "does_not_exist")
    _cleanup_stale_tmp(missing)  # не должно бросать исключение


def test_cleanup_oserror_on_remove_no_propagation(tmp_path):
    tmp_file = tmp_path / "locked.tmp"
    tmp_file.write_text("data")
    _make_stale(tmp_file)
    with patch("setup_dirs.os.remove", side_effect=OSError("permission denied")):
        _cleanup_stale_tmp(str(tmp_path))  # не должно бросать исключение
