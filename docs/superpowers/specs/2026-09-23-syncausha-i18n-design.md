# SyncAusha — Langues (français, anglais, arabe)

**Date :** 2026-09-23
**Statut :** validé en brainstorming, en attente de relecture
**S'appuie sur :** `2026-09-23-syncausha-design.md`

## 1. Objectif

Proposer SyncAusha en **français**, **anglais** et **arabe** : l'application (fenêtre, icône de notification, notifications, messages d'erreur) et l'installateur. La première release publique (GitHub) sortira avec les trois langues.

## 2. Décisions validées

| Sujet | Décision |
|---|---|
| Choix de la langue | Dans l'installateur (English / Français / العربية), modifiable ensuite dans Réglages |
| Langue par défaut | **Anglais** : présélectionné dans l'installateur et utilisé si aucun choix n'existe |
| Changement dans Réglages | Appliqué immédiatement (fenêtre reconstruite), sans redémarrage |
| Mécanisme | Catalogue Python (`tr(clé, **variables)`), pas de Qt Linguist ni gettext |
| Arabe | Interface entière de droite à gauche ; chiffres occidentaux (0-9) |
| Messages stockés | Clé + variables en JSON dans le journal, traduits à l'affichage |
| Release | Après l'ajout des langues ; notes de version en FR / EN / AR |

## 3. Résolution de la langue

Codes : `fr`, `en`, `ar`. Au démarrage, la langue active est la première disponible parmi :

1. `config.language` (`config.json`, choix fait dans Réglages ; chaîne vide = non défini) ;
2. la valeur `Language` de `HKCU\Software\SyncAusha` écrite par l'installateur ;
3. `en` (langue par défaut ; la langue de Windows n'est pas utilisée).

Une valeur inconnue à une étape est ignorée (on passe à la suivante).

## 4. Composants

**`syncausha/translations.py`** — le catalogue : `CATALOG: dict[str, dict[str, str]]`, clé → `{"fr": …, "en": …, "ar": …}`. Les variables utilisent la syntaxe `str.format` (`{title}`, `{n}`, `{detail}`…).

**`syncausha/i18n.py`**
- `LANGUAGES = {"fr": "Français", "en": "English", "ar": "العربية"}` (nom affiché dans sa propre langue).
- `set_language(code)`, `current_language()`, `is_rtl()` (vrai pour `ar`).
- `tr(key, **params)` : texte de la langue active, repli sur l'anglais puis sur la clé si absente ; les variables manquantes ne font pas planter (texte renvoyé sans substitution, avertissement dans le log).
- `resolve_language(config_language, registry_reader)` : applique l'ordre du §3 ; la lecture du registre est injectable pour les tests.
- `Message` : `(key, params)` sérialisable en JSON (`{"k": …, "p": {…}}`) ; `render(text)` traduit un `last_error` du journal : JSON → `tr`, sinon texte affiché tel quel (anciennes lignes, messages bruts).

**Moteur et modules non-UI** (`sync_engine`, `rules`, `ausha_client`, `config`) — les messages destinés à l'utilisateur deviennent des `Message` (clé + variables) au lieu de phrases françaises. Les messages renvoyés par Ausha (souvent en anglais) passent tels quels dans une variable (`{detail}`). Les messages de log restent en français (usage support).

**Journal** — `last_error` contient le JSON du `Message` ; aucun changement de schéma.

**UI** — toutes les chaînes visibles passent par `tr()` : pages, barre latérale, icône et son menu, info-bulles, notifications, boîtes de dialogue, `STATE_TEXT`. Au changement de langue :
- `QApplication.setLayoutDirection` (droite à gauche pour `ar`) ;
- traducteur Qt remplacé par `qtbase_<langue>` (boutons standard Oui/Non…) ;
- la fenêtre principale est reconstruite (le contrôleur, l'état et le journal sont conservés ; la fenêtre rouvre sur la même page) ;
- le menu et l'info-bulle de l'icône sont retraduits.

**Réglages** — nouveau champ « Langue » (liste Français / English / العربية) ; enregistrer applique le changement et le sauve dans `config.language`.

**Installateur** (`installer/syncausha.iss`)
- `[Languages]` : `english` (`Default.isl`, en premier), `french` (`French.isl`), `arabic` (`Arabic.isl`) ; la boîte de choix de langue s'affiche au lancement avec l'anglais présélectionné (`LanguageDetectionMethod=none`, `ShowLanguageDialog=yes`).
- `[CustomMessages]` traduits pour les textes propres à SyncAusha (tâches, question de désinstallation, lancement final).
- `[Registry]` : `HKCU\Software\SyncAusha`, valeur `Language` = `fr` / `en` / `ar` selon la langue choisie (`Languages:`), clé supprimée à la désinstallation (`uninsdeletekey`).
- Le fichier reste en UTF-8 avec BOM.

## 5. Documentation

- `README.md` en **anglais** (version de référence, public GitHub), avec liens vers `README.fr.md` et `README.ar.md` (même contenu).
- Notes de la release : anglais d'abord, puis français et arabe.
- `docs/verification-manuelle.md` : section « Langues » (choix à l'installation, changement dans Réglages, arabe de droite à gauche, désinstallation supprime la clé).

## 6. Tests

- Catalogue : chaque clé a les trois langues, non vides, avec exactement les mêmes variables.
- Aucun texte visible codé en dur dans `syncausha/ui/*.py` : test qui recherche les littéraux passés aux widgets hors `tr()` (liste d'exceptions explicite : noms d'objets QSS, noms de langue).
- `resolve_language` : ordre de priorité et valeurs invalides.
- `Message` : aller-retour JSON, `render` d'un JSON, d'un texte brut, d'une clé inconnue.
- Moteur : les `last_error` et `Event.detail` sont des messages traduisibles (tests existants adaptés).
- UI (offscreen) : changement de langue → fenêtre reconstruite, direction droite à gauche en arabe, textes de la barre latérale dans la bonne langue.
- Captures des trois écrans dans les trois langues (plateforme Windows réelle), vérifiées à l'œil ; relecture de l'arabe par un arabophone avant la release.

## 7. Hors périmètre

- Autres langues.
- Traduction des messages renvoyés par Ausha.
- Traduction des logs.
