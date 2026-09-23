import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

from syncausha import autostart
from syncausha.ausha_client import Show
from syncausha.config import Config, Rule, save_config
from syncausha.journal import Journal, Status
from syncausha.ui import controller as controller_module
from syncausha.ui import rules_page as rules_page_module
from syncausha.ui.activity_page import ActivityPage
from syncausha.ui.controller import AppController
from syncausha.ui.main_window import ACTIVITY, MainWindow
from syncausha.ui.rules_page import RulesPage
from syncausha.ui.settings_page import SettingsPage
from syncausha.ui.tray import Tray


def test_main_window_builds_and_navigates(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: None)
    config_path = tmp_path / "config.json"
    save_config(
        Config(watch_folder=str(tmp_path), rules=[Rule(keyword="MARS ATTACK", show_id=1, show_name="Mars Attack")]),
        config_path,
    )
    journal = Journal(tmp_path / "journal.db")
    journal.ensure("h1", "interview_brut.mp3", 1)
    journal.update("h1", status=Status.SANS_REGLE, last_error="Aucune règle ne correspond")
    journal.ensure("h2", "MARS ATTACK 12.mp3", 1)
    journal.update("h2", status=Status.PUBLIE, show_name="Mars Attack")
    controller = AppController(config_path, journal)
    window = MainWindow(controller)
    try:
        assert window.needs_setup()
        assert window.stack.currentWidget() is window.settings
        window.open_new_rule("interview_brut")
        assert window.stack.currentWidget() is window.rules
        assert window.rules.keyword.text() == "interview_brut"
        assert window.rules.list.count() == 1
        window.go_to(ACTIVITY)
        window.activity.refresh()
        assert window.stack.currentWidget() is window.activity
    finally:
        controller.shutdown()
        journal.close()


def test_settings_are_saved_even_if_autostart_cannot_be_changed(qapp, tmp_path, monkeypatch):
    def denied(enabled):
        raise PermissionError(13, "Accès refusé")

    monkeypatch.setattr(controller_module, "get_token", lambda: None)
    monkeypatch.setattr(autostart, "is_enabled", lambda: False)
    monkeypatch.setattr(autostart, "set_enabled", denied)
    journal = Journal(tmp_path / "journal.db")
    controller = AppController(tmp_path / "config.json", journal)
    page = SettingsPage(controller)
    try:
        page.interval.setValue(30)
        page.paused.setChecked(True)  # pas de synchro lancée par l'enregistrement
        page._save()
        assert controller.config.interval_minutes == 30
        assert page.saved_label.text() == "Démarrage automatique non modifié : [Errno 13] Accès refusé"
    finally:
        controller.shutdown()
        journal.close()


@pytest.fixture
def controller(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: "jeton")
    monkeypatch.setattr(autostart, "is_enabled", lambda: False)
    journal = Journal(tmp_path / "journal.db")
    controller = AppController(tmp_path / "config.json", journal)
    yield controller
    controller.shutdown()
    journal.close()


@pytest.fixture
def syncs(controller, monkeypatch):
    calls = []
    monkeypatch.setattr(controller, "sync_now", lambda: calls.append(True))
    return calls


def texts(widget, kind):
    return [child.text() for child in widget.findChildren(kind)]


def test_activity_lists_files_ignored_when_the_folder_was_chosen(controller, syncs):
    for i in range(25):
        controller.journal.ensure(f"h{i}", f"Ancien épisode {i}.mp3", 1)
        controller.journal.update(f"h{i}", status=Status.IGNORE)
    page = ActivityPage(controller)
    assert "Ignorés — déjà présents au choix du dossier" in texts(page, QLabel)
    assert texts(page, QLabel).count("Présent avant le choix du dossier") == 20
    assert "… et 5 autres" in texts(page, QLabel)
    buttons = [b for b in page.findChildren(QPushButton) if b.text() == "Publier quand même"]
    assert len(buttons) == 20
    buttons[0].click()
    assert len(controller.journal.ignored(limit=-1)) == 24
    assert syncs == [True]


def test_activity_header_when_the_token_is_refused(controller):
    page = ActivityPage(controller)
    assert "prochain passage dans" in page.detail_label.text()
    controller.auth_blocked = True
    page.refresh()
    assert "synchro automatique suspendue (jeton invalide)" in page.detail_label.text()
    assert "prochain passage" not in page.detail_label.text()


def test_pause_checkbox_and_tray_follow_the_controller(controller, syncs):
    window = MainWindow(controller)
    tray = Tray(controller, window)
    page = window.settings
    page.interval.setValue(40)  # modification non enregistrée : conservée
    controller.set_paused(True)
    assert page.paused.isChecked()
    assert tray.pause_action.text() == "Reprendre la synchronisation"
    controller.set_paused(False)
    assert not page.paused.isChecked()
    assert tray.pause_action.text() == "Mettre en pause"
    assert page.interval.value() == 40
    page.paused.setChecked(True)  # case cochée, pas encore enregistrée
    controller.state_changed.emit("syncing", "")  # début d'un cycle : la case n'est pas touchée
    assert page.paused.isChecked()


def test_settings_page_reports_settings_that_cannot_be_saved(controller, syncs, monkeypatch):
    def denied(config, path):
        raise PermissionError(13, "Accès refusé")

    monkeypatch.setattr(controller_module, "save_config", denied)
    page = SettingsPage(controller)
    page.interval.setValue(30)
    page._save()
    assert page.saved_label.text() == "Réglages non enregistrés"
    assert controller.config.interval_minutes == 15
    assert syncs == []


def test_saving_or_deleting_a_rule_runs_a_sync(controller, syncs, monkeypatch):
    monkeypatch.setattr(rules_page_module.QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    page = RulesPage(controller)
    page.catalog = {Show(1, "Mars Attack"): []}
    page.keyword.setText("interview")
    page._fill_shows()
    page._save()
    assert [r.keyword for r in controller.config.rules] == ["interview"]
    assert syncs == [True]
    page._delete()
    assert controller.config.rules == []
    assert syncs == [True, True]
    controller.update_config(Config(paused=True))
    page.keyword.setText("interview")
    page._save()
    assert syncs == [True, True]  # en pause : rien n'est lancé
