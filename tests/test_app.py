import ctypes
import logging
import os
import sqlite3
import subprocess
import sys
import uuid

import pytest

from syncausha import app as app_module
from syncausha.ui import single_instance
from syncausha.ui.single_instance import SingleInstance


def test_forget_token_removes_the_token_without_starting_the_app(monkeypatch):
    removed = []
    monkeypatch.setattr(app_module, "set_token", removed.append)
    monkeypatch.setattr(app_module, "QApplication", lambda *args: pytest.fail("aucune interface attendue"))
    assert app_module.main(["SyncAusha.exe", "--forget-token"]) == 0
    assert removed == [""]


@pytest.fixture
def user(qapp, tmp_path, monkeypatch):
    # Nom de serveur propre au test : ne ferme jamais une vraie instance de SyncAusha.
    name = f"test-{uuid.uuid4().hex}"
    monkeypatch.setattr(single_instance.getpass, "getuser", lambda: name)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(app_module, "QApplication", lambda *args: pytest.fail("aucune interface attendue"))
    return name


def test_quit_closes_the_running_instance(user, tmp_path, wait_until):
    running = SingleInstance(tmp_path / "syncausha.lock")
    quits = []
    running.quit_requested.connect(lambda: quits.append(True))
    assert running.try_acquire()
    # Comme l'installateur : un autre processus lance « SyncAusha.exe --quit ».
    code = "import sys; from syncausha.app import main; sys.exit(main(['SyncAusha.exe', '--quit']))"
    quitter = subprocess.Popen([sys.executable, "-c", code], env={**os.environ, "LOGNAME": user})
    assert wait_until(lambda: quits and quitter.poll() is not None, timeout=15)
    assert quitter.returncode == 0
    running.close()


def test_quit_without_running_instance(user):
    assert app_module.main(["SyncAusha.exe", "--quit"]) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="mutex Windows")
def test_running_mutex_is_visible_to_the_installer():
    name = f"SyncAushaTest-{uuid.uuid4().hex}"
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.OpenMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = app_module._create_mutex(name)
    assert handle
    opened = kernel32.OpenMutexW(0x00100000, False, name)  # SYNCHRONIZE, comme CheckForMutexes
    assert opened
    kernel32.CloseHandle(opened)
    kernel32.CloseHandle(handle)


class FakeApplication:
    """QApplication de remplacement : le vrai est déjà créé pour la session de tests."""

    def __init__(self, argv):
        pass

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def test_inaccessible_journal_stops_the_start_with_a_clear_log_line(user, tmp_path, monkeypatch, caplog):
    def read_only(path):
        raise sqlite3.OperationalError("attempt to write a readonly database")

    monkeypatch.setattr(sys, "excepthook", sys.excepthook)  # remplacé par main
    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    for name in ("setup_logging", "apply_style", "watch_color_scheme", "_create_mutex"):
        monkeypatch.setattr(app_module, name, lambda *args: None)
    monkeypatch.setattr(app_module, "open_journal", read_only)
    monkeypatch.setattr(app_module, "AppController", lambda *args: pytest.fail("démarrage sans journal"))
    with caplog.at_level(logging.CRITICAL, logger="syncausha.app"):
        assert app_module.main(["SyncAusha.exe", "--minimized"]) == 1
    [record] = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert "journal.db" in record.getMessage() and "attempt to write a readonly database" in record.getMessage()
