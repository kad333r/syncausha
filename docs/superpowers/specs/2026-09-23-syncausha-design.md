# SyncAusha — Design

**Date :** 2026-09-23
**Statut :** validé en brainstorming, en attente de relecture

## 1. Objectif

Remplacer l'upload manuel des épisodes sur Ausha par un agent Windows qui :

- surveille un dossier choisi par l'utilisateur ;
- toutes les X minutes, publie sur Ausha les nouveaux fichiers audio via l'API publique ;
- applique à chaque épisode une émission, une image et une playlist selon des règles « le nom du fichier contient … » (ex. `MARS ATTACK`) ;
- démarre avec Windows ;
- s'installe sur n'importe quel PC Windows via un installateur unique, sans prérequis.

## 2. Décisions validées

| Sujet | Décision |
|---|---|
| État de l'épisode | Publié immédiatement (`state=active`) |
| Configuration | Fenêtre de réglages + icône dans la zone de notification |
| Fichier après upload | Reste en place ; un journal local mémorise ce qui a été envoyé |
| Émissions | Plusieurs ; chaque règle choisit l'émission |
| Fichier sans règle | Ignoré, signalé (UI + une notification), jamais envoyé |
| Titre | Nom du fichier sans extension |
| Description | Modèle de texte défini dans la règle |
| Stack | Python 3.14 + PySide6, empaqueté PyInstaller + installateur Inno Setup |
| Distribution | `SyncAusha-Setup.exe`, installation par utilisateur (sans droits admin) |

## 3. API Ausha utilisée

Référence : https://developers.ausha.co/docs/1.0/overview

- **Auth :** jeton personnel (Mon compte → API publique), en-tête `Authorization: Bearer <jeton>`. Requiert une offre PRO (selon contrat) ou Supersonic.
- **URL de base :** `https://api-content.ausha.co/v1` par défaut, modifiable dans `config.json` (`api_base_url`). Le bouton « Tester la connexion » valide l'URL et le jeton.
- **Endpoints :**

| Besoin | Appel |
|---|---|
| Lister les émissions | `GET /shows/granted` |
| Lister les playlists | `GET /shows/{show}/playlists` |
| Chercher un épisode existant | `GET /shows/{show}/podcasts?q=<titre>` (paginé : `page`, `per_page`) |
| Créer + publier l'épisode | `POST /shows/{show}/podcasts` en multipart : `name`, `description`, `state=active`, `file` |
| Image de l'épisode | `POST /podcasts/{podcast}/image` en multipart : `file` |
| Ajout à une playlist | `POST /playlists/{playlist}/podcasts/{podcast}` |

- **Limites :** audio ≤ 500 Mo ; image ≥ 400×400 px, JPEG/PNG, ≤ 10 Mo ; titre ≤ 140 caractères ; description ≤ 3 900 caractères.
- **429 :** respecter l'en-tête `Retry-After`.

## 4. Architecture

Une seule application Python, un seul processus, une seule instance (un second lancement ramène la fenêtre existante au premier plan). L'unicité repose sur un fichier verrou `%APPDATA%\SyncAusha\syncausha.lock` (`QLockFile`, qui reconnaît le verrou laissé par un processus arrêté brutalement) : sous Windows, `QLocalServer.listen` réussit même si le nom est déjà pris, le serveur local ne sert donc qu'à transmettre la demande « afficher la fenêtre ».

```
syncausha/
  app.py            point d'entrée (--minimized au démarrage Windows)
  config.py         réglages + jeton
  ausha_client.py   appels API
  scanner.py        détection des fichiers prêts
  rules.py          correspondance fichier → règle
  journal.py        état local (SQLite)
  sync_engine.py    orchestration d'un cycle
  autostart.py      clé Run du registre
  ui/
    tray.py         icône + menu
    main_window.py  fenêtre (barre latérale)
    activity_page.py
    rules_page.py
    settings_page.py
tests/
installer/
  syncausha.iss     script Inno Setup
build.ps1           PyInstaller + Inno Setup → SyncAusha-Setup.exe
```

