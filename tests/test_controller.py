import threading
from dataclasses import replace

import pytest

import syncausha.ui.controller as controller_module
from syncausha.ausha_client import Playlist, RejectedError, Show
from syncausha.config import Config, load_config, save_config
from syncausha.i18n import msg
from syncausha.journal import Journal, Status
from syncausha.sync_engine import CycleResult, Event
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


def test_shutdown_cancels_the_engine_and_stops_the_thread(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: None)
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
    monkeypatch.setattr(controller_module, "get_token", lambda: "jeton")
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


@pytest.fixture
def messages(controller):
    received = []
    controller.notification.connect(lambda title, body: received.append((title, body)))
    return received


@pytest.fixture
def syncs(controller, monkeypatch):
    """Remplace le lancement d'un cycle (thread de synchro) par un simple relevé."""
    calls = []
    monkeypatch.setattr(controller, "sync_now", lambda: calls.append(True))
    return calls


def test_timer_tick_is_dropped_while_a_cycle_runs(controller):
    controller.busy = True
    controller._on_timer()
    assert not controller._rerun_requested
    controller.sync_now()  # une demande explicite, elle, est relancée à la fin du cycle
    assert controller._rerun_requested


def test_timer_tick_is_dropped_while_paused(controller, syncs):
    controller.update_config(replace(controller.config, paused=True))
    controller._on_timer()
    assert syncs == []
    controller.update_config(replace(controller.config, paused=False))
    controller._on_timer()
    assert syncs == [True]


@pytest.mark.parametrize(
    "token,folder,paused,attention,state",
    [
        (None, "D:/Podcasts", False, False, "not_configured"),
        ("jeton", "", False, False, "not_configured"),
        ("jeton", "D:/Podcasts", True, True, "attention"),
        ("jeton", "D:/Podcasts", True, False, "paused"),
        ("jeton", "D:/Podcasts", False, False, "ok"),
    ],
)
def test_initial_state(qapp, tmp_path, monkeypatch, token, folder, paused, attention, state):
    monkeypatch.setattr(controller_module, "get_token", lambda: token)
    save_config(Config(watch_folder=folder, baseline_folder=folder, paused=paused), tmp_path / "config.json")
    journal = Journal(tmp_path / "journal.db")
    if attention:
        journal.ensure("h1", "interview_brut.mp3", 1)
        journal.update("h1", status=Status.SANS_REGLE)
    controller = AppController(tmp_path / "config.json", journal)
    try:
        assert controller.state == state
    finally:
        controller.shutdown()
        journal.close()


def test_baseline_saves_the_folder_notifies_and_runs_the_real_cycle(controller, messages, syncs, french):
    controller.update_config(replace(controller.config, watch_folder="D:/Podcasts"))
    controller._on_cycle_finished(
        CycleResult("baseline", "3 fichier(s) déjà présent(s) ignoré(s)", count=3, folder="D:/Podcasts")
    )
    assert controller.config.baseline_folder == "D:/Podcasts"
    assert load_config(controller.config_path).baseline_folder == "D:/Podcasts"
    assert messages == [(
        "Dossier pris en compte",
        "3 fichier(s) déjà présent(s) ignoré(s). Seuls les nouveaux fichiers seront publiés.",
    )]
    assert syncs == [True]


def test_baseline_of_an_empty_folder_is_silent(controller, messages, syncs):
    controller.update_config(replace(controller.config, watch_folder="D:/Podcasts"))
    controller._on_cycle_finished(CycleResult("baseline", "0 fichier(s)", count=0, folder="D:/Podcasts"))
    assert controller.config.baseline_folder == "D:/Podcasts"
    assert messages == []
    assert syncs == [True]


def test_baseline_of_a_folder_changed_meanwhile_is_not_kept(controller, messages, syncs):
    controller.update_config(replace(controller.config, watch_folder="E:/Nouveau"))
    controller._on_cycle_finished(CycleResult("baseline", "2 fichier(s)", count=2, folder="D:/Podcasts"))
    assert controller.config.baseline_folder == ""
    assert messages == []
    assert syncs == [True]  # l'état des lieux du nouveau dossier suit


def test_publish_anyway(controller, syncs):
    controller.journal.ensure("h1", "MARS ATTACK 12.mp3", 1)
    controller.journal.update("h1", status=Status.IGNORE)
    controller.publish_anyway("h1")
    assert controller.journal.get("h1").status is Status.EN_ATTENTE
    assert syncs == [True]


