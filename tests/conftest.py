import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    # Un vrai QApplication pour toute la session : Qt refuse d'en créer un après un QCoreApplication.
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def default_language():
    """Chaque test démarre en anglais (langue par défaut) et y revient à la fin."""
    from syncausha import i18n

    i18n.set_language(i18n.DEFAULT_LANGUAGE)
    yield
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


@pytest.fixture
def french(default_language):
    """Interface en français le temps du test (textes comparés à la lettre) ; retour à l'anglais ensuite."""
    from syncausha import i18n

    i18n.set_language("fr")


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
