import itertools

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
    assert version == 1


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
