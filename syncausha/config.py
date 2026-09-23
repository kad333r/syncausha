"""Réglages de SyncAusha : fichier JSON + jeton dans le Gestionnaire d'identifiants Windows."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import keyring
from keyring.errors import PasswordDeleteError

log = logging.getLogger(__name__)

APP_NAME = "SyncAusha"
DEFAULT_API_BASE_URL = "https://api-content.ausha.co/v1"
MIN_INTERVAL, MAX_INTERVAL = 5, 120
KEYRING_SERVICE = "SyncAusha"
KEYRING_USERNAME = "ausha_token"
TOKEN_CHUNK_SIZE = 1000

if sys.platform == "win32":
    # Fige le backend pour l'exécutable PyInstaller, qui ne peut pas découvrir
    # les backends dynamiquement.
    from keyring.backends.Windows import WinVaultKeyring

    keyring.set_keyring(WinVaultKeyring())


def app_data_dir() -> Path:
    """Dossier des données de l'app (%APPDATA%\\SyncAusha), créé au besoin."""
    path = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


_RULE_STR_FIELDS = ("show_name", "playlist_name", "image_path", "description_template")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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
    def from_dict(cls, data: dict) -> Rule | None:
        """Construit une règle depuis un dict JSON, ou None si son contenu est invalide."""
        if not isinstance(data, dict):
            return None
        keyword, show_id = data.get("keyword"), data.get("show_id")
        if not isinstance(keyword, str) or not _is_int(show_id):
            return None
        kwargs = {"keyword": keyword, "show_id": show_id}
        for name in _RULE_STR_FIELDS:
            if name in data:
                if not isinstance(data[name], str):
                    return None
                kwargs[name] = data[name]
        if "playlist_id" in data:
            playlist_id = data["playlist_id"]
            if playlist_id is not None and not _is_int(playlist_id):
                return None
            kwargs["playlist_id"] = playlist_id
        return cls(**kwargs)


_CONFIG_STR_FIELDS = ("watch_folder", "api_base_url")
_CONFIG_BOOL_FIELDS = ("paused", "dry_run")


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
        kwargs = {}
        for name in _CONFIG_STR_FIELDS:
            if name in data:
                if isinstance(data[name], str):
                    kwargs[name] = data[name]
                else:
                    log.warning("Champ %s invalide, valeur par défaut conservée", name)
        for name in _CONFIG_BOOL_FIELDS:
            if name in data:
                if isinstance(data[name], bool):
                    kwargs[name] = data[name]
                else:
                    log.warning("Champ %s invalide, valeur par défaut conservée", name)
        if "interval_minutes" in data:
            if _is_int(data["interval_minutes"]):
                kwargs["interval_minutes"] = data["interval_minutes"]
            else:
                log.warning("Champ interval_minutes invalide, valeur par défaut conservée")
        config = cls(**kwargs)
        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            raw_rules = []
        rules = []
        for item in raw_rules:
            rule = Rule.from_dict(item)
            if rule is None:
                log.warning("Règle invalide ignorée : %r", item)
            else:
                rules.append(rule)
        config.rules = rules
        return config

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: Path) -> Config:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("le contenu du fichier de réglages n'est pas un objet JSON")
        return Config.from_dict(data)
    except FileNotFoundError:
        return Config()
    except Exception as exc:
        log.warning("Réglages illisibles (%s), valeurs par défaut utilisées", exc)
        try:
            os.replace(path, path.with_name(path.name + ".illisible"))
        except OSError:
            pass
        return Config()


def save_config(config: Config, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(3):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.2)


def get_token() -> str | None:
    """Relit le jeton stocké en plusieurs morceaux (le Gestionnaire d'identifiants Windows
    limite un secret à environ 1280 caractères)."""
    count = keyring.get_password(KEYRING_SERVICE, f"{KEYRING_USERNAME}.count")
    if count is None:
        return None
    try:
        chunk_count = int(count)
    except ValueError:
        return None
    chunks = []
    for i in range(chunk_count):
        chunk = keyring.get_password(KEYRING_SERVICE, f"{KEYRING_USERNAME}.{i}")
        if chunk is None:
            return None
        chunks.append(chunk)
    return "".join(chunks) or None


def set_token(token: str) -> None:
    """Enregistre le jeton en morceaux d'au plus 1000 caractères ; une chaîne vide le supprime."""
    token = token.strip()
    _delete_stored_chunks()
    if not token:
        return
    chunks = [token[i : i + TOKEN_CHUNK_SIZE] for i in range(0, len(token), TOKEN_CHUNK_SIZE)]
    for i, chunk in enumerate(chunks):
        keyring.set_password(KEYRING_SERVICE, f"{KEYRING_USERNAME}.{i}", chunk)
    keyring.set_password(KEYRING_SERVICE, f"{KEYRING_USERNAME}.count", str(len(chunks)))


def _delete_stored_chunks() -> None:
    count = keyring.get_password(KEYRING_SERVICE, f"{KEYRING_USERNAME}.count")
    try:
        chunk_count = int(count) if count is not None else 0
    except ValueError:
        chunk_count = 0
    for i in range(chunk_count):
        _delete_ignoring_missing(f"{KEYRING_USERNAME}.{i}")
    _delete_ignoring_missing(f"{KEYRING_USERNAME}.count")


def _delete_ignoring_missing(username: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, username)
    except PasswordDeleteError:
        pass
