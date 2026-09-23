"""Changement de langue : langue appliquée à Qt, fenêtre reconstruite, icône retraduite."""
import string
import sys
from dataclasses import replace

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QDateTime, QEvent, QLocale, Qt, QTranslator
from PySide6.QtWidgets import QSpinBox

from syncausha import autostart, i18n
from syncausha.config import Config, save_config
from syncausha.i18n import tr
from syncausha.journal import Journal
from syncausha.ui import controller as controller_module
from syncausha.ui import style
from syncausha.ui.activity_page import format_time, state_text
from syncausha.ui.controller import AppController
from syncausha.ui.language import apply_language
from syncausha.ui.main_window import RULES, SETTINGS, MainWindow
from syncausha.ui.settings_page import SettingsPage
from syncausha.ui.tray import Tray


@pytest.fixture(autouse=True)
def english_qt(qapp):
    """Chaque test part de l'anglais côté Qt (sens du texte, traducteur) et y revient."""
    apply_language(qapp, "en")
    yield
    apply_language(qapp, "en")
    delete_later_now()


@pytest.fixture
def errors(monkeypatch):
    """Exceptions levées dans les slots Qt : PySide les passe à sys.excepthook."""
    caught = []
    monkeypatch.setattr(sys, "excepthook", lambda *exc_info: caught.append(exc_info[1]))
    return caught


@pytest.fixture
def controller(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: None)
    monkeypatch.setattr(autostart, "is_enabled", lambda: False)
    monkeypatch.setattr(autostart, "set_enabled", lambda enabled: None)
    save_config(Config(watch_folder=str(tmp_path), baseline_folder=str(tmp_path)), tmp_path / "config.json")
    journal = Journal(tmp_path / "journal.db")
    controller = AppController(tmp_path / "config.json", journal)
    monkeypatch.setattr(controller, "sync_now", lambda: None)  # pas de vrai cycle à l'enregistrement
    yield controller
    controller.shutdown()
    journal.close()


@pytest.fixture
def window(controller):
    win = MainWindow(controller)
    yield win
    win.hide()


def delete_later_now():
    """Détruit tout de suite les objets en attente de deleteLater (hors boucle d'événements)."""
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def choose_language(qapp, window, code):
    """Choisit `code` dans Réglages, enregistre, puis laisse passer la reconstruction différée."""
    settings = window.settings
    settings.language.setCurrentIndex(settings.language.findData(code))
    settings._save()
    qapp.processEvents()
    qapp.processEvents()


def test_apply_language_sets_direction(qapp):
    apply_language(qapp, "ar")
    assert i18n.current_language() == "ar"
    assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
    apply_language(qapp, "fr")
    assert i18n.current_language() == "fr"
    assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight


def test_arabic_keeps_western_digits(qapp):
    """Formats régionaux de Windows à chiffres arabes orientaux (ar-SA) : les compteurs restent en 0-9."""
    QLocale.setDefault(QLocale("ar_SA"))
    apply_language(qapp, "ar")
    assert QLocale().toString(15) == "15"
    spin = QSpinBox()
    spin.setRange(5, 120)
    spin.setValue(15)
    assert spin.text() == "15"


def test_apply_language_turns_the_stylesheet_sides(qapp):
    """Retraits des listes et compteurs, bordure de la barre latérale : côté fin de lecture (gauche en arabe)."""
    qapp.setStyleSheet(style.stylesheet(style.LIGHT))
    try:
        apply_language(qapp, "ar")
        assert qapp.styleSheet() == style.stylesheet(style.palette(), rtl=True)
        assert "QComboBox { padding-left: 24px; }" in qapp.styleSheet()
        apply_language(qapp, "en")
        assert "QComboBox { padding-right: 24px; }" in qapp.styleSheet()
    finally:
        qapp.setStyleSheet("")


def test_apply_language_swaps_the_qt_translator(qapp):
    """Boutons des dialogues standard de Qt (Oui, Non…) dans la langue choisie, sans traducteur en anglais."""

    def yes():
        return QCoreApplication.translate("QPlatformTheme", "&Yes")

    apply_language(qapp, "fr")
    assert yes() == "&Oui"
    apply_language(qapp, "ar")
    assert yes() == "&نعم"
    delete_later_now()
    assert len(qapp.findChildren(QTranslator)) == 1
    apply_language(qapp, "en")
    assert yes() == "&Yes"
    delete_later_now()
    assert qapp.findChildren(QTranslator) == []


def test_rebuild_translates_and_keeps_page(qapp, window):
    window.go_to(RULES)
    assert window.sidebar.item(0).text() == "Activity"
    apply_language(qapp, "fr")
    window.rebuild()
    assert window.sidebar.item(0).text() == tr("nav_activity") == "Activité"
    assert window.stack.currentIndex() == RULES
    assert window.sidebar.currentRow() == RULES


def test_settings_language_change_rebuilds_window(qapp, window):
    old_settings = window.settings
    choose_language(qapp, window, "ar")
    assert i18n.current_language() == "ar"
    assert window.controller.config.language == "ar"
    assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert window.sidebar.item(0).text() == tr("nav_activity", lang="ar")
    assert window.settings is not old_settings
    assert window.stack.currentIndex() == SETTINGS
    assert window.settings.language.currentData() == "ar"
    assert window.settings.saved_label.text() == tr("settings_saved", lang="ar")


