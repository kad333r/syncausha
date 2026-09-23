from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

import syncausha.sync_engine as sync_engine
from syncausha.ausha_client import AuthError, Cancelled, Episode, Playlist, RejectedError, Show, TransientError
from syncausha.config import Config, Rule
from syncausha.i18n import render
from syncausha.journal import Journal, Status, Step
from syncausha.scanner import scan_ready_files
from syncausha.sync_engine import RECREATE_AFTER_SECONDS, SyncEngine, _same_title


class FakeClient:
    """Fausse API Ausha : mêmes méthodes qu'AushaClient, état en mémoire.

    calls : écritures ; reads : lectures ; fail : erreurs levées avant l'appel ;
    fail_after : erreurs levées après l'écriture (réponse perdue).
    """

    def __init__(self):
        self.shows = {1: "Mars Attack"}
        self.playlists = {1: {7: "Saison 3"}}
        self.episodes = {1: []}
        self.calls = []
        self.reads = []
        self.fail = {}
        self.fail_after = {}
        self.next_id = 100
        self.closed = False

    def _maybe_fail(self, name, table=None):
        errors = (self.fail if table is None else table).get(name)
        if errors:
            raise errors.pop(0)

    def list_shows(self):
        self.reads.append(("list_shows",))
        self._maybe_fail("list_shows")
        return [Show(i, n) for i, n in self.shows.items()]

    def list_playlists(self, show_id):
        self.reads.append(("list_playlists", show_id))
        self._maybe_fail(f"list_playlists:{show_id}")
        return [Playlist(i, n) for i, n in self.playlists.get(show_id, {}).items()]

    def find_episodes(self, show_id, query):
        self.reads.append(("find", show_id, query))
        self._maybe_fail("find_episodes")
        return [e for e in self.episodes.get(show_id, []) if query.casefold() in e.name.casefold()]

    def create_episode(self, show_id, name, description, audio_path, on_progress=None):
        self._maybe_fail("create_episode")
        self.calls.append(("create", show_id, name, description, audio_path.name))
        if on_progress:
            on_progress(50)
            on_progress(100)
        self.next_id += 1
        self.episodes.setdefault(show_id, []).append(Episode(self.next_id, name))
        self._maybe_fail("create_episode", self.fail_after)
        return self.next_id

    def upload_episode_image(self, episode_id, image_path):
        self._maybe_fail("upload_episode_image")
        self.calls.append(("image", episode_id, image_path.name))

    def add_to_playlist(self, playlist_id, episode_id):
        self._maybe_fail("add_to_playlist")
        self.calls.append(("playlist", playlist_id, episode_id))

    def close(self):
        self.closed = True


@pytest.fixture
def env(tmp_path):
    folder = tmp_path / "podcasts"
    folder.mkdir()
    image = tmp_path / "mars.png"
    Image.new("RGB", (1400, 1400), "red").save(image)
    rule = Rule(
        keyword="MARS ATTACK",
        show_id=1,
        show_name="Mars Attack",
        playlist_id=7,
        playlist_name="Saison 3",
        image_path=str(image),
        description_template="Nouvel épisode",
    )
    # Dossier déjà pris en compte : les fichiers ajoutés par les tests sont publiés.
    config = Config(watch_folder=str(folder), baseline_folder=str(folder), rules=[rule])
    clock = SimpleNamespace(now=1_000_000.0)  # horloge commune au journal et au moteur
    journal = Journal(tmp_path / "journal.db", clock=lambda: clock.now)
    client = FakeClient()
    events = []

    def make_engine(on_event=events.append):
        return SyncEngine(
            config,
            journal,
            lambda cfg, cancel: client,
            on_event=on_event,
            scan=lambda path: scan_ready_files(path, min_age_seconds=0),
            clock=lambda: clock.now,
        )

    yield SimpleNamespace(
        folder=folder, config=config, journal=journal, client=client, events=events, clock=clock,
        engine=make_engine(), make_engine=make_engine,
    )
    journal.close()


