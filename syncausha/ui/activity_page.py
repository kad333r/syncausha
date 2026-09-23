"""Page Activité : état, fichiers à traiter, historique récent, fichiers ignorés."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget

from syncausha.i18n import render, tr
from syncausha.journal import Entry, Status
from syncausha.rules import episode_title
from syncausha.ui.controller import AppController
from syncausha.ui.style import palette
from syncausha.ui.widgets import Row, clear_layout, make_label, pill, section_label

# Clés des textes d'état, traduites à l'affichage (la langue peut changer en cours de route).
STATE_KEYS = {
    "ok": "state_ok",
    "syncing": "state_syncing",
    "baseline": "state_baseline",
    "attention": "state_attention",
    "paused": "state_paused",
    "not_configured": "state_not_configured",
    "folder_missing": "state_folder_missing",
    "auth_error": "state_auth_error",
    "offline": "state_offline",
}
STATE_COLOR = {
    "ok": "success", "syncing": "info", "baseline": "info", "attention": "warning", "paused": "muted",
    "not_configured": "warning", "folder_missing": "warning", "auth_error": "danger", "offline": "danger",
}
MAX_IGNORED_ROWS = 20


def state_text(state: str) -> str:
    """Texte de l'état dans la langue active (l'identifiant brut s'il est inconnu)."""
    key = STATE_KEYS.get(state)
    return tr(key) if key else state


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
        self.sync_button = QPushButton(tr("activity_sync"))
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
            self.sections.addWidget(section_label(tr("activity_section_attention")))
            for entry in attention:
                self.sections.addWidget(self._attention_row(entry))
        if self.controller.dry_run_lines:
            self.sections.addWidget(section_label(tr("activity_section_dry_run")))
            for line in self.controller.dry_run_lines:
                self.sections.addWidget(Row(render(line)))
        self.sections.addWidget(section_label(tr("activity_section_recent")))
        recent = self.controller.journal.recent()
        if not recent:
            self.sections.addWidget(make_label(tr("activity_no_episodes"), "muted"))
        for entry in recent:
            self.sections.addWidget(self._recent_row(entry))
        ignored = self.controller.journal.ignored(limit=-1)
        if ignored:
            self.sections.addWidget(section_label(tr("activity_section_ignored")))
            for entry in ignored[:MAX_IGNORED_ROWS]:
                self.sections.addWidget(self._ignored_row(entry))
            if len(ignored) > MAX_IGNORED_ROWS:
                more = tr("activity_more_ignored", n=len(ignored) - MAX_IGNORED_ROWS)
                self.sections.addWidget(make_label(more, "muted"))
        self.sections.addStretch(1)

    def _update_header(self) -> None:
        c = self.controller
        color = palette()[STATE_COLOR.get(c.state, "muted")]
        status = f'<span style="color:{color}">●</span>&nbsp;{state_text(c.state)}'
        self.status_label.setText(status)
        parts = [c.config.watch_folder or tr("activity_no_folder")]
        if c.busy:
            parts.append(tr("activity_sync_running"))
        elif c.auth_blocked:
            parts.append(tr("activity_auto_sync_suspended"))
        elif not c.config.paused:
            parts.append(tr("activity_next_sync", minutes=max(1, round(c.seconds_until_next_cycle() / 60))))
        if c.message and c.state not in ("ok", "syncing"):
            parts.append(render(c.message))
        self.detail_label.setText(" · ".join(parts))
        self.sync_button.setEnabled(not c.busy)

    def _attention_row(self, entry: Entry) -> Row:
        if entry.status is Status.SANS_REGLE:
            button = QPushButton(tr("activity_create_rule"))
            button.clicked.connect(lambda _=False, name=entry.filename: self.create_rule_requested.emit(Path(name).stem))
        elif entry.status is Status.REGLE_CASSEE:
            button = QPushButton(tr("activity_edit_rules"))
            button.clicked.connect(lambda _=False: self.edit_rules_requested.emit())
        else:
            button = QPushButton(tr("common_retry"))
            button.clicked.connect(lambda _=False, h=entry.hash: self.controller.retry(h))
        return Row(entry.filename, render(entry.last_error) or tr("err_no_rule"), button)

    def _ignored_row(self, entry: Entry) -> Row:
        button = QPushButton(tr("activity_publish_anyway"))
        button.clicked.connect(lambda _=False, h=entry.hash: self.controller.publish_anyway(h))
        return Row(entry.filename, tr("activity_present_before"), button)

    def _recent_row(self, entry: Entry) -> Row:
        when = datetime.fromtimestamp(entry.updated_at).strftime("%d/%m %H:%M")
        subtitle = f"{entry.show_name} · {when}" if entry.show_name else when
        if entry.status is Status.EN_COURS:
            percent = self.controller.progress.get(episode_title(Path(entry.filename)), 0)
            badge = pill(tr("activity_uploading", percent=percent), "info")
        elif entry.status is Status.PUBLIE:
            badge = pill(tr("activity_published"), "success")
        elif entry.status is Status.DEJA_PRESENT:
            badge = pill(tr("activity_already_on_ausha"), "neutral")
        elif entry.attempts:
            badge = pill(tr("activity_retry_next_sync"), "warning")
            subtitle = f"{subtitle} · {render(entry.last_error)}"
        else:
            badge = pill(tr("activity_waiting"), "neutral")
        return Row(Path(entry.filename).stem, subtitle, badge)
