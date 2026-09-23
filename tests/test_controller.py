import threading
from dataclasses import replace

import pytest

import syncausha.ui.controller as controller_module
from syncausha.ausha_client import Playlist, RejectedError, Show
from syncausha.config import Config
from syncausha.journal import Journal
from syncausha.sync_engine import CycleResult
from syncausha.ui.controller import AppController


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
        assert controller.shutdown() is True
        assert controller.engine.cancel_event.is_set()
        assert controller._thread.isFinished()
        assert not controller._timer.isActive()
    finally:
        journal.close()


@pytest.fixture
def controller(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "set_token", lambda token: None)
    journal = Journal(tmp_path / "journal.db")
    controller = AppController(tmp_path / "config.json", journal)
    yield controller
    controller.shutdown()
    journal.close()


@pytest.fixture
def notes(controller):
    titles = []
    controller.notification.connect(lambda title, body: titles.append(title))
    return titles


def test_timer_tick_is_dropped_while_a_cycle_runs(controller):
    controller.busy = True
    controller._on_timer()
    assert not controller._rerun_requested
    controller.sync_now()  # une demande explicite, elle, est relancée à la fin du cycle
    assert controller._rerun_requested


def test_state_stays_paused_when_a_cycle_ends_after_pausing(controller):
    controller.busy = True
    controller.update_config(replace(controller.config, paused=True))
    controller._on_cycle_finished(CycleResult("ok"))
    assert controller.state == "paused"


def test_saving_settings_keeps_the_next_cycle_unless_the_interval_changes(controller, monkeypatch):
    restarts = []
    monkeypatch.setattr(controller, "_restart_timer", lambda: restarts.append(True))
    controller.update_config(replace(controller.config, dry_run=True))
    assert restarts == []
    controller.update_config(replace(controller.config, interval_minutes=30))
    assert restarts == [True]


def test_new_token_notifies_again_if_still_invalid(controller, notes):
    controller._on_cycle_finished(CycleResult("auth_error", "Unauthenticated"))
    controller._on_cycle_finished(CycleResult("auth_error", "Unauthenticated"))
    assert notes == ["Jeton Ausha invalide"]
    controller.update_token("nouveau-jeton")
    controller._on_cycle_finished(CycleResult("auth_error", "Unauthenticated"))
    assert notes == ["Jeton Ausha invalide"] * 2


def test_new_folder_notifies_again_if_still_missing(controller, notes):
    missing = CycleResult("folder_missing", "Dossier introuvable : D:\Podcasts")
    controller._on_cycle_finished(missing)
    controller.update_config(replace(controller.config, interval_minutes=20))
    controller._on_cycle_finished(missing)
    assert notes == ["Dossier introuvable"]
    controller.update_config(replace(controller.config, watch_folder="E:\Podcasts"))
    controller._on_cycle_finished(missing)
    assert notes == ["Dossier introuvable"] * 2


def test_catalog_keeps_a_show_whose_playlists_are_refused(controller, monkeypatch, wait_until):
    class FakeClient:
        def __init__(self, token, base_url):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            pass

        def list_shows(self):
            return [Show(1, "Mars Attack"), Show(2, "Silicon Talk")]

        def list_playlists(self, show_id):
            if show_id == 2:
                raise RejectedError("Forbidden (HTTP 403)")
            return [Playlist(7, "Saison 3")]

    monkeypatch.setattr(controller_module, "AushaClient", FakeClient)
    results = []
    controller.fetch_catalog(results.append, results.append, token="jeton")
    assert wait_until(lambda: results)
    assert results == [{Show(1, "Mars Attack"): [Playlist(7, "Saison 3")], Show(2, "Silicon Talk"): []}]
