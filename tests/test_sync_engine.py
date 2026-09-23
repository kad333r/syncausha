from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

import syncausha.sync_engine as sync_engine
from syncausha.ausha_client import AuthError, Cancelled, Episode, Playlist, RejectedError, Show, TransientError
from syncausha.config import Config, Rule
from syncausha.journal import Journal, Status, Step
from syncausha.scanner import scan_ready_files
from syncausha.sync_engine import SyncEngine, _same_title


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
    config = Config(watch_folder=str(folder), rules=[rule])
    journal = Journal(tmp_path / "journal.db")
    client = FakeClient()
    events = []

    def make_engine(on_event=events.append):
        return SyncEngine(
            config,
            journal,
            lambda cfg, cancel: client,
            on_event=on_event,
            scan=lambda path: scan_ready_files(path, min_age_seconds=0),
        )

    yield SimpleNamespace(
        folder=folder, config=config, journal=journal, client=client, events=events,
        engine=make_engine(), make_engine=make_engine,
    )
    journal.close()


def add_file(env, name, content=b"audio"):
    path = env.folder / name
    path.write_bytes(content)
    return path


def kinds(env):
    return [e.kind for e in env.events if e.kind != "progress"]


def only_entry(env):
    (entry,) = env.journal.recent() + env.journal.needing_attention()
    return entry


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
    assert "Playlist introuvable" in entry.last_error
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
    env.journal.reset_for_retry(only_entry(env).hash)
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
    assert (result.state, result.message) == ("paused", "Arrêt demandé")
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
    assert [(e.kind, e.detail) for e in env.events] == [("dry_run", "Serait publié dans Mars Attack")]
    env.config.dry_run = False
    env.engine.run_cycle()
    assert only_entry(env).status is Status.PUBLIE


def test_dry_run_reports_existing_episode_without_writing(env):
    env.config.dry_run = True
    env.client.episodes[1] = [Episode(55, "Mars Attack 13")]
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "ok"
    assert env.client.calls == []
    assert [(e.kind, e.detail) for e in env.events] == [("dry_run", "Déjà présent sur Ausha — ne serait pas publié")]
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
    assert "bug" in entry.last_error


def test_unexpected_os_error_is_a_file_failure_not_offline(env, monkeypatch):
    def broken(rule, catalog):
        raise PermissionError("accès refusé")

    monkeypatch.setattr(sync_engine, "validate_rule", broken)
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "ok"
    entry = only_entry(env)
    assert entry.last_error.startswith("Erreur inattendue")
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
    assert (result.state, result.message) == ("paused", "Arrêt demandé")
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
