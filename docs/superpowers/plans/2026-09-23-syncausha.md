# SyncAusha Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent Windows (icône près de l'horloge + fenêtre de réglages) qui publie automatiquement sur Ausha, via l'API publique, les fichiers audio d'un dossier, en leur appliquant émission, image et playlist selon des règles « le nom du fichier contient … », et qui s'installe via `SyncAusha-Setup.exe`.

**Architecture:** Une application Python mono-processus. Le cœur (`config`, `rules`, `scanner`, `journal`, `ausha_client`, `sync_engine`) est du Python pur, sans Qt, entièrement testé avec pytest. La couche `ui/` (PySide6) pilote le cœur : un `AppController` lance les cycles de synchro dans un `QThread` à intervalle régulier et relaie les événements vers la fenêtre, l'icône et les notifications. PyInstaller empaquette l'app, Inno Setup produit l'installateur.

**Tech Stack:** Python 3.14, PySide6-Essentials 6.11, httpx, keyring, Pillow, SQLite (stdlib), pytest + respx, PyInstaller 6, Inno Setup 6.

**Spec :** `docs/superpowers/specs/2026-09-23-syncausha-design.md`

**Conventions :**
- Toutes les commandes se lancent depuis `C:\code\syncausha`. Elles fonctionnent aussi bien dans PowerShell que dans Git Bash (chemins avec `/`).
- Chaque commit se termine par la ligne `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (second `-m`).
- Les textes visibles par l'utilisateur sont en français.

---

## Structure des fichiers

```
pyproject.toml               dépendances, config pytest
.gitignore
README.md                    installation, usage, construction
run_syncausha.py             point d'entrée PyInstaller / dev
build.ps1                    tests + PyInstaller + Inno Setup → dist/SyncAusha-Setup.exe
installer/syncausha.iss      script Inno Setup (UTF-8 avec BOM)
tools/make_icon.py           génère syncausha/assets/icon.png + icon.ico
docs/verification-manuelle.md checklist de vérification de l'UI et de l'installateur
syncausha/
  __init__.py                __version__
  config.py                  Config, Rule, load/save JSON, jeton (keyring), app_data_dir
  rules.py                   normalisation, find_rule, titre/description, validation image/règle
  scanner.py                 fichiers audio prêts dans le dossier
  journal.py                 SQLite : états des fichiers + cache d'empreintes
  ausha_client.py            client HTTP de l'API Ausha + erreurs typées
  sync_engine.py             un cycle de synchro complet (sans Qt)
  autostart.py               clé Run HKCU
  logging_setup.py           log fichier tournant
  app.py                     main() : assemble tout
  assets/icon.png, icon.ico
  ui/
    __init__.py
    style.py                 thème clair/sombre (QSS)
    icons.py                 icône de l'app + icônes d'état
    widgets.py               petits widgets partagés (Row, pill, labels)
    async_call.py            exécuter un appel Ausha hors du thread UI
    single_instance.py       une seule instance, la 2e ramène la fenêtre
    controller.py            AppController + CycleWorker
    activity_page.py
    rules_page.py
    settings_page.py
    main_window.py
    tray.py
tests/
  test_package.py test_config.py test_rules.py test_scanner.py test_journal.py
  test_ausha_client.py test_sync_engine.py test_autostart.py test_logging_setup.py
  test_ui_smoke.py
```

---

### Task 1: Squelette du projet

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `syncausha/__init__.py`, `syncausha/ui/__init__.py`, `tests/test_package.py`

- [ ] **Step 1: Créer `pyproject.toml`**

```toml
[project]
name = "syncausha"
version = "1.0.0"
description = "Publie automatiquement sur Ausha les podcasts d'un dossier"
requires-python = ">=3.12"
dependencies = [
    "PySide6-Essentials>=6.10",
    "httpx>=0.28",
    "keyring>=25",
    "Pillow>=11",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "respx>=0.22",
    "pyinstaller>=6.16",
]

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["syncausha*"]

