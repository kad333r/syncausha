"""Page Activité : état, fichiers à traiter, historique récent, fichiers ignorés."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget

from syncausha.journal import Entry, Status
from syncausha.rules import episode_title
from syncausha.ui.controller import AppController
from syncausha.ui.style import palette
from syncausha.ui.widgets import Row, clear_layout, make_label, pill, section_label

STATE_TEXT = {
    "ok": "À jour",
    "syncing": "Synchronisation…",
    "baseline": "Analyse du dossier…",
    "attention": "Des fichiers demandent votre attention",
    "paused": "En pause",
    "not_configured": "Configuration incomplète",
    "folder_missing": "Dossier introuvable",
    "auth_error": "Jeton Ausha invalide",
    "offline": "Ausha injoignable",
}
STATE_COLOR = {
    "ok": "success", "syncing": "info", "baseline": "info", "attention": "warning", "paused": "muted",
    "not_configured": "warning", "folder_missing": "warning", "auth_error": "danger", "offline": "danger",
}
MAX_IGNORED_ROWS = 20


class ActivityPage(QWidget):
    create_rule_requested = Signal(str)
    edit_rules_requested = Signal()

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)

        header = QHBoxLayout()
        texts = QVBoxLayout()
        self.status_label = make_label(object_name="pageTitle")
        self.detail_label = make_label(object_name="muted", wrap=True)
        texts.addWidget(self.status_label)
        texts.addWidget(self.detail_label)
        header.addLayout(texts, 1)
        self.sync_button = QPushButton("Synchroniser")
        self.sync_button.setObjectName("primary")
        self.sync_button.clicked.connect(controller.sync_now)
        header.addWidget(self.sync_button)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.sections = QVBoxLayout(content)
        self.sections.setContentsMargins(0, 0, 8, 0)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        controller.state_changed.connect(self.refresh)
        controller.activity_changed.connect(self.refresh)
        controller.progress_changed.connect(self.refresh)
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._update_header)
        self._tick.start(30_000)
        self.refresh()

    def refresh(self, *_args) -> None:
        self._update_header()
        clear_layout(self.sections)
        attention = self.controller.journal.needing_attention()
        if attention:
            self.sections.addWidget(section_label("À traiter"))
            for entry in attention:
                self.sections.addWidget(self._attention_row(entry))
        if self.controller.dry_run_lines:
            self.sections.addWidget(section_label("Essai à blanc — rien n'a été publié"))
            for line in self.controller.dry_run_lines:
                self.sections.addWidget(Row(line))
        self.sections.addWidget(section_label("Récent"))
        recent = self.controller.journal.recent()
        if not recent:
            self.sections.addWidget(make_label("Aucun épisode publié pour l'instant.", "muted"))
        for entry in recent:
            self.sections.addWidget(self._recent_row(entry))
        ignored = self.controller.journal.ignored(limit=-1)
        if ignored:
            self.sections.addWidget(section_label("Ignorés — déjà présents au choix du dossier"))
            for entry in ignored[:MAX_IGNORED_ROWS]:
                self.sections.addWidget(self._ignored_row(entry))
            if len(ignored) > MAX_IGNORED_ROWS:
                self.sections.addWidget(make_label(f"… et {len(ignored) - MAX_IGNORED_ROWS} autres", "muted"))
        self.sections.addStretch(1)

    def _update_header(self) -> None:
        c = self.controller
        color = palette()[STATE_COLOR.get(c.state, "muted")]
        self.status_label.setText(f'<span style="color:{color}">●</span>&nbsp;{STATE_TEXT.get(c.state, c.state)}')
        parts = [c.config.watch_folder or "Aucun dossier choisi"]
        if c.busy:
            parts.append("synchronisation en cours")
        elif c.auth_blocked:
            parts.append("synchro automatique suspendue (jeton invalide)")
        elif not c.config.paused:
            parts.append(f"prochain passage dans {max(1, round(c.seconds_until_next_cycle() / 60))} min")
        if c.message and c.state not in ("ok", "syncing"):
            parts.append(c.message)
        self.detail_label.setText(" · ".join(parts))
        self.sync_button.setEnabled(not c.busy)

    def _attention_row(self, entry: Entry) -> Row:
        if entry.status is Status.SANS_REGLE:
            button = QPushButton("Créer une règle")
            button.clicked.connect(lambda _=False, name=entry.filename: self.create_rule_requested.emit(Path(name).stem))
        elif entry.status is Status.REGLE_CASSEE:
            button = QPushButton("Modifier les règles")
            button.clicked.connect(lambda _=False: self.edit_rules_requested.emit())
        else:
            button = QPushButton("Réessayer")
            button.clicked.connect(lambda _=False, h=entry.hash: self.controller.retry(h))
        return Row(entry.filename, entry.last_error or "Aucune règle ne correspond", button)

    def _ignored_row(self, entry: Entry) -> Row:
        button = QPushButton("Publier quand même")
        button.clicked.connect(lambda _=False, h=entry.hash: self.controller.publish_anyway(h))
        return Row(entry.filename, "Présent avant le choix du dossier", button)

    def _recent_row(self, entry: Entry) -> Row:
        when = datetime.fromtimestamp(entry.updated_at).strftime("%d/%m %H:%M")
        subtitle = f"{entry.show_name} · {when}" if entry.show_name else when
        if entry.status is Status.EN_COURS:
            percent = self.controller.progress.get(episode_title(Path(entry.filename)), 0)
            badge = pill(f"Envoi {percent} %", "info")
        elif entry.status is Status.PUBLIE:
            badge = pill("Publié", "success")
        elif entry.status is Status.DEJA_PRESENT:
            badge = pill("Déjà sur Ausha", "neutral")
        elif entry.attempts:
            badge = pill("Nouvel essai au prochain passage", "warning")
            subtitle = f"{subtitle} · {entry.last_error}"
        else:
            badge = pill("En attente", "neutral")
        return Row(Path(entry.filename).stem, subtitle, badge)
