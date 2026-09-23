"""Chef d'orchestre : minuteur, thread de synchro, réglages, notifications."""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from syncausha.ausha_client import AushaClient, AuthError, Playlist, RejectedError, Show
from syncausha.config import Config, get_token, load_config, save_config, set_token
from syncausha.journal import Journal
from syncausha.sync_engine import CycleResult, Event, SyncEngine
from syncausha.ui.async_call import run_async

log = logging.getLogger(__name__)

FIRST_CYCLE_DELAY_MS = 10_000
FILE_NOTIFICATIONS = {
    "published": ("Épisode publié", "{title} · {detail}"),
    "no_rule": ("Aucune règle", "{title} n'a pas été envoyé : aucune règle ne correspond."),
    "broken_rule": ("Règle à corriger", "{title} : {detail}"),
    "rejected": ("Refusé par Ausha", "{title} : {detail}"),
    "failed": ("Échec de l'envoi", "{title} : {detail}"),
}
STATE_NOTIFICATIONS = {
    "auth_error": ("Jeton Ausha invalide", "Mettez à jour votre jeton dans les réglages."),
    "folder_missing": ("Dossier introuvable", "{message}"),
}

Catalog = dict[Show, list[Playlist]]


class CycleWorker(QObject):
    """Vit dans le thread de synchro ; exécute un cycle à la demande."""

    finished = Signal(object)

    def __init__(self, engine: SyncEngine) -> None:
        super().__init__()
        self._engine = engine

    @Slot()
    def run(self) -> None:
        try:
            result = self._engine.run_cycle()
        except Exception as exc:
            log.exception("Cycle interrompu")
            result = CycleResult("offline", str(exc))
        self.finished.emit(result)


