"""Page Réglages : langue, jeton, dossier, intervalle, démarrage, pause, essai à blanc."""
from __future__ import annotations

import os
from dataclasses import replace

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from syncausha import autostart, i18n
from syncausha.config import MAX_INTERVAL, MIN_INTERVAL, app_data_dir
from syncausha.i18n import LANGUAGES, msg, render, tr
from syncausha.ui.controller import AppController, Catalog
from syncausha.ui.widgets import leading_alignment, make_label, set_tone


class SettingsPage(QWidget):
    # Émis après un enregistrement qui change la langue : la fenêtre se reconstruit (et détruit cette page).
    language_changed = Signal(str)

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(make_label(tr("settings_title"), "pageTitle"))

        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        self.language = QComboBox()
        for code, name in LANGUAGES.items():  # chaque langue écrite dans sa propre langue
            self.language.addItem(name, code)
        self.language.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.language.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        form.addRow(tr("settings_language"), self.language)

        self.token = QLineEdit()
        self.token.setAlignment(leading_alignment() | Qt.AlignmentFlag.AlignVCenter)
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        test_button = QPushButton(tr("settings_test_connection"))
        test_button.clicked.connect(self._test)
        token_row = QHBoxLayout()
        token_row.addWidget(self.token, 1)
        token_row.addWidget(test_button)
        token_field = QVBoxLayout()
        token_field.setSpacing(6)
        token_field.addLayout(token_row)
        # Aide sous le jeton, remplacée par le résultat du test de connexion.
        self.test_result = make_label(tr("settings_token_hint"), "muted", wrap=True)
        token_field.addWidget(self.test_result)
        form.addRow(tr("settings_field_token"), token_field)

        self.folder = QLineEdit()
        self.folder.setAlignment(leading_alignment() | Qt.AlignmentFlag.AlignVCenter)  # chemin latin à droite en arabe
        self.folder.setReadOnly(True)
        folder_button = QPushButton(tr("common_choose"))
        folder_button.clicked.connect(self._choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(folder_button)
        form.addRow(tr("settings_field_folder"), folder_row)

        self.interval = QSpinBox()
        self.interval.setRange(MIN_INTERVAL, MAX_INTERVAL)
        self.interval.setSuffix(tr("settings_interval_suffix"))
        self.interval.setFixedWidth(110)
        form.addRow(tr("settings_field_interval"), self.interval)

        self.autostart = QCheckBox(tr("settings_autostart"))
        self.paused = QCheckBox(tr("settings_pause"))
        self.dry_run = QCheckBox(tr("settings_dry_run"))
        for checkbox in (self.autostart, self.paused, self.dry_run):
            form.addRow("", checkbox)
        layout.addWidget(card)

        actions = QHBoxLayout()
        logs_button = QPushButton(tr("settings_open_logs"))
        logs_button.setObjectName("link")
        logs_button.clicked.connect(self._open_logs)
        actions.addWidget(logs_button)
        actions.addStretch(1)
        self.saved_label = make_label(object_name="muted")
        self.saved_message = ""  # résultat du dernier enregistrement (msg), repris si la fenêtre est reconstruite
        actions.addWidget(self.saved_label)
        save_button = QPushButton(tr("common_save"))
        save_button.setObjectName("primary")
        save_button.clicked.connect(self._save)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        controller.state_changed.connect(self._follow_pause)
        self.load()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.load()

    def load(self) -> None:
        config = self.controller.config
        self.language.setCurrentIndex(self.language.findData(i18n.current_language()))
        self.token.clear()
        self.token.setPlaceholderText(
            tr("settings_token_saved_placeholder") if self.controller.has_token() else tr("settings_token_placeholder")
        )
        self.folder.setText(config.watch_folder)
        self.interval.setValue(config.interval_minutes)
        self.autostart.setChecked(autostart.is_enabled())
        self.paused.setChecked(config.paused)
        self._saved_paused = config.paused
        self.dry_run.setChecked(config.dry_run)
        self.show_saved("")
        self._show_test_result(tr("settings_token_hint"))

    def show_saved(self, message: str) -> None:
        """Résultat d'un enregistrement : message produit par msg, traduit à l'affichage."""
        self.saved_message = message
        self.saved_label.setText(render(message))

    def _follow_pause(self, _state: str, _message: str) -> None:
        """Pause changée ailleurs (icône) : seule cette case suit, les autres saisies sont gardées."""
        paused = self.controller.config.paused
        if paused != self._saved_paused:  # un simple début ou fin de cycle ne touche pas la case
            self._saved_paused = paused
            self.paused.setChecked(paused)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("dialog_choose_folder"), self.folder.text())
        if folder:
            self.folder.setText(os.path.normpath(folder))

    def _test(self) -> None:
        self._show_test_result(tr("settings_connecting"))
        self.controller.fetch_catalog(self._on_test_ok, self._on_test_failed, token=self.token.text().strip() or None)

    def _on_test_ok(self, catalog: Catalog) -> None:
        names = tr("common_list_separator").join(sorted(show.name for show in catalog)) or tr("settings_no_shows")
        self._show_test_result(tr("settings_connection_ok", shows=names))

    def _on_test_failed(self, error: Exception) -> None:
        self._show_test_result(tr("settings_test_failed", detail=render(str(error))), "error")

    def _show_test_result(self, text: str, tone: str = "muted") -> None:
        self.test_result.setText(text)
        set_tone(self.test_result, tone)

    def _save(self) -> None:
        token = self.token.text().strip()
        if token:
            try:
                self.controller.update_token(token)
            except Exception as exc:  # Gestionnaire d'identifiants indisponible ou refus
                self.show_saved(msg("settings_token_not_saved", detail=exc))
                return
        language = self.language.currentData()
        config = replace(
            self.controller.config,
            language=language,
            watch_folder=self.folder.text(),
            interval_minutes=self.interval.value(),
            paused=self.paused.isChecked(),
            dry_run=self.dry_run.isChecked(),
        )
        if not self.controller.update_config(config):
            self.show_saved(msg("settings_not_saved"))
            return
        message = msg("settings_saved")
        try:
            autostart.set_enabled(self.autostart.isChecked())
        except OSError as exc:  # registre verrouillé par une stratégie ou un antivirus
            message = msg("settings_autostart_failed", detail=exc)
        self.load()
        self.show_saved(message)
        if not config.paused:
            self.controller.sync_now()
        if language != i18n.current_language():  # en dernier : tout est enregistré avant la reconstruction
            self.language_changed.emit(language)

    def _open_logs(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir() / "logs")))
