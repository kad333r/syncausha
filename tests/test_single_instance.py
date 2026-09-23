import os
import subprocess
import sys
import uuid

import pytest
from PySide6.QtCore import QLockFile

from syncausha.ui import single_instance
from syncausha.ui.single_instance import SingleInstance


@pytest.fixture
def lock_path(qapp, tmp_path, monkeypatch):
    # Nom de serveur propre au test : ne réveille jamais une vraie instance de SyncAusha.
    user = f"test-{uuid.uuid4().hex}"
    monkeypatch.setattr(single_instance.getpass, "getuser", lambda: user)
    return tmp_path / "syncausha.lock"


def test_second_instance_is_refused_and_wakes_the_first(lock_path, wait_until):
    first = SingleInstance(lock_path)
    woken = []
    first.show_requested.connect(lambda: woken.append(True))
    assert first.try_acquire()
    assert not SingleInstance(lock_path).try_acquire()
    assert not SingleInstance(lock_path).try_acquire()
    assert wait_until(lambda: woken)
    assert not first._server.hasPendingConnections()
    first.close()
    assert not SingleInstance(lock_path).try_acquire()  # le verrou reste pris jusqu'à la fin du processus


def test_lock_left_by_a_killed_process_is_taken_over(lock_path):
    script = "import os, sys; from PySide6.QtCore import QLockFile; lock = QLockFile(sys.argv[1]); lock.tryLock(0); os._exit(0)"
    subprocess.run([sys.executable, "-c", script, str(lock_path)], check=True)
    assert lock_path.exists()
    assert SingleInstance(lock_path).try_acquire()


def test_lock_left_under_our_own_process_id_is_taken_over(lock_path, tmp_path):
    # Après un arrêt brutal, le numéro de processus du verrou peut avoir été réattribué au nôtre.
    holder = QLockFile(str(tmp_path / "autre.lock"))
    assert holder.tryLock(0)
    content = (tmp_path / "autre.lock").read_bytes()
    holder.unlock()
    assert content.startswith(str(os.getpid()).encode())
    lock_path.write_bytes(content)
    assert SingleInstance(lock_path).try_acquire()
