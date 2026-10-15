from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QLabel, QPushButton

from syncausha import autostart, i18n
from syncausha.config import Config, KeywordRule, ShowFolder, save_config
from syncausha.i18n import msg, render, tr
from syncausha.journal import Journal, Status
from syncausha.ui import controller as controller_module
from syncausha.ui import style
from syncausha.ui import tray as tray_module
from syncausha.ui.activity_page import ActivityPage
from syncausha.ui.controller import AppController
from syncausha.ui.main_window import ACTIVITY, SETTINGS, SHOWS, MainWindow
from syncausha.ui.settings_page import SettingsPage
from syncausha.ui.tray import Tray
from syncausha.ui.widgets import Row, bidi_text


def test_main_window_builds_and_navigates(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: None)
    config_path = tmp_path / "config.json"
    show = ShowFolder(1, "Mars Attack", str(tmp_path), str(tmp_path), [KeywordRule("MARS ATTACK")])
    save_config(Config(shows=[ShowFolder(2, "Autre", r"Z:\Autre"), show]), config_path)
    journal = Journal(tmp_path / "journal.db")
    journal.ensure("h1", "interview_brut.mp3", 1, folder=str(tmp_path))
    journal.update("h1", status=Status.SANS_REGLE, last_error="Aucune règle ne correspond")
    journal.ensure("h2", "MARS ATTACK 12.mp3", 1, folder=str(tmp_path))
    journal.update("h2", status=Status.PUBLIE, show_name="Mars Attack")
    controller = AppController(config_path, journal)
    window = MainWindow(controller)
    try:
        assert window.needs_setup()
        assert window.stack.currentWidget() is window.settings  # pas de jeton
        [create_rule] = [b for b in window.activity.findChildren(QPushButton) if b.text() == tr("activity_create_rule")]
        create_rule.click()
        assert window.stack.currentWidget() is window.shows
        assert window.sidebar.currentRow() == SHOWS
        assert window.shows.show_list.count() == 2
        assert window.shows.show_list.currentRow() == 1  # l'émission du dossier du fichier
        assert window.shows.keyword.text() == "interview_brut"
        window.go_to(ACTIVITY)
        window.activity.refresh()
        assert window.stack.currentWidget() is window.activity
        window.activity.edit_show_requested.emit(0)
        assert window.stack.currentWidget() is window.shows
        assert window.shows.show_list.currentRow() == 0
    finally:
        controller.shutdown()
        journal.close()


@pytest.mark.parametrize(
    "token,shows,page",
    [(None, [], SETTINGS), ("jeton", [], SHOWS), ("jeton", [ShowFolder(1, "Sans dossier")], SHOWS),
     ("jeton", [ShowFolder(1, "Mars Attack", r"D:\Mars")], ACTIVITY)],
)
def test_main_window_opens_where_setup_is_missing(qapp, tmp_path, monkeypatch, token, shows, page):
    monkeypatch.setattr(controller_module, "get_token", lambda: token)
    save_config(Config(shows=shows), tmp_path / "config.json")
    journal = Journal(tmp_path / "journal.db")
    controller = AppController(tmp_path / "config.json", journal)
    try:
        window = MainWindow(controller)
        assert window.stack.currentIndex() == page
        assert window.needs_setup() is (page != ACTIVITY)
    finally:
        controller.shutdown()
        journal.close()


def test_settings_are_saved_even_if_autostart_cannot_be_changed(qapp, tmp_path, monkeypatch, french):
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
    monkeypatch.setattr(autostart, "set_enabled", lambda enabled: None)  # jamais le vrai registre
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


def button(widget, text):
    found = [b for b in widget.findChildren(QPushButton) if b.text() == text]
    assert len(found) == 1, [b.text() for b in widget.findChildren(QPushButton)]
    return found[0]


def set_shows(controller, *shows):
    assert controller.update_config(Config(shows=list(shows)))


def test_activity_header_counts_the_watched_shows(controller, french):
    set_shows(
        controller,
        ShowFolder(1, "Mars Attack", r"D:\Mars", r"D:\Mars"),
        ShowFolder(2, "Silicon Talk", r"D:\Mars", r"D:\Mars"),
        ShowFolder(3, "Sans dossier"),
    )
    page = ActivityPage(controller)
    assert page.detail_label.text().startswith("Émissions surveillées : 2 · prochain passage dans")


