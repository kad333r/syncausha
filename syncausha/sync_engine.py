"""Un cycle de synchronisation : dossiers des émissions → mots-clés → Ausha. Aucune dépendance à Qt."""
from __future__ import annotations

import html
import logging
import threading
import time
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
from syncausha.config import Config, Rule, ShowFolder, same_folder
from syncausha.i18n import msg, render
from syncausha.journal import FINAL_STATUSES, Entry, Journal, Status, Step
from syncausha.rules import episode_description, episode_title, find_match, validate_rule
from syncausha.scanner import ReadyFile, scan_ready_files

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STOP_MESSAGE = msg("cycle_stop_requested")
# Délai avant de recréer un épisode dont la création est restée sans réponse : la recherche
# d'Ausha peut mettre du temps à voir un épisode tout juste créé.
RECREATE_AFTER_SECONDS = 15 * 60
CHECKING_MESSAGE = msg("err_upload_being_checked")
SHOW_CHANGED_MESSAGE = msg("err_rule_show_changed")


@dataclass(frozen=True)
class Event:
    """Événement par fichier : progress, published, no_rule, broken_rule, rejected, partial, failed, dry_run.

    detail : message traduisible (i18n.msg), sauf pour published (nom de l'émission).
    """

    kind: str
    title: str
    detail: str = ""
    percent: int = 0


@dataclass(frozen=True)
class CycleResult:
    """État global après un cycle : ok, attention, paused, not_configured, auth_error, offline,
    ou baseline (count fichiers déjà présents dans les dossiers folders ont été ignorés, rien n'a été publié ;
    chaque dossier est écrit comme dans les réglages).
    message : message traduisible (i18n.msg).
    missing : (dossier, émission) introuvables ou illisibles pendant ce cycle (état attention) ; émission :
    ShowFolder.label(), son nom ou un message à traduire."""

    state: str
    message: str = ""
    count: int = 0
    folders: tuple[str, ...] = ()
    missing: tuple[tuple[str, str], ...] = ()


class PartiallyPublished(RejectedError):
    """Refus d'Ausha après la mise en ligne de l'épisode (image, playlist)."""


