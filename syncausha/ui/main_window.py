"""Fenêtre principale : barre latérale + pages. Fermer la fenêtre la réduit dans la zone de notification."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QListWidget, QMainWindow, QStackedWidget, QWidget

from syncausha.i18n import tr
from syncausha.ui.activity_page import ActivityPage
from syncausha.ui.controller import AppController
from syncausha.ui.language import apply_language
from syncausha.ui.settings_page import SettingsPage
from syncausha.ui.shows_page import ShowsPage

ACTIVITY, SHOWS, SETTINGS = 0, 1, 2


class MainWindow(QMainWindow):
    # Émis une fois le contenu reconstruit dans la nouvelle langue (l'icône se retraduit).
    language_changed = Signal()

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.resize(880, 660)  # page Émissions entière sans défilement
        self.setMinimumSize(720, 480)
        self._build()
        self.go_to(self._first_page())

    def _build(self) -> None:
        """Construit le contenu dans la langue active ; l'ancien, s'il existe, est détruit par Qt."""
        self.setWindowTitle(tr("app_title"))
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(170)
        self.sidebar.addItems([tr("nav_activity"), tr("nav_shows"), tr("nav_settings")])
        self.stack = QStackedWidget()
        self.activity = ActivityPage(self.controller)
        self.shows = ShowsPage(self.controller)
        self.settings = SettingsPage(self.controller)
        for page in (self.activity, self.shows, self.settings):
            self.stack.addWidget(page)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.activity.create_rule_requested.connect(self.open_new_rule)
        self.activity.edit_show_requested.connect(self.open_show)
        self.settings.language_changed.connect(self._on_language_changed)
        self.setCentralWidget(central)  # l'ancien contenu central est supprimé (deleteLater)
        # Fenêtre visible : contenu affiché tout de suite, pas au prochain tour de boucle (qui
        # rechargerait Réglages et effacerait le message d'enregistrement repris par rebuild()).
        central.show()

    def rebuild(self) -> None:
        """Reconstruit le contenu dans la langue active, sur la même page, avec le même message d'enregistrement."""
        index = self.stack.currentIndex()
        saved_message = self.settings.saved_message
        self._build()
        self.go_to(index)
        self.settings.show_saved(saved_message)

    def _on_language_changed(self, code: str) -> None:
        apply_language(QApplication.instance(), code)
        # Différé : la page Réglages qui émet le signal serait détruite pendant son propre _save.
        QTimer.singleShot(0, self, self._rebuild_and_notify)

    def _rebuild_and_notify(self) -> None:
        self.rebuild()
        self.language_changed.emit()

    def needs_setup(self) -> bool:
        return self.controller.needs_setup()

    def _first_page(self) -> int:
        """Réglages sans jeton, Émissions sans émission surveillée, sinon Activité."""
        if not self.controller.has_token():
            return SETTINGS
        return SHOWS if self.needs_setup() else ACTIVITY

    def go_to(self, index: int) -> None:
        self.sidebar.setCurrentRow(index)
        self.stack.setCurrentIndex(index)

    def open_new_rule(self, folder: str, keyword: str) -> None:
        """« Créer une règle » : l'émission du dossier du fichier, avec le mot-clé proposé."""
        self.go_to(SHOWS)
        self.shows.start_new_rule(folder, keyword)

    def open_show(self, index: int) -> None:
        """« Modifier l'émission » : la page Émissions sur cette émission (-1 : la page seulement)."""
        self.go_to(SHOWS)
        self.shows.select_show(index)

    def show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
