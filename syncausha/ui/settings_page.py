"""Page Réglages : jeton, dossier, intervalle, démarrage, pause, essai à blanc."""
from __future__ import annotations

import os
from dataclasses import replace

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from syncausha import autostart
from syncausha.config import MAX_INTERVAL, MIN_INTERVAL, app_data_dir
from syncausha.ui.controller import AppController, Catalog
from syncausha.ui.widgets import make_label, set_tone

TOKEN_HINT = "Le jeton se crée dans Ausha : Mon compte → API publique."


class SettingsPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(make_label("Réglages", "pageTitle"))

        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        test_button = QPushButton("Tester la connexion")
        test_button.clicked.connect(self._test)
        token_row = QHBoxLayout()
        token_row.addWidget(self.token, 1)
        token_row.addWidget(test_button)
        token_field = QVBoxLayout()
        token_field.setSpacing(6)
        token_field.addLayout(token_row)
        # Aide sous le jeton, remplacée par le résultat du test de connexion.
        self.test_result = make_label(TOKEN_HINT, "muted", wrap=True)
        token_field.addWidget(self.test_result)
        form.addRow("Jeton Ausha", token_field)

        self.folder = QLineEdit()
        self.folder.setReadOnly(True)
        folder_button = QPushButton("Choisir…")
        folder_button.clicked.connect(self._choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(folder_button)
        form.addRow("Dossier surveillé", folder_row)

        self.interval = QSpinBox()
        self.interval.setRange(MIN_INTERVAL, MAX_INTERVAL)
        self.interval.setSuffix(" min")
        self.interval.setFixedWidth(110)
        form.addRow("Vérifier toutes les", self.interval)

        self.autostart = QCheckBox("Lancer au démarrage de Windows")
        self.paused = QCheckBox("Mettre la synchronisation en pause")
        self.dry_run = QCheckBox("Essai à blanc : ne publie rien, montre ce qui serait envoyé")
        for checkbox in (self.autostart, self.paused, self.dry_run):
            form.addRow("", checkbox)
        layout.addWidget(card)

        actions = QHBoxLayout()
        logs_button = QPushButton("Ouvrir le dossier des logs")
        logs_button.setObjectName("link")
        logs_button.clicked.connect(self._open_logs)
        actions.addWidget(logs_button)
        actions.addStretch(1)
        self.saved_label = make_label(object_name="muted")
        actions.addWidget(self.saved_label)
        save_button = QPushButton("Enregistrer")
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
        self.token.clear()
        self.token.setPlaceholderText(
            "Jeton enregistré — laissez vide pour le conserver"
            if self.controller.has_token()
            else "Collez votre jeton personnel Ausha"
        )
        self.folder.setText(config.watch_folder)
        self.interval.setValue(config.interval_minutes)
        self.autostart.setChecked(autostart.is_enabled())
        self.paused.setChecked(config.paused)
        self._saved_paused = config.paused
        self.dry_run.setChecked(config.dry_run)
        self.saved_label.clear()
        self._show_test_result(TOKEN_HINT)

    def _follow_pause(self, _state: str, _message: str) -> None:
        """Pause changée ailleurs (icône) : seule cette case suit, les autres saisies sont gardées."""
        paused = self.controller.config.paused
        if paused != self._saved_paused:  # un simple début ou fin de cycle ne touche pas la case
            self._saved_paused = paused
            self.paused.setChecked(paused)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Dossier des podcasts", self.folder.text())
        if folder:
            self.folder.setText(os.path.normpath(folder))

    def _test(self) -> None:
        self._show_test_result("Connexion à Ausha…")
        self.controller.fetch_catalog(self._on_test_ok, self._on_test_failed, token=self.token.text().strip() or None)

    def _on_test_ok(self, catalog: Catalog) -> None:
        names = ", ".join(sorted(show.name for show in catalog)) or "aucune émission"
        self._show_test_result(f"Connexion réussie. Émissions : {names}")

    def _on_test_failed(self, error: Exception) -> None:
        self._show_test_result(f"Échec : {error}", "error")

    def _show_test_result(self, text: str, tone: str = "muted") -> None:
        self.test_result.setText(text)
        set_tone(self.test_result, tone)

    def _save(self) -> None:
        token = self.token.text().strip()
        if token:
            try:
                self.controller.update_token(token)
            except Exception as exc:  # Gestionnaire d'identifiants indisponible ou refus
                self.saved_label.setText(f"Jeton non enregistré : {exc}")
                return
        config = replace(
            self.controller.config,
            watch_folder=self.folder.text(),
            interval_minutes=self.interval.value(),
            paused=self.paused.isChecked(),
            dry_run=self.dry_run.isChecked(),
        )
        if not self.controller.update_config(config):
            self.saved_label.setText("Réglages non enregistrés")
            return
        message = "Réglages enregistrés"
        try:
            autostart.set_enabled(self.autostart.isChecked())
        except OSError as exc:  # registre verrouillé par une stratégie ou un antivirus
            message = f"Démarrage automatique non modifié : {exc}"
        self.load()
        self.saved_label.setText(message)
        if not config.paused:
            self.controller.sync_now()

    def _open_logs(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir() / "logs")))
