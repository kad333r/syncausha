"""Icône de la zone de notification : état en couleur, menu rapide, notifications Windows."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from syncausha.i18n import tr
from syncausha.ui.activity_page import state_text
from syncausha.ui.controller import AppController
from syncausha.ui.icons import state_icon
from syncausha.ui.main_window import MainWindow


class Tray(QSystemTrayIcon):
    def __init__(self, controller: AppController, window: MainWindow) -> None:
        super().__init__(state_icon(controller.state))
        self.controller = controller
        self.window = window
        self._menu = QMenu()
        # Textes posés par retranslate(), ici et à chaque changement de langue.
        self.sync_action = self._menu.addAction("")
        self.sync_action.triggered.connect(controller.sync_now)
        self.pause_action = self._menu.addAction("")
        self.pause_action.triggered.connect(self._toggle_pause)
        self.open_folder_action = self._menu.addAction("")
        self.open_folder_action.triggered.connect(self._open_folder)
        self._menu.addSeparator()
        self.quit_action = self._menu.addAction("")
        self.quit_action.triggered.connect(QApplication.quit)
        self.setContextMenu(self._menu)

        self.activated.connect(self._on_activated)
        self.messageClicked.connect(window.show_and_raise)
        controller.state_changed.connect(self._update)
        controller.notification.connect(self._notify)
        window.language_changed.connect(self.retranslate)
        self.retranslate()

    def retranslate(self) -> None:
        """Menu et info-bulle dans la langue active."""
        self.sync_action.setText(tr("tray_sync_now"))
        self.open_folder_action.setText(tr("tray_open_folder"))
        self.quit_action.setText(tr("tray_quit"))
        self._update(self.controller.state, self.controller.message)  # info-bulle et Pause/Reprendre

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
        self.setToolTip(tr("tray_tooltip", state=state_text(state)))
        self.pause_action.setText(tr("tray_resume") if self.controller.config.paused else tr("tray_pause"))

    def _notify(self, title: str, body: str) -> None:
        self.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 6000)
