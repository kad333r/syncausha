"""Un cycle de synchronisation : dossier → règles → Ausha. Aucune dépendance à Qt."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from syncausha.ausha_client import AushaClient, AushaError, AuthError, RejectedError, TransientError
from syncausha.config import Config, Rule
from syncausha.journal import FINAL_STATUSES, Entry, Journal, Status, Step
from syncausha.rules import episode_description, episode_title, find_rule, validate_rule
from syncausha.scanner import ReadyFile, scan_ready_files

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


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
        client_factory: Callable[[Config], AushaClient | None],
        on_event: Callable[[Event], None] = lambda event: None,
        scan: Callable[[Path], list[ReadyFile]] = scan_ready_files,
    ) -> None:
        self.config = config
        self.journal = journal
        self._client_factory = client_factory
        self._on_event = on_event
        self._scan = scan

    def run_cycle(self) -> CycleResult:
        config = self.config
        if config.paused:
            return CycleResult("paused")
        if not config.watch_folder:
            return CycleResult("not_configured", "Choisissez le dossier à surveiller.")
        folder = Path(config.watch_folder)
        if not folder.is_dir():
            return CycleResult("folder_missing", f"Dossier introuvable : {folder}")
        client = self._client_factory(config)
        if client is None:
            return CycleResult("not_configured", "Renseignez votre jeton Ausha.")
        try:
            return self._run(config, folder, client)
        except AuthError as exc:
            log.warning("Jeton refusé par Ausha : %s", exc)
            return CycleResult("auth_error", str(exc))
        except AushaError as exc:
            log.warning("Ausha injoignable : %s", exc)
            return CycleResult("offline", str(exc))
        finally:
            client.close()

    def _run(self, config: Config, folder: Path, client: AushaClient) -> CycleResult:
        catalog = self._load_catalog(client, config.rules)
        seen: set[str] = set()
        for ready in self._scan(folder):
            try:
                file_hash = self.journal.file_hash(ready.path, ready.size, ready.mtime)
            except OSError as exc:
                log.warning("Lecture impossible de %s : %s", ready.path, exc)
                continue
            seen.add(file_hash)
            try:
                self._process(config, client, catalog, ready, file_hash)
            except AuthError:
                raise
            except Exception as exc:
                log.exception("Erreur inattendue sur %s", ready.path.name)
                self._record_failure(file_hash, episode_title(ready.path), f"Erreur inattendue : {exc}")
        self.journal.forget_unresolved(seen, {path.name for path in folder.iterdir()})
        attention = self.journal.needing_attention()
        if attention:
            return CycleResult("attention", f"{len(attention)} fichier(s) à traiter")
        return CycleResult("ok")

    def _load_catalog(self, client: AushaClient, rules: list[Rule]) -> dict[int, set[int]]:
        """Émissions accessibles utilisées par les règles → ids de leurs playlists."""
        available = {show.id for show in client.list_shows()}
        wanted = {rule.show_id for rule in rules} & available
        return {show_id: {p.id for p in client.list_playlists(show_id)} for show_id in wanted}

    def _process(self, config: Config, client: AushaClient, catalog: dict[int, set[int]], ready: ReadyFile, file_hash: str) -> None:
        entry = self.journal.ensure(file_hash, ready.path.name, ready.size)
        if entry.status in FINAL_STATUSES:
            return
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
            self._emit(Event("dry_run", title, f"Serait publié dans {rule.show_name or rule.show_id}"))
            return
        self.journal.update(file_hash, status=Status.EN_COURS, show_id=rule.show_id, show_name=rule.show_name, last_error="")
        try:
            self._publish(client, rule, ready, entry, title)
        except RejectedError as exc:
            self.journal.update(file_hash, status=Status.REJETE, last_error=str(exc))
            self._emit(Event("rejected", title, str(exc)))
        except TransientError as exc:
            self._record_failure(file_hash, title, str(exc))

    def _publish(self, client: AushaClient, rule: Rule, ready: ReadyFile, entry: Entry, title: str) -> None:
        """Enchaîne les étapes restantes ; chaque étape réussie est notée pour pouvoir reprendre."""
        file_hash, step, episode_id = entry.hash, entry.step, entry.episode_id
        if step is Step.NONE:
            existing = client.find_episodes(rule.show_id, title)
            if any(episode.name.casefold() == title.casefold() for episode in existing):
                self.journal.update(file_hash, status=Status.DEJA_PRESENT)
                return
            episode_id = client.create_episode(
                rule.show_id,
                title,
                episode_description(rule),
                ready.path,
                on_progress=lambda percent: self._emit(Event("progress", title, percent=percent)),
            )
            self.journal.update(file_hash, episode_id=episode_id, step=Step.CREATED)
            step = Step.CREATED
        if step is Step.CREATED:
            if rule.image_path:
                client.upload_episode_image(episode_id, Path(rule.image_path))
            self.journal.update(file_hash, step=Step.IMAGE_DONE)
            step = Step.IMAGE_DONE
        if step is Step.IMAGE_DONE:
            if rule.playlist_id is not None:
                client.add_to_playlist(rule.playlist_id, episode_id)
            self.journal.update(file_hash, step=Step.PLAYLIST_DONE)
        self.journal.update(file_hash, status=Status.PUBLIE, attempts=0, last_error="")
        self._emit(Event("published", title, rule.show_name))

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
