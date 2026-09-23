import gc
import sys
import threading

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QThread, QThreadPool
from PySide6.QtWidgets import QWidget

from syncausha.ui import async_call
from syncausha.ui.async_call import run_async


def live_signals() -> int:
    gc.collect()
    return sum(isinstance(obj, async_call._Signals) for obj in gc.get_objects())


def test_callbacks_run_in_the_ui_thread_and_nothing_is_left_behind(qapp, wait_until):
    before = live_signals()
    results = []

    def record(kind):
        return lambda value: results.append((kind, repr(value), QThread.currentThread() is qapp.thread()))

    run_async(lambda: 42, record("done"), record("failed"))
    run_async(lambda: 1 / 0, record("done"), record("failed"))
    assert wait_until(lambda: len(results) == 2)
    assert sorted(results) == [("done", "42", True), ("failed", "ZeroDivisionError('division by zero')", True)]
    QThreadPool.globalInstance().waitForDone(2000)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert live_signals() == before


def test_callbacks_of_a_destroyed_widget_are_skipped(qapp, monkeypatch):
    """Page détruite avant la réponse (fenêtre reconstruite au changement de langue) : rien n'est appelé."""
    errors, calls = [], []
    monkeypatch.setattr(sys, "excepthook", lambda *exc_info: errors.append(exc_info[1]))

    class Page(QWidget):
        def show_result(self, value):
            calls.append(value)
            self.setWindowTitle(repr(value))

    before = live_signals()
    page = Page()
    gate = threading.Event()
    run_async(lambda: gate.wait(2) and 42, page.show_result, page.show_result)
    page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(page)
    gate.set()
    QThreadPool.globalInstance().waitForDone(2000)
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert (calls, errors) == ([], [])
    assert live_signals() == before