def test_activity_lists_missing_folders_with_a_button_to_edit_the_show(controller, french):
    set_shows(controller, ShowFolder(1, "Mars Attack", r"D:\Mars", r"D:\Mars"), ShowFolder(2, "", r"E:\Silicon"))
    controller.missing_folders = ((r"E:\Silicon", "2"),)  # émission sans nom : son id (comme le moteur)
    page = ActivityPage(controller)
    requested = []
    page.edit_show_requested.connect(requested.append)
    assert "À traiter" in texts(page, QLabel)
    assert r"Dossier introuvable : E:\Silicon (2)" in texts(page, QLabel)
    button(page, "Modifier l'émission").click()
    assert requested == [1]


def test_create_a_rule_opens_the_show_of_the_file_folder(controller, french):
    controller.journal.ensure("h1", "interview_brut.mp3", 1, folder=r"D:\Podcasts")
    controller.journal.update("h1", status=Status.SANS_REGLE, last_error=msg("err_no_rule"))
    page = ActivityPage(controller)
    requested = []
    page.create_rule_requested.connect(lambda folder, keyword: requested.append((folder, keyword)))
    button(page, "Créer une règle").click()
    assert requested == [(r"D:\Podcasts", "interview_brut")]


def test_a_broken_rule_opens_the_show_whose_keyword_matched(controller, french):
    set_shows(
        controller,
        ShowFolder(1, "Silicon Talk", r"D:\Podcasts", r"D:\Podcasts", [KeywordRule("DEBRIEF")]),
        ShowFolder(2, "Autre", r"E:\Autre", r"E:\Autre", [KeywordRule("MARS ATTACK")]),
        ShowFolder(3, "Mars Attack", r"d:\podcasts", r"d:\podcasts", [KeywordRule("MARS ATTACK")]),
    )
    controller.journal.ensure("h1", "MARS ATTACK 13.mp3", 1, folder=r"D:\Podcasts")
    controller.journal.update("h1", status=Status.REGLE_CASSEE, last_error=msg("rule_err_show_missing", show="Mars Attack"))
    page = ActivityPage(controller)
    requested = []
    page.edit_show_requested.connect(requested.append)
    button(page, "Modifier l'émission").click()
    assert requested == [2]


def test_settings_save_keeps_the_shows(controller, syncs):
    shows = [ShowFolder(1, "Mars Attack", r"D:\Mars", r"D:\Mars", [KeywordRule("MARS ATTACK")])]
    set_shows(controller, *shows)
    page = SettingsPage(controller)
    page.interval.setValue(30)
    page._save()
    assert controller.config.interval_minutes == 30
    assert controller.config.shows == shows


