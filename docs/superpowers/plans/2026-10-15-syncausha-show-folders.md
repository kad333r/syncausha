# SyncAusha — Un dossier par émission — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le dossier surveillé unique par un dossier par émission (l'émission vient du dossier, des mots-clés obligatoires choisissent playlist/image/description), avec conversion automatique de la configuration 1.0, et publier la 1.1.0.

**Architecture:** `Config.shows` devient une liste de `ShowFolder` (émission + dossier + état des lieux + `KeywordRule`s). Le moteur garde son type interne `Rule` comme **règle effective** (émission + mot-clé fusionnés) : `rules.find_match(filename, shows)` la construit, si bien que validation, publication et reprise restent inchangées. Le moteur lit chaque dossier distinct, fait l'état des lieux émission par émission et ne s'arrête plus sur un dossier introuvable. L'UI remplace la page Règles par une page Émissions.

**Tech Stack:** Python 3.14, PySide6-Essentials 6.11, SQLite, pytest, Inno Setup 6.

**Spec :** `docs/superpowers/specs/2026-10-15-syncausha-show-folders-design.md`

**Conventions :**
- Commandes depuis `C:\code\syncausha`, Python via `.venv/Scripts/python`, branche `feat/show-folders`.
- **Commits sans aucune ligne `Co-Authored-By` ni mention de Claude** (demande explicite de l'utilisateur). Un seul `-m "<sujet>"`.
- Textes visibles : catalogue `syncausha/translations.py`, en `en`/`fr`/`ar`, règles et glossaire en tête de `docs/superpowers/plans/2026-09-23-syncausha-i18n.md` (« émission » = show / برنامج, « mot-clé » = keyword / كلمة مفتاحية, « dossier » = folder / مجلد). Logs en français.
- Les garde-fous `tests/test_ui_texts.py` et `tests/test_i18n.py` doivent rester verts.

---

## Structure des fichiers

```
syncausha/config.py        KeywordRule, ShowFolder, same_folder, Config.shows, conversion 1.0 → 1.1 ; Rule = règle effective
syncausha/rules.py         find_match(filename, shows) -> Rule | None (remplace find_rule)
syncausha/journal.py       colonne folder + migration user_version 1 → 2
syncausha/sync_engine.py   plusieurs dossiers, état des lieux par émission, dossiers introuvables non bloquants
syncausha/ui/controller.py état des lieux par émission, dossiers introuvables, needs_setup
syncausha/ui/shows_page.py page Émissions (remplace rules_page.py)
syncausha/ui/activity_page.py, settings_page.py, main_window.py, tray.py
syncausha/__init__.py, pyproject.toml, installer/syncausha.iss   version 1.1.0
README.md, README.fr.md, README.ar.md, docs/verification-manuelle.md
```

---

### Task 1: Modèle de réglages et conversion 1.0 → 1.1

**Files:**
- Modify: `syncausha/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Tests** — ajouter à `tests/test_config.py` (et retirer/adapter les tests qui utilisent `Config(watch_folder=…, rules=[Rule(…)])`) :

```python
from syncausha.config import Config, KeywordRule, ShowFolder, load_config, same_folder, save_config


def test_shows_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = Config(shows=[
        ShowFolder(show_id=1, show_name="Mars Attack", folder="D:/Podcasts/Mars", baseline_folder="D:/Podcasts/Mars",
                   rules=[KeywordRule(keyword="BONUS", playlist_id=9, playlist_name="Bonus"),
                          KeywordRule(keyword="MARS", playlist_id=7, playlist_name="Saison 3", image_path="C:/img.png",
                                      description_template="Nouvel épisode")]),
        ShowFolder(show_id=2, show_name="Silicon Talk", folder="E:/Silicon"),
    ])
    save_config(config, path)
    assert load_config(path) == config
    assert "watch_folder" not in path.read_text(encoding="utf-8")


def test_v1_config_is_converted(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("""{
      "watch_folder": "D:/Podcasts", "baseline_folder": "D:/Podcasts", "interval_minutes": 30,
      "rules": [
        {"keyword": "MARS ATTACK", "show_id": 1, "show_name": "Mars Attack", "playlist_id": 7, "playlist_name": "Saison 3",
         "image_path": "C:/mars.png", "description_template": "Nouvel épisode"},
        {"keyword": "LE DEBRIEF", "show_id": 2, "show_name": "Silicon Talk"},
        {"keyword": "MARS BONUS", "show_id": 1, "show_name": "Mars Attack", "playlist_id": 9}
      ]}""", encoding="utf-8")
    config = load_config(path)
    assert config.interval_minutes == 30
    assert [s.show_id for s in config.shows] == [1, 2]
    mars, silicon = config.shows
    assert (mars.show_name, mars.folder, mars.baseline_folder) == ("Mars Attack", "D:/Podcasts", "D:/Podcasts")
    assert [r.keyword for r in mars.rules] == ["MARS ATTACK", "MARS BONUS"]
    assert mars.rules[0] == KeywordRule(keyword="MARS ATTACK", playlist_id=7, playlist_name="Saison 3",
                                        image_path="C:/mars.png", description_template="Nouvel épisode")
    assert silicon.rules == [KeywordRule(keyword="LE DEBRIEF")]
    assert not mars.needs_baseline()


def test_v1_config_without_rules_gives_no_show(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"watch_folder": "D:/Podcasts", "rules": []}', encoding="utf-8")
    assert load_config(path).shows == []


def test_invalid_shows_and_keywords_are_skipped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"shows": [1, {"show_name": "x"}, {"show_id": 3, "folder": "F:/A", '
                    '"rules": [{"keyword": "OK"}, {"keyword": 5}, "bad"]}]}', encoding="utf-8")
    (show,) = load_config(path).shows
    assert show.show_id == 3 and [r.keyword for r in show.rules] == ["OK"]


def test_needs_baseline_and_same_folder():
    assert same_folder("D:\\Podcasts\\Mars", "d:/podcasts/mars/")
    assert not same_folder("D:/A", "")
    assert ShowFolder(show_id=1, folder="D:/A").needs_baseline()
    assert not ShowFolder(show_id=1, folder="D:/A", baseline_folder="d:\\a").needs_baseline()
    assert not ShowFolder(show_id=1, folder="").needs_baseline()
```

- [ ] **Step 2: Vérifier l'échec** — `.venv/Scripts/python -m pytest tests/test_config.py -v` → FAIL (`cannot import name 'KeywordRule'`).

- [ ] **Step 3: Implémenter** dans `syncausha/config.py` :

```python
import ntpath  # en tête

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
```

- `Rule` est conservé tel quel mais documenté comme **règle effective** (émission + mot-clé fusionnés, utilisée par le moteur, jamais enregistrée) ; son `from_dict` sert à la conversion 1.0.
- `Config` : retirer `watch_folder`, `baseline_folder`, `rules` ; ajouter `shows: list[ShowFolder] = field(default_factory=list)`. `_CONFIG_STR_FIELDS = ("api_base_url",)`.
- `Config.from_dict` : si `"shows"` est une liste → `ShowFolder.from_dict` pour chaque élément (avertissement et saut des invalides) ; sinon, si `"rules"` est présent → `config.shows = _convert_v1(data)` :

```python
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
        show.rules.append(KeywordRule(rule.keyword, rule.playlist_id, rule.playlist_name, rule.image_path, rule.description_template))
    if shows:
        log.info("Réglages 1.0 convertis : %d émission(s) dans %s", len(shows), folder)
    return list(shows.values())
```

- [ ] **Step 4:** `.venv/Scripts/python -m pytest tests/test_config.py -v` → PASS. (Le reste de la suite cassera jusqu'aux tâches suivantes : c'est attendu ; ne pas committer de suite rouge sans le signaler — utiliser `pytest tests/test_config.py`.)

- [ ] **Step 5: Commit** — `git commit -am "feat(config): émissions avec leur dossier et leurs mots-clés, conversion des réglages 1.0"`

---

### Task 2: Correspondance fichier → émission + mot-clé

**Files:** Modify `syncausha/rules.py`; Test `tests/test_rules.py`

- [ ] **Step 1: Tests** (remplacer les tests de `find_rule`) :

```python
from syncausha.config import KeywordRule, Rule, ShowFolder
from syncausha.rules import find_match

MARS = ShowFolder(show_id=1, show_name="Mars Attack", folder="D:/P",
                  rules=[KeywordRule("BONUS", playlist_id=9, playlist_name="Bonus"),
                         KeywordRule("MARS ATTACK", playlist_id=7, playlist_name="Saison 3", image_path="C:/m.png",
                                     description_template="Nouvel épisode")])
SILICON = ShowFolder(show_id=2, show_name="Silicon Talk", folder="D:/P", rules=[KeywordRule("LE DEBRIEF")])


def test_match_builds_effective_rule():
    rule = find_match("MARS ATTACK - Épisode 12.mp3", [MARS, SILICON])
    assert rule == Rule(keyword="MARS ATTACK", show_id=1, show_name="Mars Attack", playlist_id=7,
                        playlist_name="Saison 3", image_path="C:/m.png", description_template="Nouvel épisode")


def test_keyword_order_and_show_order():
    assert find_match("MARS ATTACK BONUS 3.mp3", [MARS]).playlist_id == 9
    other = ShowFolder(show_id=5, show_name="Autre", folder="D:/P", rules=[KeywordRule("MARS")])
    assert find_match("MARS ATTACK 1.mp3", [other, MARS]).show_id == 5
    assert find_match("MARS ATTACK 1.mp3", [MARS, other]).show_id == 1


def test_keyword_is_required():
    assert find_match("Episode 12.mp3", [MARS, SILICON]) is None
    assert find_match("x.mp3", [ShowFolder(show_id=1, folder="D:/P")]) is None


def test_match_ignores_case_accents_and_punctuation():
    assert find_match("le_debrief-44.mp3", [SILICON]).show_id == 2
```

- [ ] **Step 2:** FAIL (`cannot import name 'find_match'`).
- [ ] **Step 3: Implémenter** dans `syncausha/rules.py` (supprimer `find_rule`, garder `normalize`) :

```python
def find_match(filename: str, shows: list[ShowFolder]) -> Rule | None:
    """Première émission (dans l'ordre) dont un mot-clé (dans l'ordre) apparaît dans le nom du fichier."""
    name = normalize(Path(filename).stem)
    for show in shows:
        for keyword_rule in show.rules:
            keyword = normalize(keyword_rule.keyword)
            if keyword and keyword in name:
                return Rule(
                    keyword=keyword_rule.keyword, show_id=show.show_id, show_name=show.show_name,
                    playlist_id=keyword_rule.playlist_id, playlist_name=keyword_rule.playlist_name,
                    image_path=keyword_rule.image_path, description_template=keyword_rule.description_template,
                )
    return None
```

`validate_rule(rule, catalog)` reste inchangé (il reçoit la règle effective).

- [ ] **Step 4:** `.venv/Scripts/python -m pytest tests/test_rules.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -am "feat(rules): correspondance par émission puis mot-clé"`

---

### Task 3: Journal — colonne `folder` et migration

**Files:** Modify `syncausha/journal.py`; Test `tests/test_journal.py`

- [ ] **Step 1: Tests** :

```python
import sqlite3


def test_ensure_records_folder(journal):
    entry = journal.ensure("h1", "a.mp3", 10, folder="D:/Mars")
    assert entry.folder == "D:/Mars"
    assert journal.ensure("h1", "a.mp3", 10, folder="E:/Autre").folder == "E:/Autre"
    assert journal.ensure("h2", "b.mp3", 1).folder == ""


def test_migrates_v1_database(tmp_path):
    path = tmp_path / "journal.db"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE files (hash TEXT PRIMARY KEY, filename TEXT NOT NULL, size INTEGER NOT NULL, show_id INTEGER,
            show_name TEXT NOT NULL DEFAULT '', episode_id INTEGER, step TEXT NOT NULL DEFAULT 'none',
            status TEXT NOT NULL DEFAULT 'en_attente', attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL);
        CREATE TABLE hash_cache (path TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime REAL NOT NULL, hash TEXT NOT NULL);
        INSERT INTO files (hash, filename, size, status, updated_at) VALUES ('h', 'old.mp3', 1, 'publie', 1.0);
        PRAGMA user_version = 1;""")
    db.close()
    journal = Journal(path)
    entry = journal.get("h")
    assert entry.filename == "old.mp3" and entry.folder == "" and entry.status.value == "publie"
    journal.close()
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == 2
```

(Adapter le schéma de la base « v1 » ci-dessus à celui réellement créé par la version actuelle de `journal.py` — copier son `_SCHEMA` sans la nouvelle colonne.)

- [ ] **Step 2:** FAIL.
- [ ] **Step 3: Implémenter** : colonne `folder TEXT NOT NULL DEFAULT ''` dans `_SCHEMA` et `_COLUMNS`, champ `folder: str` dans `Entry` (dernier champ, défaut `""` pour ne pas casser les constructions positionnelles — vérifier `_to_entry`), `_UPDATABLE` inclut `folder`, `ensure(file_hash, filename, size, folder="")` met à jour `filename` **et** `folder` en cas de conflit. À l'ouverture : lire `PRAGMA user_version` ; 0 (base neuve) → schéma complet puis `user_version = 2` ; 1 → `ALTER TABLE files ADD COLUMN folder TEXT NOT NULL DEFAULT ''` puis `user_version = 2`.
- [ ] **Step 4:** `.venv/Scripts/python -m pytest tests/test_journal.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -am "feat(journal): dossier de chaque fichier, migration de la base"`

---

### Task 4: Moteur — plusieurs dossiers

**Files:** Modify `syncausha/sync_engine.py`, `syncausha/translations.py`; Test `tests/test_sync_engine.py`

- [ ] **Step 1: Adapter la fixture `env`** de `tests/test_sync_engine.py` : `Config(shows=[ShowFolder(show_id=1, show_name="Mars Attack", folder=str(folder), baseline_folder=str(folder), rules=[KeywordRule("MARS ATTACK", playlist_id=7, playlist_name="Saison 3", image_path=str(image), description_template="Nouvel épisode")])])`. Les tests existants qui ajoutaient une règle (`env.config.rules.append(Rule(...))`) ajoutent désormais un `KeywordRule` à `env.config.shows[0].rules` ; ceux qui vidaient `watch_folder` vident `shows[0].folder`. Tous les tests existants doivent garder le même comportement attendu.

- [ ] **Step 2: Nouveaux tests** (dans le même fichier ; `add_file_in(folder, name)` = même chose que `add_file` dans un autre dossier) :

```python
def test_each_show_publishes_its_own_folder(env, tmp_path):
    other = tmp_path / "silicon"; other.mkdir()
    env.client.shows[2] = "Silicon Talk"; env.client.playlists[2] = {}; env.client.episodes[2] = []
    env.config.shows.append(ShowFolder(show_id=2, show_name="Silicon Talk", folder=str(other), baseline_folder=str(other),
                                       rules=[KeywordRule("DEBRIEF")]))
    add_file(env, "MARS ATTACK 12.mp3")
    (other / "LE DEBRIEF 44.mp3").write_bytes(b"debrief")
    assert env.engine.run_cycle().state == "ok"
    created = [(c[1], c[2]) for c in env.client.calls if c[0] == "create"]
    assert sorted(created) == [(1, "MARS ATTACK 12"), (2, "LE DEBRIEF 44")]


def test_file_in_show_folder_without_keyword_is_not_sent(env):
    add_file(env, "Episode 12.mp3")
    assert env.engine.run_cycle().state == "attention"
    assert env.client.calls == [] and only_entry(env).status is Status.SANS_REGLE


def test_keyword_of_another_folder_does_not_apply(env, tmp_path):
    other = tmp_path / "silicon"; other.mkdir()
    env.config.shows.append(ShowFolder(show_id=2, show_name="Silicon Talk", folder=str(other), baseline_folder=str(other),
                                       rules=[KeywordRule("DEBRIEF")]))
    add_file(env, "LE DEBRIEF 44.mp3")  # dans le dossier de Mars Attack
    env.engine.run_cycle()
    assert env.client.calls == [] and only_entry(env).status is Status.SANS_REGLE


def test_shared_folder_uses_show_order(env):
    env.client.shows[2] = "Silicon Talk"; env.client.playlists[2] = {}; env.client.episodes[2] = []
    env.config.shows.insert(0, ShowFolder(show_id=2, show_name="Silicon Talk", folder=env.config.shows[0].folder,
                                          baseline_folder=env.config.shows[0].folder, rules=[KeywordRule("ATTACK")]))
    add_file(env, "MARS ATTACK 12.mp3")
    env.engine.run_cycle()
    assert [c[1] for c in env.client.calls if c[0] == "create"] == [2]


def test_missing_folder_does_not_block_other_shows(env, tmp_path):
    env.config.shows.append(ShowFolder(show_id=1, show_name="Mars Attack", folder=str(tmp_path / "absent"),
                                       baseline_folder=str(tmp_path / "absent"), rules=[KeywordRule("X")]))
    add_file(env, "MARS ATTACK 12.mp3")
    result = env.engine.run_cycle()
    assert result.state == "attention"
    assert result.missing == ((str(tmp_path / "absent"), "Mars Attack"),)
    assert [c[0] for c in env.client.calls].count("create") == 1


def test_baseline_per_show(env, tmp_path):
    new_folder = tmp_path / "nouvelle"; new_folder.mkdir()
    (new_folder / "MARS ATTACK ancien.mp3").write_bytes(b"old")
    env.config.shows.append(ShowFolder(show_id=1, show_name="Mars Attack", folder=str(new_folder),
                                       rules=[KeywordRule("MARS ATTACK")]))
    add_file(env, "MARS ATTACK 12.mp3")  # dossier déjà inventorié : publiable
    result = env.engine.run_cycle()
    assert result.state == "baseline" and result.count == 1
    assert result.folders == (str(new_folder),)
    assert env.client.calls == []


def test_shared_folder_baselined_once(env):
    shared = env.config.shows[0].folder
    for show in env.config.shows:
        show.baseline_folder = ""
    env.config.shows.append(ShowFolder(show_id=2, show_name="Silicon Talk", folder=shared, rules=[KeywordRule("X")]))
    add_file(env, "MARS ATTACK 12.mp3")
    result = env.engine.run_cycle()
    assert result.state == "baseline" and result.count == 1 and result.folders == (shared,)


def test_journal_records_folder(env):
    add_file(env, "MARS ATTACK 12.mp3")
    env.engine.run_cycle()
    assert same_folder(only_entry(env).folder, env.config.shows[0].folder)


def test_no_show_with_folder_is_not_configured(env):
    env.config.shows[0].folder = ""
    assert env.engine.run_cycle().state == "not_configured"
```

- [ ] **Step 3:** `.venv/Scripts/python -m pytest tests/test_sync_engine.py -v` → les nouveaux tests échouent.

- [ ] **Step 4: Implémenter** dans `syncausha/sync_engine.py` :
  - `CycleResult` : remplacer le champ `folder: str` par `folders: tuple[str, ...] = ()` (dossiers inventoriés, état `baseline`) et ajouter `missing: tuple[tuple[str, str], ...] = ()` ((dossier, émission) introuvables).
  - `run_cycle` : `paused` → inchangé. `shows = [s for s in config.shows if s.folder]` ; vide → `CycleResult("not_configured", msg("cycle_add_show"))` (nouvelle clé : en « Add a show and its folder in Shows. », fr « Ajoutez une émission et son dossier dans Émissions. », ar adapté). Émissions à inventorier (`needs_baseline()`) → `_take_baselines(pending)` : regrouper par dossier (`same_folder`), ignorer un dossier introuvable (il sera signalé au cycle normal), pour chaque dossier lisible marquer `IGNORE` les fichiers prêts non finaux (comme `_take_baseline` aujourd'hui) ; retourner `CycleResult("baseline", msg("cycle_existing_files_ignored", n=count), count, folders=tuple(dossiers inventoriés, chemin tel qu'écrit dans la config))`. S'il n'y a que des dossiers introuvables, continuer vers le cycle normal.
  - Cycle normal : créer le client comme aujourd'hui ; regrouper `shows` par dossier (ordre de première apparition, `same_folder`) ; pour chaque groupe : dossier introuvable/illisible → ajouter `(folder, show_name)` pour chaque émission du groupe à `missing`, passer ; sinon scanner, et pour chaque fichier `ensure(..., folder=folder)` puis `rule = find_match(name, group_shows)` (au lieu de `find_rule(name, config.rules)`), le reste de `_process` inchangé. Le catalogue est chargé une fois pour toutes les émissions configurées.
  - `forget_unresolved(seen, union des noms présents de tous les dossiers lus − noms hachés)`.
  - Fin : `missing` non vide ou fichiers à traiter → `CycleResult("attention", message, missing=missing)` ; message : s'il y a des dossiers introuvables `msg("cycle_folder_missing_show", folder=…, show=…)` pour le premier (nouvelle clé : en « Folder not found: {folder} ({show}) », fr « Dossier introuvable : {folder} ({show}) », ar « المجلد غير موجود: {folder} ({show}) »), sinon le message actuel.
  - Supprimer l'état global `folder_missing` du moteur (plus jamais renvoyé) mais laisser les clés de texte si l'UI les utilise encore jusqu'à la Task 5.

- [ ] **Step 5:** `.venv/Scripts/python -m pytest tests/test_sync_engine.py tests/test_rules.py tests/test_config.py tests/test_journal.py tests/test_i18n.py -q` → PASS.
- [ ] **Step 6: Commit** — `git commit -am "feat(engine): un dossier par émission, état des lieux par émission, dossiers introuvables non bloquants"`

---

### Task 5: Contrôleur, Réglages, Activité, icône

**Files:** Modify `syncausha/ui/controller.py`, `ui/settings_page.py`, `ui/activity_page.py`, `ui/tray.py`, `ui/main_window.py`, `syncausha/translations.py`; Tests : `tests/test_controller.py`, `tests/test_ui_smoke.py`, `tests/test_language_switch.py` et autres tests UI à adapter.

- [ ] **Step 1: Tests (contrôleur)** — adapter les fixtures à `Config(shows=[...])` et ajouter :
  - `_on_cycle_finished(CycleResult("baseline", …, count=2, folders=(f,)))` → chaque émission dont `same_folder(show.folder, f)` reçoit `baseline_folder = show.folder`, config enregistrée, **une** notification si `count > 0`, puis `sync_now()` appelé ; une émission dont le dossier a changé entre-temps n'est pas marquée.
  - `missing` : `controller.missing_folders` reflète `result.missing` ; une notification « Dossier introuvable » seulement quand l'ensemble des dossiers manquants change.
  - `needs_setup()` (ou l'équivalent dans `MainWindow`) : vrai sans jeton ou sans émission avec dossier.
- [ ] **Step 2: Implémenter** :
  - Contrôleur : `_on_baseline` adapté (plusieurs dossiers) ; `missing_folders: tuple[tuple[str, str], ...]` mis à jour à chaque fin de cycle ; état initial calculé avec les émissions (plus de `watch_folder`) ; `update_config` : la notion « dossier changé » devient « ensemble des dossiers changé » pour réinitialiser `_last_result_state`.
  - Réglages : supprimer le champ « Dossier surveillé » et son bouton (et les clés de texte devenues inutiles dans le catalogue, sauf si réutilisées).
  - Activité : en-tête `tr("activity_shows_watched", n=len(shows avec dossier))` (en « {n} shows watched », fr « Émissions surveillées : {n} », ar « البرامج المراقَبة: {n} ») + prochaine synchro comme aujourd'hui ; section « À traiter » : une ligne par dossier introuvable (`render(msg("cycle_folder_missing_show", …))`) avec un bouton `tr("activity_edit_show")` (en « Edit show », fr « Modifier l'émission », ar « تعديل البرنامج ») qui émet `edit_show_requested(show_index)` ; « Créer une règle » émet `create_rule_requested(folder, keyword)` (le dossier vient de `entry.folder`).
  - Icône : `Ouvrir le dossier` devient un sous-menu `tr("tray_open_folders")` avec une action par émission (« {show} — {folder} » via une clé `tray_open_show_folder`), reconstruit à chaque `update_config` / changement d'état et dans `retranslate()` ; sous-menu désactivé s'il n'y a aucune émission.
  - `MainWindow` : page `RULES` renommée `SHOWS` (la page elle-même arrive à la Task 6 — en attendant, brancher `create_rule_requested(folder, keyword)` et `edit_show_requested(index)` sur des méthodes de la page Émissions qui seront créées à la Task 6 ; pour garder la suite verte à cette étape, faire cette tâche et la Task 6 dans le même lot si nécessaire, mais committer séparément).
- [ ] **Step 3:** `.venv/Scripts/python -m pytest -q` → PASS (y compris garde-fous de textes et catalogue).
- [ ] **Step 4: Commit** — `git commit -am "feat(ui): émissions dans le contrôleur, l'activité, les réglages et l'icône"`

---

### Task 6: Page Émissions (remplace la page Règles)

**Files:**
- Create: `syncausha/ui/shows_page.py` (à partir de `rules_page.py`, puis supprimer `rules_page.py`)
- Modify: `syncausha/ui/main_window.py`, `syncausha/translations.py`
- Test: `tests/test_shows_page.py` (nouveau), tests UI existants

- [ ] **Step 1: Tests** (`qapp`, offscreen, `get_token` → None, catalogue simulé via `page._on_catalog({...})` comme les tests actuels de la page Règles) :
  - la liste des émissions affiche nom + dossier + nombre de mots-clés ;
  - « Ajouter une émission » → nouvelle émission ; choisir l'émission Ausha + un dossier (`page._set_folder(path)` pour éviter la boîte de dialogue) + enregistrer → `controller.config.shows` contient l'émission avec `baseline_folder == ""` ;
  - changer le dossier d'une émission existante → `baseline_folder` remis à `""` ; le changer pour le même dossier écrit autrement (`d:/x` vs `D:\x`) → inchangé ;
  - ajouter / modifier / supprimer / réordonner un mot-clé d'une émission → `config.shows[i].rules` ;
  - la liste des playlists ne propose que celles de l'émission sélectionnée ;
  - réordonner les émissions → ordre de `config.shows` ;
  - supprimer une émission (confirmation monkeypatchée) → retirée ;
  - `start_new_rule(folder, keyword)` sélectionne la première émission de ce dossier et pré-remplit le mot-clé ; sans émission pour ce dossier → nouvelle émission pré-remplie avec ce dossier ;
  - `select_show(index)` sélectionne l'émission.
  - Toute modification passe par `controller.update_config(replace(config, shows=[...]))` (jamais de mutation en place de la config courante : copier `ShowFolder`/listes avec `dataclasses.replace`), puis `controller.sync_now()`.
- [ ] **Step 2: Implémenter** la page, en réutilisant la mise en page actuelle de `rules_page.py` (cartes, `ReorderableList`, vignettes, `_set_combo_items`, `bidi_text`, validation d'image) :
  - Haut : titre `tr("shows_title")`, bouton `tr("shows_add")`, aide `tr("shows_help")` (en « Each show has its own folder. Inside it, a file is published only if its name contains one of the show's keywords. », fr et ar équivalents), liste réordonnable des émissions.
  - Carte émission : liste Émission Ausha (catalogue), dossier (champ lecture seule + « Choisir… »), bouton « Supprimer l'émission ».
  - Carte mots-clés : liste réordonnable des mots-clés de l'émission (vignette + mot-clé + playlist), bouton « Ajouter un mot-clé », éditeur (mot-clé, playlist de l'émission, image, description) avec Enregistrer / Supprimer.
  - Barre latérale : `tr("nav_shows")` (en « Shows », fr « Émissions », ar « البرامج ») à la place de `nav_rules`.
- [ ] **Step 3:** `.venv/Scripts/python -m pytest -q` → PASS.
- [ ] **Step 4: Commit** — `git rm syncausha/ui/rules_page.py` puis `git add -A syncausha tests && git commit -m "feat(ui): page Émissions avec dossier et mots-clés par émission"`

---

### Task 7: Vérification visuelle (EN / FR / AR)

- [ ] Adapter le script `C:\Users\frmje\AppData\Local\Temp\claude\C--code-syncausha\0fdf41bf-4d2c-4718-b079-5b93e61b33ec\scratchpad\grab_window.py` au nouveau modèle (3 émissions dont 2 dans le même dossier, une au dossier introuvable, mots-clés avec et sans image), plateforme Windows réelle (pas offscreen), jamais d'appel à Ausha ni d'écriture du registre réel. Captures : Activité, Émissions (émission sélectionnée + mot-clé sélectionné), Réglages, en `en`, `fr`, `ar` (+ `ar` sombre) dans `...\scratchpad\grabs_shows\`. Les regarder une par une, corriger mise en page / textes coupés / sens de lecture, recapturer jusqu'à ce que tout soit propre. Suite verte. Commit des corrections éventuelles.

---

### Task 8: Documentation

- [ ] `README.md` (EN, référence), `README.fr.md`, `README.ar.md` : sections Installation et Fonctionnement réécrites (une émission = un dossier + ses mots-clés ; mot-clé obligatoire ; fichiers déjà présents ignorés à l'ajout d'un dossier ; dossier partagé possible ; mise à jour depuis 1.0 automatique). Libellés exacts de l'UI tirés du catalogue.
- [ ] `docs/verification-manuelle.md` : mettre à jour les sections Règles/Synchro et ajouter « Émissions et dossiers » (ajout d'émission, changement de dossier → anciens fichiers ignorés, dossier partagé, dossier introuvable sans blocage, conversion depuis 1.0 sans republication).
- [ ] Commit : `git add README.md README.fr.md README.ar.md docs/verification-manuelle.md && git commit -m "docs: un dossier par émission"`

---

### Task 9: Version 1.1.0, construction et test de mise à jour

- [ ] Passer la version à `1.1.0` dans `syncausha/__init__.py`, `pyproject.toml`, `installer/syncausha.iss` (`#define AppVersion`) et le test qui vérifie la version ; garder le `.iss` en UTF-8 avec BOM. Commit `chore: version 1.1.0`.
- [ ] `powershell -ExecutionPolicy Bypass -File build.ps1` → `OK : dist\SyncAusha-Setup.exe`.
- [ ] Test de mise à jour sur ce PC (état initial propre vérifié et restauré à la fin, aucun appel à Ausha, aucun jeton) :
  1. installer la 1.0.0 depuis la release GitHub (`gh release download v1.0.0 -R kad333r/syncausha -p SyncAusha-Setup.exe -D <scratchpad>\v100`) en silencieux ;
  2. écrire un `%APPDATA%\SyncAusha\config.json` au format 1.0 (dossier de test dans le scratchpad, 2 règles pour 2 émissions, `baseline_folder` = dossier) et un `journal.db` créé par la 1.0 (lancer la 1.0 une fois `--minimized` puis `--quit`) ;
  3. installer la 1.1.0 par-dessus (`/VERYSILENT`) → l'app est fermée puis remplacée ; lancer la 1.1.0 `--minimized`, attendre 10 s, `--quit` ;
  4. vérifier : log sans traceback avec « Réglages 1.0 convertis : 2 émission(s) » ; `journal.db` en `user_version = 2` ; aucun fichier passé en « ignore » à cause de la conversion ;
  5. désinstaller (`/VERYSILENT /SUPPRESSMSGBOXES`), supprimer `%APPDATA%\SyncAusha` créé par le test, état final = état initial.
- [ ] Rapport : taille + SHA-256 de l'installateur.

---

## Couverture de la spec

| Spec | Tâche |
|---|---|
| §3 modèle, validation, conversion 1.0 | 1 |
| §5.4 correspondance émission → mot-clé, mot-clé obligatoire | 2, 4 |
| §4 journal folder + migration | 3 |
| §5 cycle (dossiers distincts, état des lieux par émission, dossier introuvable non bloquant) | 4 |
| §6 contrôleur, Réglages, Activité, icône, premier lancement | 5 |
| §6 page Émissions | 6 |
| §6 langues | 4, 5, 6, 7 |
| §7 documentation | 8 |
| §8 tests, captures, mise à jour depuis 1.0 | 1–7, 9 |