def test_partial_publication_is_notified(controller, messages, french):
    controller._on_engine_event(Event("partial", "MARS ATTACK 13", "Épisode publié, mais …"))
    assert messages == [("Publié avec un problème", "MARS ATTACK 13 : Épisode publié, mais …")]


def test_notifications_are_translated_when_emitted(controller, messages):
    controller._on_engine_event(Event("failed", "MARS ATTACK 13", msg("err_network", detail="timed out")))
    controller._on_cycle_finished(CycleResult("folder_missing", msg("cycle_folder_missing", folder=r"D:\Podcasts")))
    assert messages == [
        ("Upload failed", "MARS ATTACK 13: Can't connect to Ausha: timed out"),
        ("Folder not found", r"Folder not found: D:\Podcasts"),
    ]


def test_idle_state_message_is_a_stored_message(controller):
    assert controller.state == "not_configured"  # jeton présent, aucun dossier
    assert controller.message == msg("cycle_choose_folder")


def test_dry_run_lines_are_kept_as_stored_messages(controller):
    controller.update_config(replace(controller.config, dry_run=True))
    controller._on_engine_event(Event("dry_run", "MARS ATTACK 13", msg("dry_would_publish", show="Mars Attack")))
    controller._on_cycle_finished(CycleResult("ok"))
    assert controller.dry_run_lines == [
        msg("dry_line", title="MARS ATTACK 13", detail=msg("dry_would_publish", show="Mars Attack"))
    ]


def test_files_without_rule_are_notified_once_per_cycle(controller, messages, french):
    controller._on_engine_event(Event("no_rule", "interview_brut"))
    controller._on_cycle_finished(CycleResult("attention"))
    for title in ("a", "b", "c"):
        controller._on_engine_event(Event("no_rule", title))
    assert len(messages) == 1
    controller._on_cycle_finished(CycleResult("attention"))
    assert messages == [
        ("Aucune règle", "interview_brut n'a pas été envoyé : aucune règle ne correspond."),
        ("Fichiers sans règle", "3 fichiers n'ont pas été envoyés : aucune règle ne correspond."),
    ]


def test_progress_is_forwarded_by_steps_of_five_percent(controller):
    forwarded = []
    controller.progress_changed.connect(lambda title, percent: forwarded.append(percent))
    for percent in range(0, 101):
        controller._on_engine_event(Event("progress", "MARS ATTACK 13", percent=percent))
    assert forwarded == list(range(0, 100, 5)) + [100]
    assert controller.progress["MARS ATTACK 13"] == 100


def test_settings_that_cannot_be_saved_are_reported_and_not_applied(controller, messages, monkeypatch, french):
    def full_disk(config, path):
        raise OSError(28, "Espace disque insuffisant")

    monkeypatch.setattr(controller_module, "save_config", full_disk)
    assert controller.update_config(replace(controller.config, interval_minutes=30)) is False
    assert controller.config.interval_minutes == 15
    assert controller.engine.config.interval_minutes == 15
    assert messages == [("Réglages non enregistrés", "[Errno 28] Espace disque insuffisant")]


def test_resuming_leaves_the_paused_state(controller, syncs):
    states = []
    controller.state_changed.connect(lambda state, message: states.append(state))
    controller.set_paused(True)
    controller.set_paused(False)
    assert states == ["paused", "not_configured"]  # sans dossier choisi
    assert syncs == [True]


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


def test_new_token_notifies_again_if_still_invalid(controller, notes, french):
    controller._on_cycle_finished(CycleResult("auth_error", "Unauthenticated"))
    controller._on_cycle_finished(CycleResult("auth_error", "Unauthenticated"))
    assert notes == ["Jeton Ausha invalide"]
    controller.update_token("nouveau-jeton")
    controller._on_cycle_finished(CycleResult("auth_error", "Unauthenticated"))
    assert notes == ["Jeton Ausha invalide"] * 2


def test_new_folder_notifies_again_if_still_missing(controller, notes, french):
    missing = CycleResult("folder_missing", r"Dossier introuvable : D:\Podcasts")
    controller._on_cycle_finished(missing)
    controller.update_config(replace(controller.config, interval_minutes=20))
    controller._on_cycle_finished(missing)
    assert notes == ["Dossier introuvable"]
    controller.update_config(replace(controller.config, watch_folder=r"E:\Podcasts"))
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