class AppController(QObject):
    state_changed = Signal(str, str)
    activity_changed = Signal()
    progress_changed = Signal(str, int)
    notification = Signal(str, str)
    _engine_event = Signal(object)
    _start_cycle = Signal()

    def __init__(self, config_path: Path, journal: Journal, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config_path = config_path
        self.config = load_config(config_path)
        self.journal = journal
        self.state, self.message = ("paused" if self.config.paused else "ok"), ""
        self.busy = False
        self._rerun_requested = False
        self.auth_blocked = False
        self.progress: dict[str, int] = {}
        self.dry_run_lines: list[str] = []
        self._pending_dry_run: list[str] = []
        self._last_result_state = ""

        self.engine = SyncEngine(self.config, journal, self._make_client, on_event=self._engine_event.emit)
        self._engine_event.connect(self._on_engine_event)

        self._thread = QThread(self)
        self._worker = CycleWorker(self.engine)
        self._worker.moveToThread(self._thread)
        self._start_cycle.connect(self._worker.run)
        self._worker.finished.connect(self._on_cycle_finished)
        self._thread.start()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._restart_timer()

    @staticmethod
    def _make_client(config: Config, cancel_event: threading.Event) -> AushaClient | None:
        token = get_token()
        return AushaClient(token, config.api_base_url, cancel=cancel_event) if token else None

    # --- Synchro -------------------------------------------------------------

    def start(self) -> None:
        QTimer.singleShot(FIRST_CYCLE_DELAY_MS, self._on_timer)

    def sync_now(self) -> None:
        if self.busy:
            self._rerun_requested = True  # relancé dès la fin du cycle en cours
            return
        self._rerun_requested = False
        self.busy = True
        self._pending_dry_run = []
        self._set_state("syncing", "")
        self._start_cycle.emit()
        self._restart_timer()

    def seconds_until_next_cycle(self) -> int:
        return max(0, self._timer.remainingTime() // 1000)

    def retry(self, file_hash: str) -> None:
        self.journal.reset_for_retry(file_hash)
        self.activity_changed.emit()
        self.sync_now()

    def _on_timer(self) -> None:
        # Un passage du minuteur pendant un cycle est simplement ignoré.
        if not self.auth_blocked and not self.busy:
            self.sync_now()

    def _restart_timer(self) -> None:
        self._timer.start(self.config.interval_minutes * 60_000)

    @Slot(object)
    def _on_engine_event(self, event: Event) -> None:
        if event.kind == "progress":
            self.progress[event.title] = event.percent
            self.progress_changed.emit(event.title, event.percent)
            return
        if event.kind == "dry_run":
            self._pending_dry_run.append(f"{event.title} — {event.detail}")
            return
        self.progress.pop(event.title, None)
        template = FILE_NOTIFICATIONS.get(event.kind)
        if template:
            self.notification.emit(template[0], template[1].format(title=event.title, detail=event.detail))
        self.activity_changed.emit()

    @Slot(object)
    def _on_cycle_finished(self, result: CycleResult) -> None:
        self.busy = False
        self.progress.clear()
        self.dry_run_lines = self._pending_dry_run if self.config.dry_run else []
        self.auth_blocked = result.state == "auth_error"
        if result.state != self._last_result_state and result.state in STATE_NOTIFICATIONS:
            title, body = STATE_NOTIFICATIONS[result.state]
            self.notification.emit(title, body.format(message=result.message))
        self._last_result_state = result.state
        if self.config.paused:  # mis en pause pendant le cycle
            self._set_state("paused", "")
        else:
            self._set_state(result.state, result.message)
        self.activity_changed.emit()
        if self._rerun_requested:
            self.sync_now()

    def _set_state(self, state: str, message: str) -> None:
        self.state, self.message = state, message
        self.state_changed.emit(state, message)

    # --- Réglages ------------------------------------------------------------

    def has_token(self) -> bool:
        return get_token() is not None

    def update_config(self, config: Config) -> None:
        """Enregistre et applique de nouveaux réglages. Ne jamais muter self.config en place."""
        previous = self.config
        save_config(config, self.config_path)
        self.config = config
        self.engine.config = config
        if config.interval_minutes != previous.interval_minutes:
            self._restart_timer()
        if config.watch_folder != previous.watch_folder:
            self._last_result_state = ""  # un dossier toujours introuvable sera de nouveau signalé
        if config.paused:
            self._set_state("paused", "")
        self.activity_changed.emit()

    def update_token(self, token: str) -> None:
        set_token(token)
        self.auth_blocked = False
        self._last_result_state = ""  # un jeton toujours invalide sera de nouveau signalé

    def set_paused(self, paused: bool) -> None:
        self.update_config(replace(self.config, paused=paused))
        if not paused:
            self.sync_now()

    # --- Ausha (hors thread UI) ---------------------------------------------

    def fetch_catalog(
        self,
        on_done: Callable[[Catalog], None],
        on_failed: Callable[[Exception], None],
        token: str | None = None,
    ) -> None:
        """Charge émissions et playlists en arrière-plan (token : jeton à tester, sinon celui enregistré)."""
        token = token or get_token()
        base_url = self.config.api_base_url

        def load() -> Catalog:
            if not token:
                raise AuthError("Aucun jeton Ausha enregistré.")
            with AushaClient(token, base_url) as client:
                return {show: _playlists(client, show) for show in client.list_shows()}

        run_async(load, on_done, on_failed)

    def shutdown(self) -> bool:
        """Interrompt l'envoi en cours (reprise au prochain lancement) puis arrête le thread.

        Renvoie False si le thread tourne encore après 15 s (réponse d'Ausha attendue).
        """
        self.engine.cancel()
        self._timer.stop()
        self._thread.quit()
        return self._thread.wait(15000)


def _playlists(client: AushaClient, show: Show) -> list[Playlist]:
    """Playlists de l'émission ; une émission dont Ausha les refuse reste proposée, sans playlist."""
    try:
        return client.list_playlists(show.id)
    except RejectedError as exc:
        log.warning("Playlists de l'émission %s refusées par Ausha : %s", show.id, exc)
        return []
