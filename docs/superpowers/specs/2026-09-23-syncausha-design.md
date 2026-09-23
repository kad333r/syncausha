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
| Fichiers déjà présents au choix du dossier | Jamais publiés automatiquement (statut `ignore`) ; seuls les fichiers ajoutés ensuite le sont. Publication au cas par cas : Activité → « Publier quand même » |
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

Une seule application Python, un seul processus, une seule instance (un second lancement ramène la fenêtre existante au premier plan). L'unicité repose sur un fichier verrou `%APPDATA%\SyncAusha\syncausha.lock` (`QLockFile`, qui reconnaît le verrou laissé par un processus arrêté brutalement) : sous Windows, `QLocalServer.listen` réussit même si le nom est déjà pris, le serveur local ne sert donc qu'à transmettre une demande à l'instance en cours : `show` (afficher la fenêtre, second lancement) ou `quit` (`SyncAusha.exe --quit`, lancé par l'installateur). Tant qu'elle tourne, l'application détient aussi le mutex Windows nommé `SyncAushaRunning`, guetté par l'installateur (§8).

```
syncausha/
  app.py            point d'entrée (--minimized au démarrage Windows ; --quit, --forget-token pour l'installateur)
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
- `%APPDATA%\SyncAusha\config.json` : `watch_folder`, `baseline_folder` (dossier dont les fichiers déjà présents ont été ignorés, voir §5), `interval_minutes` (5–120, défaut 15), `paused`, `dry_run`, `api_base_url`, `rules[]`.
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
- `status` : `en_attente`, `sans_regle`, `regle_cassee`, `en_cours`, `publie`, `deja_present`, `rejete`, `echec`, `ignore`.
- `ignore` : fichier déjà dans le dossier quand celui-ci a été choisi (état des lieux, §5). Statut final : jamais traité automatiquement, absent des listes « À traiter » et « Récent » ; « Publier quand même » le remet `en_attente`. Comme les autres entrées à l'étape `none` non publiées, il est oublié quand son fichier quitte le dossier.
- « Réessayer » et « Publier quand même » remettent `en_attente` et `attempts` à 0 sans toucher `updated_at` : l'attente de 15 min d'une création restée sans réponse (§5) ne repart pas de zéro.
- L'identité par empreinte fait qu'un fichier renommé ou déplacé dans le dossier n'est pas renvoyé.

**`sync_engine`**
- Tourne dans un thread de travail ; l'UI reçoit les événements via des signaux Qt.
- Minuteur `interval_minutes` + déclenchement manuel. Un passage du minuteur pendant un cycle est ignoré ; une demande explicite (Synchroniser, Réessayer, enregistrement des réglages, reprise après pause) relance un cycle dès la fin du cycle en cours.
- En pause : aucun cycle. En essai à blanc : tout le cycle s'exécute sauf les appels d'écriture (création, image, playlist) ; l'Activité affiche « serait publié dans … ».

**`autostart`**
- Valeur `SyncAusha` sous `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `"<chemin>\SyncAusha.exe" --minimized`.
- Pilotée par la case de l'installateur et par la case « Lancer au démarrage de Windows » des Réglages.

## 5. Déroulé d'un cycle

