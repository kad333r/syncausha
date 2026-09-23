from syncausha import autostart
from syncausha.config import Config, Rule, save_config
from syncausha.journal import Journal, Status
from syncausha.ui import controller as controller_module
from syncausha.ui.controller import AppController
from syncausha.ui.main_window import ACTIVITY, MainWindow
from syncausha.ui.settings_page import SettingsPage


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
