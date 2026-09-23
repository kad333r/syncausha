"""Détection des fichiers audio prêts à être envoyés."""
from __future__ import annotations

import stat as stat_module
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
    """Fichiers audio du premier niveau, non modifiés depuis min_age_seconds et lisibles.

    Les fichiers vides, cachés (« . ») ou temporaires (« ~$ ») sont ignorés, de même que ceux
    qui disparaissent entre le listage du dossier et leur lecture. Une date de modification
    dans le futur est considérée comme prête (seul un âge positif inférieur au minimum est écarté).
    """
    now = time.time()
    ready = []
    for entry in sorted(folder.iterdir()):
        if entry.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if entry.name.startswith(".") or entry.name.startswith("~$"):
            continue
        try:
            st = entry.stat()
        except OSError:
            continue
        if not stat_module.S_ISREG(st.st_mode) or st.st_size == 0:
            continue
        age = now - st.st_mtime
        if (0 <= age < min_age_seconds) or not _can_open(entry):
            continue
        ready.append(ReadyFile(entry, st.st_size, st.st_mtime))
    return ready


def _can_open(path: Path) -> bool:
    try:
        with open(path, "rb"):
            return True
    except OSError:
        return False
