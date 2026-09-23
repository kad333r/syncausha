"""Icône de la zone de notification : état en couleur, menu rapide, notifications Windows."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from syncausha.ui.activity_page import STATE_TEXT
from syncausha.ui.controller import AppController
from syncausha.ui.icons import state_icon
from syncausha.ui.main_window import MainWindow


class Tray(QSystemTrayIcon):
    def __init__(self, controller: AppController, window: MainWindow) -> None:
        super().__init__(state_icon(controller.state))
        self.controller = controller
        self.window = window
        self._menu = QMenu()
        self._menu.addAction("Synchroniser maintenant").triggered.connect(controller.sync_now)
        self.pause_action = self._menu.addAction("Mettre en pause")
        self.pause_action.triggered.connect(self._toggle_pause)
        self._menu.addAction("Ouvrir le dossier").triggered.connect(self._open_folder)
        self._menu.addSeparator()
        self._menu.addAction("Quitter").triggered.connect(QApplication.quit)
        self.setContextMenu(self._menu)

        self.activated.connect(self._on_activated)
        self.messageClicked.connect(window.show_and_raise)
        controller.state_changed.connect(self._update)
        controller.notification.connect(self._notify)
        self._update(controller.state, controller.message)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.window.show_and_raise()

    def _toggle_pause(self) -> None:
        self.controller.set_paused(not self.controller.config.paused)

    def _open_folder(self) -> None:
        folder = self.controller.config.watch_folder
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _update(self, state: str, _message: str) -> None:
        self.setIcon(state_icon(state))
        self.setToolTip(f"SyncAusha — {STATE_TEXT.get(state, state)}")
        self.pause_action.setText("Reprendre la synchronisation" if self.controller.config.paused else "Mettre en pause")

    def _notify(self, title: str, body: str) -> None:
        self.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 6000)
