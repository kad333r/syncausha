import itertools
import sqlite3

import pytest

import syncausha.journal as journal_module
from syncausha.journal import Journal, Status, Step, open_journal


@pytest.fixture
def journal(tmp_path):
    ticks = itertools.count(1000)
    j = Journal(tmp_path / "journal.db", clock=lambda: float(next(ticks)))
    yield j
    j.close()


def test_hash_is_content_based_and_cached(tmp_path, journal, monkeypatch):
    a = tmp_path / "a.mp3"
    b = tmp_path / "b.mp3"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    hash_a = journal.file_hash(a, 4, 1.0)
    assert journal.file_hash(b, 4, 2.0) == hash_a
    monkeypatch.setattr(journal_module, "_sha256", lambda path: pytest.fail("ne doit pas relire le fichier"))
    assert journal.file_hash(a, 4, 1.0) == hash_a


def test_hash_recomputed_when_file_changes(tmp_path, journal):
    a = tmp_path / "a.mp3"
    a.write_bytes(b"v1")
    first = journal.file_hash(a, 2, 1.0)
    a.write_bytes(b"v2")
    assert journal.file_hash(a, 2, 2.0) != first


def test_ensure_creates_pending_entry_and_keeps_state(journal):
    entry = journal.ensure("h1", "a.mp3", 10)
    assert entry.status is Status.EN_ATTENTE
    assert entry.step is Step.NONE
    assert entry.attempts == 0
    assert entry.episode_id is None
    journal.update("h1", status=Status.PUBLIE, step=Step.PLAYLIST_DONE, episode_id=42, show_id=1, show_name="Mars")
    entry = journal.ensure("h1", "renamed.mp3", 10)
    assert entry.filename == "renamed.mp3"
    assert entry.status is Status.PUBLIE
    assert entry.episode_id == 42
    assert entry.show_name == "Mars"


def test_ensure_records_folder(journal):
    entry = journal.ensure("h1", "a.mp3", 10, folder="D:/Mars")
    assert entry.folder == "D:/Mars"
    assert journal.ensure("h1", "a.mp3", 10, folder="E:/Autre").folder == "E:/Autre"
    assert journal.ensure("h2", "b.mp3", 1).folder == ""


def test_update_rejects_unknown_fields(journal):
    journal.ensure("h1", "a.mp3", 1)
    with pytest.raises(ValueError):
        journal.update("h1", nope=1)


def test_recent_attention_and_ignored_lists(journal):
    for name in ("a", "b", "c", "d", "e", "f"):
        journal.ensure(name, f"{name}.mp3", 1)
    journal.update("a", status=Status.PUBLIE)
    journal.update("b", status=Status.SANS_REGLE)
    journal.update("c", status=Status.EN_COURS)
    journal.update("d", status=Status.ECHEC)
    journal.update("e", status=Status.IGNORE)
    journal.update("f", status=Status.IGNORE)
    assert [e.hash for e in journal.recent()] == ["c", "a"]
    assert [e.hash for e in journal.needing_attention()] == ["d", "b"]
    assert [e.hash for e in journal.ignored()] == ["f", "e"]
    assert [e.hash for e in journal.ignored(limit=1)] == ["f"]


def test_reset_for_retry(journal):
    journal.ensure("h1", "a.mp3", 1)
    journal.update("h1", status=Status.ECHEC, attempts=3, last_error="x")
    journal.reset_for_retry("h1")
    entry = journal.get("h1")
    assert entry.status is Status.EN_ATTENTE
    assert entry.attempts == 0
    assert entry.last_error == ""


def test_reset_for_retry_keeps_the_date_of_the_last_upload(journal):
    # « Réessayer » ne doit pas relancer l'attente de 15 min d'un envoi resté sans réponse.
    journal.ensure("h1", "a.mp3", 1)
    journal.update("h1", status=Status.ECHEC, step=Step.UPLOADING, updated_at=500.0)
    journal.reset_for_retry("h1")
    entry = journal.get("h1")
    assert (entry.status, entry.step, entry.updated_at) == (Status.EN_ATTENTE, Step.UPLOADING, 500.0)
    journal.reset_for_retry("absent")  # sans effet


def test_forget_unresolved_forgets_ignored_files_that_are_gone(journal):
    journal.ensure("gone", "gone.mp3", 1)
    journal.ensure("present", "present.mp3", 1)
    journal.update("gone", status=Status.IGNORE)
    journal.update("present", status=Status.IGNORE)
    journal.forget_unresolved({"present"})
    assert journal.get("gone") is None
    assert journal.get("present").status is Status.IGNORE


