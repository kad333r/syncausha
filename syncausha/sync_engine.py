"""Un cycle de synchronisation : dossier → règles → Ausha. Aucune dépendance à Qt."""
from __future__ import annotations

import html
import logging
import threading
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from syncausha.ausha_client import (
    AushaClient,
    AushaError,
    AuthError,
    Cancelled,
    Episode,
    RejectedError,
    TransientError,
)
from syncausha.config import Config, Rule
from syncausha.journal import FINAL_STATUSES, Entry, Journal, Status, Step
from syncausha.rules import episode_description, episode_title, find_rule, validate_rule
from syncausha.scanner import ReadyFile, scan_ready_files

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STOP_MESSAGE = "Arrêt demandé"


@dataclass(frozen=True)
class Event:
    """Événement par fichier : progress, published, no_rule, broken_rule, rejected, failed, dry_run."""

    kind: str
    title: str
    detail: str = ""
    percent: int = 0


@dataclass(frozen=True)
class CycleResult:
    """État global après un cycle : ok, attention, paused, not_configured, folder_missing, auth_error, offline."""

    state: str
    message: str = ""


class SyncEngine:
    def __init__(
        self,
        config: Config,
        journal: Journal,
        client_factory: Callable[[Config, threading.Event], AushaClient | None],
        on_event: Callable[[Event], None] = lambda event: None,
        scan: Callable[[Path], list[ReadyFile]] = scan_ready_files,
    ) -> None:
        self.config = config
        self.journal = journal
        self._client_factory = client_factory
        self._on_event = on_event
        self._scan = scan
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        """Interrompt le cycle en cours et les suivants (fermeture de l'application)."""
        self.cancel_event.set()

    def run_cycle(self) -> CycleResult:
        config = self.config
        if config.paused:
            return CycleResult("paused")
        if not config.watch_folder:
            return CycleResult("not_configured", "Choisissez le dossier à surveiller.")
        folder = Path(config.watch_folder)
        if not folder.is_dir():
            return CycleResult("folder_missing", f"Dossier introuvable : {folder}")
        try:
            client = self._client_factory(config, self.cancel_event)
        except AuthError as exc:
            log.warning("Jeton Ausha inutilisable : %s", exc)
            return CycleResult("auth_error", str(exc))
        if client is None:
            return CycleResult("not_configured", "Renseignez votre jeton Ausha.")
        try:
            return self._run(config, folder, client)
        except Cancelled:
            log.info("Synchronisation interrompue")
            return CycleResult("paused", STOP_MESSAGE)
        except AuthError as exc:
            log.warning("Jeton refusé par Ausha : %s", exc)
            return CycleResult("auth_error", str(exc))
        except AushaError as exc:
            log.warning("Ausha injoignable : %s", exc)
            return CycleResult("offline", str(exc))
        finally:
            client.close()

    def _run(self, config: Config, folder: Path, client: AushaClient) -> CycleResult:
        try:
            ready_files = self._scan(folder)
        except OSError as exc:
            return _folder_unreadable(folder, exc)
        catalog: dict[int, set[int]] | None = None  # chargé au premier fichier qui a du travail
        seen: set[str] = set()
        hashed_names: set[str] = set()
        for ready in ready_files:
            if self.cancel_event.is_set():
                return CycleResult("paused", STOP_MESSAGE)
            if self.config.paused:
                return CycleResult("paused")
            try:
                file_hash = self.journal.file_hash(ready.path, ready.size, ready.mtime)
            except OSError as exc:
                log.warning("Lecture impossible de %s : %s", ready.path, exc)
                continue
            seen.add(file_hash)
            hashed_names.add(ready.path.name)
            entry = self.journal.get(file_hash)
            if entry is not None and entry.status in FINAL_STATUSES:
                continue
            if catalog is None:
                catalog = self._load_catalog(client, config.rules)
            try:
                self._process(config, client, catalog, ready, file_hash)
            except (AuthError, Cancelled):
                raise
            except Exception as exc:
                log.exception("Erreur inattendue sur %s", ready.path.name)
                self._record_failure(file_hash, episode_title(ready.path), f"Erreur inattendue : {exc}")
        try:
            present = {path.name for path in folder.iterdir()}
        except OSError as exc:
            return _folder_unreadable(folder, exc)
        # Un fichier réexporté sous le même nom (nouveau hash) libère l'entrée de l'ancienne version.
        self.journal.forget_unresolved(seen, present - hashed_names)
        attention = self.journal.needing_attention()
        if attention:
            return CycleResult("attention", f"{len(attention)} fichier(s) à traiter")
        return CycleResult("ok")

    def _load_catalog(self, client: AushaClient, rules: list[Rule]) -> dict[int, set[int]]:
        """Émissions accessibles utilisées par les règles → ids de leurs playlists.

        Une émission dont Ausha refuse les playlists est laissée de côté : ses règles
        deviennent « à corriger » sans bloquer les autres émissions.
        """
        available = {show.id for show in client.list_shows()}
        catalog: dict[int, set[int]] = {}
        for show_id in {rule.show_id for rule in rules} & available:
            try:
                catalog[show_id] = {p.id for p in client.list_playlists(show_id)}
            except RejectedError as exc:
                log.warning("Playlists de l'émission %s refusées par Ausha : %s", show_id, exc)
        return catalog

    def _process(self, config: Config, client: AushaClient, catalog: dict[int, set[int]], ready: ReadyFile, file_hash: str) -> None:
        entry = self.journal.ensure(file_hash, ready.path.name, ready.size)
        title = episode_title(ready.path)
        rule = find_rule(ready.path.name, config.rules)
        if rule is None:
            self._flag(entry, Status.SANS_REGLE, "Aucune règle ne correspond", "no_rule", title)
            return
        problem = validate_rule(rule, catalog)
        if problem:
            self._flag(entry, Status.REGLE_CASSEE, problem, "broken_rule", title)
            return
        if config.dry_run:
            self.journal.update(file_hash, status=Status.EN_ATTENTE, last_error="")
            self._guarded(file_hash, title, lambda: self._dry_run(client, rule, entry, title))
            return
        self.journal.update(file_hash, status=Status.EN_COURS, show_id=rule.show_id, show_name=rule.show_name, last_error="")
        self._guarded(file_hash, title, lambda: self._publish(client, rule, ready, entry, title))

    def _guarded(self, file_hash: str, title: str, action: Callable[[], None]) -> None:
        """Exécute action et range les erreurs Ausha dans le journal (Auth et annulation remontent)."""
        try:
            action()
        except RejectedError as exc:
            self.journal.update(file_hash, status=Status.REJETE, last_error=str(exc))
            self._emit(Event("rejected", title, str(exc)))
        except TransientError as exc:
            self._record_failure(file_hash, title, str(exc))
        except (AuthError, Cancelled):
            self.journal.update(file_hash, status=Status.EN_ATTENTE)  # jamais « en cours » figé
            raise

    def _dry_run(self, client: AushaClient, rule: Rule, entry: Entry, title: str) -> None:
        """Simulation : les mêmes lectures qu'une publication, aucune écriture sur Ausha."""
        if entry.step is Step.NONE and self._find_same_title(client, rule.show_id, title):
            detail = "Déjà présent sur Ausha — ne serait pas publié"
        else:
            detail = f"Serait publié dans {rule.show_name or rule.show_id}"
        self._emit(Event("dry_run", title, detail))

    def _publish(self, client: AushaClient, rule: Rule, ready: ReadyFile, entry: Entry, title: str) -> None:
        """Enchaîne les étapes restantes ; chaque étape réussie est notée pour pouvoir reprendre."""
        file_hash, step, episode_id = entry.hash, entry.step, entry.episode_id
        if step in (Step.NONE, Step.UPLOADING):
            existing = self._find_same_title(client, rule.show_id, title)
            if existing is not None and step is Step.NONE:
                self.journal.update(file_hash, status=Status.DEJA_PRESENT)
                return
            if existing is not None:
                # La réponse à la création s'était perdue : l'épisode existe, on le reprend.
                log.info("Épisode « %s » retrouvé sur Ausha (id %s)", title, existing.id)
                episode_id = existing.id
            else:
                episode_id = self._create(client, rule, ready, file_hash, title)
            self.journal.update(file_hash, episode_id=episode_id, step=Step.CREATED, attempts=0)
            step = Step.CREATED
        if step is Step.CREATED:
            if rule.image_path:
                client.upload_episode_image(episode_id, Path(rule.image_path))
            self.journal.update(file_hash, step=Step.IMAGE_DONE, attempts=0)
            step = Step.IMAGE_DONE
        if step is Step.IMAGE_DONE:
            if rule.playlist_id is not None:
                client.add_to_playlist(rule.playlist_id, episode_id)
            self.journal.update(file_hash, step=Step.PLAYLIST_DONE, attempts=0)
        self.journal.update(file_hash, status=Status.PUBLIE, attempts=0, last_error="")
        self._emit(Event("published", title, rule.show_name))

    def _create(self, client: AushaClient, rule: Rule, ready: ReadyFile, file_hash: str, title: str) -> int:
        """Envoie l'épisode. L'étape « uploading » est notée avant : si la réponse se perd,
        le cycle suivant cherche l'épisode sur Ausha au lieu de le recréer."""
        self.journal.update(file_hash, step=Step.UPLOADING)
        try:
            return client.create_episode(
                rule.show_id,
                title,
                episode_description(rule),
                ready.path,
                on_progress=lambda percent: self._emit(Event("progress", title, percent=percent)),
            )
        except RejectedError:
            self.journal.update(file_hash, step=Step.NONE)  # refusé : rien n'a été créé
            raise

    @staticmethod
    def _find_same_title(client: AushaClient, show_id: int, title: str) -> Episode | None:
        return next((e for e in client.find_episodes(show_id, title) if _same_title(e.name, title)), None)

    def _flag(self, entry: Entry, status: Status, message: str, kind: str, title: str) -> None:
        """Marque un fichier bloqué ; ne notifie qu'au changement de statut."""
        if entry.status is not status:
            self._emit(Event(kind, title, message))
        self.journal.update(entry.hash, status=status, last_error=message)

    def _record_failure(self, file_hash: str, title: str, message: str) -> None:
        entry = self.journal.get(file_hash)
        attempts = (entry.attempts if entry else 0) + 1
        if attempts >= MAX_ATTEMPTS:
            self.journal.update(file_hash, status=Status.ECHEC, attempts=attempts, last_error=message)
            self._emit(Event("failed", title, message))
        else:
            self.journal.update(file_hash, status=Status.EN_ATTENTE, attempts=attempts, last_error=message)

    def _emit(self, event: Event) -> None:
        try:
            self._on_event(event)
        except Exception:
            log.exception("Gestionnaire d'événement en erreur")


def _same_title(a: str, b: str) -> bool:
    """Titres égaux aux entités HTML, à la forme Unicode, aux espaces et à la casse près."""
    return _title_key(a) == _title_key(b)


def _title_key(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", html.unescape(text)).split()).casefold()


def _folder_unreadable(folder: Path, exc: OSError) -> CycleResult:
    log.warning("Dossier illisible %s : %s", folder, exc)
    return CycleResult("folder_missing", f"Dossier introuvable : {folder}")