class Killed(BaseException):
    """Arrêt brutal du processus : aucune écriture ne suit."""


def add_file(env, name, content=b"audio"):
    path = env.folder / name
    path.write_bytes(content)
    return path


def kinds(env):
    return [e.kind for e in env.events if e.kind != "progress"]


def only_entry(env):
    (entry,) = env.journal.recent() + env.journal.needing_attention()
    return entry


def creates(env):
    return [c[2] for c in env.client.calls if c[0] == "create"]


def test_new_file_is_published_with_image_and_playlist(env):
    add_file(env, "MARS ATTACK - Épisode 12.mp3")
    assert env.engine.run_cycle().state == "ok"
    assert env.client.calls == [
        ("create", 1, "MARS ATTACK - Épisode 12", "Nouvel épisode", "MARS ATTACK - Épisode 12.mp3"),
        ("image", 101, "mars.png"),
        ("playlist", 7, 101),
    ]
    entry = only_entry(env)
    assert entry.status is Status.PUBLIE
    assert entry.step is Step.PLAYLIST_DONE
    assert entry.episode_id == 101
    assert entry.show_name == "Mars Attack"
    assert kinds(env) == ["published"]
    assert [e.percent for e in env.events if e.kind == "progress"] == [50, 100]
    assert env.client.closed


def test_published_file_is_not_sent_again_even_if_renamed(env):
    path = add_file(env, "MARS ATTACK - Épisode 12.mp3")
    env.engine.run_cycle()
    path.rename(env.folder / "MARS ATTACK - Épisode 12 (copie).mp3")
    env.engine.run_cycle()
    assert [c[0] for c in env.client.calls].count("create") == 1


def test_file_without_rule_is_flagged_once(env):
    add_file(env, "interview_brut.mp3")
    assert env.engine.run_cycle().state == "attention"
    env.engine.run_cycle()
    assert env.client.calls == []
    assert kinds(env) == ["no_rule"]
    assert only_entry(env).status is Status.SANS_REGLE


def test_file_is_published_once_a_rule_exists(env):
    add_file(env, "interview_brut.mp3")
    env.engine.run_cycle()
    env.config.rules.append(Rule(keyword="interview", show_id=1, show_name="Mars Attack"))
    assert env.engine.run_cycle().state == "ok"
    assert env.client.calls == [("create", 1, "interview_brut", "", "interview_brut.mp3")]


def test_broken_rule_blocks_upload(env):
    env.client.playlists = {1: {}}
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "attention"
    entry = only_entry(env)
    assert entry.status is Status.REGLE_CASSEE
    assert "Playlist introuvable" in render(entry.last_error, lang="fr")
    assert env.client.calls == []
    assert kinds(env) == ["broken_rule"]


def test_refused_show_does_not_stop_other_shows(env):
    env.client.shows[2] = "Silicon Talk"
    env.config.rules.append(Rule(keyword="SILICON", show_id=2, show_name="Silicon Talk"))
    env.client.fail["list_playlists:2"] = [RejectedError("Forbidden")]
    add_file(env, "MARS ATTACK 13.mp3", b"mars")
    add_file(env, "SILICON TALK 4.mp3", b"silicon")
    assert env.engine.run_cycle().state == "attention"
    statuses = {e.filename: e.status for e in env.journal.recent() + env.journal.needing_attention()}
    assert statuses == {"MARS ATTACK 13.mp3": Status.PUBLIE, "SILICON TALK 4.mp3": Status.REGLE_CASSEE}


def test_existing_episode_on_ausha_is_not_duplicated(env):
    env.client.episodes[1] = [Episode(55, "mars attack 13")]
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "ok"
    assert env.client.calls == []
    assert only_entry(env).status is Status.DEJA_PRESENT