1. Si pause, dossier non choisi ou introuvable → fin.
2. **État des lieux** si le dossier n'a pas encore été pris en compte (`watch_folder ≠ baseline_folder` : premier choix ou changement de dossier), avant tout appel à Ausha et même sans jeton : chaque fichier prêt dont l'entrée est absente, ou non finale et encore à l'étape `none`, est noté `ignore` ; rien n'est publié. Un fichier encore en cours de copie (pas encore prêt) n'est pas concerné : il sera publié une fois prêt. L'application enregistre alors `baseline_folder = watch_folder`, notifie « Dossier pris en compte » (« N fichier(s) déjà présent(s) ignoré(s). Seuls les nouveaux fichiers seront publiés. ») s'il y en a, et lance aussitôt un cycle normal.
3. Jeton absent → fin. Scanner le dossier → fichiers prêts.
4. Pour chaque fichier :
   1. Calculer (ou lire en cache) l'empreinte. Statut `publie`, `deja_present`, `rejete` ou `ignore` dans le journal → ignorer. Statut `echec` → ignorer jusqu'à « Réessayer ».
   2. Au premier fichier qui a du travail, charger une fois pour le cycle les émissions et playlists Ausha (pour valider les règles). En cas d'`AuthError` → état « jeton invalide », fin. Une émission dont Ausha refuse les playlists est laissée de côté : ses règles deviennent « à corriger ». Sans fichier à traiter, aucun appel à Ausha : un jeton révoqué n'est donc détecté qu'au prochain fichier à traiter, ou avec « Tester la connexion ».
   3. Chercher la règle. Aucune → `sans_regle` (signalé une seule fois par fichier ; une seule notification en fin de cycle, « Fichiers sans règle » s'il y en a plusieurs). Si l'étape est déjà au-delà de `none` et que la règle vise désormais une autre émission que celle de l'entrée → `regle_cassee` (« La règle a changé d'émission pendant la publication : vérifiez l'épisode sur Ausha. »), sans appel à Ausha. Règle invalide → `regle_cassee` + notification.
   4. Si `step = none` : chercher dans l'émission un épisode dont le nom est égal au titre (insensible à la casse, aux entités HTML et aux espaces). Trouvé → `deja_present`, passer au fichier suivant.
   5. Si `step = uploading` (réponse à une création perdue) : chercher l'épisode du même titre. Trouvé → il est adopté (`episode_id`, `step = created`). Pas trouvé → il n'est recréé que si la dernière écriture de l'entrée date de plus de 15 min ; sinon le fichier reste `en_attente` (« Envoi précédent en cours de vérification sur Ausha »), sans compter d'essai et sans rajeunir cette date, car la recherche d'Ausha peut tarder à voir un épisode tout juste créé.
   6. `status = en_cours`. Si l'épisode reste à créer : noter `step = uploading`, créer l'épisode (audio, titre, description, `state=active`) ; `uploading` est noté de nouveau quand le fichier est entièrement envoyé, pour que les 15 min partent de la fin d'un long envoi (arrêt forcé en attendant la réponse) ; enregistrer aussitôt `episode_id` et `step = created`. Un refus d'Ausha ne remet `step = none` que si l'étape était `none` avant l'envoi.
   7. Si `step = created` et image dans la règle : envoyer l'image ; `step = image_done`.
   8. Si playlist dans la règle : ajouter l'épisode ; `step = playlist_done`.
   9. `status = publie`, notification « Épisode publié ».
5. Mettre à jour l'état global (icône, page Activité).

Chaque issue est tracée dans le log (niveau INFO ou plus, jamais le jeton) : publié (titre, émission, id de l'épisode), déjà présent, refusé, publication partielle, échec, nombre de fichiers ignorés à l'état des lieux.

Titre : nom du fichier sans extension, espaces en trop retirés, tronqué à 140 caractères. Description : modèle de la règle, tronqué à 3 900 caractères.

## 6. Gestion des erreurs

| Cas | Comportement |
|---|---|
| `TransientError` (réseau, délai, 5xx) | Fichier laissé en l'état, `attempts + 1`, repris au cycle suivant à l'étape interrompue. Un épisode déjà créé n'est jamais recréé ; une création restée sans réponse est d'abord cherchée sur Ausha (règle des 15 min, §5). |
| 429 | Attente `Retry-After` (défaut 60 s), puis même requête. |
| `AuthError` : 401 → jeton invalide ; 403 → jeton invalide seulement sur la liste des émissions, sinon refus ponctuel (`RejectedError`) | Icône rouge, notification « Jeton Ausha invalide » (de nouveau après un nouveau jeton s'il est toujours refusé), plus aucun cycle automatique jusqu'à modification du jeton. |
| `RejectedError` (422, 403 hors liste des émissions, autres 4xx) | `status = rejete`, message Ausha affiché. Pas de nouvel essai automatique ; bouton « Réessayer ». |
| Refus de l'image ou de la playlist alors que l'épisode est déjà en ligne | `status = rejete`, message « Épisode publié, mais l'image n'a pas pu être ajoutée : … » (ou « … mais il n'a pas pu être ajouté à la playlist : … »), notification « Publié avec un problème ». « Réessayer » reprend à l'étape refusée, sans recréer l'épisode. |
| 3 échecs consécutifs sur un fichier | `status = echec`, notification, bouton « Réessayer » (remet `attempts` à 0). |
| Dossier surveillé introuvable | Icône orange, message dans l'Activité, cycle ignoré. |
| Exception inattendue | Journalisée avec trace, le cycle passe au fichier suivant. |
| Fermeture pendant un envoi | L'envoi est interrompu (`Cancelled`) et repris au démarrage suivant. Si le thread de synchro ne s'arrête pas en 15 s (réponse d'Ausha attendue), sortie forcée après écriture des logs ; l'étape `uploading` fait vérifier l'épisode au redémarrage. |
| Réglages impossibles à enregistrer (disque plein, fichier verrouillé) | Les réglages précédents restent en vigueur, notification « Réglages non enregistrés » avec la cause. |

Logs : `%APPDATA%\SyncAusha\logs\syncausha.log`, rotation 1 Mo × 5 fichiers. Le jeton n'apparaît jamais dans les logs.

## 7. Interface

Fenêtre unique avec barre latérale, thème clair/sombre selon Windows, style sobre (surfaces plates, bordures fines, une seule couleur d'accent).

- **Activité**
  - En-tête : état (À jour / Synchronisation… / En pause / Erreur), dossier surveillé, prochain passage (ou « synchro automatique suspendue (jeton invalide) »), bouton « Synchroniser ». Au démarrage, l'état est déduit des réglages et du journal (configuration incomplète, fichiers à traiter, pause, à jour).
  - « À traiter » : fichiers `sans_regle`, `regle_cassee`, `rejete`, `echec`, avec l'action directe (« Créer une règle » pré-remplie avec le nom du fichier, « Modifier la règle », « Réessayer »).
  - « Récent » : 50 derniers fichiers traités avec émission, date et statut (`En cours` avec pourcentage d'envoi, rafraîchi tous les 5 %, `Publié`, `Déjà présent`).
  - « Ignorés — déjà présents au choix du dossier » : fichiers `ignore` (20 au plus, puis « … et N autres »), chacun avec « Publier quand même ».
- **Règles**
  - Liste avec miniature de l'image, mot-clé, émission → playlist ; réordonnable par glisser-déposer.
  - Éditeur : mot-clé, émission (liste Ausha), playlist (liste Ausha de l'émission choisie), image (sélecteur + aperçu, validée au choix), modèle de description. Boutons Enregistrer / Supprimer.
- **Réglages**
  - Jeton Ausha (champ masqué) + « Tester la connexion » (affiche les émissions trouvées).
  - Dossier surveillé (sélecteur), intervalle en minutes.
  - Cases : Lancer au démarrage de Windows, Mettre en pause, Essai à blanc.
  - Liens : Ouvrir le dossier des logs.
- **Icône de notification** : verte (à jour), bleue (synchro en cours), orange (fichiers à traiter), rouge (erreur), grise (pause). Clic gauche : ouvre la fenêtre. Clic droit : Synchroniser maintenant, Mettre en pause / Reprendre, Ouvrir le dossier, Quitter. Fermer la fenêtre la réduit dans la zone de notification.
- **Notifications Windows** : une par événement (publié, publié avec un problème, règle cassée, refus, échec, jeton invalide, dossier pris en compte) ; les fichiers sans règle d'un même cycle sont regroupés en une seule notification.
- Enregistrer ou supprimer une règle relance aussitôt une synchro (hors pause) ; un passage du minuteur en pause est ignoré. Les dialogues standard de Qt (Oui / Non…) sont en français.
- **Premier lancement** : si aucun jeton ou dossier, la fenêtre s'ouvre sur Réglages.

## 8. Installation

- `build.ps1` : crée l'environnement, lance les tests, construit `dist\SyncAusha\` avec PyInstaller (mode dossier, sans console), puis compile `installer\syncausha.iss` avec Inno Setup → `SyncAusha-Setup.exe`.
- Installateur en français, installation dans `%LOCALAPPDATA%\Programs\SyncAusha` (sans droits admin) :
  - case cochée « Lancer SyncAusha au démarrage de Windows » ;
  - case « Créer un raccourci sur le bureau » ;
  - raccourci dans le menu Démarrer ;
  - lance l'application à la fin.
- Windows 10 ou plus récent, 64 bits (`ArchitecturesAllowed=x64compatible`, `MinVersion=10.0`) ; PyInstaller sans UPX.
- **Application en cours d'exécution** : l'installateur guette le mutex `SyncAushaRunning` (`AppMutex`). Avant cette vérification, il lance `SyncAusha.exe --quit` (l'instance en cours se ferme proprement, un envoi interrompu reprendra au lancement suivant) et attend jusqu'à 20 s sa disparition : au démarrage de la mise à jour (`InitializeSetup`, avec le dossier de l'installation précédente lu dans le registre, car Setup vérifie `AppMutex` avant l'assistant), avant l'installation si l'app a été relancée entre-temps (`PrepareToInstall`), et à la désinstallation (`usAppMutexCheck`). Si elle tourne encore, le message standard d'Inno Setup demande de la fermer.
- Désinstallation depuis Paramètres → Applications : supprime le programme et la clé Run ; demande, avant la suppression des fichiers, « Supprimer aussi vos réglages et l'historique SyncAusha ? » (« Non » par défaut). « Oui » retire le jeton du Gestionnaire d'identifiants Windows (`SyncAusha.exe --forget-token`) puis supprime `%APPDATA%\SyncAusha` (réglages, journal, logs).
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
