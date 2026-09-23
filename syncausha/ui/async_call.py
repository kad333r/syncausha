"""Exécute un appel bloquant (réseau Ausha) hors du thread UI et rappelle dans le thread UI."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QThreadPool, Signal, Slot


class _Signals(QObject):
    """Créé dans le thread UI, qui exécute donc ses slots et les rappels.

    Possédé par l'application et non par Python : le thread de travail peut lâcher sa
    référence sans le détruire ; seul deleteLater() le détruit, dans le thread UI.
    """

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, on_done: Callable[[Any], None], on_failed: Callable[[Exception], None]) -> None:
        super().__init__(QCoreApplication.instance())
        self._on_done, self._on_failed = on_done, on_failed
        self.done.connect(self._finish_done)
        self.failed.connect(self._finish_failed)

    @Slot(object)
    def _finish_done(self, result: Any) -> None:
        self._finish(self._on_done, result)

    @Slot(object)
    def _finish_failed(self, error: Exception) -> None:
        self._finish(self._on_failed, error)

    def _finish(self, callback: Callable[[Any], None], value: Any) -> None:
        try:
            callback(value)
        finally:
            self.deleteLater()


def run_async(fn: Callable[[], Any], on_done: Callable[[Any], None], on_failed: Callable[[Exception], None]) -> None:
    signals = _Signals(on_done, on_failed)

    def run() -> None:
        try:
            result = fn()
        except Exception as exc:
            signals.failed.emit(exc)
            return
        signals.done.emit(result)

    # Qt enveloppe la fonction dans un QRunnable supprimé après exécution.
    QThreadPool.globalInstance().start(run)
