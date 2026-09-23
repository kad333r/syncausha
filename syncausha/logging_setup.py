"""Log fichier tournant dans %APPDATA%\\SyncAusha\\logs (1 Mo × 5)."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path) -> Path:
    """Branche le fichier de log sur le logger racine (une seule fois par fichier)."""
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "syncausha.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(getattr(h, "baseFilename", None) == os.path.abspath(path) for h in root.handlers):
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
        root.addHandler(handler)
    # httpx logue les URL à INFO : on le limite aux avertissements (le jeton n'est jamais logué).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return path
