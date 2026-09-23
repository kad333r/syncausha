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

- Toutes les X minutes, chaque fichier audio (`.mp3 .m4a .wav .ogg .flac .mp4`) du dossier, non modifié depuis 30 s, est comparé aux règles. La première règle dont le mot-clé apparaît dans le nom du fichier (majuscules/minuscules, accents et ponctuation ignorés : `_`, `-`, apostrophes…) s'applique. Les fichiers vides et les fichiers cachés (nom commençant par `.` ou `~$`) sont ignorés.
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
