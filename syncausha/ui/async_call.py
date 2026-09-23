"""Exécute un appel bloquant (réseau Ausha) hors du thread UI et rappelle dans le thread UI."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

_pending: set[_Task] = set()


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.fn = fn
        self.signals = _Signals()  # créé dans le thread UI → slots appelés dans le thread UI

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:
            self.signals.failed.emit(exc)
            return
        self.signals.done.emit(result)


def run_async(fn: Callable[[], Any], on_done: Callable[[Any], None], on_failed: Callable[[Exception], None]) -> None:
    task = _Task(fn)
    _pending.add(task)
    task.signals.done.connect(on_done)
    task.signals.failed.connect(on_failed)
    task.signals.done.connect(lambda _result: _pending.discard(task))
    task.signals.failed.connect(lambda _error: _pending.discard(task))
    QThreadPool.globalInstance().start(task)