### 4.1 Composants

**`config`**
- `%APPDATA%\SyncAusha\config.json` : `watch_folder`, `interval_minutes` (5–120, défaut 15), `paused`, `dry_run`, `api_base_url`, `rules[]`.
- Une règle : `keyword`, `show_id`, `show_name`, `playlist_id` (optionnel), `playlist_name`, `image_path` (optionnel), `description_template`. L'ordre de la liste est l'ordre de priorité.
- Jeton stocké dans le Gestionnaire d'identifiants Windows (bibliothèque `keyring`), jamais dans le JSON.

**`ausha_client`**
- Client `httpx` synchrone, une méthode par endpoint du §3.
- Envois multipart en streaming (pas de chargement du fichier en mémoire).
- Erreurs typées : `AuthError` (401 ; 403 seulement sur la liste des émissions), `RejectedError` (422 et autres 4xx, dont un 403 ailleurs, avec message Ausha), `TransientError` (réseau, délai, 5xx, 429 persistant), `Cancelled` (arrêt de l'application, vérifié avant chaque requête). Le 429 est géré en interne par attente.

**`scanner`**
- Premier niveau du dossier uniquement.
- Extensions : `.mp3 .m4a .wav .ogg .flac .mp4` (insensible à la casse).
- Un fichier est « prêt » si sa date de modification date de plus de 30 s et s'il peut être ouvert en lecture sans violation de partage.

**`rules`**
- Correspondance : le mot-clé est contenu dans le nom du fichier, comparaison insensible à la casse et aux accents (normalisation Unicode NFKD + suppression des diacritiques).
- Première règle correspondante dans l'ordre de la liste.
- Validation avant usage : image existante, JPEG/PNG, ≥ 400×400, ≤ 10 Mo ; émission et playlist présentes dans les listes Ausha chargées au cycle.

**`journal`** — `%APPDATA%\SyncAusha\journal.db` (SQLite)
- Table `files` : `hash` (SHA-256 du contenu, clé), `filename`, `size`, `show_id`, `episode_id`, `step`, `status`, `attempts`, `last_error`, `updated_at`.
- Table `hash_cache` : `path`, `size`, `mtime`, `hash` — évite de relire un fichier inchangé.
- `step` : `none` → `uploading` → `created` → `image_done` → `playlist_done`. `uploading` est noté juste avant l'envoi de la création : si la réponse se perd, l'épisode existe peut-être déjà sur Ausha (voir §5).
- `status` : `en_attente`, `sans_regle`, `regle_cassee`, `en_cours`, `publie`, `deja_present`, `rejete`, `echec`.
- L'identité par empreinte fait qu'un fichier renommé ou déplacé dans le dossier n'est pas renvoyé.

**`sync_engine`**
- Tourne dans un thread de travail ; l'UI reçoit les événements via des signaux Qt.
- Minuteur `interval_minutes` + déclenchement manuel. Un passage du minuteur pendant un cycle est ignoré ; une demande explicite (Synchroniser, Réessayer, enregistrement des réglages, reprise après pause) relance un cycle dès la fin du cycle en cours.
- En pause : aucun cycle. En essai à blanc : tout le cycle s'exécute sauf les appels d'écriture (création, image, playlist) ; l'Activité affiche « serait publié dans … ».

**`autostart`**
- Valeur `SyncAusha` sous `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `"<chemin>\SyncAusha.exe" --minimized`.
- Pilotée par la case de l'installateur et par la case « Lancer au démarrage de Windows » des Réglages.

## 5. Déroulé d'un cycle

1. Si pause ou jeton absent → fin.
2. Scanner le dossier → fichiers prêts.
3. Pour chaque fichier :
   1. Calculer (ou lire en cache) l'empreinte. Statut `publie`, `deja_present` ou `rejete` dans le journal → ignorer. Statut `echec` → ignorer jusqu'à « Réessayer ».
   2. Au premier fichier qui a du travail, charger une fois pour le cycle les émissions et playlists Ausha (pour valider les règles). En cas d'`AuthError` → état « jeton invalide », fin. Une émission dont Ausha refuse les playlists est laissée de côté : ses règles deviennent « à corriger ». Sans fichier à traiter, aucun appel à Ausha : un jeton révoqué n'est donc détecté qu'au prochain fichier à traiter, ou avec « Tester la connexion ».
   3. Chercher la règle. Aucune → `sans_regle` (notification une seule fois par fichier). Règle invalide → `regle_cassee` + notification.
   4. Si `step = none` : chercher dans l'émission un épisode dont le nom est égal au titre (insensible à la casse, aux entités HTML et aux espaces). Trouvé → `deja_present`, passer au fichier suivant.
   5. Si `step = uploading` (réponse à une création perdue) : chercher l'épisode du même titre. Trouvé → il est adopté (`episode_id`, `step = created`). Pas trouvé → il n'est recréé que si la dernière écriture de l'entrée date de plus de 15 min ; sinon le fichier reste `en_attente` (« Envoi précédent en cours de vérification sur Ausha »), sans compter d'essai et sans rajeunir cette date, car la recherche d'Ausha peut tarder à voir un épisode tout juste créé.
   6. `status = en_cours`. Si l'épisode reste à créer : noter `step = uploading`, créer l'épisode (audio, titre, description, `state=active`) ; enregistrer aussitôt `episode_id` et `step = created`. Un refus d'Ausha ne remet `step = none` que si l'étape était `none` avant l'envoi.
   7. Si `step = created` et image dans la règle : envoyer l'image ; `step = image_done`.
   8. Si playlist dans la règle : ajouter l'épisode ; `step = playlist_done`.
   9. `status = publie`, notification « Publié : <titre> ».
4. Mettre à jour l'état global (icône, page Activité).

Titre : nom du fichier sans extension, espaces en trop retirés, tronqué à 140 caractères. Description : modèle de la règle, tronqué à 3 900 caractères.

## 6. Gestion des erreurs

| Cas | Comportement |
|---|---|
| `TransientError` (réseau, délai, 5xx) | Fichier laissé en l'état, `attempts + 1`, repris au cycle suivant à l'étape interrompue. Un épisode déjà créé n'est jamais recréé ; une création restée sans réponse est d'abord cherchée sur Ausha (règle des 15 min, §5). |
| 429 | Attente `Retry-After` (défaut 60 s), puis même requête. |
| `AuthError` : 401 → jeton invalide ; 403 → jeton invalide seulement sur la liste des émissions, sinon refus ponctuel (`RejectedError`) | Icône rouge, notification « Jeton Ausha invalide » (de nouveau après un nouveau jeton s'il est toujours refusé), plus aucun cycle automatique jusqu'à modification du jeton. |
| `RejectedError` (422, 403 hors liste des émissions, autres 4xx) | `status = rejete`, message Ausha affiché. Pas de nouvel essai automatique ; bouton « Réessayer ». |
| 3 échecs consécutifs sur un fichier | `status = echec`, notification, bouton « Réessayer » (remet `attempts` à 0). |
| Dossier surveillé introuvable | Icône orange, message dans l'Activité, cycle ignoré. |
| Exception inattendue | Journalisée avec trace, le cycle passe au fichier suivant. |
| Fermeture pendant un envoi | L'envoi est interrompu (`Cancelled`) et repris au démarrage suivant. Si le thread de synchro ne s'arrête pas en 15 s (réponse d'Ausha attendue), sortie forcée après écriture des logs ; l'étape `uploading` fait vérifier l'épisode au redémarrage. |

Logs : `%APPDATA%\SyncAusha\logs\syncausha.log`, rotation 1 Mo × 5 fichiers. Le jeton n'apparaît jamais dans les logs.

## 7. Interface

Fenêtre unique avec barre latérale, thème clair/sombre selon Windows, style sobre (surfaces plates, bordures fines, une seule couleur d'accent).

- **Activité**
  - En-tête : état (À jour / Synchronisation… / En pause / Erreur), dossier surveillé, prochain passage, bouton « Synchroniser ».
  - « À traiter » : fichiers `sans_regle`, `regle_cassee`, `rejete`, `echec`, avec l'action directe (« Créer une règle » pré-remplie avec le nom du fichier, « Modifier la règle », « Réessayer »).
  - « Récent » : 50 derniers fichiers traités avec émission, date et statut (`En cours` avec pourcentage d'envoi, `Publié`, `Déjà présent`).
- **Règles**
  - Liste avec miniature de l'image, mot-clé, émission → playlist ; réordonnable par glisser-déposer.
  - Éditeur : mot-clé, émission (liste Ausha), playlist (liste Ausha de l'émission choisie), image (sélecteur + aperçu, validée au choix), modèle de description. Boutons Enregistrer / Supprimer.
- **Réglages**
  - Jeton Ausha (champ masqué) + « Tester la connexion » (affiche les émissions trouvées).
  - Dossier surveillé (sélecteur), intervalle en minutes.
  - Cases : Lancer au démarrage de Windows, Mettre en pause, Essai à blanc.
  - Liens : Ouvrir le dossier des logs.
- **Icône de notification** : verte (à jour), bleue (synchro en cours), orange (fichiers à traiter), rouge (erreur), grise (pause). Clic gauche : ouvre la fenêtre. Clic droit : Synchroniser maintenant, Mettre en pause / Reprendre, Ouvrir le dossier, Quitter. Fermer la fenêtre la réduit dans la zone de notification.
- **Notifications Windows** : une par événement (publié, sans règle, règle cassée, échec, jeton invalide).
- **Premier lancement** : si aucun jeton ou dossier, la fenêtre s'ouvre sur Réglages.

## 8. Installation

- `build.ps1` : crée l'environnement, lance les tests, construit `dist\SyncAusha\` avec PyInstaller (mode dossier, sans console), puis compile `installer\syncausha.iss` avec Inno Setup → `SyncAusha-Setup.exe`.
- Installateur en français, installation dans `%LOCALAPPDATA%\Programs\SyncAusha` (sans droits admin) :
  - case cochée « Lancer SyncAusha au démarrage de Windows » ;
  - case « Créer un raccourci sur le bureau » ;
  - raccourci dans le menu Démarrer ;
  - lance l'application à la fin.
- Désinstallation depuis Paramètres → Applications : supprime le programme et la clé Run ; propose de conserver ou supprimer `%APPDATA%\SyncAusha` (réglages et journal).
- Exécutable non signé : SmartScreen affichera un avertissement au premier lancement (« Informations complémentaires → Exécuter quand même »).

## 9. Tests

- **pytest**, sans accès réseau réel :
  - `rules` : casse, accents, priorité, aucune correspondance, validation d'image.
  - `scanner` : fichier trop récent ignoré, fichier verrouillé ignoré, filtrage des extensions, sous-dossiers ignorés.
  - `journal` : cache d'empreinte, fichier renommé non renvoyé, transitions de `step` et `status`.
  - `ausha_client` avec `respx` : forme des requêtes (multipart, `state=active`), en-tête d'auth, 401 / 422 / 429 / 5xx, pagination.
  - `sync_engine` contre une fausse API : nouveau fichier publié de bout en bout, doublon côté Ausha, reprise après échec à chaque étape, règle cassée, 3 échecs → `echec`, essai à blanc sans écriture, pause.
- **UI** : checklist de vérification manuelle (premier lancement, test de connexion, création/réordonnancement de règles, icône et menu, notifications).
- **Installateur** : installation, démarrage avec Windows, désinstallation, vérifiés sur ce PC.
- **Bout en bout** : par l'utilisateur, avec un vrai jeton, d'abord en essai à blanc puis sur une émission de test.

## 10. Hors périmètre

- Sous-dossiers, plusieurs dossiers surveillés.
- Brouillon ou programmation (publication immédiate uniquement).
- Modification d'un épisode après publication.
- Signature de code, mise à jour automatique.
- macOS / Linux.
- Synchronisation des règles entre PC (évolution possible : export/import des règles en JSON).
