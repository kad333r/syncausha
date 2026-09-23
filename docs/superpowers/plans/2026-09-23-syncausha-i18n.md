# SyncAusha — Langues (EN / FR / AR) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Traduire SyncAusha (app + installateur + docs) en anglais (défaut), français et arabe (interface de droite à gauche), langue choisie à l'installation et modifiable dans Réglages avec effet immédiat.

**Architecture:** Un catalogue Python (`translations.py`) et un module `i18n.py` (`tr`, `msg`, `render`, `resolve_language`). Les modules non-UI produisent des messages « clé + variables » sérialisés en JSON (`msg`) : ils transitent dans les exceptions, les événements et le journal, et l'UI les traduit à l'affichage (`render`). L'UI appelle `tr()` partout ; un changement de langue reconstruit le contenu de la fenêtre et retraduit l'icône de notification. L'installateur Inno Setup propose les trois langues et écrit la langue choisie dans `HKCU\Software\SyncAusha\Language`.

**Tech Stack:** Python 3.14, PySide6-Essentials 6.11 (QTranslator, `qtbase_fr.qm` / `qtbase_ar.qm` fournis), Inno Setup 6 (`Default.isl`, `French.isl`, `Arabic.isl`), pytest.

**Spec :** `docs/superpowers/specs/2026-09-23-syncausha-i18n-design.md`