[tool.setuptools.package-data]
syncausha = ["assets/*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Créer `.gitignore`**

```
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
build/
dist/
SyncAusha.spec
```

- [ ] **Step 3: Écrire le test qui échoue**

`tests/test_package.py` :

```python
import syncausha


def test_version():
    assert syncausha.__version__ == "1.0.0"
```

- [ ] **Step 4: Créer l'environnement et vérifier l'échec**

Run:
```
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/test_package.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha'` (ou échec d'installation si le paquet n'existe pas encore : créer d'abord les fichiers du step 5 puis relancer `pip install -e ".[dev]"`).

- [ ] **Step 5: Implémenter**

`syncausha/__init__.py` :

```python
"""SyncAusha : publie automatiquement sur Ausha les podcasts d'un dossier."""

__version__ = "1.0.0"
```

`syncausha/ui/__init__.py` : fichier vide.

Relancer `.venv/Scripts/python -m pip install -e ".[dev]"`.

- [ ] **Step 6: Vérifier que le test passe**

Run: `.venv/Scripts/python -m pytest tests/test_package.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```
git add pyproject.toml .gitignore syncausha tests
git commit -m "chore: squelette du projet SyncAusha" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Réglages (`config.py`)

**Files:**
- Create: `syncausha/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_config.py` :

```python
from syncausha import config as cfg
from syncausha.config import Config, Rule, load_config, save_config


def test_missing_file_gives_defaults(tmp_path):
    config = load_config(tmp_path / "config.json")
    assert config == Config()
    assert config.interval_minutes == 15
    assert config.rules == []
    assert config.api_base_url == "https://api-content.ausha.co/v1"


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = Config(
        watch_folder="D:/Podcasts",
        interval_minutes=30,
        dry_run=True,
        rules=[
            Rule(
                keyword="MARS ATTACK",
                show_id=12,
                show_name="Mars Attack",
                playlist_id=7,
                playlist_name="Saison 3",
                image_path="C:/images/mars.png",
                description_template="Nouvel épisode de Mars Attack",
            )
        ],
    )
    save_config(config, path)
    assert load_config(path) == config


def test_interval_is_clamped():
    assert Config(interval_minutes=1).interval_minutes == 5
    assert Config(interval_minutes=500).interval_minutes == 120


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"watch_folder": "X", "future": 1,'
        ' "rules": [{"keyword": "A", "show_id": 1, "extra": true}]}',
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.watch_folder == "X"
    assert config.rules == [Rule(keyword="A", show_id=1)]


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{pas du json", encoding="utf-8")
    assert load_config(path) == Config()


def test_token_roundtrip(monkeypatch):
    store = {}

    def delete(service, user):
        if (service, user) not in store:
            raise cfg.PasswordDeleteError()
        del store[(service, user)]

    monkeypatch.setattr(cfg.keyring, "get_password", lambda s, u: store.get((s, u)))
    monkeypatch.setattr(cfg.keyring, "set_password", lambda s, u, p: store.__setitem__((s, u), p))
    monkeypatch.setattr(cfg.keyring, "delete_password", delete)

    assert cfg.get_token() is None
    cfg.set_token("  abc  ")
    assert cfg.get_token() == "abc"
    cfg.set_token("")
    assert cfg.get_token() is None
    cfg.set_token("")  # supprimer un jeton absent ne plante pas
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.config'`

- [ ] **Step 3: Implémenter**

`syncausha/config.py` :

```python
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
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```
git add syncausha/config.py tests/test_config.py
git commit -m "feat: réglages JSON et jeton Ausha dans le Gestionnaire d'identifiants" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Règles (`rules.py`)

Correspondance insensible à la casse et aux accents. `_`, `-` et `.` comptent comme des espaces, pour que `Mars_Attack_ep12.mp3` corresponde à `MARS ATTACK`.

**Files:**
- Create: `syncausha/rules.py`
- Test: `tests/test_rules.py`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_rules.py` :

```python
from pathlib import Path

import pytest
from PIL import Image

from syncausha.config import Rule
from syncausha.rules import (
    episode_description,
    episode_title,
    find_rule,
    validate_image,
    validate_rule,
)

MARS = Rule(keyword="MARS ATTACK", show_id=1, show_name="Mars Attack")
DEBRIEF = Rule(keyword="Le Débrief", show_id=2)


@pytest.mark.parametrize(
    "filename",
    [
        "MARS ATTACK - Épisode 12.mp3",
        "mars attack 12.mp3",
        "Mars_Attack_ep12.wav",
        "Replay MARS-ATTACK.m4a",
    ],
)
def test_keyword_matches_ignoring_case_and_separators(filename):
    assert find_rule(filename, [MARS]) is MARS


def test_accents_are_ignored():
    assert find_rule("LE DEBRIEF 44.mp3", [DEBRIEF]) is DEBRIEF


def test_first_matching_rule_wins():
    generic = Rule(keyword="ATTACK", show_id=9)
    assert find_rule("MARS ATTACK 1.mp3", [generic, MARS]) is generic
    assert find_rule("MARS ATTACK 1.mp3", [MARS, generic]) is MARS


def test_no_match_returns_none():
    assert find_rule("interview_brut.mp3", [MARS, DEBRIEF]) is None


def test_empty_keyword_never_matches():
    assert find_rule("x.mp3", [Rule(keyword="  ", show_id=1)]) is None


def test_extension_is_not_part_of_match():
    assert find_rule("episode.mp3", [Rule(keyword="mp3", show_id=1)]) is None


def test_episode_title_strips_extension_and_extra_spaces():
    assert episode_title(Path("D:/p/MARS ATTACK  -  Épisode 12.mp3")) == "MARS ATTACK - Épisode 12"


def test_episode_title_is_truncated():
    assert len(episode_title(Path("x" * 200 + ".mp3"))) == 140


def test_episode_description_from_template():
    assert episode_description(Rule(keyword="A", show_id=1, description_template="  Bonjour \n")) == "Bonjour"
    long_rule = Rule(keyword="A", show_id=1, description_template="y" * 5000)
    assert len(episode_description(long_rule)) == 3900


def make_image(path: Path, size=(1400, 1400), fmt="PNG") -> Path:
    Image.new("RGB", size, "purple").save(path, fmt)
    return path


def test_valid_png_and_jpeg(tmp_path):
    assert validate_image(make_image(tmp_path / "a.png")) is None
    assert validate_image(make_image(tmp_path / "a.jpg", fmt="JPEG")) is None


def test_missing_image(tmp_path):
    assert "introuvable" in validate_image(tmp_path / "nope.png")


def test_small_image(tmp_path):
    assert "trop petite" in validate_image(make_image(tmp_path / "s.png", (300, 300)))


def test_wrong_format(tmp_path):
    assert "JPEG ou PNG" in validate_image(make_image(tmp_path / "a.gif", fmt="GIF"))


def test_not_an_image(tmp_path):
    path = tmp_path / "x.png"
    path.write_bytes(b"pas une image")
    assert validate_image(path) == "Image illisible"


def test_too_heavy(tmp_path, monkeypatch):
    monkeypatch.setattr("syncausha.rules.MAX_IMAGE_BYTES", 10)
    assert "trop lourde" in validate_image(make_image(tmp_path / "a.png"))


def test_validate_rule_checks_show_playlist_and_image(tmp_path):
    rule = Rule(keyword="A", show_id=1, show_name="Mars", playlist_id=7, playlist_name="S3")
    assert validate_rule(rule, {1: {7}}) is None
    assert "Émission introuvable" in validate_rule(rule, {2: set()})
    assert "Playlist introuvable" in validate_rule(rule, {1: {8}})
    rule.image_path = str(tmp_path / "missing.png")
    assert "Image introuvable" in validate_rule(rule, {1: {7}})


def test_rule_without_playlist_or_image_is_valid():
    assert validate_rule(Rule(keyword="A", show_id=1), {1: set()}) is None
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.rules'`

- [ ] **Step 3: Implémenter**

`syncausha/rules.py` :

```python
"""Correspondance fichier → règle, titre/description d'épisode, validation des règles."""
from __future__ import annotations

import unicodedata
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from syncausha.config import Rule

MAX_TITLE_LENGTH = 140
MAX_DESCRIPTION_LENGTH = 3900
MIN_IMAGE_SIDE = 400
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_SEPARATORS = str.maketrans({"_": " ", "-": " ", ".": " "})


def normalize(text: str) -> str:
    """Minuscules, sans accents, séparateurs → espaces, espaces multiples réduits."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.translate(_SEPARATORS).casefold().split())


def find_rule(filename: str, rules: list[Rule]) -> Rule | None:
    """Première règle dont le mot-clé apparaît dans le nom du fichier (sans extension)."""
    name = normalize(Path(filename).stem)
    for rule in rules:
        keyword = normalize(rule.keyword)
        if keyword and keyword in name:
            return rule
    return None


def episode_title(path: Path) -> str:
    return " ".join(path.stem.split())[:MAX_TITLE_LENGTH]


def episode_description(rule: Rule) -> str:
    return rule.description_template.strip()[:MAX_DESCRIPTION_LENGTH]


def validate_image(path: str | Path) -> str | None:
    """Renvoie un message d'erreur si l'image ne convient pas à Ausha, sinon None."""
    image_path = Path(path)
    if not image_path.is_file():
        return f"Image introuvable : {image_path}"
    if image_path.stat().st_size > MAX_IMAGE_BYTES:
        return "Image trop lourde (10 Mo maximum)"
    try:
        with Image.open(image_path) as image:
            fmt, (width, height) = image.format, image.size
    except (OSError, UnidentifiedImageError):
        return "Image illisible"
    if fmt not in ("JPEG", "PNG"):
        return "L'image doit être au format JPEG ou PNG"
    if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
        return f"Image trop petite ({width}×{height}, minimum 400×400)"
    return None


def validate_rule(rule: Rule, playlists_by_show: dict[int, set[int]]) -> str | None:
    """Vérifie que l'émission, la playlist et l'image de la règle sont utilisables."""
    if rule.show_id not in playlists_by_show:
        return f"Émission introuvable sur Ausha : {rule.show_name or rule.show_id}"
    if rule.playlist_id is not None and rule.playlist_id not in playlists_by_show[rule.show_id]:
        return f"Playlist introuvable sur Ausha : {rule.playlist_name or rule.playlist_id}"
    if rule.image_path:
        return validate_image(rule.image_path)
    return None
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```
git add syncausha/rules.py tests/test_rules.py
git commit -m "feat: correspondance des règles et validation des images" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Scanner (`scanner.py`)

**Files:**
- Create: `syncausha/scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_scanner.py` :

```python
import os
import time

import pytest

from syncausha import scanner
from syncausha.scanner import scan_ready_files


def touch(path, age_seconds=120, content=b"audio"):
    path.write_bytes(content)
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def test_returns_old_audio_files_sorted(tmp_path):
    touch(tmp_path / "b.mp3")
    touch(tmp_path / "a.M4A")
    result = scan_ready_files(tmp_path)
    assert [f.path.name for f in result] == ["a.M4A", "b.mp3"]
    assert result[0].size == 5


def test_ignores_other_extensions(tmp_path):
    touch(tmp_path / "notes.txt")
    touch(tmp_path / "cover.png")
    assert scan_ready_files(tmp_path) == []


def test_ignores_recent_files(tmp_path):
    touch(tmp_path / "new.mp3", age_seconds=5)
    assert scan_ready_files(tmp_path) == []
    assert len(scan_ready_files(tmp_path, min_age_seconds=0)) == 1


def test_ignores_subfolders(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    touch(sub / "x.mp3")
    assert scan_ready_files(tmp_path) == []


def test_ignores_locked_files(tmp_path, monkeypatch):
    touch(tmp_path / "locked.mp3")
    monkeypatch.setattr(scanner, "_can_open", lambda path: False)
    assert scan_ready_files(tmp_path) == []


def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_ready_files(tmp_path / "absent")
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.scanner'`

- [ ] **Step 3: Implémenter**

`syncausha/scanner.py` :

```python
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
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `.venv/Scripts/python -m pytest tests/test_scanner.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```
git add syncausha/scanner.py tests/test_scanner.py
git commit -m "feat: détection des fichiers audio prêts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Journal local (`journal.py`)

Ajoute le statut `en_attente` (fichier vu, pas encore traité ou en attente d'un nouvel essai), implicite dans la spec.

**Files:**
- Create: `syncausha/journal.py`
- Test: `tests/test_journal.py`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_journal.py` :

```python
import itertools

import pytest

import syncausha.journal as journal_module
from syncausha.journal import Journal, Status, Step


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


def test_recent_and_attention_lists(journal):
    for name in ("a", "b", "c", "d"):
        journal.ensure(name, f"{name}.mp3", 1)
    journal.update("a", status=Status.PUBLIE)
    journal.update("b", status=Status.SANS_REGLE)
    journal.update("c", status=Status.EN_COURS)
    journal.update("d", status=Status.ECHEC)
    assert [e.hash for e in journal.recent()] == ["c", "a"]
    assert [e.hash for e in journal.needing_attention()] == ["d", "b"]


def test_reset_for_retry(journal):
    journal.ensure("h1", "a.mp3", 1)
    journal.update("h1", status=Status.ECHEC, attempts=3, last_error="x")
    journal.reset_for_retry("h1")
    entry = journal.get("h1")
    assert entry.status is Status.EN_ATTENTE
    assert entry.attempts == 0
    assert entry.last_error == ""


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


def test_persists_across_instances(tmp_path):
    first = Journal(tmp_path / "j.db")
    first.ensure("h", "a.mp3", 1)
    first.update("h", status=Status.PUBLIE)
    first.close()
    second = Journal(tmp_path / "j.db")
    assert second.get("h").status is Status.PUBLIE
    second.close()
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_journal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.journal'`

- [ ] **Step 3: Implémenter**

`syncausha/journal.py` :

```python
"""Journal local (SQLite) : état de publication de chaque fichier, identifié par son contenu."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Status(StrEnum):
    EN_ATTENTE = "en_attente"
    SANS_REGLE = "sans_regle"
    REGLE_CASSEE = "regle_cassee"
    EN_COURS = "en_cours"
    PUBLIE = "publie"
    DEJA_PRESENT = "deja_present"
    REJETE = "rejete"
    ECHEC = "echec"


class Step(StrEnum):
    NONE = "none"
    CREATED = "created"
    IMAGE_DONE = "image_done"
    PLAYLIST_DONE = "playlist_done"


# Statuts qu'un cycle ne retraite pas (seul « Réessayer » relance REJETE et ECHEC).
FINAL_STATUSES = frozenset({Status.PUBLIE, Status.DEJA_PRESENT, Status.REJETE, Status.ECHEC})
ATTENTION_STATUSES = (Status.SANS_REGLE, Status.REGLE_CASSEE, Status.REJETE, Status.ECHEC)


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
    {"filename", "size", "show_id", "show_name", "episode_id", "step", "status", "attempts", "last_error"}
)


class Journal:
    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock:
            self._db.executescript(_SCHEMA)

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
        unknown = set(values) - _UPDATABLE
        if unknown:
            raise ValueError(f"Champs inconnus : {sorted(unknown)}")
        values["updated_at"] = self._clock()
        assignments = ", ".join(f"{name} = ?" for name in values)
        params = tuple(str(v) if isinstance(v, StrEnum) else v for v in values.values())
        with self._lock, self._db:
            self._db.execute(f"UPDATE files SET {assignments} WHERE hash = ?", (*params, file_hash))

    def reset_for_retry(self, file_hash: str) -> None:
        self.update(file_hash, status=Status.EN_ATTENTE, attempts=0, last_error="")

    def recent(self, limit: int = 50) -> list[Entry]:
        return self._select(f"status NOT IN ({_placeholders()})", ATTENTION_STATUSES, limit)

    def needing_attention(self) -> list[Entry]:
        return self._select(f"status IN ({_placeholders()})", ATTENTION_STATUSES, -1)

    def forget_unresolved(self, keep: set[str]) -> None:
        """Oublie les fichiers disparus du dossier qui n'ont jamais donné d'épisode."""
        with self._lock, self._db:
            rows = self._db.execute(
                "SELECT hash FROM files WHERE step = 'none' AND status NOT IN ('publie', 'deja_present')"
            ).fetchall()
            stale = [(h,) for (h,) in rows if h not in keep]
            self._db.executemany("DELETE FROM files WHERE hash = ?", stale)

    def _select(self, where: str, params: tuple, limit: int) -> list[Entry]:
        query = f"SELECT {_COLUMNS} FROM files WHERE {where} ORDER BY updated_at DESC, rowid DESC LIMIT ?"
        with self._lock:
            rows = self._db.execute(query, (*(str(p) for p in params), limit)).fetchall()
        return [_to_entry(row) for row in rows]


def _placeholders() -> str:
    return ", ".join("?" * len(ATTENTION_STATUSES))


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
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `.venv/Scripts/python -m pytest tests/test_journal.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```
git add syncausha/journal.py tests/test_journal.py
git commit -m "feat: journal SQLite des fichiers publiés" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Client API Ausha (`ausha_client.py`)

Référence API : https://developers.ausha.co/docs/1.0/overview. Les envois de fichiers se font en `multipart/form-data`, champ `file`. Le fichier est lu en streaming, avec un rappel de progression.

**Files:**
- Create: `syncausha/ausha_client.py`
- Test: `tests/test_ausha_client.py`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_ausha_client.py` :

```python
import httpx
import pytest
import respx

from syncausha.ausha_client import (
    AushaClient,
    AuthError,
    Episode,
    Playlist,
    RejectedError,
    Show,
    TransientError,
)

BASE = "https://api.test/v1"


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def client(sleeps):
    c = AushaClient("secret-token", BASE, sleep=sleeps.append)
    yield c
    c.close()


@pytest.fixture
def api():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "MARS ATTACK 12.mp3"
    path.write_bytes(b"ID3" + b"x" * 5000)
    return path


def test_list_shows_sends_token_and_follows_pages(api, client):
    route = api.get("/shows/granted")
    route.side_effect = [
        httpx.Response(200, json={"data": [{"id": 1, "name": "Mars Attack"}], "meta": {"pagination": {"total_pages": 2}}}),
        httpx.Response(200, json={"data": [{"id": 2, "name": "Silicon Talk"}], "meta": {"pagination": {"total_pages": 2}}}),
    ]
    assert client.list_shows() == [Show(1, "Mars Attack"), Show(2, "Silicon Talk")]
    first = route.calls[0].request
    assert first.headers["Authorization"] == "Bearer secret-token"
    assert first.url.params["page"] == "1"
    assert route.calls[1].request.url.params["page"] == "2"


def test_list_playlists(api, client):
    api.get("/shows/1/playlists").respond(200, json={"data": [{"id": 7, "name": "Saison 3"}]})
    assert client.list_playlists(1) == [Playlist(7, "Saison 3")]


def test_find_episodes_passes_query(api, client):
    route = api.get("/shows/1/podcasts").respond(200, json={"data": [{"id": 99, "name": "MARS ATTACK 12"}]})
    assert client.find_episodes(1, "MARS ATTACK 12") == [Episode(99, "MARS ATTACK 12")]
    assert route.calls.last.request.url.params["q"] == "MARS ATTACK 12"


def test_create_episode_uploads_multipart_and_publishes(api, client, audio):
    route = api.post("/shows/1/podcasts").respond(201, json={"data": {"id": 321}})
    progress = []
    assert client.create_episode(1, "MARS ATTACK 12", "Nouvel épisode", audio, on_progress=progress.append) == 321
    request = route.calls.last.request
    body = request.read()
    assert request.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="state"\r\n\r\nactive' in body
    assert b'name="name"\r\n\r\nMARS ATTACK 12' in body
    assert 'name="description"\r\n\r\nNouvel épisode'.encode() in body
    assert b'filename="MARS ATTACK 12.mp3"' in body
    assert b"audio/mpeg" in body
    assert progress and progress[-1] == 100


def test_description_is_omitted_when_empty(api, client, audio):
    route = api.post("/shows/1/podcasts").respond(201, json={"data": {"id": 1}})
    client.create_episode(1, "T", "", audio)
    assert b'name="description"' not in route.calls.last.request.read()


def test_upload_image_and_add_to_playlist(api, client, tmp_path):
    image = tmp_path / "cover.png"
    image.write_bytes(b"\x89PNG fake")
    image_route = api.post("/podcasts/321/image").respond(200, json={"data": {"url": "x"}})
    playlist_route = api.post("/playlists/7/podcasts/321").respond(201, json={})
    client.upload_episode_image(321, image)
    client.add_to_playlist(7, 321)
    assert b'filename="cover.png"' in image_route.calls.last.request.read()
    assert playlist_route.called


def test_rate_limit_waits_then_retries(api, client, sleeps):
    api.get("/shows/granted").side_effect = [
        httpx.Response(429, headers={"Retry-After": "3"}),
        httpx.Response(200, json={"data": []}),
    ]
    assert client.list_shows() == []
    assert sleeps == [3.0]


def test_rate_limit_gives_up_after_max_retries(api, sleeps):
    limited = AushaClient("t", BASE, sleep=sleeps.append, max_rate_limit_retries=2)
    api.get("/shows/granted").respond(429)
    with pytest.raises(TransientError):
        limited.list_shows()
    assert sleeps == [60.0, 60.0]
    limited.close()


@pytest.mark.parametrize(
    "status,error",
    [(401, AuthError), (403, AuthError), (404, RejectedError), (422, RejectedError), (500, TransientError), (503, TransientError)],
)
def test_http_errors_are_typed(api, client, status, error):
    api.get("/shows/granted").respond(status, json={"message": "Nope"})
    with pytest.raises(error, match="Nope"):
        client.list_shows()


def test_validation_errors_are_readable(api, client, audio):
    api.post("/shows/1/podcasts").respond(
        422,
        json={"message": "The given data was invalid.", "errors": {"file": ["The file may not be greater than 500000 kilobytes."]}},
    )
    with pytest.raises(RejectedError, match="500000 kilobytes"):
        client.create_episode(1, "T", "", audio)


def test_network_error_is_transient(api, client):
    api.get("/shows/granted").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(TransientError):
        client.list_shows()
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_ausha_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.ausha_client'`

- [ ] **Step 3: Implémenter**

`syncausha/ausha_client.py` :

```python
"""Client minimal de l'API publique Ausha (https://developers.ausha.co)."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from syncausha.config import DEFAULT_API_BASE_URL

log = logging.getLogger(__name__)

PAGE_SIZE = 50
DEFAULT_RETRY_AFTER = 60.0
_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/x-m4a",
    ".wav": "audio/x-wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/x-flac",
    ".mp4": "video/mp4",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

ProgressCallback = Callable[[int], None]


class AushaError(Exception):
    """Erreur renvoyée par Ausha ou par le réseau."""


class AuthError(AushaError):
    """Jeton absent, invalide ou sans droits (401/403)."""


class RejectedError(AushaError):
    """Requête refusée par Ausha : inutile de la renvoyer telle quelle."""


class TransientError(AushaError):
    """Problème passager : réseau, délai dépassé, 5xx, 429 persistant."""


@dataclass(frozen=True)
class Show:
    id: int
    name: str


@dataclass(frozen=True)
class Playlist:
    id: int
    name: str


@dataclass(frozen=True)
class Episode:
    id: int
    name: str


class AushaClient:
    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_API_BASE_URL,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_rate_limit_retries: int = 5,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=httpx.Timeout(60.0),
            transport=transport,
        )
        self._sleep = sleep
        self._max_retries = max_rate_limit_retries

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> AushaClient:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def list_shows(self) -> list[Show]:
        return [Show(int(item["id"]), _name(item)) for item in self._get_all("/shows/granted")]

    def list_playlists(self, show_id: int) -> list[Playlist]:
        return [Playlist(int(item["id"]), _name(item)) for item in self._get_all(f"/shows/{show_id}/playlists")]

    def find_episodes(self, show_id: int, query: str) -> list[Episode]:
        items = self._get_all(f"/shows/{show_id}/podcasts", {"q": query})
        return [Episode(int(item["id"]), _name(item)) for item in items]

    def create_episode(
        self,
        show_id: int,
        name: str,
        description: str,
        audio_path: Path,
        on_progress: ProgressCallback | None = None,
    ) -> int:
        """Crée et publie immédiatement l'épisode (state=active). Renvoie son id."""
        data = {"name": name, "state": "active"}
        if description:
            data["description"] = description
        body = self._send("POST", f"/shows/{show_id}/podcasts", data=data, file_path=audio_path, on_progress=on_progress)
        return int(body["data"]["id"])

    def upload_episode_image(self, episode_id: int, image_path: Path) -> None:
        self._send("POST", f"/podcasts/{episode_id}/image", file_path=image_path)

    def add_to_playlist(self, playlist_id: int, episode_id: int) -> None:
        self._send("POST", f"/playlists/{playlist_id}/podcasts/{episode_id}")

    def _get_all(self, url: str, params: dict | None = None) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            body = self._send("GET", url, params={**(params or {}), "page": page, "per_page": PAGE_SIZE})
            items.extend(body.get("data") or [])
            pagination = (body.get("meta") or {}).get("pagination") or {}
            if page >= int(pagination.get("total_pages") or 1):
                return items
            page += 1

    def _send(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        file_path: Path | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            response = self._request_once(method, url, params, data, file_path, on_progress)
            if response.status_code != 429 or attempt == self._max_retries:
                break
            delay = _retry_after(response)
            log.info("Ausha demande une pause de %.0f s", delay)
            self._sleep(delay)
        return _parse(response)

    def _request_once(self, method, url, params, data, file_path, on_progress) -> httpx.Response:
        handle = None
        try:
            files = None
            if file_path is not None:
                handle = open(file_path, "rb")
                reader = _ProgressReader(handle, file_path.stat().st_size, on_progress)
                files = {"file": (file_path.name, reader, _MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream"))}
            return self._http.request(method, url, params=params, data=data, files=files)
        except httpx.TransportError as exc:
            raise TransientError(f"Connexion à Ausha impossible : {exc}") from exc
        finally:
            if handle is not None:
                handle.close()


class _ProgressReader:
    """Enveloppe un fichier ouvert et signale le pourcentage lu (donc envoyé)."""

    def __init__(self, handle, total: int, callback: ProgressCallback | None) -> None:
        self._handle = handle
        self._total = total
        self._callback = callback
        self._sent = 0
        self._last = -1

    def read(self, size: int = -1) -> bytes:
        chunk = self._handle.read(size)
        if self._callback and self._total:
            self._sent += len(chunk)
            percent = min(100, self._sent * 100 // self._total)
            if percent != self._last:
                self._last = percent
                self._callback(percent)
        return chunk

    def seek(self, offset: int, whence: int = 0) -> int:
        if offset == 0 and whence == 0:
            self._sent = 0
        return self._handle.seek(offset, whence)

    def __getattr__(self, name: str):
        return getattr(self._handle, name)


def _retry_after(response: httpx.Response) -> float:
    try:
        return max(0.0, float(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER)))
    except ValueError:
        return DEFAULT_RETRY_AFTER


def _parse(response: httpx.Response) -> dict[str, Any]:
    status = response.status_code
    if status < 400:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}
    message = _error_message(response)
    if status in (401, 403):
        raise AuthError(message)
    if status in (408, 429) or status >= 500:
        raise TransientError(message)
    raise RejectedError(message)


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        parts = [str(body.get("message") or "")]
        errors = body.get("errors")
        if isinstance(errors, dict):
            for messages in errors.values():
                parts.extend(messages if isinstance(messages, list) else [str(messages)])
        text = " ".join(p for p in parts if p).strip()
        if text:
            return f"{text} (HTTP {response.status_code})"
    return f"Ausha a répondu HTTP {response.status_code}"


def _name(item: dict) -> str:
    return str(item.get("name") or item.get("title") or item.get("id"))
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `.venv/Scripts/python -m pytest tests/test_ausha_client.py -v`
Expected: all passed. Si `test_create_episode_uploads_multipart_and_publishes` échoue sur `progress` vide ou sur `request.read()` (fichier déjà fermé), c'est que la version de respx installée ne lit pas le corps avant de répondre : dans ce test, remplacer `.respond(...)` par un `side_effect` qui lit le corps pendant l'appel :

```python
    bodies = []

    def capture(request):
        bodies.append(request.read())
        return httpx.Response(201, json={"data": {"id": 321}})

    route = api.post("/shows/1/podcasts").mock(side_effect=capture)
    # ... puis utiliser body = bodies[-1]
```

- [ ] **Step 5: Commit**

```
git add syncausha/ausha_client.py tests/test_ausha_client.py
git commit -m "feat: client de l'API Ausha avec erreurs typées et gestion du 429" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Moteur de synchro (`sync_engine.py`)

**Files:**
- Create: `syncausha/sync_engine.py`
- Test: `tests/test_sync_engine.py`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_sync_engine.py` :

```python
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
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_sync_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.sync_engine'`

- [ ] **Step 3: Implémenter**

`syncausha/sync_engine.py` :

```python
"""Un cycle de synchronisation : dossier → règles → Ausha. Aucune dépendance à Qt."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from syncausha.ausha_client import AushaClient, AushaError, AuthError, RejectedError, TransientError
from syncausha.config import Config, Rule
from syncausha.journal import FINAL_STATUSES, Entry, Journal, Status, Step
from syncausha.rules import episode_description, episode_title, find_rule, validate_rule
from syncausha.scanner import ReadyFile, scan_ready_files

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Event:
    """Événement par fichier : progress, published, no_rule, broken_rule, rejected, failed, dry_run."""

    kind: str
    title: str
    detail: str = ""
    percent: int = 0


@dataclass(frozen=True)
class CycleResult:
    """État global après un cycle : ok, attention, paused, not_configured, folder_missing, auth_error, offline."""

    state: str
    message: str = ""


class SyncEngine:
    def __init__(
        self,
        config: Config,
        journal: Journal,
        client_factory: Callable[[Config], AushaClient | None],
        on_event: Callable[[Event], None] = lambda event: None,
        scan: Callable[[Path], list[ReadyFile]] = scan_ready_files,
    ) -> None:
        self.config = config
        self.journal = journal
        self._client_factory = client_factory
        self._on_event = on_event
        self._scan = scan

    def run_cycle(self) -> CycleResult:
        config = self.config
        if config.paused:
            return CycleResult("paused")
        if not config.watch_folder:
            return CycleResult("not_configured", "Choisissez le dossier à surveiller.")
        folder = Path(config.watch_folder)
        if not folder.is_dir():
            return CycleResult("folder_missing", f"Dossier introuvable : {folder}")
        client = self._client_factory(config)
        if client is None:
            return CycleResult("not_configured", "Renseignez votre jeton Ausha.")
        try:
            return self._run(config, folder, client)
        except AuthError as exc:
            log.warning("Jeton refusé par Ausha : %s", exc)
            return CycleResult("auth_error", str(exc))
        except AushaError as exc:
            log.warning("Ausha injoignable : %s", exc)
            return CycleResult("offline", str(exc))
        finally:
            client.close()

    def _run(self, config: Config, folder: Path, client: AushaClient) -> CycleResult:
        catalog = self._load_catalog(client, config.rules)
        seen: set[str] = set()
        for ready in self._scan(folder):
            try:
                file_hash = self.journal.file_hash(ready.path, ready.size, ready.mtime)
            except OSError as exc:
                log.warning("Lecture impossible de %s : %s", ready.path, exc)
                continue
            seen.add(file_hash)
            try:
                self._process(config, client, catalog, ready, file_hash)
            except AuthError:
                raise
            except Exception as exc:
                log.exception("Erreur inattendue sur %s", ready.path.name)
                self._record_failure(file_hash, episode_title(ready.path), f"Erreur inattendue : {exc}")
        self.journal.forget_unresolved(seen)
        attention = self.journal.needing_attention()
        if attention:
            return CycleResult("attention", f"{len(attention)} fichier(s) à traiter")
        return CycleResult("ok")

    def _load_catalog(self, client: AushaClient, rules: list[Rule]) -> dict[int, set[int]]:
        """Émissions accessibles utilisées par les règles → ids de leurs playlists."""
        available = {show.id for show in client.list_shows()}
        wanted = {rule.show_id for rule in rules} & available
        return {show_id: {p.id for p in client.list_playlists(show_id)} for show_id in wanted}

    def _process(self, config: Config, client: AushaClient, catalog: dict[int, set[int]], ready: ReadyFile, file_hash: str) -> None:
        entry = self.journal.ensure(file_hash, ready.path.name, ready.size)
        if entry.status in FINAL_STATUSES:
            return
        title = episode_title(ready.path)
        rule = find_rule(ready.path.name, config.rules)
        if rule is None:
            self._flag(entry, Status.SANS_REGLE, "Aucune règle ne correspond", "no_rule", title)
            return
        problem = validate_rule(rule, catalog)
        if problem:
            self._flag(entry, Status.REGLE_CASSEE, problem, "broken_rule", title)
            return
        if config.dry_run:
            self.journal.update(file_hash, status=Status.EN_ATTENTE, last_error="")
            self._emit(Event("dry_run", title, f"Serait publié dans {rule.show_name or rule.show_id}"))
            return
        self.journal.update(file_hash, status=Status.EN_COURS, show_id=rule.show_id, show_name=rule.show_name, last_error="")
        try:
            self._publish(client, rule, ready, entry, title)
        except RejectedError as exc:
            self.journal.update(file_hash, status=Status.REJETE, last_error=str(exc))
            self._emit(Event("rejected", title, str(exc)))
        except TransientError as exc:
            self._record_failure(file_hash, title, str(exc))

    def _publish(self, client: AushaClient, rule: Rule, ready: ReadyFile, entry: Entry, title: str) -> None:
        """Enchaîne les étapes restantes ; chaque étape réussie est notée pour pouvoir reprendre."""
        file_hash, step, episode_id = entry.hash, entry.step, entry.episode_id
        if step is Step.NONE:
            existing = client.find_episodes(rule.show_id, title)
            if any(episode.name.casefold() == title.casefold() for episode in existing):
                self.journal.update(file_hash, status=Status.DEJA_PRESENT)
                return
            episode_id = client.create_episode(
                rule.show_id,
                title,
                episode_description(rule),
                ready.path,
                on_progress=lambda percent: self._emit(Event("progress", title, percent=percent)),
            )
            self.journal.update(file_hash, episode_id=episode_id, step=Step.CREATED)
            step = Step.CREATED
        if step is Step.CREATED:
            if rule.image_path:
                client.upload_episode_image(episode_id, Path(rule.image_path))
            self.journal.update(file_hash, step=Step.IMAGE_DONE)
            step = Step.IMAGE_DONE
        if step is Step.IMAGE_DONE:
            if rule.playlist_id is not None:
                client.add_to_playlist(rule.playlist_id, episode_id)
            self.journal.update(file_hash, step=Step.PLAYLIST_DONE)
        self.journal.update(file_hash, status=Status.PUBLIE, attempts=0, last_error="")
        self._emit(Event("published", title, rule.show_name))

    def _flag(self, entry: Entry, status: Status, message: str, kind: str, title: str) -> None:
        """Marque un fichier bloqué ; ne notifie qu'au changement de statut."""
        if entry.status is not status:
            self._emit(Event(kind, title, message))
        self.journal.update(entry.hash, status=status, last_error=message)

    def _record_failure(self, file_hash: str, title: str, message: str) -> None:
        entry = self.journal.get(file_hash)
        attempts = (entry.attempts if entry else 0) + 1
        if attempts >= MAX_ATTEMPTS:
            self.journal.update(file_hash, status=Status.ECHEC, attempts=attempts, last_error=message)
            self._emit(Event("failed", title, message))
        else:
            self.journal.update(file_hash, status=Status.EN_ATTENTE, attempts=attempts, last_error=message)

    def _emit(self, event: Event) -> None:
        try:
            self._on_event(event)
        except Exception:
            log.exception("Gestionnaire d'événement en erreur")
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `.venv/Scripts/python -m pytest tests/test_sync_engine.py -v`
Expected: all passed

- [ ] **Step 5: Lancer toute la suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all passed

- [ ] **Step 6: Commit**

```
git add syncausha/sync_engine.py tests/test_sync_engine.py
git commit -m "feat: moteur de synchro avec reprise par étape et anti-doublon" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Démarrage automatique (`autostart.py`)

**Files:**
- Create: `syncausha/autostart.py`
- Test: `tests/test_autostart.py`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_autostart.py` (écrit une valeur de test `SyncAushaTest` dans HKCU\...\Run puis la supprime) :

```python
import pytest

winreg = pytest.importorskip("winreg")

from syncausha import autostart  # noqa: E402

NAME = "SyncAushaTest"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    autostart.set_enabled(False, NAME)


def test_enable_then_disable():
    assert not autostart.is_enabled(NAME)
    autostart.set_enabled(True, NAME, command='"C:\\x.exe" --minimized')
    assert autostart.is_enabled(NAME)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.RUN_KEY) as key:
        assert winreg.QueryValueEx(key, NAME)[0] == '"C:\\x.exe" --minimized'
    autostart.set_enabled(False, NAME)
    assert not autostart.is_enabled(NAME)
    autostart.set_enabled(False, NAME)  # idempotent


def test_launch_command_in_dev_mode():
    command = autostart.launch_command()
    assert command.endswith("--minimized")
    assert "run_syncausha.py" in command
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_autostart.py -v`
Expected: FAIL — `ImportError: cannot import name 'autostart'`

- [ ] **Step 3: Implémenter**

`syncausha/autostart.py` :

```python
"""Lancement au démarrage de Windows via HKCU\\...\\Run (sans droits administrateur)."""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SyncAusha"


def launch_command() -> str:
    """Commande enregistrée dans Run : l'exe empaqueté, ou pythonw + script en développement."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    script = Path(__file__).resolve().parent.parent / "run_syncausha.py"
    return f'"{pythonw}" "{script}" --minimized'


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, value_name)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool, value_name: str = VALUE_NAME, command: str | None = None) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command or launch_command())
            return
        try:
            winreg.DeleteValue(key, value_name)
        except FileNotFoundError:
            pass
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `.venv/Scripts/python -m pytest tests/test_autostart.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```
git add syncausha/autostart.py tests/test_autostart.py
git commit -m "feat: lancement au démarrage de Windows" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Logs et icône de l'application

**Files:**
- Create: `syncausha/logging_setup.py`, `tools/make_icon.py`, `syncausha/assets/icon.png`, `syncausha/assets/icon.ico`
- Test: `tests/test_logging_setup.py`

- [ ] **Step 1: Écrire le test qui échoue**

`tests/test_logging_setup.py` :

```python
import logging

from syncausha.logging_setup import setup_logging


def test_logs_go_to_rotating_file(tmp_path):
    path = setup_logging(tmp_path / "logs")
    root = logging.getLogger()
    try:
        logging.getLogger("syncausha.test").info("bonjour")
        for handler in root.handlers:
            handler.flush()
        assert path == tmp_path / "logs" / "syncausha.log"
        assert "bonjour" in path.read_text(encoding="utf-8")
        assert logging.getLogger("httpx").level == logging.WARNING
    finally:
        for handler in list(root.handlers):
            if getattr(handler, "baseFilename", "").startswith(str(tmp_path)):
                root.removeHandler(handler)
                handler.close()
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_logging_setup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.logging_setup'`

- [ ] **Step 3: Implémenter**

`syncausha/logging_setup.py` :

```python
"""Log fichier tournant dans %APPDATA%\\SyncAusha\\logs (1 Mo × 5)."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "syncausha.log"
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # httpx logue les URL à INFO : on le limite aux avertissements (le jeton n'est jamais logué).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return path
```

- [ ] **Step 4: Vérifier que le test passe**

Run: `.venv/Scripts/python -m pytest tests/test_logging_setup.py -v`
Expected: 1 passed

- [ ] **Step 5: Générer l'icône**

`tools/make_icon.py` :

```python
"""Génère syncausha/assets/icon.png et icon.ico (carré bleu arrondi + onde sonore)."""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "syncausha" / "assets"


def draw(size: int = 512) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=(47, 111, 219, 255))
    bars = [0.35, 0.6, 0.85, 0.6, 0.35]
    bar_width, gap = size // 12, size // 18
    x = (size - (len(bars) * bar_width + (len(bars) - 1) * gap)) // 2
    for height in bars:
        bar_height = int(size * 0.55 * height)
        top = (size - bar_height) // 2
        pen.rounded_rectangle((x, top, x + bar_width, top + bar_height), radius=bar_width // 2, fill="white")
        x += bar_width + gap
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    image = draw()
    image.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / "icon.png")
    image.save(ASSETS / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
```

Run: `.venv/Scripts/python tools/make_icon.py`
Expected: `syncausha/assets/icon.png` et `syncausha/assets/icon.ico` créés. Ouvrir `icon.png` pour vérifier le rendu.

- [ ] **Step 6: Commit**

```
git add syncausha/logging_setup.py tests/test_logging_setup.py tools/make_icon.py syncausha/assets
git commit -m "feat: logs tournants et icône de l'application" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Fondations UI (style, icônes, widgets, appels asynchrones, instance unique)

Couche UI : pas de TDD unitaire. Elle est couverte par le test de fumée de la Task 14 et par la checklist manuelle de la Task 16.

**Files:**
- Create: `syncausha/ui/style.py`, `syncausha/ui/icons.py`, `syncausha/ui/widgets.py`, `syncausha/ui/async_call.py`, `syncausha/ui/single_instance.py`

- [ ] **Step 1: `syncausha/ui/style.py`**

```python
"""Thème sobre, clair ou sombre selon le réglage de Windows."""
from __future__ import annotations

from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

LIGHT = {
    "bg": "#F7F7F5", "surface": "#FFFFFF", "sidebar": "#F0EFEA", "text": "#1F1F1E", "muted": "#6B6A66",
    "border": "#E3E1DA", "hover": "#ECEAE4", "accent": "#2F6FDB", "accent_hover": "#285FBD", "accent_text": "#FFFFFF",
    "success_bg": "#E6F3E6", "success": "#2E7D32", "warning_bg": "#FDF1DC", "warning": "#9A6200",
    "danger_bg": "#FBE9E9", "danger": "#B3261E", "info_bg": "#E6EEFB", "info": "#1F5BB5",
}
DARK = {
    "bg": "#1E1E1D", "surface": "#262625", "sidebar": "#1A1A19", "text": "#ECECEA", "muted": "#A3A29E",
    "border": "#3A3A38", "hover": "#302F2D", "accent": "#5B8DEF", "accent_hover": "#709CF1", "accent_text": "#FFFFFF",
    "success_bg": "#1F3322", "success": "#7BC47F", "warning_bg": "#3A2E14", "warning": "#E0B35C",
    "danger_bg": "#3D1F1D", "danger": "#F08A80", "info_bg": "#1D2B45", "info": "#8AB0F5",
}

_QSS = Template("""
QWidget { background: $bg; color: $text; font-family: "Segoe UI"; font-size: 10pt; }
QListWidget#sidebar { background: $sidebar; border: none; border-right: 1px solid $border; padding: 16px 8px; outline: 0; }
QListWidget#sidebar::item { padding: 8px 12px; margin: 1px 0; border-radius: 6px; color: $muted; }
QListWidget#sidebar::item:hover { background: $hover; }
QListWidget#sidebar::item:selected { background: $hover; color: $text; }
QLabel#pageTitle { font-size: 15pt; font-weight: 600; }
QLabel#section { color: $muted; font-size: 9pt; padding-top: 14px; }
QLabel#muted { color: $muted; font-size: 9pt; }
QLabel#error { color: $danger; font-size: 9pt; }
QFrame#row { border: none; border-bottom: 1px solid $border; }
QFrame#card { background: $surface; border: 1px solid $border; border-radius: 8px; }
QFrame#card QLabel, QFrame#card QCheckBox { background: transparent; }
QPushButton { background: $surface; border: 1px solid $border; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover { background: $hover; }
QPushButton:disabled { color: $muted; }
QPushButton#primary { background: $accent; color: $accent_text; border: 1px solid $accent; }
QPushButton#primary:hover { background: $accent_hover; }
QPushButton#danger { color: $danger; }
QPushButton#link { border: none; background: transparent; color: $accent; padding: 0; text-align: left; }
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox { background: $surface; border: 1px solid $border; border-radius: 6px; padding: 5px 8px; selection-background-color: $accent; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid $accent; }
QListWidget#rules { background: $surface; border: 1px solid $border; border-radius: 8px; outline: 0; padding: 4px; }
QListWidget#rules::item { padding: 6px; border-radius: 6px; }
QListWidget#rules::item:selected { background: $hover; color: $text; }
QLabel#imagePreview { background: $hover; border-radius: 8px; color: $muted; }
QLabel[pill="success"] { background: $success_bg; color: $success; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="warning"] { background: $warning_bg; color: $warning; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="danger"] { background: $danger_bg; color: $danger; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="info"] { background: $info_bg; color: $info; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="neutral"] { background: $hover; color: $muted; border-radius: 6px; padding: 2px 8px; }
QScrollArea { border: none; }
QMenu { background: $surface; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: $hover; color: $text; }
""")


def palette() -> dict[str, str]:
    return DARK if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else LIGHT


def apply_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(_QSS.substitute(palette()))


def watch_color_scheme(app: QApplication) -> None:
    app.styleHints().colorSchemeChanged.connect(lambda _scheme: apply_style(app))
```

- [ ] **Step 2: `syncausha/ui/icons.py`**

```python
"""Icône de l'application et variantes avec pastille d'état pour la zone de notification."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

ASSETS = Path(__file__).resolve().parent.parent / "assets"
STATE_COLORS = {
    "ok": "#2E9E4F",
    "syncing": "#2F6FDB",
    "attention": "#E39B17",
    "not_configured": "#E39B17",
    "folder_missing": "#E39B17",
    "paused": "#8A8984",
    "auth_error": "#D93A2F",
    "offline": "#D93A2F",
}


def app_icon() -> QIcon:
    return QIcon(str(ASSETS / "icon.png"))


def state_icon(state: str) -> QIcon:
    pixmap = QPixmap(str(ASSETS / "icon.png")).scaled(
        64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("white"))
    painter.drawEllipse(36, 36, 28, 28)
    painter.setBrush(QColor(STATE_COLORS.get(state, "#8A8984")))
    painter.drawEllipse(40, 40, 20, 20)
    painter.end()
    return QIcon(pixmap)
```

- [ ] **Step 3: `syncausha/ui/widgets.py`**

```python
"""Petits widgets partagés par les pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget


def make_label(text: str = "", object_name: str | None = None, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(wrap)
    return label


def section_label(text: str) -> QLabel:
    return make_label(text, "section")


def pill(text: str, kind: str) -> QLabel:
    """Badge coloré ; kind ∈ success, warning, danger, info, neutral."""
    label = QLabel(text)
    label.setProperty("pill", kind)
    return label


class Row(QFrame):
    """Ligne de liste : titre, sous-titre discret, et un widget à droite (badge ou bouton)."""

    def __init__(self, title: str, subtitle: str = "", trailing: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title_label = QLabel(title)
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        texts.addWidget(title_label)
        if subtitle:
            texts.addWidget(make_label(subtitle, "muted", wrap=True))
        layout.addLayout(texts, 1)
        if trailing is not None:
            layout.addWidget(trailing, 0, Qt.AlignmentFlag.AlignVCenter)


def clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
```

- [ ] **Step 4: `syncausha/ui/async_call.py`**

```python
"""Exécute un appel bloquant (réseau Ausha) hors du thread UI et rappelle dans le thread UI."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

_pending: set[_Task] = set()


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.fn = fn
        self.signals = _Signals()  # créé dans le thread UI → slots appelés dans le thread UI

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:
            self.signals.failed.emit(exc)
            return
        self.signals.done.emit(result)


def run_async(fn: Callable[[], Any], on_done: Callable[[Any], None], on_failed: Callable[[Exception], None]) -> None:
    task = _Task(fn)
    _pending.add(task)
    task.signals.done.connect(on_done)
    task.signals.failed.connect(on_failed)
    task.signals.done.connect(lambda _result: _pending.discard(task))
    task.signals.failed.connect(lambda _error: _pending.discard(task))
    QThreadPool.globalInstance().start(task)
```

- [ ] **Step 5: `syncausha/ui/single_instance.py`**

```python
"""Une seule instance par utilisateur : un second lancement ramène la fenêtre existante."""
from __future__ import annotations

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    show_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._name = f"SyncAusha-{getpass.getuser()}"
        self._server: QLocalServer | None = None

    def try_acquire(self) -> bool:
        """True si on est la première instance ; sinon réveille l'autre et renvoie False."""
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if socket.waitForConnected(300):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(300)
            socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._server.listen(self._name)
        return True

    def _on_connection(self) -> None:
        connection = self._server.nextPendingConnection()
        if connection is not None:
            connection.disconnectFromServer()
        self.show_requested.emit()
```

Note : `QtNetwork` fait partie de PySide6-Essentials.

- [ ] **Step 6: Vérifier l'import**

Run: `.venv/Scripts/python -c "import syncausha.ui.style, syncausha.ui.icons, syncausha.ui.widgets, syncausha.ui.async_call, syncausha.ui.single_instance; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```
git add syncausha/ui
git commit -m "feat(ui): thème, icônes d'état, widgets et instance unique" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Contrôleur (`ui/controller.py`)

**Files:**
- Create: `syncausha/ui/controller.py`

- [ ] **Step 1: Implémenter**

```python
"""Chef d'orchestre : minuteur, thread de synchro, réglages, notifications."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from syncausha.ausha_client import AushaClient, AuthError, Playlist, Show
from syncausha.config import Config, get_token, load_config, save_config, set_token
from syncausha.journal import Journal
from syncausha.sync_engine import CycleResult, Event, SyncEngine
from syncausha.ui.async_call import run_async

log = logging.getLogger(__name__)

FIRST_CYCLE_DELAY_MS = 10_000
FILE_NOTIFICATIONS = {
    "published": ("Épisode publié", "{title} · {detail}"),
    "no_rule": ("Aucune règle", "{title} n'a pas été envoyé : aucune règle ne correspond."),
    "broken_rule": ("Règle à corriger", "{title} : {detail}"),
    "rejected": ("Refusé par Ausha", "{title} : {detail}"),
    "failed": ("Échec de l'envoi", "{title} : {detail}"),
}
STATE_NOTIFICATIONS = {
    "auth_error": ("Jeton Ausha invalide", "Mettez à jour votre jeton dans les réglages."),
    "folder_missing": ("Dossier introuvable", "{message}"),
}

Catalog = dict[Show, list[Playlist]]


class CycleWorker(QObject):
    """Vit dans le thread de synchro ; exécute un cycle à la demande."""

    finished = Signal(object)

    def __init__(self, engine: SyncEngine) -> None:
        super().__init__()
        self._engine = engine

    @Slot()
    def run(self) -> None:
        try:
            result = self._engine.run_cycle()
        except Exception as exc:
            log.exception("Cycle interrompu")
            result = CycleResult("offline", str(exc))
        self.finished.emit(result)


class AppController(QObject):
    state_changed = Signal(str, str)
    activity_changed = Signal()
    progress_changed = Signal(str, int)
    notification = Signal(str, str)
    _engine_event = Signal(object)
    _start_cycle = Signal()

    def __init__(self, config_path: Path, journal: Journal, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config_path = config_path
        self.config = load_config(config_path)
        self.journal = journal
        self.state, self.message = ("paused" if self.config.paused else "ok"), ""
        self.busy = False
        self.auth_blocked = False
        self.progress: dict[str, int] = {}
        self.dry_run_lines: list[str] = []
        self._pending_dry_run: list[str] = []
        self._last_result_state = ""

        self.engine = SyncEngine(self.config, journal, self._make_client, on_event=self._engine_event.emit)
        self._engine_event.connect(self._on_engine_event)

        self._thread = QThread(self)
        self._worker = CycleWorker(self.engine)
        self._worker.moveToThread(self._thread)
        self._start_cycle.connect(self._worker.run)
        self._worker.finished.connect(self._on_cycle_finished)
        self._thread.start()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._restart_timer()

    @staticmethod
    def _make_client(config: Config) -> AushaClient | None:
        token = get_token()
        return AushaClient(token, config.api_base_url) if token else None

    # --- Synchro -------------------------------------------------------------

    def start(self) -> None:
        QTimer.singleShot(FIRST_CYCLE_DELAY_MS, self._on_timer)

    def sync_now(self) -> None:
        if self.busy:
            return
        self.busy = True
        self._pending_dry_run = []
        self._set_state("syncing", "")
        self._start_cycle.emit()
        self._restart_timer()

    def seconds_until_next_cycle(self) -> int:
        return max(0, self._timer.remainingTime() // 1000)

    def retry(self, file_hash: str) -> None:
        self.journal.reset_for_retry(file_hash)
        self.activity_changed.emit()
        self.sync_now()

    def _on_timer(self) -> None:
        if not self.auth_blocked:
            self.sync_now()

    def _restart_timer(self) -> None:
        self._timer.start(self.config.interval_minutes * 60_000)

    @Slot(object)
    def _on_engine_event(self, event: Event) -> None:
        if event.kind == "progress":
            self.progress[event.title] = event.percent
            self.progress_changed.emit(event.title, event.percent)
            return
        if event.kind == "dry_run":
            self._pending_dry_run.append(f"{event.title} — {event.detail}")
            return
        self.progress.pop(event.title, None)
        template = FILE_NOTIFICATIONS.get(event.kind)
        if template:
            self.notification.emit(template[0], template[1].format(title=event.title, detail=event.detail))
        self.activity_changed.emit()

    @Slot(object)
    def _on_cycle_finished(self, result: CycleResult) -> None:
        self.busy = False
        self.progress.clear()
        self.dry_run_lines = self._pending_dry_run if self.config.dry_run else []
        self.auth_blocked = result.state == "auth_error"
        if result.state != self._last_result_state and result.state in STATE_NOTIFICATIONS:
            title, body = STATE_NOTIFICATIONS[result.state]
            self.notification.emit(title, body.format(message=result.message))
        self._last_result_state = result.state
        self._set_state(result.state, result.message)
        self.activity_changed.emit()

    def _set_state(self, state: str, message: str) -> None:
        self.state, self.message = state, message
        self.state_changed.emit(state, message)

    # --- Réglages ------------------------------------------------------------

    def has_token(self) -> bool:
        return get_token() is not None

    def update_config(self, config: Config) -> None:
        """Enregistre et applique de nouveaux réglages. Ne jamais muter self.config en place."""
        save_config(config, self.config_path)
        self.config = config
        self.engine.config = config
        self._restart_timer()
        if config.paused:
            self._set_state("paused", "")
        self.activity_changed.emit()

    def update_token(self, token: str) -> None:
        set_token(token)
        self.auth_blocked = False

    def set_paused(self, paused: bool) -> None:
        self.update_config(replace(self.config, paused=paused))
        if not paused:
            self.sync_now()

    # --- Ausha (hors thread UI) ---------------------------------------------

    def fetch_catalog(
        self,
        on_done: Callable[[Catalog], None],
        on_failed: Callable[[Exception], None],
        token: str | None = None,
    ) -> None:
        """Charge émissions et playlists en arrière-plan (token : jeton à tester, sinon celui enregistré)."""
        token = token or get_token()
        base_url = self.config.api_base_url

        def load() -> Catalog:
            if not token:
                raise AuthError("Aucun jeton Ausha enregistré.")
            with AushaClient(token, base_url) as client:
                return {show: client.list_playlists(show.id) for show in client.list_shows()}

        run_async(load, on_done, on_failed)

    def shutdown(self) -> None:
        self._timer.stop()
        self._thread.quit()
        self._thread.wait(5000)
```

- [ ] **Step 2: Vérifier l'import**

Run: `.venv/Scripts/python -c "import syncausha.ui.controller; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```
git add syncausha/ui/controller.py
git commit -m "feat(ui): contrôleur avec thread de synchro et minuteur" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Pages Activité et Réglages

**Files:**
- Create: `syncausha/ui/activity_page.py`, `syncausha/ui/settings_page.py`

- [ ] **Step 1: `syncausha/ui/activity_page.py`**

```python
"""Page Activité : état, fichiers à traiter, historique récent."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget

from syncausha.journal import Entry, Status
from syncausha.rules import episode_title
from syncausha.ui.controller import AppController
from syncausha.ui.style import palette
from syncausha.ui.widgets import Row, clear_layout, make_label, pill, section_label

STATE_TEXT = {
    "ok": "À jour",
    "syncing": "Synchronisation…",
    "attention": "Des fichiers demandent votre attention",
    "paused": "En pause",
    "not_configured": "Configuration incomplète",
    "folder_missing": "Dossier introuvable",
    "auth_error": "Jeton Ausha invalide",
    "offline": "Ausha injoignable",
}
STATE_COLOR = {
    "ok": "success", "syncing": "info", "attention": "warning", "paused": "muted",
    "not_configured": "warning", "folder_missing": "warning", "auth_error": "danger", "offline": "danger",
}


class ActivityPage(QWidget):
    create_rule_requested = Signal(str)
    edit_rules_requested = Signal()

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)

        header = QHBoxLayout()
        texts = QVBoxLayout()
        self.status_label = make_label(object_name="pageTitle")
        self.detail_label = make_label(object_name="muted", wrap=True)
        texts.addWidget(self.status_label)
        texts.addWidget(self.detail_label)
        header.addLayout(texts, 1)
        self.sync_button = QPushButton("Synchroniser")
        self.sync_button.setObjectName("primary")
        self.sync_button.clicked.connect(controller.sync_now)
        header.addWidget(self.sync_button)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.sections = QVBoxLayout(content)
        self.sections.setContentsMargins(0, 0, 8, 0)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        controller.state_changed.connect(self.refresh)
        controller.activity_changed.connect(self.refresh)
        controller.progress_changed.connect(self.refresh)
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._update_header)
        self._tick.start(30_000)
        self.refresh()

    def refresh(self, *_args) -> None:
        self._update_header()
        clear_layout(self.sections)
        attention = self.controller.journal.needing_attention()
        if attention:
            self.sections.addWidget(section_label("À traiter"))
            for entry in attention:
                self.sections.addWidget(self._attention_row(entry))
        if self.controller.dry_run_lines:
            self.sections.addWidget(section_label("Essai à blanc — rien n'a été publié"))
            for line in self.controller.dry_run_lines:
                self.sections.addWidget(Row(line))
        self.sections.addWidget(section_label("Récent"))
        recent = self.controller.journal.recent()
        if not recent:
            self.sections.addWidget(make_label("Aucun épisode publié pour l'instant.", "muted"))
        for entry in recent:
            self.sections.addWidget(self._recent_row(entry))
        self.sections.addStretch(1)

    def _update_header(self) -> None:
        c = self.controller
        color = palette()[STATE_COLOR.get(c.state, "muted")]
        self.status_label.setText(f'<span style="color:{color}">●</span>&nbsp;{STATE_TEXT.get(c.state, c.state)}')
        parts = [c.config.watch_folder or "Aucun dossier choisi"]
        if c.busy:
            parts.append("synchronisation en cours")
        elif not c.config.paused:
            parts.append(f"prochain passage dans {max(1, round(c.seconds_until_next_cycle() / 60))} min")
        if c.message and c.state not in ("ok", "syncing"):
            parts.append(c.message)
        self.detail_label.setText(" · ".join(parts))
        self.sync_button.setEnabled(not c.busy)

    def _attention_row(self, entry: Entry) -> Row:
        if entry.status is Status.SANS_REGLE:
            button = QPushButton("Créer une règle")
            button.clicked.connect(lambda _=False, name=entry.filename: self.create_rule_requested.emit(Path(name).stem))
        elif entry.status is Status.REGLE_CASSEE:
            button = QPushButton("Modifier les règles")
            button.clicked.connect(lambda _=False: self.edit_rules_requested.emit())
        else:
            button = QPushButton("Réessayer")
            button.clicked.connect(lambda _=False, h=entry.hash: self.controller.retry(h))
        return Row(entry.filename, entry.last_error or "Aucune règle ne correspond", button)

    def _recent_row(self, entry: Entry) -> Row:
        when = datetime.fromtimestamp(entry.updated_at).strftime("%d/%m %H:%M")
        subtitle = f"{entry.show_name} · {when}" if entry.show_name else when
        if entry.status is Status.EN_COURS:
            percent = self.controller.progress.get(episode_title(Path(entry.filename)), 0)
            badge = pill(f"Envoi {percent} %", "info")
        elif entry.status is Status.PUBLIE:
            badge = pill("Publié", "success")
        elif entry.status is Status.DEJA_PRESENT:
            badge = pill("Déjà sur Ausha", "neutral")
        elif entry.attempts:
            badge = pill("Nouvel essai au prochain passage", "warning")
            subtitle = f"{subtitle} · {entry.last_error}"
        else:
            badge = pill("En attente", "neutral")
        return Row(Path(entry.filename).stem, subtitle, badge)
```

- [ ] **Step 2: `syncausha/ui/settings_page.py`**

```python
"""Page Réglages : jeton, dossier, intervalle, démarrage, pause, essai à blanc."""
from __future__ import annotations

import os
from dataclasses import replace

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from syncausha import autostart
from syncausha.config import MAX_INTERVAL, MIN_INTERVAL, app_data_dir
from syncausha.ui.controller import AppController, Catalog
from syncausha.ui.widgets import make_label


class SettingsPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(make_label("Réglages", "pageTitle"))

        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setVerticalSpacing(12)

        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        test_button = QPushButton("Tester la connexion")
        test_button.clicked.connect(self._test)
        token_row = QHBoxLayout()
        token_row.addWidget(self.token, 1)
        token_row.addWidget(test_button)
        form.addRow("Jeton Ausha", token_row)
        self.test_result = make_label(object_name="muted", wrap=True)
        form.addRow("", self.test_result)
        form.addRow("", make_label("Le jeton se crée dans Ausha : Mon compte → API publique.", "muted", wrap=True))

        self.folder = QLineEdit()
        self.folder.setReadOnly(True)
        folder_button = QPushButton("Choisir…")
        folder_button.clicked.connect(self._choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(folder_button)
        form.addRow("Dossier surveillé", folder_row)

        self.interval = QSpinBox()
        self.interval.setRange(MIN_INTERVAL, MAX_INTERVAL)
        self.interval.setSuffix(" min")
        form.addRow("Vérifier toutes les", self.interval)

        self.autostart = QCheckBox("Lancer au démarrage de Windows")
        self.paused = QCheckBox("Mettre la synchronisation en pause")
        self.dry_run = QCheckBox("Essai à blanc : ne publie rien, montre ce qui serait envoyé")
        for checkbox in (self.autostart, self.paused, self.dry_run):
            form.addRow("", checkbox)
        layout.addWidget(card)

        actions = QHBoxLayout()
        logs_button = QPushButton("Ouvrir le dossier des logs")
        logs_button.setObjectName("link")
        logs_button.clicked.connect(self._open_logs)
        actions.addWidget(logs_button)
        actions.addStretch(1)
        self.saved_label = make_label(object_name="muted")
        actions.addWidget(self.saved_label)
        save_button = QPushButton("Enregistrer")
        save_button.setObjectName("primary")
        save_button.clicked.connect(self._save)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        self.load()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.load()

    def load(self) -> None:
        config = self.controller.config
        self.token.clear()
        self.token.setPlaceholderText(
            "Jeton enregistré — laissez vide pour le conserver"
            if self.controller.has_token()
            else "Collez votre jeton personnel Ausha"
        )
        self.folder.setText(config.watch_folder)
        self.interval.setValue(config.interval_minutes)
        self.autostart.setChecked(autostart.is_enabled())
        self.paused.setChecked(config.paused)
        self.dry_run.setChecked(config.dry_run)
        self.saved_label.clear()

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Dossier des podcasts", self.folder.text())
        if folder:
            self.folder.setText(os.path.normpath(folder))

    def _test(self) -> None:
        self.test_result.setText("Connexion à Ausha…")
        self.controller.fetch_catalog(self._on_test_ok, self._on_test_failed, token=self.token.text().strip() or None)

    def _on_test_ok(self, catalog: Catalog) -> None:
        names = ", ".join(sorted(show.name for show in catalog)) or "aucune émission"
        self.test_result.setText(f"Connexion réussie. Émissions : {names}")

    def _on_test_failed(self, error: Exception) -> None:
        self.test_result.setText(f"Échec : {error}")

    def _save(self) -> None:
        token = self.token.text().strip()
        if token:
            self.controller.update_token(token)
        config = replace(
            self.controller.config,
            watch_folder=self.folder.text(),
            interval_minutes=self.interval.value(),
            paused=self.paused.isChecked(),
            dry_run=self.dry_run.isChecked(),
        )
        self.controller.update_config(config)
        autostart.set_enabled(self.autostart.isChecked())
        self.load()
        self.saved_label.setText("Réglages enregistrés")
        if not config.paused:
            self.controller.sync_now()

    def _open_logs(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir() / "logs")))
```

- [ ] **Step 3: Vérifier l'import**

Run: `.venv/Scripts/python -c "import syncausha.ui.activity_page, syncausha.ui.settings_page; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```
git add syncausha/ui/activity_page.py syncausha/ui/settings_page.py
git commit -m "feat(ui): pages Activité et Réglages" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Page Règles

**Files:**
- Create: `syncausha/ui/rules_page.py`

- [ ] **Step 1: Implémenter**

```python
"""Page Règles : liste réordonnable + éditeur (mot-clé, émission, playlist, image, description)."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from syncausha.config import Rule
from syncausha.rules import validate_image
from syncausha.ui.controller import AppController, Catalog
from syncausha.ui.widgets import make_label

NO_PLAYLIST = "Aucune playlist"
PREVIEW_SIZE = 110


class ReorderableList(QListWidget):
    reordered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self.reordered.emit()


class RulesPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.catalog: Catalog = {}
        self._editing_index: int | None = None
        self._editing = Rule(keyword="", show_id=0)
        self._image_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        header = QHBoxLayout()
        header.addWidget(make_label("Règles", "pageTitle"))
        header.addStretch(1)
        add_button = QPushButton("Ajouter")
        add_button.clicked.connect(lambda _=False: self.start_new_rule(""))
        header.addWidget(add_button)
        layout.addLayout(header)
        layout.addWidget(make_label(
            "La première règle dont le mot-clé apparaît dans le nom du fichier s'applique. "
            "Glissez les règles pour changer l'ordre.", "muted", wrap=True))
        self.catalog_status = make_label(object_name="muted", wrap=True)
        layout.addWidget(self.catalog_status)

        self.list = ReorderableList()
        self.list.setObjectName("rules")
        self.list.setIconSize(QSize(36, 36))
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.reordered.connect(self._on_reordered)
        layout.addWidget(self.list, 1)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(16)
        form = QFormLayout()
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("MARS ATTACK")
        form.addRow("Le nom du fichier contient", self.keyword)
        self.show_combo = QComboBox()
        self.show_combo.currentIndexChanged.connect(lambda _i: self._fill_playlists())
        form.addRow("Émission", self.show_combo)
        self.playlist_combo = QComboBox()
        form.addRow("Playlist", self.playlist_combo)
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText("Nouvel épisode de Mars Attack. Retrouvez-nous sur…")
        self.description.setFixedHeight(90)
        form.addRow("Description", self.description)
        card_layout.addLayout(form, 1)

        image_column = QVBoxLayout()
        image_column.addWidget(make_label("Image", "muted"))
        self.image_preview = QLabel("Aucune image")
        self.image_preview.setObjectName("imagePreview")
        self.image_preview.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_column.addWidget(self.image_preview)
        choose_button = QPushButton("Choisir…")
        choose_button.clicked.connect(self._choose_image)
        remove_button = QPushButton("Retirer")
        remove_button.clicked.connect(lambda _=False: self._set_image(""))
        image_column.addWidget(choose_button)
        image_column.addWidget(remove_button)
        self.image_error = make_label(object_name="error", wrap=True)
        self.image_error.setFixedWidth(PREVIEW_SIZE + 40)
        image_column.addWidget(self.image_error)
        image_column.addStretch(1)
        card_layout.addLayout(image_column)
        layout.addWidget(card)

        actions = QHBoxLayout()
        self.form_error = make_label(object_name="error")
        actions.addWidget(self.form_error, 1)
        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self._delete)
        actions.addWidget(self.delete_button)
        save_button = QPushButton("Enregistrer")
        save_button.setObjectName("primary")
        save_button.clicked.connect(self._save)
        actions.addWidget(save_button)
        layout.addLayout(actions)

        self._render_list()
        self.start_new_rule("")

    # --- Catalogue Ausha -----------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload_catalog()

    def reload_catalog(self) -> None:
        self.catalog_status.setText("Chargement des émissions Ausha…")
        self.controller.fetch_catalog(self._on_catalog, self._on_catalog_failed)

    def _on_catalog(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.catalog_status.clear()
        self._fill_shows()

    def _on_catalog_failed(self, error: Exception) -> None:
        self.catalog_status.setText(f"Impossible de charger les émissions Ausha : {error}")

    # --- Liste ---------------------------------------------------------------

    def _render_list(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for index, rule in enumerate(self.controller.config.rules):
            target = rule.show_name or f"Émission {rule.show_id}"
            if rule.playlist_name:
                target += f" → {rule.playlist_name}"
            item = QListWidgetItem(_thumbnail(rule.image_path), f"{rule.keyword}\n{target}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self.controller.config.rules):
            self._load_into_editor(row, self.controller.config.rules[row])

    def _on_reordered(self) -> None:
        old = self.controller.config.rules
        order = [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())]
        self.controller.update_config(replace(self.controller.config, rules=[old[i] for i in order]))
        self._render_list()
        self.start_new_rule("")

    # --- Éditeur -------------------------------------------------------------

    def start_new_rule(self, keyword: str) -> None:
        self.list.blockSignals(True)
        self.list.setCurrentRow(-1)
        self.list.blockSignals(False)
        self._load_into_editor(None, Rule(keyword=keyword, show_id=0))

    def _load_into_editor(self, index: int | None, rule: Rule) -> None:
        self._editing_index, self._editing = index, rule
        self.keyword.setText(rule.keyword)
        self.description.setPlainText(rule.description_template)
        self._set_image(rule.image_path)
        self.delete_button.setVisible(index is not None)
        self.form_error.clear()
        self._fill_shows()

    def _fill_shows(self) -> None:
        rule = self._editing
        items = [(show.name, show.id) for show in sorted(self.catalog, key=lambda s: s.name.casefold())]
        if rule.show_id and rule.show_id not in {show.id for show in self.catalog}:
            items.insert(0, (rule.show_name or f"Émission {rule.show_id}", rule.show_id))
        _set_combo_items(self.show_combo, items, rule.show_id or None)
        self._fill_playlists()

    def _fill_playlists(self) -> None:
        show_id = self.show_combo.currentData()
        playlists = next((pls for show, pls in self.catalog.items() if show.id == show_id), [])
        items: list[tuple[str, int | None]] = [(NO_PLAYLIST, None)]
        items += [(p.name, p.id) for p in sorted(playlists, key=lambda p: p.name.casefold())]
        rule = self._editing
        selected = rule.playlist_id if rule.show_id == show_id else None
        if selected is not None and selected not in {p.id for p in playlists}:
            items.append((rule.playlist_name or f"Playlist {selected}", selected))
        _set_combo_items(self.playlist_combo, items, selected)

    def _set_image(self, path: str) -> None:
        self._image_path = path
        pixmap = QPixmap(path) if path else QPixmap()
        if pixmap.isNull():
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("Aucune image")
        else:
            self.image_preview.setPixmap(pixmap.scaled(
                PREVIEW_SIZE, PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.image_error.setText((validate_image(path) or "") if path else "")

    def _choose_image(self) -> None:
        start = str(Path(self._image_path).parent) if self._image_path else ""
        path, _filter = QFileDialog.getOpenFileName(self, "Choisir l'image", start, "Images (*.png *.jpg *.jpeg)")
        if path:
            self._set_image(path)

    def _save(self) -> None:
        keyword = self.keyword.text().strip()
        show_id = self.show_combo.currentData()
        if not keyword:
            self.form_error.setText("Indiquez un mot-clé.")
            return
        if not show_id:
            self.form_error.setText("Choisissez une émission.")
            return
        if self._image_path and validate_image(self._image_path):
            self.form_error.setText("Corrigez l'image avant d'enregistrer.")
            return
        playlist_id = self.playlist_combo.currentData()
        rule = Rule(
            keyword=keyword,
            show_id=int(show_id),
            show_name=self.show_combo.currentText(),
            playlist_id=playlist_id,
            playlist_name=self.playlist_combo.currentText() if playlist_id is not None else "",
            image_path=self._image_path,
            description_template=self.description.toPlainText().strip(),
        )
        rules = list(self.controller.config.rules)
        if self._editing_index is None:
            rules.append(rule)
            index = len(rules) - 1
        else:
            rules[self._editing_index] = rule
            index = self._editing_index
        self.controller.update_config(replace(self.controller.config, rules=rules))
        self._render_list()
        self.list.setCurrentRow(index)

    def _delete(self) -> None:
        if self._editing_index is None:
            return
        answer = QMessageBox.question(self, "Supprimer la règle", f"Supprimer la règle « {self._editing.keyword} » ?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        rules = list(self.controller.config.rules)
        del rules[self._editing_index]
        self.controller.update_config(replace(self.controller.config, rules=rules))
        self._render_list()
        self.start_new_rule("")


def _thumbnail(path: str) -> QIcon:
    pixmap = QPixmap(path) if path else QPixmap()
    if pixmap.isNull():
        return QIcon()
    return QIcon(pixmap.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))


def _set_combo_items(combo: QComboBox, items: list[tuple[str, object]], selected: object) -> None:
    combo.blockSignals(True)
    combo.clear()
    for text, data in items:
        combo.addItem(text, data)
    index = combo.findData(selected) if selected is not None else 0
    combo.setCurrentIndex(max(index, 0))
    combo.blockSignals(False)
```

- [ ] **Step 2: Vérifier l'import**

Run: `.venv/Scripts/python -c "import syncausha.ui.rules_page; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```
git add syncausha/ui/rules_page.py
git commit -m "feat(ui): page Règles avec éditeur et réordonnancement" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Fenêtre, icône de notification, point d'entrée + test de fumée

**Files:**
- Create: `syncausha/ui/main_window.py`, `syncausha/ui/tray.py`, `syncausha/app.py`, `run_syncausha.py`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Écrire le test de fumée qui échoue**

`tests/test_ui_smoke.py` :

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from syncausha.config import Config, Rule, save_config  # noqa: E402
from syncausha.journal import Journal, Status  # noqa: E402
from syncausha.ui import controller as controller_module  # noqa: E402
from syncausha.ui.controller import AppController  # noqa: E402
from syncausha.ui.main_window import ACTIVITY, MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_main_window_builds_and_navigates(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: None)
    config_path = tmp_path / "config.json"
    save_config(
        Config(watch_folder=str(tmp_path), rules=[Rule(keyword="MARS ATTACK", show_id=1, show_name="Mars Attack")]),
        config_path,
    )
    journal = Journal(tmp_path / "journal.db")
    journal.ensure("h1", "interview_brut.mp3", 1)
    journal.update("h1", status=Status.SANS_REGLE, last_error="Aucune règle ne correspond")
    journal.ensure("h2", "MARS ATTACK 12.mp3", 1)
    journal.update("h2", status=Status.PUBLIE, show_name="Mars Attack")
    controller = AppController(config_path, journal)
    window = MainWindow(controller)
    try:
        assert window.needs_setup()
        assert window.stack.currentWidget() is window.settings
        window.open_new_rule("interview_brut")
        assert window.stack.currentWidget() is window.rules
        assert window.rules.keyword.text() == "interview_brut"
        assert window.rules.list.count() == 1
        window.go_to(ACTIVITY)
        window.activity.refresh()
        assert window.stack.currentWidget() is window.activity
    finally:
        controller.shutdown()
        journal.close()
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_ui_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.ui.main_window'`

- [ ] **Step 3: `syncausha/ui/main_window.py`**

```python
"""Fenêtre principale : barre latérale + pages. Fermer la fenêtre la réduit dans la zone de notification."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QMainWindow, QStackedWidget, QWidget

from syncausha.ui.activity_page import ActivityPage
from syncausha.ui.controller import AppController
from syncausha.ui.rules_page import RulesPage
from syncausha.ui.settings_page import SettingsPage

ACTIVITY, RULES, SETTINGS = 0, 1, 2


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("SyncAusha")
        self.resize(880, 600)
        self.setMinimumSize(720, 480)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(170)
        self.sidebar.addItems(["Activité", "Règles", "Réglages"])
        self.stack = QStackedWidget()
        self.activity = ActivityPage(controller)
        self.rules = RulesPage(controller)
        self.settings = SettingsPage(controller)
        for page in (self.activity, self.rules, self.settings):
            self.stack.addWidget(page)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.activity.create_rule_requested.connect(self.open_new_rule)
        self.activity.edit_rules_requested.connect(lambda: self.go_to(RULES))
        self.go_to(SETTINGS if self.needs_setup() else ACTIVITY)

    def needs_setup(self) -> bool:
        return not (self.controller.has_token() and self.controller.config.watch_folder)

    def go_to(self, index: int) -> None:
        self.sidebar.setCurrentRow(index)
        self.stack.setCurrentIndex(index)

    def open_new_rule(self, keyword: str) -> None:
        self.go_to(RULES)
        self.rules.start_new_rule(keyword)

    def show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
```

- [ ] **Step 4: `syncausha/ui/tray.py`**

```python
"""Icône de la zone de notification : état en couleur, menu rapide, notifications Windows."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from syncausha.ui.activity_page import STATE_TEXT
from syncausha.ui.controller import AppController
from syncausha.ui.icons import state_icon
from syncausha.ui.main_window import MainWindow


class Tray(QSystemTrayIcon):
    def __init__(self, controller: AppController, window: MainWindow) -> None:
        super().__init__(state_icon(controller.state))
        self.controller = controller
        self.window = window
        self._menu = QMenu()
        self._menu.addAction("Synchroniser maintenant").triggered.connect(controller.sync_now)
        self.pause_action = self._menu.addAction("Mettre en pause")
        self.pause_action.triggered.connect(self._toggle_pause)
        self._menu.addAction("Ouvrir le dossier").triggered.connect(self._open_folder)
        self._menu.addSeparator()
        self._menu.addAction("Quitter").triggered.connect(QApplication.quit)
        self.setContextMenu(self._menu)

        self.activated.connect(self._on_activated)
        self.messageClicked.connect(window.show_and_raise)
        controller.state_changed.connect(self._update)
        controller.notification.connect(self._notify)
        self._update(controller.state, controller.message)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.window.show_and_raise()

    def _toggle_pause(self) -> None:
        self.controller.set_paused(not self.controller.config.paused)

    def _open_folder(self) -> None:
        folder = self.controller.config.watch_folder
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _update(self, state: str, _message: str) -> None:
        self.setIcon(state_icon(state))
        self.setToolTip(f"SyncAusha — {STATE_TEXT.get(state, state)}")
        self.pause_action.setText("Reprendre la synchronisation" if self.controller.config.paused else "Mettre en pause")

    def _notify(self, title: str, body: str) -> None:
        self.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 6000)
```

- [ ] **Step 5: `syncausha/app.py` et `run_syncausha.py`**

`syncausha/app.py` :

```python
"""Point d'entrée : assemble réglages, journal, contrôleur, fenêtre et icône."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from syncausha import __version__
from syncausha.config import app_data_dir
from syncausha.journal import Journal
from syncausha.logging_setup import setup_logging
from syncausha.ui.controller import AppController
from syncausha.ui.icons import app_icon
from syncausha.ui.main_window import MainWindow
from syncausha.ui.single_instance import SingleInstance
from syncausha.ui.style import apply_style, watch_color_scheme
from syncausha.ui.tray import Tray

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("SyncAusha")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    instance = SingleInstance()
    if not instance.try_acquire():
        return 0

    data_dir = app_data_dir()
    setup_logging(data_dir / "logs")
    sys.excepthook = lambda *exc_info: log.critical("Erreur non gérée", exc_info=exc_info)
    log.info("Démarrage de SyncAusha %s", __version__)

    apply_style(app)
    watch_color_scheme(app)
    journal = Journal(data_dir / "journal.db")
    controller = AppController(data_dir / "config.json", journal)
    window = MainWindow(controller)
    tray = Tray(controller, window)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()
    instance.show_requested.connect(window.show_and_raise)
    if "--minimized" not in argv or window.needs_setup():
        window.show_and_raise()
    controller.start()

    code = app.exec()
    controller.shutdown()
    journal.close()
    return code
```

`run_syncausha.py` :

```python
import sys

from syncausha.app import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Vérifier que le test de fumée et toute la suite passent**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all passed

- [ ] **Step 7: Lancer l'application pour de vrai**

Run: `.venv/Scripts/python run_syncausha.py`
Expected : la fenêtre s'ouvre sur « Réglages » (pas de jeton), l'icône apparaît près de l'horloge, fermer la fenêtre la cache sans quitter, clic sur l'icône la rouvre, « Quitter » dans le menu ferme l'app. Relancer une 2e fois pendant que la 1re tourne : la fenêtre existante revient au premier plan, pas de 2e icône.

- [ ] **Step 8: Commit**

```
git add syncausha/ui/main_window.py syncausha/ui/tray.py syncausha/app.py run_syncausha.py tests/test_ui_smoke.py
git commit -m "feat(ui): fenêtre principale, icône de notification et point d'entrée" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Installateur (PyInstaller + Inno Setup)

**Files:**
- Create: `installer/syncausha.iss`, `build.ps1`

- [ ] **Step 1: Installer Inno Setup 6 (une fois, sur le PC de construction)**

Demander l'accord de l'utilisateur avant d'installer un logiciel, puis :

Run: `winget install -e --id JRSoftware.InnoSetup`
Expected: `ISCC.exe` présent dans `%LOCALAPPDATA%\Programs\Inno Setup 6\` ou `C:\Program Files (x86)\Inno Setup 6\`.

- [ ] **Step 2: `installer/syncausha.iss`**

```ini
#define AppName "SyncAusha"
#define AppVersion "1.0.0"
#define AppExe "SyncAusha.exe"

[Setup]
AppId={{8F3C2A51-6B7D-4E2A-9C1F-3D5B7A9E4C21}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Silicon
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SyncAusha-Setup
SetupIconFile=..\syncausha\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "autostart"; Description: "Lancer SyncAusha au démarrage de Windows"; GroupDescription: "Options :"
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Options :"; Flags: unchecked

[Files]
Source: "..\dist\SyncAusha\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"" --minimized"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Lancer SyncAusha maintenant"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}');
  if CurUninstallStep = usPostUninstall then
    if SuppressibleMsgBox('Supprimer aussi vos réglages et l''historique SyncAusha ?',
                          mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      DelTree(ExpandConstant('{userappdata}\{#AppName}'), True, True, True);
end;
```

Le fichier doit être en UTF-8 **avec BOM**, sinon les accents s'affichent mal dans l'installateur :

Run (PowerShell) :
```
$p = "installer\syncausha.iss"; $c = [IO.File]::ReadAllText($p); [IO.File]::WriteAllText($p, $c, (New-Object Text.UTF8Encoding $true))
```

- [ ] **Step 3: `build.ps1`** (sans accents : Windows PowerShell 5.1 lit les .ps1 sans BOM en ANSI)

```powershell
# Construit dist\SyncAusha-Setup.exe : dependances, tests, PyInstaller, Inno Setup.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { python -m venv .venv }
$python = ".venv\Scripts\python.exe"
& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Installation des dependances impossible" }

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Des tests echouent : construction annulee" }

& $python -m PyInstaller --noconfirm --clean --windowed --name SyncAusha `
    --icon syncausha\assets\icon.ico `
    --add-data "syncausha\assets;syncausha\assets" `
    run_syncausha.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a echoue" }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 introuvable. Installez-le : winget install -e --id JRSoftware.InnoSetup" }

& $iscc installer\syncausha.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup a echoue" }
Write-Host "OK : dist\SyncAusha-Setup.exe"
```

- [ ] **Step 4: Construire**

Run: `powershell -ExecutionPolicy Bypass -File build.ps1`
Expected: se termine par `OK : dist\SyncAusha-Setup.exe`.

- [ ] **Step 5: Vérifier l'exécutable empaqueté avant l'installateur**

Run: `dist/SyncAusha/SyncAusha.exe`
Expected : même comportement qu'à la Task 14 step 7 (fenêtre, icône, notifications). Si l'app ne démarre pas, lire `%APPDATA%\SyncAusha\logs\syncausha.log`. Si le log mentionne `keyring.errors.NoKeyringError`, ajouter `--collect-submodules keyring.backends --copy-metadata keyring` à la commande PyInstaller de `build.ps1` et reconstruire.

- [ ] **Step 6: Tester installation / désinstallation silencieuses**

Quitter l'app lancée au step 5 (menu → Quitter), puis :

Run (PowerShell) :
```
dist\SyncAusha-Setup.exe /VERYSILENT /TASKS="autostart"
Test-Path "$env:LOCALAPPDATA\Programs\SyncAusha\SyncAusha.exe"
(Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run).SyncAusha
& "$env:LOCALAPPDATA\Programs\SyncAusha\unins000.exe" /VERYSILENT
Start-Sleep 3
Test-Path "$env:LOCALAPPDATA\Programs\SyncAusha\SyncAusha.exe"
(Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run).SyncAusha
```
Expected: `True`, puis `"C:\Users\...\AppData\Local\Programs\SyncAusha\SyncAusha.exe" --minimized`, puis `False` et une valeur vide après désinstallation. En mode silencieux, la question « Supprimer aussi vos réglages » prend la réponse par défaut (Non) : `%APPDATA%\SyncAusha` est conservé.

- [ ] **Step 7: Commit**

```
git add installer/syncausha.iss build.ps1
git commit -m "build: installateur SyncAusha-Setup.exe (PyInstaller + Inno Setup)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: README et checklist de vérification manuelle

**Files:**
- Create: `README.md`, `docs/verification-manuelle.md`

- [ ] **Step 1: `README.md`**

````markdown
# SyncAusha

Publie automatiquement sur [Ausha](https://www.ausha.co) les podcasts déposés dans un dossier de votre PC.

## Installer

1. Lancez `SyncAusha-Setup.exe`. Si Windows affiche « Windows a protégé votre PC », cliquez sur **Informations complémentaires → Exécuter quand même** (l'exécutable n'est pas signé).
2. Gardez cochée **Lancer SyncAusha au démarrage de Windows**.
3. Au premier lancement, la fenêtre s'ouvre sur **Réglages** :
   - collez votre jeton Ausha (Ausha → Mon compte → API publique ; offre PRO ou Supersonic requise) puis **Tester la connexion** ;
   - choisissez le dossier à surveiller et l'intervalle ;
   - cochez **Essai à blanc** pour une première vérification sans rien publier.
4. Dans **Règles**, ajoutez une règle par série : mot-clé (ex. `MARS ATTACK`), émission, playlist, image, description.

## Fonctionnement

- Toutes les X minutes, chaque fichier audio (`.mp3 .m4a .wav .ogg .flac .mp4`) du dossier, non modifié depuis 30 s, est comparé aux règles. La première règle dont le mot-clé apparaît dans le nom du fichier (majuscules, accents, `_`, `-` ignorés) s'applique.
- L'épisode est créé **et publié immédiatement**, titre = nom du fichier, puis reçoit l'image et est ajouté à la playlist.
- Un fichier sans règle n'est jamais envoyé : il apparaît dans **Activité → À traiter**.
- Les fichiers restent dans le dossier ; `%APPDATA%\SyncAusha\journal.db` mémorise ce qui a été publié (un fichier renommé n'est pas renvoyé). Avant de publier, SyncAusha vérifie aussi qu'aucun épisode du même titre n'existe déjà sur Ausha.

## Développer

```
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python run_syncausha.py
```

## Construire l'installateur

Prérequis : Inno Setup 6 (`winget install -e --id JRSoftware.InnoSetup`).

```
powershell -ExecutionPolicy Bypass -File build.ps1
```

Résultat : `dist\SyncAusha-Setup.exe`.

## Fichiers

- Réglages : `%APPDATA%\SyncAusha\config.json` (le jeton est dans le Gestionnaire d'identifiants Windows)
- Journal : `%APPDATA%\SyncAusha\journal.db`
- Logs : `%APPDATA%\SyncAusha\logs\syncausha.log`
````

- [ ] **Step 2: `docs/verification-manuelle.md`**

```markdown
# Vérification manuelle de SyncAusha

À dérouler avant chaque diffusion de `SyncAusha-Setup.exe`.

## Installation
- [ ] L'installateur est en français, propose « Lancer au démarrage » (cochée) et « Raccourci bureau » (décochée).
- [ ] Aucune demande de droits administrateur.
- [ ] L'app se lance en fin d'installation, fenêtre sur Réglages.

## Réglages
- [ ] Mauvais jeton + « Tester la connexion » → « Échec : … (HTTP 401) ».
- [ ] Bon jeton → « Connexion réussie. Émissions : … ».
- [ ] « Enregistrer » affiche « Réglages enregistrés » ; le jeton n'apparaît pas dans `config.json`.
- [ ] Décocher « Lancer au démarrage » supprime la valeur `SyncAusha` de HKCU\...\Run ; la recocher la recrée.

## Règles
- [ ] Les listes Émission / Playlist se remplissent depuis Ausha.
- [ ] Une image < 400×400 affiche « Image trop petite » et bloque l'enregistrement.
- [ ] Glisser une règle change l'ordre, conservé après redémarrage.
- [ ] Supprimer demande confirmation.

## Synchro (sur une émission de test)
- [ ] Essai à blanc : Activité liste « … — Serait publié dans … », rien n'apparaît sur Ausha.
- [ ] Fichier sans règle : notification « Aucune règle » une seule fois, bouton « Créer une règle » pré-remplit le mot-clé.
- [ ] Fichier avec règle : badge « Envoi xx % » pendant l'upload, puis notification « Épisode publié » ; sur Ausha l'épisode est publié, avec l'image et dans la playlist.
- [ ] Renommer le fichier publié : il n'est pas renvoyé.
- [ ] Couper le réseau pendant un envoi : l'épisode reprend au cycle suivant sans doublon sur Ausha.
- [ ] Jeton révoqué : icône rouge, notification « Jeton Ausha invalide », plus de cycle automatique jusqu'à un nouveau jeton.

## Icône et fenêtre
- [ ] Couleurs : vert (à jour), bleu (synchro), orange (à traiter), rouge (erreur), gris (pause).
- [ ] Clic gauche ouvre la fenêtre ; fermer la fenêtre ne quitte pas l'app.
- [ ] Menu : Synchroniser maintenant, Mettre en pause / Reprendre, Ouvrir le dossier, Quitter.
- [ ] Thème sombre de Windows → fenêtre en thème sombre.
- [ ] Redémarrage du PC : l'app démarre réduite dans la zone de notification.

## Désinstallation
- [ ] Depuis Paramètres → Applications : la question sur les réglages s'affiche ; « Non » conserve `%APPDATA%\SyncAusha`.
- [ ] La valeur `SyncAusha` de HKCU\...\Run a disparu.
```

- [ ] **Step 3: Commit**

```
git add README.md docs/verification-manuelle.md
git commit -m "docs: README et checklist de vérification manuelle" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Couverture de la spec

| Spec | Tâche |
|---|---|
| §3 API (endpoints, multipart, 429, limites) | 6 |
| §4.1 config, jeton keyring | 2 |
| §4.1 rules (casse, accents, priorité, validation) | 3 |
| §4.1 scanner (premier niveau, 30 s, verrou) | 4 |
| §4.1 journal (empreinte, cache, step/status) | 5 |
| §4.1 sync_engine, pause, essai à blanc | 7, 11 |
| §4.1 autostart | 8, 12, 15 |
| §5 déroulé du cycle, anti-doublon, reprise | 7 |
| §6 erreurs (transitoire, 429, 401, 422, 3 échecs, dossier, exception) | 6, 7, 11 |
| §6 logs tournants, jeton jamais logué | 9 |
| §7 interface (Activité, Règles, Réglages, icône, notifications, premier lancement) | 10–14 |
| §8 installation (Inno Setup, sans admin, cases, désinstallation) | 15 |
| §9 tests (pytest, respx, UI manuelle, installateur) | 2–9, 14, 15, 16 |
