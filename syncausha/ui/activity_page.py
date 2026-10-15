"""Page Activité : état, fichiers à traiter, historique récent, fichiers ignorés."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDateTime, QLocale, Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget

from syncausha.config import ShowFolder, folder_key, same_folder
from syncausha.i18n import msg, render, tr
from syncausha.journal import Entry, Status
from syncausha.rules import episode_title, find_match
from syncausha.ui.controller import AppController, MissingFolder, watched_shows
from syncausha.ui.style import palette
from syncausha.ui.widgets import Row, bidi_text, clear_layout, isolate, joined, make_label, pill, section_label

# Clés des textes d'état, traduites à l'affichage (la langue peut changer en cours de route).
STATE_KEYS = {
    "ok": "state_ok",
    "syncing": "state_syncing",
    "baseline": "state_baseline",
    "attention": "state_attention",
    "paused": "state_paused",
    "not_configured": "state_not_configured",
    "auth_error": "state_auth_error",
    "offline": "state_offline",
}
STATE_COLOR = {
    "ok": "success", "syncing": "info", "baseline": "info", "attention": "warning", "paused": "muted",
    "not_configured": "warning", "auth_error": "danger", "offline": "danger",
}
MAX_IGNORED_ROWS = 20


def state_text(state: str) -> str:
    """Texte de l'état dans la langue active (l'identifiant brut s'il est inconnu)."""
    key = STATE_KEYS.get(state)
    return tr(key) if key else state


def format_time(timestamp: float) -> str:
    """Date et heure courtes au format de la langue (QLocale par défaut, réglée par apply_language : chiffres
    0-9 en arabe aussi)."""
    return QLocale().toString(QDateTime.fromSecsSinceEpoch(int(timestamp)), QLocale.FormatType.ShortFormat)


class ActivityPage(QWidget):
    create_rule_requested = Signal(str, str)  # dossier du fichier, mot-clé proposé
    edit_show_requested = Signal(int)  # position de l'émission dans les réglages, -1 si aucune ne convient

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
        # Écart avec la barre de défilement, de son côté (à gauche en arabe : Qt ne retourne pas les marges).
        rtl = self.layoutDirection() == Qt.LayoutDirection.RightToLeft
        self.sections.setContentsMargins(8 if rtl else 0, 0, 0 if rtl else 8, 0)
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
        missing = self.controller.missing_folders
        if attention or missing:
            self.sections.addWidget(section_label(tr("activity_section_attention")))
            for item in missing:
                self.sections.addWidget(self._missing_folder_row(item))
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
        status = f'<span style="color:{color}">●</span>&nbsp;{bidi_text(state_text(c.state))}'
        self.status_label.setText(status)
        parts = [tr("activity_shows_watched", n=len(watched_shows(c.config)))]
        if c.busy:
            parts.append(tr("activity_sync_running"))
        elif c.auth_blocked:
            parts.append(tr("activity_auto_sync_suspended"))
        elif not c.config.paused:
            parts.append(tr("activity_next_sync", minutes=max(1, round(c.seconds_until_next_cycle() / 60))))
        if c.message and c.state not in ("ok", "syncing"):
            parts.append(render(c.message))
        self.detail_label.setText(joined(parts))
        self.sync_button.setEnabled(not c.busy)

    def _shows_in(self, folder: str) -> list[tuple[int, ShowFolder]]:
        """(position, émission) des émissions qui surveillent ce dossier, dans l'ordre des réglages."""
        return [(i, show) for i, show in enumerate(self.controller.config.shows) if same_folder(show.folder, folder)]

    def _missing_folder_row(self, item: MissingFolder) -> Row:
        """Dossier introuvable : « Modifier l'émission » ouvre celle qui le surveille (même dossier, même nom)."""
        folder, label = item
        in_folder = self._shows_in(folder)
        named = [i for i, show in in_folder if show.label() == label]
        index = (named or [i for i, _ in in_folder] or [-1])[0]
        button = QPushButton(tr("activity_edit_show"))
        button.clicked.connect(lambda _=False, i=index: self.edit_show_requested.emit(i))
        return Row(render(msg("cycle_folder_missing_show", folder=folder, show=label)), "", button)

    def _file_folder(self, entry: Entry) -> str:
        """Dossier du fichier. Une ligne du journal 1.0 n'en a pas : le seul dossier surveillé s'il n'y en a qu'un
        (celui des réglages 1.0), sinon aucun."""
        if entry.folder:
            return entry.folder
        watched = watched_shows(self.controller.config)
        return watched[0].folder if len({folder_key(show.folder) for show in watched}) == 1 else ""

    def _matching_show(self, entry: Entry) -> int:
        """Émission du dossier du fichier dont un mot-clé correspond (celle qui l'a pris), sinon la première de
        ce dossier, sinon -1."""
        in_folder = self._shows_in(self._file_folder(entry))
        matched = [i for i, show in in_folder if find_match(entry.filename, [show])]
        return (matched or [i for i, _ in in_folder] or [-1])[0]

    def _attention_row(self, entry: Entry) -> Row:
        if entry.status is Status.SANS_REGLE:
            button = QPushButton(tr("activity_create_rule"))
            button.clicked.connect(
                lambda _=False, e=entry: self.create_rule_requested.emit(self._file_folder(e), Path(e.filename).stem)
            )
        elif entry.status is Status.REGLE_CASSEE:
            button = QPushButton(tr("activity_edit_show"))
            button.clicked.connect(lambda _=False, i=self._matching_show(entry): self.edit_show_requested.emit(i))
        else:
            button = QPushButton(tr("common_retry"))
            button.clicked.connect(lambda _=False, h=entry.hash: self.controller.retry(h))
        return Row(entry.filename, render(entry.last_error) or tr("err_no_rule"), button)

    def _ignored_row(self, entry: Entry) -> Row:
        button = QPushButton(tr("activity_publish_anyway"))
        button.clicked.connect(lambda _=False, h=entry.hash: self.controller.publish_anyway(h))
        return Row(entry.filename, tr("activity_present_before"), button)

    def _recent_row(self, entry: Entry) -> Row:
        when = format_time(entry.updated_at)
        parts = [isolate(entry.show_name), when] if entry.show_name else [when]
        if entry.status is Status.EN_COURS:
            percent = self.controller.progress.get(episode_title(Path(entry.filename)), 0)
            badge = pill(tr("activity_uploading", percent=percent), "info")
        elif entry.status is Status.PUBLIE:
            badge = pill(tr("activity_published"), "success")
        elif entry.status is Status.DEJA_PRESENT:
            badge = pill(tr("activity_already_on_ausha"), "neutral")
        elif entry.attempts:
            badge = pill(tr("activity_retry_next_sync"), "warning")
            parts.append(render(entry.last_error))
        else:
            badge = pill(tr("activity_waiting"), "neutral")
        return Row(Path(entry.filename).stem, joined(parts), badge)