class SyncEngine:
    def __init__(
        self,
        config: Config,
        journal: Journal,
        client_factory: Callable[[Config, threading.Event], AushaClient | None],
        on_event: Callable[[Event], None] = lambda event: None,
        scan: Callable[[Path], list[ReadyFile]] = scan_ready_files,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.config = config
        self.journal = journal
        self._client_factory = client_factory
        self._on_event = on_event
        self._scan = scan
        self._clock = clock
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        """Interrompt le cycle en cours et les suivants (fermeture de l'application)."""
        self.cancel_event.set()

    def run_cycle(self) -> CycleResult:
        config = self.config
        if config.paused:
            return CycleResult("paused")
        shows = [show for show in config.shows if show.folder]
        if not shows:
            return CycleResult("not_configured", msg("cycle_add_show"))
        pending = [show for show in shows if show.needs_baseline()]
        if pending:
            baseline = self._take_baselines(pending, shows)
            if baseline is not None:
                return baseline
        try:
            client = self._client_factory(config, self.cancel_event)
        except AuthError as exc:
            log.warning("Jeton Ausha inutilisable : %s", render(str(exc), lang="fr"))
            return CycleResult("auth_error", str(exc))
        if client is None:
            return CycleResult("not_configured", msg("cycle_enter_token"))
        try:
            return self._run(config, shows, client)
        except Cancelled:
            log.info("Synchronisation interrompue")
            return CycleResult("paused", STOP_MESSAGE)
        except AuthError as exc:
            log.warning("Jeton refusé par Ausha : %s", render(str(exc), lang="fr"))
            return CycleResult("auth_error", str(exc))
        except AushaError as exc:
            log.warning("Ausha injoignable : %s", render(str(exc), lang="fr"))
            return CycleResult("offline", str(exc))
        finally:
            client.close()

    def _take_baselines(self, pending: list[ShowFolder], shows: list[ShowFolder]) -> CycleResult | None:
        """Dossiers tout juste choisis : leurs fichiers prêts sont ignorés (statut « ignore »), sans appel à Ausha.

        folders du résultat : dossiers dont les émissions ont leur état des lieux fait.
        Un dossier partagé par plusieurs émissions n'est lu qu'une fois. Un dossier déjà surveillé et
        inventorié par une autre émission n'est pas relu : rien n'y est ignoré, ses fichiers en attente
        (souvent « sans règle ») sont justement ceux que la nouvelle émission doit publier.
        Un dossier introuvable ou illisible est laissé au cycle normal, qui le signale ; None si aucun
        dossier n'est traité.
        Un fichier encore en cours de copie n'est pas concerné : il sera publié une fois prêt.
        Une entrée déjà envoyée (étape au-delà de « none ») non plus : son épisode existe peut-être.
        """
        count = 0
        folders: list[str] = []
        for folder, _ in _by_folder(pending):
            if any(same_folder(other.folder, folder) and not other.needs_baseline() for other in shows):
                log.info("Dossier %s déjà pris en compte par une autre émission : aucun fichier ignoré", folder)
                folders.append(folder)
                continue
            ready_files = self._ready_files(Path(folder))
            if ready_files is None:
                continue
            ignored = 0
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
                entry = self.journal.get(file_hash)
                if entry is not None and (entry.status in FINAL_STATUSES or entry.step is not Step.NONE):
                    continue
                self.journal.ensure(file_hash, ready.path.name, ready.size, folder=folder)
                self.journal.update(file_hash, status=Status.IGNORE, last_error="")
                ignored += 1
            log.info("Dossier %s pris en compte : %d fichier(s) déjà présent(s) ignoré(s)", folder, ignored)
            count += ignored
            folders.append(folder)
        if not folders:
            return None
        return CycleResult("baseline", msg("cycle_existing_files_ignored", n=count), count, folders=tuple(folders))

    def _run(self, config: Config, shows: list[ShowFolder], client: AushaClient) -> CycleResult:
        """Lit chaque dossier distinct une fois ; un dossier introuvable est signalé sans arrêter les autres."""
        catalog: dict[int, set[int]] | None = None  # chargé au premier fichier qui a du travail
        seen: set[str] = set()
        # Noms présents mais pas lus à ce cycle (fichier pas encore prêt, illisible), dossier par dossier : leur
        # entrée est gardée. Un homonyme lu dans un autre dossier ne compte pas.
        present: set[str] = set()
        missing: list[tuple[str, str]] = []
        for folder, group in _by_folder(shows):
            if any(show.needs_baseline() for show in group):
                # Introuvable pendant l'état des lieux : jamais lu avant qu'il soit fait, même s'il vient
                # d'apparaître, sinon ses fichiers déjà présents seraient publiés.
                missing += _missing(folder, group)
                continue
            ready_files = self._ready_files(Path(folder))
            if ready_files is None:
                missing += _missing(folder, group)
                continue
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
                    catalog = self._load_catalog(client, shows)
                try:
                    self._process(config, client, catalog, ready, file_hash, folder, group)
                except (AuthError, Cancelled):
                    raise
                except Exception as exc:
                    log.exception("Erreur inattendue sur %s", ready.path.name)
                    self._record_failure(file_hash, episode_title(ready.path), msg("err_unexpected", detail=exc))
            try:
                present |= {path.name for path in Path(folder).iterdir()} - hashed_names
            except OSError as exc:
                log.warning("Dossier illisible %s : %s", folder, exc)
                missing += _missing(folder, group)
        if missing:
            # Pas d'oubli tant qu'un dossier manque : ses fichiers ignorés seraient publiés à son retour.
            folder, show = missing[0]
            message = msg("cycle_folder_missing_show", folder=folder, show=show)
            return CycleResult("attention", message, missing=tuple(missing))
        # Un fichier réexporté sous le même nom (nouveau hash) libère l'entrée de l'ancienne version.
        self.journal.forget_unresolved(seen, present)
        attention = self.journal.needing_attention()
        if attention:
            return CycleResult("attention", msg("cycle_files_need_attention", n=len(attention)))
        return CycleResult("ok")

    def _ready_files(self, folder: Path) -> list[ReadyFile] | None:
        """Fichiers prêts du dossier, ou None s'il est introuvable ou illisible."""
        if not folder.is_dir():
            log.warning("Dossier introuvable : %s", folder)
            return None
        try:
            return self._scan(folder)
        except OSError as exc:
            log.warning("Dossier illisible %s : %s", folder, exc)
            return None

    def _load_catalog(self, client: AushaClient, shows: list[ShowFolder]) -> dict[int, set[int]]:
        """Émissions configurées et accessibles → ids de leurs playlists.

        Une émission dont Ausha refuse les playlists est laissée de côté : ses mots-clés
        deviennent « à corriger » sans bloquer les autres émissions.
        """
        available = {show.id for show in client.list_shows()}
        catalog: dict[int, set[int]] = {}
        for show_id in {show.show_id for show in shows} & available:
            try:
                catalog[show_id] = {p.id for p in client.list_playlists(show_id)}
            except RejectedError as exc:
                log.warning("Playlists de l'émission %s refusées par Ausha : %s", show_id, render(str(exc), lang="fr"))
        return catalog

    def _process(
        self,
        config: Config,
        client: AushaClient,
        catalog: dict[int, set[int]],
        ready: ReadyFile,
        file_hash: str,
        folder: str,
        shows: list[ShowFolder],
    ) -> None:
        """Traite un fichier du dossier folder : seules les émissions de ce dossier (shows) peuvent le prendre."""
        entry = self.journal.ensure(file_hash, ready.path.name, ready.size, folder=folder)
        title = episode_title(ready.path)
        rule = find_match(ready.path.name, shows)
        if rule is None:
            self._flag(entry, Status.SANS_REGLE, msg("err_no_rule"), "no_rule", title)
            return
        if entry.step is not Step.NONE and entry.show_id is not None and entry.show_id != rule.show_id:
            # Continuer publierait les étapes restantes dans une autre émission que l'épisode.
            self._flag(entry, Status.REGLE_CASSEE, SHOW_CHANGED_MESSAGE, "broken_rule", title)
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
            partial = isinstance(exc, PartiallyPublished)
            self.journal.update(file_hash, status=Status.REJETE, last_error=str(exc))
            log.warning("%s : « %s » : %s", "Publication partielle" if partial else "Refusé par Ausha", title, render(str(exc), lang="fr"))
            self._emit(Event("partial" if partial else "rejected", title, str(exc)))
        except TransientError as exc:
            self._record_failure(file_hash, title, str(exc))
        except (AuthError, Cancelled):
            self.journal.update(file_hash, status=Status.EN_ATTENTE)  # jamais « en cours » figé
            raise

    def _dry_run(self, client: AushaClient, rule: Rule, entry: Entry, title: str) -> None:
        """Simulation : les mêmes lectures qu'une publication, aucune écriture sur Ausha."""
        if entry.step is Step.NONE and self._find_same_title(client, rule.show_id, title):
            detail = msg("dry_already_on_ausha")
        else:
            detail = msg("dry_would_publish", show=rule.show_name or rule.show_id)
        self.journal.update(entry.hash, attempts=0, last_error="")
        self._emit(Event("dry_run", title, detail))

    def _publish(self, client: AushaClient, rule: Rule, ready: ReadyFile, entry: Entry, title: str) -> None:
        """Enchaîne les étapes restantes ; chaque étape réussie est notée pour pouvoir reprendre."""
        file_hash, step, episode_id = entry.hash, entry.step, entry.episode_id
        if step in (Step.NONE, Step.UPLOADING):
            existing = self._find_same_title(client, rule.show_id, title)
            if existing is not None and step is Step.NONE:
                self.journal.update(file_hash, status=Status.DEJA_PRESENT)
                log.info("Déjà présent sur Ausha, non publié : « %s » (%s, épisode %s)", title, _show(rule), existing.id)
                return
            if existing is not None:
                # La réponse à la création s'était perdue : l'épisode existe, on le reprend.
                log.info("Épisode « %s » retrouvé sur Ausha (id %s)", title, existing.id)
                episode_id = existing.id
            elif step is Step.UPLOADING and self._clock() - entry.updated_at < RECREATE_AFTER_SECONDS:
                # Pas encore visible : on patiente sans compter d'essai, en gardant la date de
                # l'envoi (updated_at) pour que l'attente ne reparte pas de zéro à chaque cycle.
                self.journal.update(
                    file_hash, status=Status.EN_ATTENTE, last_error=CHECKING_MESSAGE, updated_at=entry.updated_at
                )
                return
            else:
                episode_id = self._create(client, rule, ready, entry, title)
            self.journal.update(file_hash, episode_id=episode_id, step=Step.CREATED, attempts=0)
            step = Step.CREATED
        if step is Step.CREATED:
            if rule.image_path:
                _after_publication(
                    lambda: client.upload_episode_image(episode_id, Path(rule.image_path)),
                    "err_partial_image",
                )
            self.journal.update(file_hash, step=Step.IMAGE_DONE, attempts=0)
            step = Step.IMAGE_DONE
        if step is Step.IMAGE_DONE:
            if rule.playlist_id is not None:
                _after_publication(
                    lambda: client.add_to_playlist(rule.playlist_id, episode_id),
                    "err_partial_playlist",
                )
            self.journal.update(file_hash, step=Step.PLAYLIST_DONE, attempts=0)
        self.journal.update(file_hash, status=Status.PUBLIE, attempts=0, last_error="")
        log.info("Publié : « %s » dans %s (épisode %s)", title, _show(rule), episode_id)
        self._emit(Event("published", title, rule.show_name))

    def _create(self, client: AushaClient, rule: Rule, ready: ReadyFile, entry: Entry, title: str) -> int:
        """Envoie l'épisode. L'étape « uploading » est notée avant : si la réponse se perd,
        le cycle suivant cherche l'épisode sur Ausha au lieu de le recréer."""
        file_hash = entry.hash

        def on_progress(percent: int) -> None:
            if percent >= 100:
                # Fichier entièrement envoyé : l'attente avant une recréation part de maintenant,
                # pas du début d'un long envoi (arrêt forcé en attendant la réponse d'Ausha).
                self.journal.update(file_hash, step=Step.UPLOADING)
            self._emit(Event("progress", title, percent=percent))

        self.journal.update(file_hash, step=Step.UPLOADING)
        try:
            return client.create_episode(rule.show_id, title, episode_description(rule), ready.path, on_progress=on_progress)
        except RejectedError:
            # Refusé : rien n'a été créé par cet appel. Après une réponse perdue, l'épisode
            # d'un envoi précédent existe peut-être encore : on garde alors « uploading ».
            if entry.step is Step.NONE:
                self.journal.update(file_hash, step=Step.NONE)
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
            log.warning("Échec de l'envoi de « %s » après %d essais : %s", title, attempts, render(message, lang="fr"))
            self._emit(Event("failed", title, message))
        else:
            self.journal.update(file_hash, status=Status.EN_ATTENTE, attempts=attempts, last_error=message)
            log.info("Envoi de « %s » à reprendre (essai %d sur %d) : %s", title, attempts, MAX_ATTEMPTS, render(message, lang="fr"))

    def _emit(self, event: Event) -> None:
        try:
            self._on_event(event)
        except Exception:
            log.exception("Gestionnaire d'événement en erreur")


def _after_publication(action: Callable[[], None], failure_key: str) -> None:
    """Étape qui suit la mise en ligne : un refus d'Ausha devient une publication partielle.

    failure_key : clé du message (err_partial_*), qui reçoit le refus d'Ausha dans {detail}.
    """
    try:
        action()
    except RejectedError as exc:
        raise PartiallyPublished(msg(failure_key, detail=str(exc))) from exc


def _show(rule: Rule) -> str:
    return rule.show_name or f"émission {rule.show_id}"


def _same_title(a: str, b: str) -> bool:
    """Titres égaux aux entités HTML, à la forme Unicode, aux espaces et à la casse près."""
    return _title_key(a) == _title_key(b)


def _title_key(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", html.unescape(text)).split()).casefold()


def _by_folder(shows: list[ShowFolder]) -> list[tuple[str, list[ShowFolder]]]:
    """Émissions regroupées par dossier (same_folder), dans l'ordre de première apparition ;
    chaque groupe garde le chemin écrit pour sa première émission et l'ordre des émissions."""
    groups: list[tuple[str, list[ShowFolder]]] = []
    for show in shows:
        group = next((members for folder, members in groups if same_folder(folder, show.folder)), None)
        if group is None:
            groups.append((show.folder, [show]))
        else:
            group.append(show)
    return groups


def _missing(folder: str, shows: list[ShowFolder]) -> list[tuple[str, str]]:
    """(dossier, émission) pour chaque émission d'un dossier introuvable (ShowFolder.label)."""
    return [(folder, show.label()) for show in shows]