**Conventions :**
- Commandes lancées depuis `C:\code\syncausha`, Python via `.venv/Scripts/python`.
- Chaque commit se termine par `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
- Les messages de **log** restent en français ; seuls les textes vus par l'utilisateur sont traduits.

## Règles de traduction (valables pour toutes les tâches)

- **Clés** : `snake_case` en anglais, préfixées par zone : `state_*`, `nav_*`, `activity_*`, `rules_*`, `settings_*`, `tray_*`, `notif_*`, `err_*`, `rule_err_*`, `cycle_*`, `dry_*`, `dialog_*`, `common_*`. Une clé = un texte ; pas de concaténation de morceaux traduits (utiliser des variables `{title}`, `{n}`, `{show}`, `{detail}`, `{status}`, `{folder}`…).
- **Anglais** : ton sobre, « sentence case », pas de point final sur les libellés/boutons.
- **Arabe** : arabe standard moderne, concis ; noms propres non traduits (`SyncAusha`, `Ausha`) ; chiffres occidentaux 0-9 ; pas de ponctuation latine collée (utiliser « ، » et « ؟ » quand il y a une virgule ou une question).
- **Pluriels** : formulations neutres (« Fichiers ignorés : {n} » / « Ignored files: {n} » / « الملفات المتجاهَلة: {n} ») plutôt que « fichier(s) ».
- **Glossaire** (en / fr / ar) — à respecter partout :

| en | fr | ar |
|---|---|---|
| episode | épisode | حلقة |
| show | émission | برنامج |
| playlist | playlist | قائمة تشغيل |
| rule | règle | قاعدة |
| keyword | mot-clé | كلمة مفتاحية |
| watched folder | dossier surveillé | المجلد المراقَب |
| token | jeton | رمز الوصول |
| sync | synchronisation | مزامنة |
| publish / published | publier / publié | نشر / تم النشر |
| dry run | essai à blanc | تشغيل تجريبي |
| ignored | ignoré | متجاهَل |
| Activity / Rules / Settings | Activité / Règles / Réglages | النشاط / القواعد / الإعدادات |
| Retry | Réessayer | إعادة المحاولة |
| pause / resume | pause / reprendre | إيقاف مؤقت / استئناف |
| cover image | image | صورة الغلاف |
| logs | logs | السجلات |

---

## Structure des fichiers

```
syncausha/i18n.py            langue active, tr, msg, render, resolve_language, read_installer_language   (nouveau)
syncausha/translations.py    CATALOG : clé → {"en", "fr", "ar"}                                           (nouveau)
syncausha/config.py          + champ language
syncausha/rules.py           messages de validation → msg()
syncausha/ausha_client.py    messages d'erreur → msg()
syncausha/sync_engine.py     messages (CycleResult, Event.detail, last_error) → msg()
syncausha/ui/language.py     apply_language(app, code) : i18n + direction + traducteur Qt               (nouveau)
syncausha/ui/*.py            textes → tr() / render() ; MainWindow.rebuild ; Tray.retranslate ; champ Langue
syncausha/app.py             résolution de la langue au démarrage
installer/syncausha.iss      3 langues, CustomMessages, clé de registre Language
README.md (anglais), README.fr.md, README.ar.md, docs/verification-manuelle.md
tests/test_i18n.py, tests/test_ui_texts.py, tests/test_language_switch.py                                (nouveaux)
```

---

### Task 1: Noyau i18n

**Files:**
- Create: `syncausha/i18n.py`, `syncausha/translations.py`
- Test: `tests/test_i18n.py`

- [ ] **Step 1: Écrire les tests**

`tests/test_i18n.py` :

```python
import string

import pytest

from syncausha import i18n
from syncausha.i18n import LANGUAGES, msg, render, resolve_language, tr
from syncausha.translations import CATALOG


@pytest.fixture(autouse=True)
def reset_language():
    yield
    i18n.set_language("en")


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_catalog_is_complete_and_consistent():
    for key, entry in CATALOG.items():
        assert set(entry) == set(LANGUAGES), key
        for lang, text in entry.items():
            assert text.strip(), (key, lang)
        assert placeholders(entry["fr"]) == placeholders(entry["en"]) == placeholders(entry["ar"]), key


def test_default_language_is_english():
    assert i18n.DEFAULT_LANGUAGE == "en"
    assert i18n.current_language() == "en"


def test_tr_uses_current_language_and_params(monkeypatch):
    monkeypatch.setitem(CATALOG, "t_hello", {"en": "Hello {name}", "fr": "Bonjour {name}", "ar": "مرحبا {name}"})
    assert tr("t_hello", name="Kader") == "Hello Kader"
    i18n.set_language("fr")
    assert tr("t_hello", name="Kader") == "Bonjour Kader"
    assert tr("t_hello", lang="ar", name="K") == "مرحبا K"


def test_tr_fallbacks(monkeypatch):
    assert tr("does_not_exist") == "does_not_exist"
    monkeypatch.setitem(CATALOG, "t_x", {"en": "Hi {name}", "fr": "Salut {name}", "ar": "أهلا {name}"})
    assert tr("t_x") == "Hi {name}"  # variable absente : texte brut, pas de plantage


def test_set_language_rejects_unknown():
    with pytest.raises(ValueError):
        i18n.set_language("de")


def test_is_rtl():
    i18n.set_language("ar")
    assert i18n.is_rtl()
    assert not i18n.is_rtl("fr")


def test_msg_roundtrip_and_nested(monkeypatch):
    monkeypatch.setitem(CATALOG, "t_outer", {"en": "{title}: {detail}", "fr": "{title} : {detail}", "ar": "{title}: {detail}"})
    monkeypatch.setitem(CATALOG, "t_inner", {"en": "missing {n}", "fr": "manque {n}", "ar": "ينقص {n}"})
    stored = msg("t_outer", title="Ep 1", detail=msg("t_inner", n=3))
    assert render(stored) == "Ep 1: missing 3"
    assert render(stored, lang="fr") == "Ep 1 : manque 3"
    i18n.set_language("ar")
    assert render(stored) == "Ep 1: ينقص 3"


def test_render_plain_text_and_garbage():
    assert render("") == ""
    assert render("File too large (HTTP 422)") == "File too large (HTTP 422)"
    assert render('{"k": broken') == '{"k": broken'
    assert render(msg("unknown_key_xyz")) == "unknown_key_xyz"


def test_resolve_language_priority():
    assert resolve_language("fr", lambda: "ar") == "fr"
    assert resolve_language("", lambda: "ar") == "ar"
    assert resolve_language("", lambda: None) == "en"
    assert resolve_language("de", lambda: "xx") == "en"


def test_read_installer_language_from_registry():
    winreg = pytest.importorskip("winreg")
    path = r"Software\SyncAushaTest"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, "Language", 0, winreg.REG_SZ, "ar")
        assert i18n.read_installer_language(path) == "ar"
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    assert i18n.read_installer_language(path) is None
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/Scripts/python -m pytest tests/test_i18n.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'syncausha.i18n'`

- [ ] **Step 3: Implémenter**

`syncausha/translations.py` :

```python
"""Catalogue des textes de l'interface : clé → {"en", "fr", "ar"}.

Règles : voir docs/superpowers/plans/2026-09-23-syncausha-i18n.md (clés, glossaire, arabe).
"""

CATALOG: dict[str, dict[str, str]] = {}
```

`syncausha/i18n.py` :

```python
"""Langues de l'interface : langue active, traduction des textes et des messages stockés."""
from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable

from syncausha.translations import CATALOG

log = logging.getLogger(__name__)

LANGUAGES = {"en": "English", "fr": "Français", "ar": "العربية"}
DEFAULT_LANGUAGE = "en"
RTL_LANGUAGES = frozenset({"ar"})
REGISTRY_KEY = r"Software\SyncAusha"
_MESSAGE_PREFIX = '{"k":'

_current = DEFAULT_LANGUAGE


def set_language(code: str) -> None:
    global _current
    if code not in LANGUAGES:
        raise ValueError(f"Langue inconnue : {code}")
    _current = code


def current_language() -> str:
    return _current


def is_rtl(code: str | None = None) -> bool:
    return (code or _current) in RTL_LANGUAGES


def tr(key: str, *, lang: str | None = None, **params: object) -> str:
    """Texte de `key` dans la langue voulue (défaut : active ; repli : anglais, puis la clé)."""
    entry = CATALOG.get(key)
    if entry is None:
        log.warning("Clé de traduction inconnue : %s", key)
        return key
    text = entry.get(lang or _current) or entry.get(DEFAULT_LANGUAGE) or key
    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        log.warning("Variables invalides pour %s : %s", key, sorted(params))
        return text


def msg(key: str, **params: object) -> str:
    """Message traduisible à stocker (journal) ou à transporter (exceptions, événements)."""
    payload = {"k": key, "p": {name: str(value) for name, value in params.items()}}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def render(text: str, *, lang: str | None = None) -> str:
    """Traduit un message produit par `msg` ; tout autre texte est renvoyé tel quel."""
    if not text or not text.startswith(_MESSAGE_PREFIX):
        return text or ""
    try:
        data = json.loads(text)
        key, params = data["k"], data.get("p") or {}
    except (ValueError, KeyError, TypeError):
        return text
    if not isinstance(key, str) or not isinstance(params, dict):
        return text
    return tr(key, lang=lang, **{name: render(str(value), lang=lang) for name, value in params.items()})


def read_installer_language(key_path: str = REGISTRY_KEY) -> str | None:
    """Langue choisie dans l'installateur (HKCU\\<key_path>, valeur Language)."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, "Language")
    except OSError:
        return None
    return value if isinstance(value, str) else None


def resolve_language(
    config_language: str,
    registry_reader: Callable[[], str | None] = read_installer_language,
) -> str:
    """Réglages, puis installateur, puis anglais."""
    for candidate in (config_language, registry_reader()):
        if candidate in LANGUAGES:
            return candidate
    return DEFAULT_LANGUAGE
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `.venv/Scripts/python -m pytest tests/test_i18n.py -v` puis `.venv/Scripts/python -m pytest -q`
Expected: tout passe.

- [ ] **Step 5: Commit**

```
git add syncausha/i18n.py syncausha/translations.py tests/test_i18n.py
git commit -m "feat(i18n): catalogue, tr, messages stockés et choix de la langue" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Champ `language` dans les réglages

**Files:**
- Modify: `syncausha/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Tests**

Ajouter à `tests/test_config.py` :

```python
def test_language_roundtrip_and_validation(tmp_path):
    path = tmp_path / "config.json"
    save_config(Config(language="ar"), path)
    assert load_config(path).language == "ar"
    path.write_text('{"language": "de"}', encoding="utf-8")
    assert load_config(path).language == ""
    path.write_text('{"language": 3}', encoding="utf-8")
    assert load_config(path).language == ""
    assert Config().language == ""
```

- [ ] **Step 2: Vérifier l'échec** — `.venv/Scripts/python -m pytest tests/test_config.py -v` → FAIL (`unexpected keyword argument 'language'`).

- [ ] **Step 3: Implémenter** dans `syncausha/config.py` :
  - champ `language: str = ""` dans `Config` (après `baseline_folder`), commentaire : `# "" = non choisi (installateur puis anglais)`;
  - dans `Config.from_dict` : accepter `language` seulement si c'est une chaîne présente dans `syncausha.i18n.LANGUAGES` (import `from syncausha.i18n import LANGUAGES`), sinon garder `""` et journaliser un avertissement comme pour les autres champs.

- [ ] **Step 4: Tests** — `.venv/Scripts/python -m pytest -q` → tout passe.

- [ ] **Step 5: Commit** — `git commit -am "feat(config): langue choisie dans les réglages" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 3: Messages traduisibles dans le cœur (rules, client API, moteur)

Objectif : plus aucune phrase française destinée à l'utilisateur dans `rules.py`, `ausha_client.py`, `sync_engine.py`. Chaque message devient `msg("clé", **variables)` et la clé est ajoutée au `CATALOG` dans les trois langues.

**Files:**
- Modify: `syncausha/rules.py`, `syncausha/ausha_client.py`, `syncausha/sync_engine.py`, `syncausha/translations.py`
- Modify (tests) : `tests/test_rules.py`, `tests/test_ausha_client.py`, `tests/test_sync_engine.py`, et tout autre test qui compare un texte français de ces modules.

- [ ] **Step 1: Inventaire** — lister toutes les chaînes destinées à l'utilisateur :
  - `rules.py` : retours de `validate_image` / `validate_rule` (image introuvable, trop lourde, illisible, format, trop petite ; émission introuvable ; playlist introuvable) → clés `rule_err_*`.
  - `ausha_client.py` : messages des exceptions (`AuthError`, `RejectedError`, `TransientError`, `Cancelled`), `_error_message` (texte Ausha + statut HTTP), redirection, réponse inattendue, fichier illisible, patienter N s, jeton invalide → clés `err_*`. Le texte renvoyé par Ausha reste brut dans une variable : `msg("err_ausha", detail=text, status=response.status_code)` (EN : `"{detail} (HTTP {status})"`) ; sans texte : `msg("err_http_status", status=…)`.
  - `sync_engine.py` : `CycleResult.message` (dossier introuvable, choisissez le dossier, renseignez le jeton, arrêt demandé, N fichiers ignorés, N fichiers à traiter), `Event.detail` (dry run : « serait publié dans {show} », « déjà présent sur Ausha — ne serait pas publié » ; publié partiel), `last_error` (aucune règle ne correspond, vérification en cours sur Ausha, règle a changé d'émission, erreur inattendue {detail}, « Épisode publié, mais l'image… {detail} », « … playlist {detail} »), constantes `STOP_MESSAGE`, `CHECKING_MESSAGE` → clés `cycle_*`, `dry_*`, `err_*`.
  - Les exceptions portent le message sérialisé : `raise TransientError(msg("err_network", detail=str(exc)))`. Le moteur continue de stocker `str(exc)` : c'est déjà un message traduisible. Pour imbriquer, passer le message comme variable : `msg("err_partial_image", detail=str(exc))`.
  - Les variables numériques/texte (`n`, `folder`, `show`, `title`) passent en variables, jamais concaténées.
  - `Event.detail` pour `published` reste le nom de l'émission (donnée, pas un texte).

- [ ] **Step 2: Adapter les tests d'abord** — partout où un test compare une phrase française de ces modules, comparer le rendu : `from syncausha.i18n import render` puis `assert "Playlist introuvable" in render(entry.last_error, lang="fr")`. Ajouter dans `tests/test_sync_engine.py` :

```python
from syncausha.i18n import render


def test_messages_are_translatable(env):
    add_file(env, "interview_brut.mp3")
    env.engine.run_cycle()
    entry = only_entry(env)
    assert render(entry.last_error, lang="en") == "No rule matches this file"
    assert render(entry.last_error, lang="fr") == "Aucune règle ne correspond"
    assert render(entry.last_error, lang="ar") != entry.last_error
```

(Adapter le texte anglais attendu à celui du catalogue ; le français doit rester identique à l'ancien texte.)

Run: `.venv/Scripts/python -m pytest -q` → les tests adaptés échouent (messages encore en français brut).

- [ ] **Step 3: Implémenter** — remplacer chaque message par `msg(...)`, ajouter chaque clé au `CATALOG` en `en`/`fr`/`ar` (français = ancien texte exact). Dans les appels de **log** qui affichent une exception ou un message, utiliser `render(str(exc), lang="fr")` pour garder des logs lisibles en français.

- [ ] **Step 4: Vérifier** — `.venv/Scripts/python -m pytest -q` → tout passe, y compris `test_catalog_is_complete_and_consistent`. Puis :

Run: `.venv/Scripts/python -c "import re,pathlib; [print(p, i+1, l.strip()) for p in ['syncausha/rules.py','syncausha/ausha_client.py','syncausha/sync_engine.py'] for i,l in enumerate(pathlib.Path(p).read_text(encoding='utf-8').splitlines()) if re.search(r'[éèêàçù]', l) and 'log.' not in l and not l.strip().startswith(('#','\"\"\"'))]"`
Expected : seulement des docstrings/commentaires multi-lignes, aucun texte utilisateur.

- [ ] **Step 5: Commit** — `git commit -am "feat(i18n): messages du cœur traduisibles (règles, API, moteur)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 4: Test de garde « aucun texte en dur dans l'UI »

**Files:**
- Create: `tests/test_ui_texts.py`

- [ ] **Step 1: Écrire le test** (il échouera tant que l'UI n'est pas traduite — c'est la cible de la Task 5)

```python
"""Garde-fou : aucun texte visible écrit en dur dans syncausha/ui (tout passe par tr())."""
import ast
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent.parent / "syncausha" / "ui"
# fonction/méthode → positions des arguments qui sont des textes visibles
SINKS = {
    "QLabel": (0,), "QPushButton": (0,), "QCheckBox": (0,), "QMenu": (0,),
    "setText": (0,), "setToolTip": (0,), "setWindowTitle": (0,), "setPlaceholderText": (0,),
    "addAction": (0,), "addItem": (0,), "addItems": (0,), "addRow": (0,), "setSuffix": (0,),
    "showMessage": (0, 1), "make_label": (0,), "section_label": (0,), "pill": (0,), "Row": (0, 1),
    "question": (1, 2), "information": (1, 2), "warning": (1, 2), "critical": (1, 2),
    "getOpenFileName": (1, 3), "getExistingDirectory": (1,),
}
LOGGERS = {"log", "logging", "logger"}
FRENCH_CHARS = set("éèêëàâçîïôûùœÉÈÀÇ")


def _is_text(node):
    if isinstance(node, ast.JoinedStr):
        return True
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and any(c.isalpha() for c in node.value)


def _call_name(func):
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name) and func.value.id in LOGGERS:
            return ""
        return func.attr
    return func.id if isinstance(func, ast.Name) else ""


def _docstrings(tree):
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                nodes.add(id(first.value))
    return nodes


def _log_args(tree):
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in LOGGERS:
            for sub in ast.walk(node):
                nodes.add(id(sub))
    return nodes


def test_no_hardcoded_text_passed_to_widgets():
    offenders = []
    for path in sorted(UI_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            positions = SINKS.get(_call_name(node.func))
            if not positions:
                continue
            for index in positions:
                if index >= len(node.args):
                    continue
                arg = node.args[index]
                items = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
                offenders += [f"{path.name}:{node.lineno}: {ast.unparse(item)[:70]}" for item in items if _is_text(item)]
    assert offenders == []


def test_no_french_text_left_in_ui_modules():
    offenders = []
    for path in sorted(UI_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _docstrings(tree) | _log_args(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
                if FRENCH_CHARS & set(node.value):
                    offenders.append(f"{path.name}:{node.lineno}: {node.value[:70]!r}")
    assert offenders == []
```

- [ ] **Step 2: Vérifier l'échec** — `.venv/Scripts/python -m pytest tests/test_ui_texts.py -v` → FAIL avec la liste des textes en dur (c'est la liste de travail de la Task 5). Si un faux positif apparaît (ex. texte technique non visible), ne PAS affaiblir le test : le signaler.

- [ ] **Step 3: Commit** (test rouge attendu, marqué xfail le temps de la Task 5)

Ajouter `@pytest.mark.xfail(reason="UI en cours de traduction (Task 5)", strict=True)` (avec `import pytest`) sur les deux tests, vérifier que la suite passe (`2 xfailed`), puis :

```
git add tests/test_ui_texts.py
git commit -m "test(i18n): garde-fou contre les textes en dur dans l'UI" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Traduction de toute l'UI

**Files:**
- Modify: `syncausha/ui/activity_page.py`, `rules_page.py`, `settings_page.py`, `controller.py`, `main_window.py`, `tray.py`, `widgets.py` (si besoin), `syncausha/translations.py`
- Modify: `tests/test_ui_texts.py` (retirer les `xfail`), tests UI existants qui comparent des textes français

- [ ] **Step 1:** Retirer les deux `@pytest.mark.xfail` de `tests/test_ui_texts.py`. Run → FAIL (liste des textes à traduire).

- [ ] **Step 2: Convertir, fichier par fichier** :
  - Tout texte visible → `tr("clé", **variables)` ; ajouter la clé au `CATALOG` (fr = texte actuel exact, en, ar selon les règles et le glossaire).
  - Les tables de textes (ex. `STATE_TEXT`, `FILE_NOTIFICATIONS`, `STATE_NOTIFICATIONS`) deviennent des tables de **clés**, traduites au moment de l'affichage/émission (ex. `def state_text(state): return tr(f"state_{state}")` et le tray l'utilise). Ne jamais traduire au chargement du module (la langue peut changer ensuite).
  - Les `last_error`, `CycleResult.message` et `Event.detail` venant du cœur s'affichent via `render(...)` (Activité, notifications, en-tête).
  - Dates : format `"%d/%m %H:%M"` inchangé (chiffres occidentaux).
  - Le filtre du sélecteur d'image devient `tr("rules_image_filter")` (EN : `"Images (*.png *.jpg *.jpeg)"`, garder les motifs identiques dans les trois langues).
  - Barre latérale : `self.sidebar.addItems([tr("nav_activity"), tr("nav_rules"), tr("nav_settings")])`.

- [ ] **Step 3: Adapter les tests UI** existants (`test_ui_smoke.py`, `test_controller.py`, …) qui comparent un texte français : soit `i18n.set_language("fr")` dans le test (et remettre `"en"` à la fin via une fixture), soit comparer à `tr("clé")`.

- [ ] **Step 4: Vérifier** — `.venv/Scripts/python -m pytest -q` → tout passe, `tests/test_ui_texts.py` inclus.

- [ ] **Step 5: Commit** — `git commit -am "feat(i18n): interface traduite (anglais, français, arabe)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 6: Appliquer et changer la langue (démarrage, Réglages, reconstruction)

**Files:**
- Create: `syncausha/ui/language.py`
- Modify: `syncausha/app.py`, `syncausha/ui/main_window.py`, `syncausha/ui/tray.py`, `syncausha/ui/settings_page.py`, `syncausha/translations.py`
- Test: `tests/test_language_switch.py`

- [ ] **Step 1: Tests** — `tests/test_language_switch.py` (utilise la fixture `qapp` de `tests/conftest.py`, plateforme offscreen) :

```python
import pytest
from PySide6.QtCore import Qt

from syncausha import i18n
from syncausha.config import Config, save_config
from syncausha.i18n import tr
from syncausha.journal import Journal
from syncausha.ui import controller as controller_module
from syncausha.ui.controller import AppController
from syncausha.ui.language import apply_language
from syncausha.ui.main_window import RULES, MainWindow


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(controller_module, "get_token", lambda: None)
    save_config(Config(watch_folder=str(tmp_path), baseline_folder=str(tmp_path)), tmp_path / "config.json")
    journal = Journal(tmp_path / "journal.db")
    controller = AppController(tmp_path / "config.json", journal)
    apply_language(qapp, "en")
    win = MainWindow(controller)
    yield win
    apply_language(qapp, "en")
    controller.shutdown()
    journal.close()


def test_apply_language_sets_direction(qapp):
    apply_language(qapp, "ar")
    assert i18n.current_language() == "ar"
    assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
    apply_language(qapp, "fr")
    assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight


def test_rebuild_translates_and_keeps_page(qapp, window):
    window.go_to(RULES)
    assert window.sidebar.item(0).text() == "Activity"
    apply_language(qapp, "fr")
    window.rebuild()
    assert window.sidebar.item(0).text() == tr("nav_activity") == "Activité"
    assert window.stack.currentIndex() == RULES


def test_settings_language_change_rebuilds_window(qapp, window, monkeypatch):
    monkeypatch.setattr("syncausha.autostart.set_enabled", lambda enabled: None)
    settings = window.settings
    index = settings.language.findData("ar")
    settings.language.setCurrentIndex(index)
    settings._save()
    qapp.processEvents()
    qapp.processEvents()
    assert i18n.current_language() == "ar"
    assert window.controller.config.language == "ar"
    assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert window.sidebar.item(0).text() == tr("nav_activity", lang="ar")
```

(Si `_save` a un autre nom ou si le champ n'est pas encore là, c'est ce que le step 3 ajoute. Adapter uniquement les noms au code réel, pas le comportement testé.)

- [ ] **Step 2: Vérifier l'échec** — `.venv/Scripts/python -m pytest tests/test_language_switch.py -v` → FAIL (`No module named 'syncausha.ui.language'`).

- [ ] **Step 3: Implémenter**

`syncausha/ui/language.py` :

```python
"""Applique une langue à l'interface Qt : langue active, sens du texte, boîtes de dialogue standard."""
from __future__ import annotations

import logging

from PySide6.QtCore import QLibraryInfo, Qt, QTranslator
from PySide6.QtWidgets import QApplication

from syncausha import i18n

log = logging.getLogger(__name__)

_qt_translator: QTranslator | None = None


def apply_language(app: QApplication, code: str) -> None:
    global _qt_translator
    i18n.set_language(code)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.is_rtl(code) else Qt.LayoutDirection.LeftToRight)
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    if code == i18n.DEFAULT_LANGUAGE:
        return
    translator = QTranslator(app)
    if translator.load(f"qtbase_{code}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        _qt_translator = translator
    else:
        log.warning("Traductions Qt introuvables pour %s", code)
```

`syncausha/ui/main_window.py` — déplacer la construction du contenu dans `_build()` et ajouter `rebuild()` + un signal :

```python
from PySide6.QtCore import QTimer, Signal
# ...
class MainWindow(QMainWindow):
    language_changed = Signal()

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.resize(880, 600)
        self.setMinimumSize(720, 480)
        self._build()
        self.go_to(SETTINGS if self.needs_setup() else ACTIVITY)

    def _build(self) -> None:
        self.setWindowTitle(tr("app_title"))  # "SyncAusha" dans les trois langues
        central = QWidget()
        # ... même construction qu'avant (sidebar avec tr("nav_*"), pages, connexions) ...
        self.settings.language_changed.connect(self._on_language_changed)
        self.setCentralWidget(central)  # l'ancien widget central et ses pages sont détruits par Qt

    def rebuild(self) -> None:
        """Reconstruit le contenu dans la langue active, en restant sur la même page."""
        index = self.stack.currentIndex()
        self._build()
        self.go_to(index)

    def _on_language_changed(self, code: str) -> None:
        apply_language(QApplication.instance(), code)
        # Différé : la page Réglages qui émet le signal est détruite par la reconstruction.
        QTimer.singleShot(0, self._rebuild_and_notify)

    def _rebuild_and_notify(self) -> None:
        self.rebuild()
        self.language_changed.emit()
```

`syncausha/ui/settings_page.py` :
  - signal `language_changed = Signal(str)` ;
  - champ `self.language = QComboBox()` rempli avec `for code, name in LANGUAGES.items(): self.language.addItem(name, code)` (noms dans leur propre langue ; ces littéraux sont des données, pas des textes à traduire) et placé en premier dans le formulaire avec le libellé `tr("settings_language")` ;
  - `load()` sélectionne `i18n.current_language()` ;
  - `_save()` enregistre `language=self.language.currentData()` dans la config (via `replace`) ; si la langue a changé par rapport à `i18n.current_language()`, émettre `self.language_changed.emit(code)` **après** l'enregistrement.

`syncausha/ui/tray.py` — ajouter `retranslate()` qui remet les textes du menu (`tray_sync_now`, `tray_pause`/`tray_resume`, `tray_open_folder`, `tray_quit`) et l'info-bulle ; l'appeler à la fin de `__init__` (construction des actions sans texte puis `retranslate()`), et `window.language_changed.connect(tray.retranslate)` dans `app.py`.

`syncausha/app.py` — supprimer `_install_qt_translation` ; après la création du contrôleur et avant `MainWindow(...)` :

```python
    apply_language(app, resolve_language(controller.config.language))
```

(imports : `from syncausha.i18n import resolve_language`, `from syncausha.ui.language import apply_language`). Brancher `window.language_changed.connect(tray.retranslate)`.

- [ ] **Step 4: Vérifier** — `.venv/Scripts/python -m pytest -q` → tout passe (dont `tests/test_ui_texts.py`).

- [ ] **Step 5: Commit** — `git add -A syncausha tests && git commit -m "feat(i18n): langue au démarrage, choix dans Réglages et reconstruction immédiate" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 7: Vérification visuelle dans les trois langues

**Files:** aucun fichier du dépôt sauf corrections de style/mise en page nécessaires (`syncausha/ui/style.py`, pages).

- [ ] **Step 1:** Adapter le script de capture `C:\Users\frmje\AppData\Local\Temp\claude\C--code-syncausha\0fdf41bf-4d2c-4718-b079-5b93e61b33ec\scratchpad\grab_window.py` : paramètre de langue (`en`, `fr`, `ar`) appliqué avec `apply_language` avant de créer la fenêtre ; plateforme Windows réelle (pas offscreen) ; sortie `win_<page>_<lang>.png` (et `_dark` en option). Ne jamais appeler Ausha, ne jamais écrire dans le registre réel.
- [ ] **Step 2:** Générer les 9 captures (3 pages × 3 langues) et les regarder une par une. Vérifier : aucun texte coupé (l'allemand n'est pas en jeu mais l'anglais et l'arabe changent les longueurs), boutons alignés, en arabe la barre latérale à droite, textes alignés à droite, champs et listes cohérents, flèches des listes déroulantes du bon côté, pastilles lisibles.
- [ ] **Step 3:** Corriger les défauts (largeurs fixes → `minimumWidth`, `text-align: left` → alignement logique, etc.), relancer les captures jusqu'à ce que les 9 soient propres. Lancer `.venv/Scripts/python -m pytest -q`.
- [ ] **Step 4: Commit** — `git commit -am "fix(ui): mise en page en anglais et en arabe (droite à gauche)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"` (seulement si des fichiers ont changé).

---

### Task 8: Installateur multilingue

**Files:**
- Modify: `installer/syncausha.iss` (garder UTF-8 **avec BOM**)

- [ ] **Step 1: Langues** — remplacer `[Languages]` par :

```ini
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
```

et ajouter dans `[Setup]` : `ShowLanguageDialog=yes` et `LanguageDetectionMethod=none` (anglais présélectionné).

- [ ] **Step 2: Textes propres à SyncAusha** — déplacer chaque texte français codé en dur du script (descriptions des tâches, groupe « Options : », lancement final, question de désinstallation, messages éventuels du `[Code]`) dans `[CustomMessages]` :

```ini
[CustomMessages]
english.TaskAutostart=Start SyncAusha when Windows starts
french.TaskAutostart=Lancer SyncAusha au démarrage de Windows
arabic.TaskAutostart=تشغيل SyncAusha عند بدء تشغيل Windows
english.TaskDesktopIcon=Create a desktop shortcut
french.TaskDesktopIcon=Créer un raccourci sur le bureau
arabic.TaskDesktopIcon=إنشاء اختصار على سطح المكتب
english.GroupOptions=Options:
french.GroupOptions=Options :
arabic.GroupOptions=خيارات:
english.RunNow=Launch SyncAusha now
french.RunNow=Lancer SyncAusha maintenant
arabic.RunNow=تشغيل SyncAusha الآن
english.DeleteSettings=Also delete your SyncAusha settings, history and Ausha token?
french.DeleteSettings=Supprimer aussi vos réglages, l'historique et le jeton Ausha de SyncAusha ?
arabic.DeleteSettings=هل تريد أيضًا حذف إعدادات SyncAusha وسجلّها ورمز الوصول إلى Ausha؟
```

Utiliser `{cm:TaskAutostart}`, `{cm:GroupOptions}`… dans `[Tasks]`/`[Run]`, et `CustomMessage('DeleteSettings')` dans `[Code]`. Ajouter toute autre chaîne utilisateur trouvée dans le script de la même façon.

- [ ] **Step 3: Langue pour l'app** — dans `[Registry]` :

```ini
Root: HKCU; Subkey: "Software\SyncAusha"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\SyncAusha"; ValueType: string; ValueName: "Language"; ValueData: "en"; Languages: english
Root: HKCU; Subkey: "Software\SyncAusha"; ValueType: string; ValueName: "Language"; ValueData: "fr"; Languages: french
Root: HKCU; Subkey: "Software\SyncAusha"; ValueType: string; ValueName: "Language"; ValueData: "ar"; Languages: arabic
```

- [ ] **Step 4: BOM + compilation de contrôle**

Run (PowerShell) :
```
$p = "installer\syncausha.iss"; $c = [IO.File]::ReadAllText($p); [IO.File]::WriteAllText($p, $c, (New-Object Text.UTF8Encoding $true))
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" /O"$env:TEMP\syncausha-iss-check" installer\syncausha.iss
```
Expected : `Successful compile`. (La construction complète et les tests d'installation se font à la Task 10.)

- [ ] **Step 5: Commit** — `git commit -am "feat(installer): installateur en anglais, français et arabe" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 9: Documentation

**Files:**
- Modify: `README.md` (→ anglais), `docs/verification-manuelle.md`
- Create: `README.fr.md` (contenu français actuel, mis à jour), `README.ar.md`

- [ ] **Step 1:** `README.fr.md` = l'actuel `README.md` en français, complété d'une section « Langues » (choix à l'installation, changement dans Réglages → Langue, arabe de droite à gauche).
- [ ] **Step 2:** `README.md` = traduction anglaise fidèle de `README.fr.md`, avec en tête : `**English** · [Français](README.fr.md) · [العربية](README.ar.md)`. Même ligne de liens (adaptée) en tête des deux autres fichiers.
- [ ] **Step 3:** `README.ar.md` = traduction arabe (glossaire ci-dessus), encadrée par `<div dir="rtl">` … `</div>` pour l'affichage GitHub ; blocs de code et noms de fichiers inchangés.
- [ ] **Step 4:** `docs/verification-manuelle.md` : section « Langues » avec cases à cocher — installateur : choix de la langue (anglais présélectionné), pages et cases traduites ; app : démarre dans la langue choisie ; Réglages → Langue change immédiatement la fenêtre et le menu de l'icône ; arabe de droite à gauche, textes non coupés ; notifications dans la langue active ; désinstallation supprime `HKCU\Software\SyncAusha`.
- [ ] **Step 5: Commit** — `git add README.md README.fr.md README.ar.md docs/verification-manuelle.md && git commit -m "docs: README en anglais, français et arabe" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`

---

### Task 10: Construction et vérification de l'installateur

- [ ] **Step 1:** Garder la version `1.0.0` partout (la release publique n'est pas encore sortie ; le tag `v1.0.0` sera déplacé sur le commit final au moment de la publication, avec l'accord de l'utilisateur).
- [ ] **Step 2:** `powershell -ExecutionPolicy Bypass -File build.ps1` → `OK : dist\SyncAusha-Setup.exe`.
- [ ] **Step 3:** Sur ce PC, en partant d'un état propre (rien d'installé, pas de `%APPDATA%\SyncAusha`, pas de `HKCU\Software\SyncAusha`) : installation silencieuse en arabe `dist\SyncAusha-Setup.exe /VERYSILENT /LANG=arabic /TASKS="autostart"` → vérifier `HKCU\Software\SyncAusha\Language = ar` ; lancer l'app installée `--minimized`, vérifier dans le log le démarrage et l'absence de traceback ; `--quit` ; désinstaller `/VERYSILENT /SUPPRESSMSGBOXES` → vérifier que `HKCU\Software\SyncAusha` a disparu ; supprimer le `%APPDATA%\SyncAusha` créé par le test ; état final = état initial.
- [ ] **Step 4:** Rapport : taille de l'installateur, SHA-256.

---

## Couverture de la spec

| Spec | Tâche |
|---|---|
| §2 anglais par défaut, choix installateur, modifiable dans Réglages, immédiat | 1, 6, 8 |
| §3 résolution (réglages → registre → anglais) | 1, 6 |
| §4 translations.py, i18n.py, Message/render | 1 |
| §4 cœur en messages traduisibles, logs en français | 3 |
| §4 UI via tr(), direction, traducteur Qt, reconstruction, tray | 5, 6 |
| §4 champ Langue dans Réglages | 6 |
| §4 installateur (langues, CustomMessages, registre, BOM) | 8 |
| §5 README EN + FR + AR, vérification manuelle | 9 |
| §6 tests (catalogue, textes en dur, résolution, render, UI, captures) | 1, 3, 4, 6, 7 |
| Construction et test de l'installateur | 10 |
