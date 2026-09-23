import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    # Un vrai QApplication pour toute la session : Qt refuse d'en créer un après un QCoreApplication.
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def wait_until(qapp):
    """Fait tourner la boucle d'événements jusqu'à ce que condition() soit vraie (2 s au plus)."""
    from PySide6.QtCore import QCoreApplication, QEventLoop

    def wait(condition, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        return bool(condition())

    return wait
