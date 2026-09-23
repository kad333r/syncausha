"""Réglages de SyncAusha : fichier JSON + jeton dans le Gestionnaire d'identifiants Windows."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import keyring
from keyring.errors import PasswordDeleteError

log = logging.getLogger(__name__)

APP_NAME = "SyncAusha"
DEFAULT_API_BASE_URL = "https://api-content.ausha.co/v1"
MIN_INTERVAL, MAX_INTERVAL = 5, 120
KEYRING_SERVICE = "SyncAusha"
KEYRING_USERNAME = "ausha_token"


def app_data_dir() -> Path:
    """Dossier des données de l'app (%APPDATA%\\SyncAusha), créé au besoin."""
    path = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Rule:
    keyword: str
    show_id: int
    show_name: str = ""
    playlist_id: int | None = None
    playlist_name: str = ""
    image_path: str = ""
    description_template: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Rule:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Config:
    watch_folder: str = ""
    interval_minutes: int = 15
    paused: bool = False
    dry_run: bool = False
    api_base_url: str = DEFAULT_API_BASE_URL
    rules: list[Rule] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.interval_minutes = max(MIN_INTERVAL, min(MAX_INTERVAL, int(self.interval_minutes)))

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        known = {f.name for f in fields(cls)} - {"rules"}
        config = cls(**{k: v for k, v in data.items() if k in known})
        config.rules = [Rule.from_dict(r) for r in data.get("rules", [])]
        return config

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: Path) -> Config:
    try:
        return Config.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return Config()
    except (OSError, ValueError, TypeError) as exc:
        log.warning("Réglages illisibles (%s), valeurs par défaut utilisées", exc)
        return Config()


def save_config(config: Config, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def get_token() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or None


def set_token(token: str) -> None:
    """Enregistre le jeton ; une chaîne vide le supprime."""
    token = token.strip()
    if token:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token)
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except PasswordDeleteError:
        pass
