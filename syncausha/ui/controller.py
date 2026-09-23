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
    "partial": ("Publié avec un problème", "{title} : {detail}"),
    "failed": ("Échec de l'envoi", "{title} : {detail}"),
}
NO_RULE_GROUPED = ("Fichiers sans règle", "{count} fichiers n'ont pas été envoyés : aucune règle ne correspond.")
BASELINE_NOTIFICATION = (
    "Dossier pris en compte",
    "{count} fichier(s) déjà présent(s) ignoré(s). Seuls les nouveaux fichiers seront publiés.",
)
PROGRESS_STEP = 5  # points de pourcentage entre deux rafraîchissements de l'affichage
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
        self.busy = False
        self._rerun_requested = False
        self.auth_blocked = False
        self.progress: dict[str, int] = {}
        self.dry_run_lines: list[str] = []
        self._pending_dry_run: list[str] = []
        self._no_rule_titles: list[str] = []
        self._last_result_state = ""
        self.state, self.message = self._idle_state()

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
        self._no_rule_titles = []
        self._set_state("syncing", "")
        self._start_cycle.emit()
        self._restart_timer()

    def seconds_until_next_cycle(self) -> int:
        return max(0, self._timer.remainingTime() // 1000)

    def retry(self, file_hash: str) -> None:
        self.journal.reset_for_retry(file_hash)
        self.activity_changed.emit()
        self.sync_now()

    def publish_anyway(self, file_hash: str) -> None:
        """Publie un fichier ignoré car déjà présent au choix du dossier."""
        self.retry(file_hash)

    def _on_timer(self) -> None:
        # Un passage du minuteur pendant un cycle, en pause ou avec un jeton refusé est ignoré.
        if not (self.auth_blocked or self.busy or self.config.paused):
            self.sync_now()

    def _restart_timer(self) -> None:
        self._timer.start(self.config.interval_minutes * 60_000)

    @Slot(object)
    def _on_engine_event(self, event: Event) -> None:
        if event.kind == "progress":
            self._on_progress(event.title, event.percent)
            return
        if event.kind == "dry_run":
            self._pending_dry_run.append(f"{event.title} — {event.detail}")
            return
        self.progress.pop(event.title, None)
        if event.kind == "no_rule":
            self._no_rule_titles.append(event.title)  # une seule notification en fin de cycle
        elif template := FILE_NOTIFICATIONS.get(event.kind):
            self.notification.emit(template[0], template[1].format(title=event.title, detail=event.detail))
        self.activity_changed.emit()

    def _on_progress(self, title: str, percent: int) -> None:
        """Ne rafraîchit l'affichage que tous les 5 points, et à 100 %."""
        last = self.progress.get(title)
        if percent == last or (last is not None and abs(percent - last) < PROGRESS_STEP and percent < 100):
            return
        self.progress[title] = percent
        self.progress_changed.emit(title, percent)

    def _notify_files_without_rule(self) -> None:
        titles, self._no_rule_titles = self._no_rule_titles, []
        if len(titles) == 1:
            title, body = FILE_NOTIFICATIONS["no_rule"]
            self.notification.emit(title, body.format(title=titles[0]))
        elif titles:
            self.notification.emit(NO_RULE_GROUPED[0], NO_RULE_GROUPED[1].format(count=len(titles)))

    @Slot(object)
    def _on_cycle_finished(self, result: CycleResult) -> None:
        self.busy = False
        self.progress.clear()
        self._notify_files_without_rule()
        if result.state == "baseline":
            self._on_baseline(result)
            return
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

    def _on_baseline(self, result: CycleResult) -> None:
        """Fichiers déjà présents ignorés : le dossier est noté comme pris en compte, puis le vrai cycle suit."""
        if result.folder == self.config.watch_folder:  # sinon le dossier a changé : nouvel état des lieux
            if not self.update_config(replace(self.config, baseline_folder=result.folder)):
                self._set_state("not_configured", "Réglages non enregistrés")
                return
            if result.count:
                title, body = BASELINE_NOTIFICATION
                self.notification.emit(title, body.format(count=result.count))
        if self.config.paused:
            self._set_state("paused", "")
        else:
            self.sync_now()

    def _set_state(self, state: str, message: str) -> None:
        self.state, self.message = state, message
        self.state_changed.emit(state, message)

    def _idle_state(self) -> tuple[str, str]:
        """État hors cycle (démarrage, reprise après une pause), déduit des réglages et du journal."""
        if not self.has_token():
            return "not_configured", "Renseignez votre jeton Ausha."
        if not self.config.watch_folder:
            return "not_configured", "Choisissez le dossier à surveiller."
        attention = self.journal.needing_attention()
        if attention:
            return "attention", f"{len(attention)} fichier(s) à traiter"
        if self.config.paused:
            return "paused", ""
        return "ok", ""

    # --- Réglages ------------------------------------------------------------

    def has_token(self) -> bool:
        return get_token() is not None

    def update_config(self, config: Config) -> bool:
        """Enregistre et applique de nouveaux réglages. Ne jamais muter self.config en place.

        Si l'écriture échoue, les réglages précédents restent en vigueur, l'utilisateur est
        prévenu et False est renvoyé.
        """
        previous = self.config
        try:
            save_config(config, self.config_path)
        except OSError as exc:
            log.error("Réglages non enregistrés : %s", exc)
            self.notification.emit("Réglages non enregistrés", str(exc))
            return False
        self.config = config
        self.engine.config = config
        if config.interval_minutes != previous.interval_minutes:
            self._restart_timer()
        if config.watch_folder != previous.watch_folder:
            self._last_result_state = ""  # un dossier toujours introuvable sera de nouveau signalé
        if config.paused:
            self._set_state("paused", "")
        elif previous.paused:
            self._set_state(*(("syncing", "") if self.busy else self._idle_state()))
        self.activity_changed.emit()
        return True

    def update_token(self, token: str) -> None:
        set_token(token)
        self.auth_blocked = False
        self._last_result_state = ""  # un jeton toujours invalide sera de nouveau signalé

    def set_paused(self, paused: bool) -> None:
        if self.update_config(replace(self.config, paused=paused)) and not paused:
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
