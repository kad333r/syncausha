import threading

import pytest
from PySide6.QtWidgets import QApplication

import syncausha.ui.controller as controller_module
from syncausha.config import Config
from syncausha.journal import Journal
from syncausha.ui.controller import AppController


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_make_client_passes_the_cancel_event(monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: "jeton")
    cancel = threading.Event()
    client = AppController._make_client(Config(), cancel)
    try:
        assert client._cancel is cancel
    finally:
        client.close()


def test_make_client_without_token(monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: None)
    assert AppController._make_client(Config(), threading.Event()) is None


def test_shutdown_cancels_the_engine_and_stops_the_thread(qapp, tmp_path):
    journal = Journal(tmp_path / "journal.db")
    try:
        controller = AppController(tmp_path / "config.json", journal)
        controller.shutdown()
        assert controller.engine.cancel_event.is_set()
        assert controller._thread.isFinished()
        assert not controller._timer.isActive()
    finally:
        journal.close()