def test_rebuild_waits_until_the_settings_page_has_returned(qapp, window, errors):
    """La page Réglages qui émet le changement est détruite par la reconstruction : celle-ci est différée."""
    settings = window.settings
    settings.language.setCurrentIndex(settings.language.findData("fr"))
    settings._save()
    assert i18n.current_language() == "fr"
    assert window.settings is settings
    qapp.processEvents()
    assert window.settings is not settings
    assert window.sidebar.item(2).text() == "Réglages"
    assert errors == []


def test_old_pages_are_destroyed_and_no_longer_called(qapp, window, controller, errors):
    old = (window.activity, window.rules, window.settings, window.sidebar, window.stack)
    choose_language(qapp, window, "ar")
    delete_later_now()
    assert not any(shiboken6.isValid(widget) for widget in old)
    controller.state_changed.emit("idle", "")
    controller.activity_changed.emit()
    controller.progress_changed.emit("MARS ATTACK 12", 50)
    controller.set_paused(True)  # suivi par la nouvelle page Réglages
    qapp.processEvents()
    assert window.settings.paused.isChecked()
    assert errors == []


def test_language_change_keeps_the_window_visible_and_in_place(qapp, window):
    window.show()
    window.setGeometry(100, 120, 900, 640)
    qapp.processEvents()
    geometry = window.geometry()
    choose_language(qapp, window, "fr")
    delete_later_now()
    qapp.processEvents()
    assert window.isVisible()
    assert window.settings.isVisible()
    assert window.geometry() == geometry
    assert window.settings.saved_label.text() == "Réglages enregistrés"  # pas effacé par l'affichage de la page


def test_rebuild_of_a_hidden_window_keeps_it_hidden(qapp, window):
    apply_language(qapp, "fr")
    window.rebuild()
    qapp.processEvents()
    assert not window.isVisible()


def test_language_change_also_saves_the_other_settings(qapp, window):
    window.settings.interval.setValue(45)
    window.settings.dry_run.setChecked(True)
    choose_language(qapp, window, "fr")
    config = window.controller.config
    assert (config.language, config.interval_minutes, config.dry_run) == ("fr", 45, True)
    assert window.settings.interval.value() == 45


def test_saving_without_language_change_does_not_rebuild(qapp, window):
    rebuilt = []
    window.language_changed.connect(lambda: rebuilt.append(True))
    settings, sidebar = window.settings, window.sidebar
    settings.interval.setValue(45)
    settings._save()
    qapp.processEvents()
    qapp.processEvents()
    assert window.controller.config.interval_minutes == 45
    assert rebuilt == []
    assert window.settings is settings and window.sidebar is sidebar
    assert settings.saved_label.text() == "Settings saved"


def test_saving_without_touching_the_language_does_not_pin_it(qapp, controller):
    """Langue venue de l'installateur (aucune dans les réglages) : l'enregistrer sans toucher à la liste ne la
    fige pas, une réinstallation dans une autre langue sera suivie. La choisir, si."""
    apply_language(qapp, "fr")
    page = SettingsPage(controller)
    changes = []
    page.language_changed.connect(changes.append)
    assert page.language.currentData() == "fr"
    page.interval.setValue(45)
    page._save()
    assert (controller.config.language, controller.config.interval_minutes) == ("", 45)
    assert changes == []
    page.language.setCurrentIndex(page.language.findData("ar"))
    page._save()
    assert controller.config.language == "ar"
    assert changes == ["ar"]


def test_saving_keeps_a_language_chosen_earlier(qapp, controller):
    controller.update_config(replace(controller.config, language="fr"))
    apply_language(qapp, "fr")
    page = SettingsPage(controller)
    page.interval.setValue(45)
    page._save()
    assert controller.config.language == "fr"


def test_activity_dates_follow_the_language_with_western_digits(qapp):
    """Dates au format de la langue ; en arabe, chiffres 0-9 même si Windows est réglé en ar-SA."""
    timestamp = 1_790_000_000  # septembre 2026
    QLocale.setDefault(QLocale("ar_SA"))
    apply_language(qapp, "ar")
    text = format_time(timestamp)
    digits = [char for char in text if char.isdigit()]
    assert "2026" in text
    assert digits and all(char in string.digits for char in digits)
    apply_language(qapp, "fr")
    expected = QLocale("fr_FR").toString(QDateTime.fromSecsSinceEpoch(timestamp), QLocale.FormatType.ShortFormat)
    assert format_time(timestamp) == expected


def test_tray_is_retranslated_after_a_language_change(qapp, window, controller):
    controller.set_paused(True)
    tray = Tray(controller, window)
    assert tray.pause_action.text() == "Resume sync"
    choose_language(qapp, window, "ar")
    actions = (tray.sync_action, tray.pause_action, tray.open_folder_action, tray.quit_action)
    assert [action.text() for action in actions] == [
        tr("tray_sync_now", lang="ar"),
        tr("tray_resume", lang="ar"),
        tr("tray_open_folder", lang="ar"),
        tr("tray_quit", lang="ar"),
    ]
    assert state_text("paused") == tr("state_paused", lang="ar")
    assert tray.toolTip() == tr("tray_tooltip", lang="ar", state=state_text("paused"))
    assert tray.contextMenu().layoutDirection() == Qt.LayoutDirection.RightToLeft
