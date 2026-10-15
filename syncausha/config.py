"""Réglages de SyncAusha : fichier JSON + jeton dans le Gestionnaire d'identifiants Windows."""
from __future__ import annotations

import json
import logging
import ntpath
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import keyring
from keyring.errors import PasswordDeleteError

from syncausha.i18n import LANGUAGES

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
    """Règle effective : une émission et un mot-clé fusionnés, utilisée par le moteur.

    Jamais enregistrée (les réglages contiennent des ShowFolder) ; from_dict sert à la
    conversion des réglages 1.0.
    """

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


def same_folder(a: str, b: str) -> bool:
    """Même dossier Windows (casse, séparateurs et barre finale ignorés) ; un chemin vide n'égale rien."""
    if not a or not b:
        return False
    return ntpath.normcase(ntpath.normpath(a)) == ntpath.normcase(ntpath.normpath(b))


_KEYWORD_STR_FIELDS = ("playlist_name", "image_path", "description_template")


@dataclass
class KeywordRule:
    keyword: str
    playlist_id: int | None = None
    playlist_name: str = ""
    image_path: str = ""
    description_template: str = ""

    @classmethod
    def from_dict(cls, data: object) -> KeywordRule | None:
        """Construit un mot-clé depuis un dict JSON, ou None si son contenu est invalide."""
        if not isinstance(data, dict) or not isinstance(data.get("keyword"), str):
            return None
        kwargs = {"keyword": data["keyword"]}
        for name in _KEYWORD_STR_FIELDS:
            if name in data:
                if not isinstance(data[name], str):
                    return None
                kwargs[name] = data[name]
        if "playlist_id" in data:
            if data["playlist_id"] is not None and not _is_int(data["playlist_id"]):
                return None
            kwargs["playlist_id"] = data["playlist_id"]
        return cls(**kwargs)


@dataclass
class ShowFolder:
    show_id: int
    show_name: str = ""
    folder: str = ""
    # Dossier dont les fichiers déjà présents ont été ignorés ; différent de folder : état des lieux à faire.
    baseline_folder: str = ""
    rules: list[KeywordRule] = field(default_factory=list)  # l'ordre est la priorité

    def needs_baseline(self) -> bool:
        return bool(self.folder) and not same_folder(self.folder, self.baseline_folder)

    @classmethod
    def from_dict(cls, data: object) -> ShowFolder | None:
        """Construit une émission depuis un dict JSON, ou None si son contenu est invalide ;
        un mot-clé invalide est ignoré, les autres sont gardés."""
        if not isinstance(data, dict) or not _is_int(data.get("show_id")):
            return None
        kwargs = {"show_id": data["show_id"]}
        for name in ("show_name", "folder", "baseline_folder"):
            if name in data:
                if not isinstance(data[name], str):
                    return None
                kwargs[name] = data[name]
        show = cls(**kwargs)
        raw = data.get("rules", [])
        for item in raw if isinstance(raw, list) else []:
            rule = KeywordRule.from_dict(item)
            if rule is None:
                log.warning("Mot-clé invalide ignoré : %r", item)
            else:
                show.rules.append(rule)
        return show


_CONFIG_STR_FIELDS = ("api_base_url",)
_CONFIG_BOOL_FIELDS = ("paused", "dry_run")


@dataclass
class Config:
    language: str = ""  # "" = non choisi (installateur puis anglais)
    interval_minutes: int = 15
    paused: bool = False
    dry_run: bool = False
    api_base_url: str = DEFAULT_API_BASE_URL
    shows: list[ShowFolder] = field(default_factory=list)  # l'ordre est la priorité entre émissions d'un même dossier

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
        if "language" in data:
            language = data["language"]
            if isinstance(language, str) and (language == "" or language in LANGUAGES):  # "" : pas encore choisie
                kwargs["language"] = language
            else:
                log.warning("Champ language invalide, valeur par défaut conservée")
        if "interval_minutes" in data:
            if _is_int(data["interval_minutes"]):
                kwargs["interval_minutes"] = data["interval_minutes"]
            else:
                log.warning("Champ interval_minutes invalide, valeur par défaut conservée")
        config = cls(**kwargs)
        if isinstance(data.get("shows"), list):
            for item in data["shows"]:
                show = ShowFolder.from_dict(item)
                if show is None:
                    log.warning("Émission invalide ignorée : %r", item)
                else:
                    config.shows.append(show)
        else:
            if "shows" in data:
                log.warning("Champ shows invalide, valeur par défaut conservée")
            if "rules" in data:
                config.shows = _convert_v1(data)
        return config

    def to_dict(self) -> dict:
        return asdict(self)


def _convert_v1(data: dict) -> list[ShowFolder]:
    """Réglages 1.0 (dossier unique + règles) → une émission par show_id, dans l'ordre d'apparition."""
    folder = data.get("watch_folder") if isinstance(data.get("watch_folder"), str) else ""
    baseline = data.get("baseline_folder") if isinstance(data.get("baseline_folder"), str) else ""
    shows: dict[int, ShowFolder] = {}
    raw = data.get("rules")
    for item in raw if isinstance(raw, list) else []:
        rule = Rule.from_dict(item)
        if rule is None:
            log.warning("Règle invalide ignorée : %r", item)
            continue
        show = shows.setdefault(rule.show_id, ShowFolder(rule.show_id, rule.show_name, folder, baseline))
        show.rules.append(
            KeywordRule(rule.keyword, rule.playlist_id, rule.playlist_name, rule.image_path, rule.description_template)
        )
    if shows:
        log.info("Réglages 1.0 convertis : %d émission(s) dans %s", len(shows), folder)
    return list(shows.values())


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
