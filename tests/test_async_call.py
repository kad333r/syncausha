import gc

from PySide6.QtCore import QCoreApplication, QEvent, QThread, QThreadPool

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
