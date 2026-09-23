from types import SimpleNamespace

import pytest
from PIL import Image

from syncausha.ausha_client import AuthError, Episode, Playlist, RejectedError, Show, TransientError
from syncausha.config import Config, Rule
from syncausha.journal import Journal, Status, Step
from syncausha.scanner import scan_ready_files
from syncausha.sync_engine import SyncEngine


class FakeClient:
    """Fausse API Ausha : mêmes méthodes qu'AushaClient, état en mémoire."""

    def __init__(self):
        self.shows = {1: "Mars Attack"}
        self.playlists = {1: {7: "Saison 3"}}
        self.episodes = {1: []}
        self.calls = []
        self.fail = {}
        self.next_id = 100
        self.closed = False

    def _maybe_fail(self, name):
        errors = self.fail.get(name)
        if errors:
            raise errors.pop(0)

    def list_shows(self):
        self._maybe_fail("list_shows")
        return [Show(i, n) for i, n in self.shows.items()]

    def list_playlists(self, show_id):
        return [Playlist(i, n) for i, n in self.playlists.get(show_id, {}).items()]

    def find_episodes(self, show_id, query):
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
    engine = SyncEngine(
        config,
        journal,
        lambda cfg: client,
        on_event=events.append,
        scan=lambda path: scan_ready_files(path, min_age_seconds=0),
    )
    yield SimpleNamespace(folder=folder, config=config, journal=journal, client=client, events=events, engine=engine)
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
    add_file(env, "MARS ATTACK 14.mp3")
    assert env.engine.run_cycle().state == "auth_error"
    assert env.client.calls == []


def test_offline_catalog_gives_offline_state(env):
    env.client.fail["list_shows"] = [TransientError("pas de réseau")]
    assert env.engine.run_cycle().state == "offline"


def test_dry_run_publishes_nothing(env):
    env.config.dry_run = True
    add_file(env, "MARS ATTACK 13.mp3")
    assert env.engine.run_cycle().state == "ok"
    assert env.client.calls == []
    assert [(e.kind, e.detail) for e in env.events] == [("dry_run", "Serait publié dans Mars Attack")]
    env.config.dry_run = False
    env.engine.run_cycle()
    assert only_entry(env).status is Status.PUBLIE


def test_paused_and_unconfigured_states(env, tmp_path):
    env.config.paused = True
    assert env.engine.run_cycle().state == "paused"
    env.config.paused = False
    env.config.watch_folder = ""
    assert env.engine.run_cycle().state == "not_configured"
    env.config.watch_folder = str(tmp_path / "absent")
    assert env.engine.run_cycle().state == "folder_missing"
    env.config.watch_folder = str(env.folder)
    no_token = SyncEngine(env.config, env.journal, lambda cfg: None)
    assert no_token.run_cycle().state == "not_configured"


def test_unexpected_error_counts_as_attempt(env):
    env.client.fail["create_episode"] = [RuntimeError("bug")]
    add_file(env, "MARS ATTACK 13.mp3")
    env.engine.run_cycle()
    entry = only_entry(env)
    assert entry.status is Status.EN_ATTENTE
    assert entry.attempts == 1
    assert "bug" in entry.last_error
