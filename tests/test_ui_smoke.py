from syncausha.config import Config, Rule, save_config
from syncausha.journal import Journal, Status
from syncausha.ui import controller as controller_module
from syncausha.ui.controller import AppController
from syncausha.ui.main_window import ACTIVITY, MainWindow


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