def test_forget_unresolved_keeps_created_and_published(journal):
    for name in ("gone_norule", "gone_created", "gone_published", "present"):
        journal.ensure(name, name, 1)
    journal.update("gone_norule", status=Status.SANS_REGLE)
    journal.update("gone_created", step=Step.CREATED, episode_id=5)
    journal.update("gone_published", status=Status.PUBLIE, step=Step.PLAYLIST_DONE)
    journal.update("present", status=Status.SANS_REGLE)
    journal.forget_unresolved({"present"})
    assert journal.get("gone_norule") is None
    assert journal.get("gone_created") is not None
    assert journal.get("gone_published") is not None
    assert journal.get("present") is not None


def test_forget_unresolved_never_forgets_an_upload_in_progress(journal):
    journal.ensure("h1", "gone.mp3", 1)
    journal.update("h1", step=Step.UPLOADING, status=Status.EN_ATTENTE)
    journal.forget_unresolved(keep=set(), present_filenames=set())
    assert journal.get("h1") is not None


def test_forget_unresolved_keeps_entries_matching_present_filename(journal):
    journal.ensure("h1", "still_on_disk.mp3", 1)
    journal.update("h1", status=Status.ECHEC)
    journal.forget_unresolved(keep=set(), present_filenames={"still_on_disk.mp3"})
    assert journal.get("h1") is not None


def test_persists_across_instances(tmp_path):
    first = Journal(tmp_path / "j.db")
    first.ensure("h", "a.mp3", 1)
    first.update("h", status=Status.PUBLIE)
    first.close()
    second = Journal(tmp_path / "j.db")
    assert second.get("h").status is Status.PUBLIE
    second.close()


def test_sets_user_version_on_creation(tmp_path):
    j = Journal(tmp_path / "j.db")
    version = j._db.execute("PRAGMA user_version").fetchone()[0]
    j.close()
    assert version == 2


# Schéma du journal avant la colonne folder (version 1 de la base).
V1_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    hash TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    size INTEGER NOT NULL,
    show_id INTEGER,
    show_name TEXT NOT NULL DEFAULT '',
    episode_id INTEGER,
    step TEXT NOT NULL DEFAULT 'none',
    status TEXT NOT NULL DEFAULT 'en_attente',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS hash_cache (
    path TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    hash TEXT NOT NULL
);
"""


def make_v1_database(path, user_version=1):
    db = sqlite3.connect(path)
    db.executescript(V1_SCHEMA)
    db.execute("INSERT INTO files (hash, filename, size, status, updated_at) VALUES ('h', 'old.mp3', 1, 'publie', 1.0)")
    db.execute(f"PRAGMA user_version = {user_version}")
    db.commit()
    db.close()


def read_user_version(path):
    db = sqlite3.connect(path)
    try:
        return db.execute("PRAGMA user_version").fetchone()[0]
    finally:
        db.close()


def test_migrates_v1_database(tmp_path):
    path = tmp_path / "journal.db"
    make_v1_database(path)
    journal = Journal(path)
    entry = journal.get("h")
    assert entry.filename == "old.mp3" and entry.folder == "" and entry.status.value == "publie"
    assert journal.ensure("h", "old.mp3", 1, folder="D:/Mars").folder == "D:/Mars"
    journal.close()
    assert read_user_version(path) == 2


def test_migrates_unversioned_old_tables(tmp_path):
    path = tmp_path / "journal.db"
    make_v1_database(path, user_version=0)
    journal = Journal(path)
    assert journal.get("h").folder == ""
    journal.close()
    assert read_user_version(path) == 2


def test_migration_survives_a_previous_interruption(tmp_path):
    # Colonne déjà ajoutée mais version restée à 1 (arrêt entre l'ALTER et l'écriture de la version).
    path = tmp_path / "journal.db"
    make_v1_database(path)
    db = sqlite3.connect(path)
    db.execute("ALTER TABLE files ADD COLUMN folder TEXT NOT NULL DEFAULT ''")
    db.commit()
    db.close()
    journal = Journal(path)
    assert journal.get("h").folder == ""
    journal.close()
    assert read_user_version(path) == 2


def test_open_journal_quarantines_corrupt_file_and_starts_fresh(tmp_path):
    path = tmp_path / "journal.db"
    path.write_bytes(b"pas une base sqlite valide")
    j = open_journal(path)
    try:
        entry = j.ensure("h1", "a.mp3", 1)
        assert entry.status is Status.EN_ATTENTE
        assert j.get("h1") is entry or j.get("h1") == entry
    finally:
        j.close()
    assert (tmp_path / "journal.db.corrompu").exists()
