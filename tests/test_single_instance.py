import os
import subprocess
import sys
import uuid

import pytest
from PySide6.QtCore import QLockFile

from syncausha.ui import single_instance
from syncausha.ui.single_instance import SingleInstance


@pytest.fixture
def user(qapp, monkeypatch):
    # Nom de serveur propre au test : ne réveille jamais une vraie instance de SyncAusha.
    name = f"test-{uuid.uuid4().hex}"
    monkeypatch.setattr(single_instance.getpass, "getuser", lambda: name)
    return name


@pytest.fixture
def lock_path(user, tmp_path):
    return tmp_path / "syncausha.lock"


def other_process(user, code):
    """Exécute code dans un autre processus, comme un second lancement (même nom de serveur).

    Le tube local n'a pas de tampon : l'envoi n'aboutit que si l'instance en cours tourne
    sa boucle d'événements, donc depuis un autre processus que le sien.
    """
    prelude = "from pathlib import Path; from syncausha.ui.single_instance import SingleInstance; "
    return subprocess.Popen(
        [sys.executable, "-c", prelude + code], env={**os.environ, "LOGNAME": user}, stdout=subprocess.PIPE, text=True
    )


def test_second_instance_is_refused_and_wakes_the_first(user, lock_path, wait_until):
    first = SingleInstance(lock_path)
    woken = []
    first.show_requested.connect(lambda: woken.append(True))
    assert first.try_acquire()
    second = other_process(user, f"print(SingleInstance(Path(r'{lock_path}')).try_acquire())")
    assert wait_until(lambda: woken and second.poll() is not None, timeout=15)
    assert second.stdout.read().strip() == "False"
    assert not first._server.hasPendingConnections()
    first.close()
    assert not SingleInstance(lock_path).try_acquire()  # le verrou reste pris jusqu'à la fin du processus


def test_quit_request_reaches_the_running_instance(user, lock_path, wait_until):
    first = SingleInstance(lock_path)
    shown, quits = [], []
    first.show_requested.connect(lambda: shown.append(True))
    first.quit_requested.connect(lambda: quits.append(True))
    assert first.try_acquire()
    other = other_process(user, "print(SingleInstance(Path('autre.lock')).request('quit'))")
    assert wait_until(lambda: quits and other.poll() is not None, timeout=15)
    assert other.stdout.read().strip() == "True"
    assert shown == []
    first.close()


def test_request_without_running_instance(lock_path):
    assert SingleInstance(lock_path).request("quit") is False


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