def test_tray_menu_opens_the_folder_of_each_watched_show(controller, monkeypatch):
    opened = []
    monkeypatch.setattr(tray_module.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    tray = Tray(controller, MainWindow(controller))
    menu = tray.folders_menu
    assert menu.title() == "Open folder"
    assert not menu.menuAction().isEnabled()  # aucune émission
    set_shows(
        controller,
        ShowFolder(1, "Mars Attack", "D:/Mars", "D:/Mars"),
        ShowFolder(2, "Sans dossier"),
        ShowFolder(3, "", "E:/Silicon", "E:/Silicon"),
    )
    assert menu.menuAction().isEnabled()
    assert [action.text() for action in menu.actions()] == ["Mars Attack — D:/Mars", "Show 3 — E:/Silicon"]
    menu.actions()[1].trigger()
    assert opened == ["E:/Silicon"]
    set_shows(controller)
    assert menu.actions() == [] and not menu.menuAction().isEnabled()


def test_activity_lists_files_ignored_when_the_folder_was_chosen(controller, syncs, french):
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


def test_activity_header_when_the_token_is_refused(controller, french):
    page = ActivityPage(controller)
    assert "prochain passage dans" in page.detail_label.text()
    controller.auth_blocked = True
    page.refresh()
    assert "synchro automatique suspendue (jeton invalide)" in page.detail_label.text()
    assert "prochain passage" not in page.detail_label.text()


def test_pause_checkbox_and_tray_follow_the_controller(controller, syncs, french):
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


def test_settings_page_reports_settings_that_cannot_be_saved(controller, syncs, monkeypatch, french):
    def denied(config, path):
        raise PermissionError(13, "Accès refusé")

    monkeypatch.setattr(controller_module, "save_config", denied)
    page = SettingsPage(controller)
    page.interval.setValue(30)
    page._save()
    assert page.saved_label.text() == "Réglages non enregistrés"
    assert controller.config.interval_minutes == 15
    assert syncs == []


def test_activity_refresh_hides_the_previous_rows_at_once(controller):
    controller.journal.ensure("h1", "interview_brut.mp3", 1)
    controller.journal.update("h1", status=Status.SANS_REGLE, last_error="Aucune règle ne correspond")
    page = ActivityPage(controller)
    page.refresh()  # les anciennes lignes, détruites plus tard, ne doivent plus s'afficher
    visible = [label.text() for label in page.findChildren(QLabel) if label.isVisibleTo(page)]
    assert visible.count("interview_brut.mp3") == 1


def test_activity_shows_core_messages_in_the_current_language(controller):
    controller.journal.ensure("h1", "MARS ATTACK 13.mp3", 1)
    stored_error = msg("rule_err_show_missing", show="Mars Attack")
    controller.journal.update("h1", status=Status.REGLE_CASSEE, last_error=stored_error)
    controller.dry_run_lines = [msg("dry_line", title="MARS ATTACK 14", detail=msg("dry_would_publish", show="Mars Attack"))]
    controller.state, controller.message = "attention", msg("cycle_files_need_attention", n=1)
    page = ActivityPage(controller)
    assert "Show not found on Ausha: Mars Attack" in texts(page, QLabel)
    assert "MARS ATTACK 14 — Would be published to Mars Attack" in texts(page, QLabel)
    assert "Some files need your attention" in page.status_label.text()
    assert page.detail_label.text().endswith("Files needing attention: 1")
    i18n.set_language("ar")
    page.refresh()
    assert tr("rule_err_show_missing", show="Mars Attack") in texts(page, QLabel)
    assert tr("state_attention") in page.status_label.text()
    assert page.detail_label.text().endswith(tr("cycle_files_need_attention", n=1))


def test_tray_texts_follow_the_state(controller, syncs):
    tray = Tray(controller, MainWindow(controller))
    assert tray.toolTip() == "SyncAusha — Setup incomplete"  # jeton présent, aucune émission
    controller.set_paused(True)
    assert tray.toolTip() == "SyncAusha — Paused"
    assert tray.pause_action.text() == "Resume sync"
    controller.set_paused(False)
    assert tray.pause_action.text() == "Pause sync"


def test_token_test_result_replaces_the_hint(controller, french):
    page = SettingsPage(controller)
    assert page.test_result.text() == tr("settings_token_hint")
    page._on_test_failed(Exception("jeton refusé"))
    assert page.test_result.text() == "Échec de la connexion : jeton refusé"
    assert page.test_result.objectName() == "error"
    page.load()
    assert page.test_result.text() == tr("settings_token_hint")
    assert page.test_result.objectName() == "muted"


def test_arabic_labels_starting_with_latin_text_read_right_to_left(qapp):
    """RLM en tête : un nom de fichier (isolé, donc intact) ou une phrase qui commence par un titre latin
    (isolé par tr) s'affiche de droite à gauche, aligné à droite ; une phrase arabe reste telle quelle.

    Un titre de ligne est sélectionnable, donc affiché par un QTextDocument : son sens est celui du premier
    caractère fort, isolats compris. Sans la marque, « titre — ستُنشر… » partirait à gauche."""
    rlm, fsi, pdi = "\u200f", "\u2068", "\u2069"

    def direction(text):
        document = QTextDocument()
        document.setPlainText(text)
        return document.firstBlock().textDirection()

    i18n.set_language("ar")
    row = Row("2024-05 MARS ATTACK (bonus).mp3", tr("err_no_rule"))
    title, subtitle = row.findChildren(QLabel)
    assert title.text().startswith(rlm)
    assert title.text() == f"{rlm}{fsi}2024-05 MARS ATTACK (bonus).mp3{pdi}"
    assert subtitle.text() == tr("err_no_rule")
    line = render(msg("dry_line", title="LE DEBRIEF 45", detail=msg("dry_would_publish", show="Silicon Talk")))
    assert line.startswith(f"{fsi}LE DEBRIEF 45{pdi}")
    assert direction(line) == Qt.LayoutDirection.LeftToRight
    assert bidi_text(line) == rlm + line
    assert direction(bidi_text(line)) == Qt.LayoutDirection.RightToLeft
    # Message d'Ausha sans lettre arabe : isolé en bloc une seule fois, avec la marque RLM en tête.
    detail = render(msg("err_ausha", detail="File too large", status=422))
    assert bidi_text(detail) == f"{rlm}{fsi}{detail}{pdi}"
    for text in (line, detail):
        assert bidi_text(bidi_text(text)) == bidi_text(text)  # jamais de marque en double
    i18n.set_language("en")
    assert bidi_text("MARS ATTACK 12.mp3") == "MARS ATTACK 12.mp3"


def test_stylesheet_is_complete_for_both_palettes():
    assert style.LIGHT.keys() == style.DARK.keys()
    for path in style.IMAGES.values():
        assert Path(path).is_file()
    for colors in (style.LIGHT, style.DARK):
        assert "$" not in style.stylesheet(colors)
