"""Fenêtre principale : barre latérale + pages. Fermer la fenêtre la réduit dans la zone de notification."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QMainWindow, QStackedWidget, QWidget

from syncausha.ui.activity_page import ActivityPage
from syncausha.ui.controller import AppController
from syncausha.ui.rules_page import RulesPage
from syncausha.ui.settings_page import SettingsPage

ACTIVITY, RULES, SETTINGS = 0, 1, 2


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("SyncAusha")
        self.resize(880, 600)
        self.setMinimumSize(720, 480)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(170)
        self.sidebar.addItems(["Activité", "Règles", "Réglages"])
        self.stack = QStackedWidget()
        self.activity = ActivityPage(controller)
        self.rules = RulesPage(controller)
        self.settings = SettingsPage(controller)
        for page in (self.activity, self.rules, self.settings):
            self.stack.addWidget(page)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.activity.create_rule_requested.connect(self.open_new_rule)
        self.activity.edit_rules_requested.connect(lambda: self.go_to(RULES))
        self.go_to(SETTINGS if self.needs_setup() else ACTIVITY)

    def needs_setup(self) -> bool:
        return not (self.controller.has_token() and self.controller.config.watch_folder)

    def go_to(self, index: int) -> None:
        self.sidebar.setCurrentRow(index)
        self.stack.setCurrentIndex(index)

    def open_new_rule(self, keyword: str) -> None:
        self.go_to(RULES)
        self.rules.start_new_rule(keyword)

    def show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
