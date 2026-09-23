import os
import time
from pathlib import Path

import pytest

from syncausha import scanner
from syncausha.scanner import scan_ready_files


def touch(path, age_seconds=120, content=b"audio"):
    path.write_bytes(content)
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def test_returns_old_audio_files_sorted(tmp_path):
    touch(tmp_path / "b.mp3")
    touch(tmp_path / "a.M4A")
    result = scan_ready_files(tmp_path)
    assert [f.path.name for f in result] == ["a.M4A", "b.mp3"]
    assert result[0].size == 5


def test_ignores_other_extensions(tmp_path):
    touch(tmp_path / "notes.txt")
    touch(tmp_path / "cover.png")
    assert scan_ready_files(tmp_path) == []


def test_ignores_recent_files(tmp_path):
    touch(tmp_path / "new.mp3", age_seconds=5)
    assert scan_ready_files(tmp_path) == []
    assert len(scan_ready_files(tmp_path, min_age_seconds=0)) == 1


def test_ignores_subfolders(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    touch(sub / "x.mp3")
    assert scan_ready_files(tmp_path) == []


def test_ignores_locked_files(tmp_path, monkeypatch):
    touch(tmp_path / "locked.mp3")
    monkeypatch.setattr(scanner, "_can_open", lambda path: False)
    assert scan_ready_files(tmp_path) == []


def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_ready_files(tmp_path / "absent")


def test_ignores_empty_files(tmp_path):
    touch(tmp_path / "empty.mp3", content=b"")
    assert scan_ready_files(tmp_path) == []


def test_ignores_hidden_and_temp_names(tmp_path):
    touch(tmp_path / "._x.mp3")
    touch(tmp_path / "~$x.mp3")
    assert scan_ready_files(tmp_path) == []


def test_future_mtime_is_ready(tmp_path):
    touch(tmp_path / "future.mp3", age_seconds=-3600)
    result = scan_ready_files(tmp_path)
    assert [f.path.name for f in result] == ["future.mp3"]


def test_skips_file_that_vanishes_before_stat(tmp_path, monkeypatch):
    touch(tmp_path / "a.mp3")
    gone = touch(tmp_path / "gone.mp3")

    real_stat = Path.stat

    def flaky_stat(self, *args, **kwargs):
        if self == gone:
            raise FileNotFoundError()
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)
    result = scan_ready_files(tmp_path)
    assert [f.path.name for f in result] == ["a.mp3"]
