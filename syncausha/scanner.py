"""Détection des fichiers audio prêts à être envoyés."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

AUDIO_EXTENSIONS = frozenset({".mp3", ".m4a", ".wav", ".ogg", ".flac", ".mp4"})
MIN_AGE_SECONDS = 30.0


@dataclass(frozen=True)
class ReadyFile:
    path: Path
    size: int
    mtime: float


def scan_ready_files(folder: Path, *, min_age_seconds: float = MIN_AGE_SECONDS) -> list[ReadyFile]:
    """Fichiers audio du premier niveau, non modifiés depuis min_age_seconds et lisibles."""
    now = time.time()
    ready = []
    for entry in sorted(folder.iterdir()):
        if not entry.is_file() or entry.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        stat = entry.stat()
        if now - stat.st_mtime < min_age_seconds or not _can_open(entry):
            continue
        ready.append(ReadyFile(entry, stat.st_size, stat.st_mtime))
    return ready


def _can_open(path: Path) -> bool:
    try:
        with open(path, "rb"):
            return True
    except OSError:
        return False