def test_resumes_at_failed_step_without_recreating(env):
    env.client.fail["add_to_playlist"] = [TransientError("coupure")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    entry = only_entry(env)
    assert entry.status is Status.EN_ATTENTE
    assert entry.step is Step.IMAGE_DONE
    assert entry.attempts == 1
    assert entry.last_error == "coupure"
    env.engine.run_cycle()
    assert [c[0] for c in env.client.calls] == ["create", "image", "playlist"]
    assert only_entry(env).status is Status.PUBLIE


def test_three_transient_failures_mark_file_as_failed(env):
    env.client.fail["create_episode"] = [TransientError("délai dépassé") for _ in range(3)]
    add_file(env, "MARS ATTACK 13.mp3")
    for _ in range(4):
        env.engine.run_cycle()
        env.clock.now += RECREATE_AFTER_SECONDS  # une création sans réponse n'est retentée qu'après ce délai
    entry = only_entry(env)
    assert entry.status is Status.ECHEC
    assert entry.attempts == 3
    assert kinds(env) == ["failed"]
    assert env.client.calls == []


def test_retry_after_failure_publishes(env):
    env.client.fail["create_episode"] = [TransientError("x") for _ in range(3)]
    add_file(env, "MARS ATTACK 13.mp3")
    for _ in range(3):
        env.engine.run_cycle()
        env.clock.now += RECREATE_AFTER_SECONDS
    env.journal.reset_for_retry(only_entry(env).hash)
    env.clock.now += RECREATE_AFTER_SECONDS
    env.engine.run_cycle()
    assert only_entry(env).status is Status.PUBLIE


def test_rejected_file_is_not_retried_automatically(env):
    env.client.fail["create_episode"] = [RejectedError("Fichier trop lourd")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    env.engine.run_cycle()
    entry = only_entry(env)
    assert entry.status is Status.REJETE
    assert "trop lourd" in entry.last_error
    assert kinds(env) == ["rejected"]
    assert env.client.calls == []


def test_auth_error_on_catalog_stops_cycle(env):
    env.client.fail["list_shows"] = [AuthError("Unauthenticated")]
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "auth_error"
    assert env.client.calls == []
    assert env.client.closed


def test_auth_error_during_upload_stops_cycle(env):
    env.client.fail["create_episode"] = [AuthError("expiré")]
    add_file(env, "MARS ATTACK 13.mp3")
    add_file(env, "MARS ATTACK 14.mp3", b"episode 14")
    assert env.engine.run_cycle().state == "auth_error"
    assert env.client.calls == []
    assert [entry.status for entry in env.journal.recent()] == [Status.EN_ATTENTE]


def test_cancel_during_upload_leaves_file_pending(env):
    env.client.fail["create_episode"] = [Cancelled("Envoi interrompu.")]
    add_file(env, "MARS ATTACK 13.mp3")
    result = env.engine.run_cycle()
    assert (result.state, render(result.message, lang="fr")) == ("paused", "Arrêt demandé")
    entry = only_entry(env)
    assert entry.status is Status.EN_ATTENTE
    assert entry.attempts == 0


def test_invalid_token_in_factory_gives_auth_error(env):
    def factory(cfg, cancel):
        raise AuthError("Jeton Ausha invalide (caractères non autorisés).")

    add_file(env, "MARS ATTACK 13.mp3")
    assert SyncEngine(env.config, env.journal, factory).run_cycle().state == "auth_error"


def test_client_factory_receives_the_cancel_event(env):
    received = []
    engine = SyncEngine(env.config, env.journal, lambda cfg, cancel: received.append(cancel) or env.client)
    engine.run_cycle()
    assert received == [engine.cancel_event]


def test_offline_catalog_gives_offline_state(env):
    env.client.fail["list_shows"] = [TransientError("pas de réseau")]
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "offline"
    assert all(entry.attempts == 0 for entry in env.journal.recent())


def test_dry_run_publishes_nothing(env):
    env.config.dry_run = True
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "ok"
    assert env.client.calls == []
    assert ("find", 1, "MARS ATTACK 13") in env.client.reads
    assert [(e.kind, render(e.detail, lang="fr")) for e in env.events] == [("dry_run", "Serait publié dans Mars Attack")]
    env.config.dry_run = False
    env.engine.run_cycle()
    assert only_entry(env).status is Status.PUBLIE


def test_dry_run_reports_existing_episode_without_writing(env):
    env.config.dry_run = True
    env.client.episodes[1] = [Episode(55, "Mars Attack 13")]
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "ok"
    assert env.client.calls == []
    assert [(e.kind, render(e.detail, lang="fr")) for e in env.events] == [
        ("dry_run", "Déjà présent sur Ausha — ne serait pas publié")
    ]
    entry = only_entry(env)
    assert (entry.status, entry.step) == (Status.EN_ATTENTE, Step.NONE)


def test_dry_run_read_failure_counts_as_attempt(env):
    env.config.dry_run = True
    env.client.fail["find_episodes"] = [TransientError("pas de réseau")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    entry = only_entry(env)
    assert (entry.status, entry.step, entry.attempts) == (Status.EN_ATTENTE, Step.NONE, 1)
    assert env.events == []


def test_successful_dry_run_check_clears_the_previous_failure(env):
    env.config.dry_run = True
    env.client.fail["find_episodes"] = [TransientError("pas de réseau")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    env.engine.run_cycle()
    entry = only_entry(env)
    assert (entry.status, entry.attempts, entry.last_error) == (Status.EN_ATTENTE, 0, "")


def test_paused_and_unconfigured_states(env, tmp_path):
    env.config.paused = True
    assert env.engine.run_cycle().state == "paused"
    env.config.paused = False
    env.config.watch_folder = ""
    assert env.engine.run_cycle().state == "not_configured"
    env.config.watch_folder = str(tmp_path / "absent")
    assert env.engine.run_cycle().state == "folder_missing"
    env.config.watch_folder = str(env.folder)
    no_token = SyncEngine(env.config, env.journal, lambda cfg, cancel: None)
    assert no_token.run_cycle().state == "not_configured"


def test_unexpected_error_counts_as_attempt(env):
    env.client.fail["create_episode"] = [RuntimeError("bug")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    entry = only_entry(env)
    assert entry.status is Status.EN_ATTENTE
    assert entry.attempts == 1
    assert render(entry.last_error, lang="fr") == "Erreur inattendue : bug"


def test_unexpected_os_error_is_a_file_failure_not_offline(env, monkeypatch):
    def broken(rule, catalog):
        raise PermissionError("accès refusé")

    monkeypatch.setattr(sync_engine, "validate_rule", broken)
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "ok"
    entry = only_entry(env)
    assert render(entry.last_error, lang="fr").startswith("Erreur inattendue")
    assert entry.attempts == 1


def test_lost_create_response_adopts_the_episode_next_cycle(env):
    env.client.fail_after["create_episode"] = [TransientError("délai dépassé")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    entry = only_entry(env)
    assert (entry.status, entry.step) == (Status.EN_ATTENTE, Step.UPLOADING)
    env.engine.run_cycle()
    assert env.client.calls == [
        ("create", 1, "MARS ATTACK 13", "Nouvel épisode", "MARS ATTACK 13.mp3"),
        ("image", 101, "mars.png"),
        ("playlist", 7, 101),
    ]
    entry = only_entry(env)
    assert entry.status is Status.PUBLIE
    assert entry.episode_id == 101


def test_lost_create_response_is_not_recreated_while_ausha_search_lags(env):
    env.client.fail_after["create_episode"] = [TransientError("délai dépassé")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    env.client.episodes[1] = []  # la recherche d'Ausha ne voit pas encore l'épisode créé
    for minutes in (5, 9):
        env.clock.now += minutes * 60
        assert env.engine.run_cycle().state == "ok"
    entry = only_entry(env)
    assert [c[0] for c in env.client.calls] == ["create"]
    assert (entry.status, entry.step, entry.attempts) == (Status.EN_ATTENTE, Step.UPLOADING, 1)
    assert render(entry.last_error, lang="fr") == "Envoi précédent en cours de vérification sur Ausha"
    env.clock.now += 60  # 15 min après l'échec de la création
    env.engine.run_cycle()
    assert [c[0] for c in env.client.calls] == ["create", "create", "image", "playlist"]
    assert only_entry(env).status is Status.PUBLIE


def test_rejected_create_after_lost_response_keeps_the_uploading_step(env):
    env.client.fail_after["create_episode"] = [TransientError("délai dépassé")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    env.client.episodes[1] = []
    env.client.fail["create_episode"] = [RejectedError("Titre déjà utilisé")]
    env.clock.now += RECREATE_AFTER_SECONDS
    env.engine.run_cycle()
    entry = only_entry(env)
    assert (entry.status, entry.step) == (Status.REJETE, Step.UPLOADING)


def test_find_failure_while_resuming_upload_is_retried(env):
    env.client.fail_after["create_episode"] = [TransientError("délai dépassé")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    env.client.fail["find_episodes"] = [TransientError("pas de réseau")]
    env.engine.run_cycle()
    entry = only_entry(env)
    assert (entry.status, entry.step, entry.attempts) == (Status.EN_ATTENTE, Step.UPLOADING, 2)
    env.engine.run_cycle()
    assert [c[0] for c in env.client.calls] == ["create", "image", "playlist"]
    assert only_entry(env).status is Status.PUBLIE


def test_find_failure_before_create_is_retried(env):
    env.client.fail["find_episodes"] = [TransientError("pas de réseau")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    entry = only_entry(env)
    assert (entry.status, entry.step, entry.attempts) == (Status.EN_ATTENTE, Step.NONE, 1)
    env.engine.run_cycle()
    assert [c[0] for c in env.client.calls] == ["create", "image", "playlist"]


def test_resumes_at_image_step(env):
    env.client.fail["upload_episode_image"] = [TransientError("coupure")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    assert only_entry(env).step is Step.CREATED
    env.client.calls.clear()
    env.client.reads.clear()
    env.engine.run_cycle()
    assert env.client.calls == [("image", 101, "mars.png"), ("playlist", 7, 101)]
    assert not [r for r in env.client.reads if r[0] == "find"]
    assert only_entry(env).status is Status.PUBLIE


def test_attempts_reset_after_each_successful_step(env):
    env.client.fail["create_episode"] = [TransientError("x"), TransientError("x")]
    env.client.fail["add_to_playlist"] = [TransientError("coupure")]
    add_file(env, "MARS ATTACK 13.mp3")
    for _ in range(3):
        env.engine.run_cycle()
        env.clock.now += RECREATE_AFTER_SECONDS
    entry = only_entry(env)
    assert (entry.status, entry.step, entry.attempts) == (Status.EN_ATTENTE, Step.IMAGE_DONE, 1)
    env.engine.run_cycle()
    assert only_entry(env).status is Status.PUBLIE


def test_longer_title_on_ausha_is_not_a_duplicate(env):
    env.client.episodes[1] = [Episode(55, "MARS ATTACK 130")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    assert [c[0] for c in env.client.calls] == ["create", "image", "playlist"]
    assert only_entry(env).status is Status.PUBLIE


@pytest.mark.parametrize(
    "a,b,same",
    [
        ("Tom &amp; Jerry", "Tom & Jerry", True),
        ("Épisode 1", "Épisode 1", True),
        ("  MARS   attack 13 ", "mars attack 13", True),
        ("Straße", "STRASSE", True),
        ("MARS ATTACK 130", "MARS ATTACK 13", False),
    ],
)
def test_same_title(a, b, same):
    assert _same_title(a, b) is same


def test_replaced_file_under_same_name_forgets_the_rejected_version(env):
    env.client.fail["create_episode"] = [RejectedError("Fichier trop lourd")]
    add_file(env, "MARS ATTACK 13.mp3", b"version 1")
    assert env.engine.run_cycle().state == "attention"
    add_file(env, "MARS ATTACK 13.mp3", b"version 2 corrigee")
    assert env.engine.run_cycle().state == "ok"
    assert only_entry(env).status is Status.PUBLIE


def test_pause_between_files(env):
    def on_event(event):
        env.events.append(event)
        if event.kind == "published":
            env.config.paused = True

    engine = env.make_engine(on_event)
    add_file(env, "MARS ATTACK 13.mp3")
    add_file(env, "MARS ATTACK 14.mp3", b"episode 14")
    assert engine.run_cycle().state == "paused"
    assert [c[2] for c in env.client.calls if c[0] == "create"] == ["MARS ATTACK 13"]


def test_cancel_between_files(env):
    def on_event(event):
        if event.kind == "published":
            engine.cancel()

    engine = env.make_engine(on_event)
    add_file(env, "MARS ATTACK 13.mp3")
    add_file(env, "MARS ATTACK 14.mp3", b"episode 14")
    result = engine.run_cycle()
    assert (result.state, render(result.message, lang="fr")) == ("paused", "Arrêt demandé")
    assert [c[2] for c in env.client.calls if c[0] == "create"] == ["MARS ATTACK 13"]


def test_nothing_to_do_makes_no_api_call(env, monkeypatch):
    assert env.engine.run_cycle().state == "ok"
    assert env.client.reads == []
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    env.client.calls.clear()
    env.client.reads.clear()
    monkeypatch.setattr(env.journal, "ensure", lambda *args: pytest.fail("aucune écriture pour un fichier publié"))
    assert env.engine.run_cycle().state == "ok"
    assert env.client.reads == []
    assert env.client.calls == []


def test_folder_listing_error_gives_folder_missing(env, monkeypatch):
    add_file(env, "MARS ATTACK 13.mp3")
    ready = scan_ready_files(env.folder, min_age_seconds=0)
    engine = SyncEngine(env.config, env.journal, lambda cfg, cancel: env.client, scan=lambda path: ready)

    def broken(self):
        raise PermissionError("accès refusé")

    monkeypatch.setattr(Path, "iterdir", broken)
    assert engine.run_cycle().state == "folder_missing"


def test_scan_error_gives_folder_missing(env):
    def broken(path):
        raise PermissionError("accès refusé")

    engine = SyncEngine(env.config, env.journal, lambda cfg, cancel: env.client, scan=broken)
    assert engine.run_cycle().state == "folder_missing"


# --- Fichiers déjà présents au choix du dossier ---------------------------------


def test_files_present_when_the_folder_is_chosen_are_ignored_without_calling_ausha(env):
    env.config.baseline_folder = ""
    add_file(env, "MARS ATTACK 12.mp3", b"12")
    add_file(env, "interview_brut.mp3", b"interview")
    factory_calls = []
    engine = SyncEngine(
        env.config, env.journal, lambda cfg, cancel: factory_calls.append(cfg) or env.client,
        on_event=env.events.append, scan=lambda path: scan_ready_files(path, min_age_seconds=0),
    )
    result = engine.run_cycle()
    assert (result.state, result.count, result.folder) == ("baseline", 2, str(env.folder))
    assert render(result.message, lang="fr") == "2 fichier(s) déjà présent(s) ignoré(s)"
    assert factory_calls == []
    assert env.client.reads == [] and env.client.calls == []
    assert env.events == []
    assert sorted(e.filename for e in env.journal.ignored()) == ["MARS ATTACK 12.mp3", "interview_brut.mp3"]
    assert env.journal.recent() == [] and env.journal.needing_attention() == []


def test_only_files_added_after_the_baseline_are_published(env):
    env.config.baseline_folder = ""
    add_file(env, "MARS ATTACK 12.mp3", b"12")
    assert env.engine.run_cycle().state == "baseline"
    env.config.baseline_folder = env.config.watch_folder
    add_file(env, "MARS ATTACK 13.mp3", b"13")
    assert env.engine.run_cycle().state == "ok"
    env.engine.run_cycle()
    assert creates(env) == ["MARS ATTACK 13"]
    assert [e.filename for e in env.journal.ignored()] == ["MARS ATTACK 12.mp3"]


def test_ignored_file_is_published_once_requested(env):
    env.config.baseline_folder = ""
    add_file(env, "MARS ATTACK 12.mp3", b"12")
    env.engine.run_cycle()
    env.config.baseline_folder = env.config.watch_folder
    (ignored,) = env.journal.ignored()
    env.journal.reset_for_retry(ignored.hash)  # « Publier quand même »
    assert env.engine.run_cycle().state == "ok"
    assert creates(env) == ["MARS ATTACK 12"]
    assert only_entry(env).status is Status.PUBLIE
    assert env.journal.ignored() == []


def test_changing_the_folder_takes_a_new_baseline(env, tmp_path):
    add_file(env, "MARS ATTACK 12.mp3", b"12")
    env.engine.run_cycle()
    other = tmp_path / "autre"
    other.mkdir()
    (other / "MARS ATTACK 12.mp3").write_bytes(b"12")  # même contenu : reste publié
    (other / "MARS ATTACK 13.mp3").write_bytes(b"13")
    env.config.watch_folder = str(other)
    result = env.engine.run_cycle()
    assert (result.state, result.count, result.folder) == ("baseline", 1, str(other))
    assert creates(env) == ["MARS ATTACK 12"]
    assert [e.filename for e in env.journal.ignored()] == ["MARS ATTACK 13.mp3"]
    assert [e.status for e in env.journal.recent()] == [Status.PUBLIE]


def test_baseline_leaves_an_upload_in_progress_alone(env):
    # L'épisode existe peut-être déjà sur Ausha : la publication doit se terminer.
    path = add_file(env, "MARS ATTACK 13.mp3")
    st = path.stat()
    file_hash = env.journal.file_hash(path, st.st_size, st.st_mtime)
    env.journal.ensure(file_hash, path.name, st.st_size)
    env.journal.update(file_hash, step=Step.UPLOADING, status=Status.EN_ATTENTE, show_id=1)
    env.config.baseline_folder = ""
    assert env.engine.run_cycle().count == 0
    assert env.journal.get(file_hash).status is Status.EN_ATTENTE


def test_files_still_being_copied_are_not_part_of_the_baseline(env):
    env.config.baseline_folder = ""
    add_file(env, "MARS ATTACK 13.mp3")
    still_copying = SyncEngine(env.config, env.journal, lambda cfg, cancel: env.client, scan=scan_ready_files)
    assert still_copying.run_cycle().count == 0
    env.config.baseline_folder = env.config.watch_folder
    env.engine.run_cycle()
    assert creates(env) == ["MARS ATTACK 13"]


def test_stopping_during_the_baseline(env):
    env.config.baseline_folder = ""
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.cancel()
    assert env.engine.run_cycle().state == "paused"
    assert env.journal.ignored() == []


# --- Robustesse de la publication ------------------------------------------------


def test_forced_quit_after_a_long_upload_waits_from_the_end_of_the_upload(env):
    # Envoi commencé à t0, fini à t0 + 20 min, puis processus tué avant la réponse d'Ausha.
    t0 = env.clock.now

    def on_event(event):
        if event.kind == "progress" and event.percent == 50:
            env.clock.now += 20 * 60

    env.client.fail_after["create_episode"] = [Killed()]
    add_file(env, "MARS ATTACK 13.mp3")
    with pytest.raises(Killed):
        env.make_engine(on_event).run_cycle()
    entry = env.journal.recent()[0]
    assert (entry.step, entry.updated_at) == (Step.UPLOADING, t0 + 20 * 60)
    env.client.episodes[1] = []  # la recherche d'Ausha ne voit pas encore l'épisode
    env.clock.now = t0 + 34 * 60
    env.engine.run_cycle()
    assert creates(env) == ["MARS ATTACK 13"]
    env.clock.now = t0 + 35 * 60
    env.engine.run_cycle()
    assert creates(env) == ["MARS ATTACK 13", "MARS ATTACK 13"]


def test_retry_does_not_restart_the_wait_after_a_lost_response(env):
    env.client.fail_after["create_episode"] = [TransientError("délai dépassé")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    env.client.episodes[1] = []
    entry = only_entry(env)
    env.journal.update(entry.hash, status=Status.ECHEC, updated_at=entry.updated_at)
    env.clock.now += RECREATE_AFTER_SECONDS
    env.journal.reset_for_retry(entry.hash)  # « Réessayer » 15 min après l'envoi
    env.engine.run_cycle()
    assert creates(env) == ["MARS ATTACK 13", "MARS ATTACK 13"]
    assert only_entry(env).status is Status.PUBLIE


@pytest.mark.parametrize(
    "step,message",
    [
        ("upload_episode_image", "Épisode publié, mais l'image n'a pas pu être ajoutée : Refus"),
        ("add_to_playlist", "Épisode publié, mais il n'a pas pu être ajouté à la playlist : Refus"),
    ],
)
def test_refusal_after_the_episode_is_live_is_a_partial_publication(env, step, message):
    env.client.fail[step] = [RejectedError("Refus")]
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "attention"
    entry = only_entry(env)
    assert (entry.status, render(entry.last_error, lang="fr")) == (Status.REJETE, message)
    assert [(e.kind, render(e.detail, lang="fr")) for e in env.events if e.kind != "progress"] == [("partial", message)]
    env.journal.reset_for_retry(entry.hash)  # « Réessayer » reprend à l'étape refusée
    env.engine.run_cycle()
    assert creates(env) == ["MARS ATTACK 13"]
    assert only_entry(env).status is Status.PUBLIE


def test_rule_moved_to_another_show_mid_publication_is_flagged(env):
    env.client.fail["upload_episode_image"] = [TransientError("coupure")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    assert only_entry(env).step is Step.CREATED
    env.client.shows[2] = "Silicon Talk"
    env.config.rules[0] = Rule(keyword="MARS ATTACK", show_id=2, show_name="Silicon Talk")
    env.client.calls.clear()
    env.client.reads.clear()
    assert env.engine.run_cycle().state == "attention"
    entry = only_entry(env)
    assert entry.status is Status.REGLE_CASSEE
    assert render(entry.last_error, lang="fr") == (
        "La règle a changé d'émission pendant la publication : vérifiez l'épisode sur Ausha."
    )
    assert env.client.calls == []
    assert not [r for r in env.client.reads if r[0] == "find"]
    assert kinds(env)[-1] == "broken_rule"


def test_messages_are_translatable(env):
    add_file(env, "interview_brut.mp3")
    env.engine.run_cycle()
    entry = only_entry(env)
    assert render(entry.last_error, lang="en") == "No rule matches this file"
    assert render(entry.last_error, lang="fr") == "Aucune règle ne correspond"
    assert render(entry.last_error, lang="ar") != entry.last_error


def test_cycle_messages_are_translatable(env, tmp_path):
    env.config.watch_folder = str(tmp_path / "absent")
    result = env.engine.run_cycle()
    assert render(result.message, lang="en") == f"Folder not found: {tmp_path / 'absent'}"
    assert render(result.message, lang="fr") == f"Dossier introuvable : {tmp_path / 'absent'}"
    env.config.watch_folder = str(env.folder)
    env.config.baseline_folder = ""
    add_file(env, "MARS ATTACK 12.mp3")
    result = env.engine.run_cycle()
    assert render(result.message, lang="en") == "Existing files ignored: 1"
    assert render(result.message, lang="ar") == "الملفات الموجودة مسبقًا المتجاهَلة: 1"


def test_partial_publication_keeps_the_ausha_detail_in_every_language(env):
    env.client.fail["add_to_playlist"] = [RejectedError("Refus")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    stored = only_entry(env).last_error
    assert render(stored, lang="en") == "Episode published, but it couldn't be added to the playlist: Refus"
    assert render(stored, lang="ar").endswith(": \u2068Refus\u2069")  # détail d'Ausha isolé
