"""Journal local (SQLite) : état de publication de chaque fichier, identifié par son contenu."""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

log = logging.getLogger(__name__)


class Status(StrEnum):
    EN_ATTENTE = "en_attente"
    SANS_REGLE = "sans_regle"
    REGLE_CASSEE = "regle_cassee"
    EN_COURS = "en_cours"
    PUBLIE = "publie"
    DEJA_PRESENT = "deja_present"
    REJETE = "rejete"
    ECHEC = "echec"
    IGNORE = "ignore"  # déjà dans le dossier quand il a été choisi


class Step(StrEnum):
    NONE = "none"
    UPLOADING = "uploading"  # création envoyée : l'épisode existe peut-être déjà sur Ausha
    CREATED = "created"
    IMAGE_DONE = "image_done"
    PLAYLIST_DONE = "playlist_done"


# Statuts qu'un cycle ne retraite pas : seuls « Réessayer » (REJETE, ECHEC) et
# « Publier quand même » (IGNORE) les remettent en attente.
FINAL_STATUSES = frozenset({Status.PUBLIE, Status.DEJA_PRESENT, Status.REJETE, Status.ECHEC, Status.IGNORE})
ATTENTION_STATUSES = (Status.SANS_REGLE, Status.REGLE_CASSEE, Status.REJETE, Status.ECHEC)
_NOT_RECENT = (*ATTENTION_STATUSES, Status.IGNORE)


@dataclass
class Entry:
    hash: str
    filename: str
    size: int
    show_id: int | None
    show_name: str
    episode_id: int | None
    step: Step
    status: Status
    attempts: int
    last_error: str
    updated_at: float


_SCHEMA = """
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
_COLUMNS = "hash, filename, size, show_id, show_name, episode_id, step, status, attempts, last_error, updated_at"
_UPDATABLE = frozenset(
    {"filename", "size", "show_id", "show_name", "episode_id", "step", "status", "attempts", "last_error", "updated_at"}
)


class Journal:
    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock:
            try:
                self._db.executescript(_SCHEMA)
            except Exception:
                # Referme la connexion pour ne pas garder le fichier verrouillé sous Windows.
                self._db.close()
                raise
            if self._db.execute("PRAGMA user_version").fetchone()[0] == 0:
                self._db.execute("PRAGMA user_version = 1")
                self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def file_hash(self, path: Path, size: int, mtime: float) -> str:
        """SHA-256 du contenu, relu seulement si le chemin, la taille ou la date ont changé."""
        key = str(path)
        with self._lock:
            row = self._db.execute("SELECT size, mtime, hash FROM hash_cache WHERE path = ?", (key,)).fetchone()
        if row and row[0] == size and row[1] == mtime:
            return row[2]
        digest = _sha256(path)
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO hash_cache (path, size, mtime, hash) VALUES (?, ?, ?, ?)",
                (key, size, mtime, digest),
            )
        return digest

    def get(self, file_hash: str) -> Entry | None:
        with self._lock:
            row = self._db.execute(f"SELECT {_COLUMNS} FROM files WHERE hash = ?", (file_hash,)).fetchone()
        return _to_entry(row) if row else None

    def ensure(self, file_hash: str, filename: str, size: int) -> Entry:
        """Crée l'entrée si besoin (statut en_attente) ; met à jour le nom sinon."""
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO files (hash, filename, size, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(hash) DO UPDATE SET filename = excluded.filename",
                (file_hash, filename, size, self._clock()),
            )
        return self.get(file_hash)

    def update(self, file_hash: str, **values) -> None:
        """Met à jour les champs donnés ; updated_at vaut maintenant, sauf s'il est fourni."""
        unknown = set(values) - _UPDATABLE
        if unknown:
            raise ValueError(f"Champs inconnus : {sorted(unknown)}")
        values.setdefault("updated_at", self._clock())
        assignments = ", ".join(f"{name} = ?" for name in values)
        params = tuple(str(v) if isinstance(v, StrEnum) else v for v in values.values())
        with self._lock, self._db:
            self._db.execute(f"UPDATE files SET {assignments} WHERE hash = ?", (*params, file_hash))

    def reset_for_retry(self, file_hash: str) -> None:
        """Remet le fichier en attente. updated_at est conservé : l'attente de 15 min d'une
        création restée sans réponse ne repart pas de zéro."""
        entry = self.get(file_hash)
        if entry is not None:
            self.update(file_hash, status=Status.EN_ATTENTE, attempts=0, last_error="", updated_at=entry.updated_at)

    def recent(self, limit: int = 50) -> list[Entry]:
        return self._select(f"status NOT IN ({_placeholders(_NOT_RECENT)})", _NOT_RECENT, limit)

    def needing_attention(self) -> list[Entry]:
        return self._select(f"status IN ({_placeholders(ATTENTION_STATUSES)})", ATTENTION_STATUSES, -1)

    def ignored(self, limit: int = 200) -> list[Entry]:
        """Fichiers déjà présents quand le dossier a été choisi (limit=-1 : tous)."""
        return self._select("status = ?", (Status.IGNORE,), limit)

    def forget_unresolved(self, keep: set[str], present_filenames: set[str] = frozenset()) -> None:
        """Oublie les fichiers disparus du dossier qui n'ont jamais donné d'épisode.

        Seules les entrées à l'étape « none » (jamais « uploading », dont l'épisode existe
        peut-être) et dont le statut n'est ni publié ni déjà présent (ignorées comprises)
        sont concernées, et seulement si leur hash n'est pas dans keep ET que leur nom de
        fichier n'est pas dans present_filenames (un fichier retrouvé sous le même nom, même
        modifié, n'est donc pas oublié à tort).
        """
        with self._lock, self._db:
            rows = self._db.execute(
                "SELECT hash, filename FROM files WHERE step = ? AND status NOT IN (?, ?)",
                (Step.NONE, Status.PUBLIE, Status.DEJA_PRESENT),
            ).fetchall()
            stale = [(h,) for (h, filename) in rows if h not in keep and filename not in present_filenames]
            self._db.executemany("DELETE FROM files WHERE hash = ?", stale)

    def _select(self, where: str, params: tuple, limit: int) -> list[Entry]:
        query = f"SELECT {_COLUMNS} FROM files WHERE {where} ORDER BY updated_at DESC, rowid DESC LIMIT ?"
        with self._lock:
            rows = self._db.execute(query, (*(str(p) for p in params), limit)).fetchall()
        return [_to_entry(row) for row in rows]


def open_journal(path: Path) -> Journal:
    """Ouvre le journal ; si le fichier est corrompu, le met de côté (journal.db.corrompu)
    et repart d'un journal neuf plutôt que de planter au démarrage."""
    try:
        return Journal(path)
    except sqlite3.DatabaseError as exc:
        log.warning("Journal illisible (%s), il est mis de côté", exc)
        try:
            os.replace(path, path.with_name(path.name + ".corrompu"))
        except OSError:
            pass
        return Journal(path)


def _placeholders(values: tuple) -> str:
    return ", ".join("?" * len(values))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_entry(row: tuple) -> Entry:
    (file_hash, filename, size, show_id, show_name, episode_id, step, status, attempts, last_error, updated_at) = row
    return Entry(
        file_hash, filename, size, show_id, show_name, episode_id,
        Step(step), Status(status), attempts, last_error, updated_at,
    )
