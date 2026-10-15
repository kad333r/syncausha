[English](README.md) · **Français** · [العربية](README.ar.md)

# SyncAusha

Publie automatiquement sur [Ausha](https://www.ausha.co) les podcasts déposés dans des dossiers de votre PC, un dossier par émission.

## Installer

1. Téléchargez `SyncAusha-Setup.exe` depuis la [dernière version](https://github.com/kad333r/syncausha/releases/latest) et lancez-le. Si Windows affiche « Windows a protégé votre PC », cliquez sur **Informations complémentaires → Exécuter quand même** (l'exécutable n'est pas signé). Choisissez ensuite la langue (anglais présélectionné).
2. Gardez cochée **Lancer SyncAusha au démarrage de Windows**.
3. Au premier lancement, la fenêtre s'ouvre sur **Réglages** :
   - collez votre jeton Ausha (Ausha → Mon compte → API publique ; offre PRO ou Supersonic requise) puis **Tester la connexion** ;
   - choisissez l'intervalle (**Vérifier toutes les**) ;
   - cochez **Essai à blanc** pour une première vérification sans rien publier ;
   - cliquez sur **Enregistrer**.
4. Dans **Émissions**, cliquez sur **Ajouter une émission** pour chacune de vos émissions Ausha : choisissez l'**Émission Ausha**, puis son **Dossier** (**Choisir…**, n'importe où sur votre PC), et cliquez sur **Enregistrer**.
5. Toujours dans **Émissions**, donnez à chaque émission au moins un mot-clé avec **Ajouter un mot-clé** : dans **Le nom du fichier contient**, le texte à chercher (ex. `MARS ATTACK`), puis la **Playlist**, l'**Image** et la **Description**, et cliquez sur **Enregistrer**. Une émission peut avoir plusieurs mots-clés, par exemple un par série.

**Un fichier n'est publié que si son nom contient un des mots-clés de son émission.**

**Les fichiers déjà présents dans un dossier au moment où vous ajoutez son émission (ou changez le dossier de l'émission) ne sont pas publiés**, sauf si une autre émission surveille déjà ce dossier (voir **Fonctionnement**) : seuls les fichiers ajoutés ensuite le sont. Pour en publier un quand même, ouvrez **Activité → Ignorés** et cliquez sur **Publier quand même** (un fichier à la fois).

Pour mettre à jour, lancez le nouveau `SyncAusha-Setup.exe` : SyncAusha est fermé automatiquement (un envoi en cours reprendra au lancement suivant) et vos réglages sont conservés. Les réglages de la version 1.0 sont convertis automatiquement au premier lancement : chaque émission de vos règles devient une émission avec l'ancien dossier surveillé et les mots-clés de ses règles (playlist, image et description inchangées). Rien n'est republié et aucun fichier n'est ignoré en plus. Si un nom de fichier correspond aux mots-clés de plusieurs émissions, c'est désormais l'ordre des émissions dans **Émissions** qui décide. Si vous n'aviez encore aucune règle, ajoutez vos émissions dans **Émissions**.

## Langues

SyncAusha existe en anglais, en français et en arabe.

- L'installateur demande la langue au lancement (anglais présélectionné) ; l'application démarre ensuite dans cette langue.
- Pour en changer : **Réglages → Langue**, puis **Enregistrer**. La fenêtre et le menu de l'icône changent aussitôt de langue, sans redémarrage ; les notifications suivantes sont dans la nouvelle langue.
- La langue enregistrée dans les Réglages l'emporte sur celle choisie dans l'installateur (lors d'une mise à jour, par exemple).
- En arabe, toute l'interface s'affiche de droite à gauche.

## Fonctionnement

- Chaque émission a son propre dossier, choisi n'importe où sur votre PC. Le dossier fixe l'émission Ausha ; le mot-clé fixe la playlist, l'image et la description.
- Toutes les X minutes, chaque fichier audio (`.mp3 .m4a .wav .ogg .flac .mp4`) placé directement dans le dossier d'une émission (les sous-dossiers ne sont pas lus) et non modifié depuis 30 s est comparé aux mots-clés de cette émission. Le premier mot-clé qui apparaît dans le nom du fichier (majuscules/minuscules, accents et ponctuation ignorés : `_`, `-`, apostrophes…) s'applique. Les fichiers vides et les fichiers cachés (nom commençant par `.` ou `~$`) sont ignorés.
- L'épisode est créé **et publié immédiatement** (en ligne pour vos auditeurs, sans brouillon ni programmation), titre = nom du fichier, puis reçoit l'image et est ajouté à la playlist.
- Un fichier dont le nom ne contient aucun mot-clé de son émission n'est jamais envoyé : il apparaît dans **Activité → À traiter**, où **Créer une règle** ouvre son émission avec un nouveau mot-clé pré-rempli d'après le nom du fichier.
- Plusieurs émissions peuvent utiliser le même dossier : les émissions sont essayées dans leur ordre dans **Émissions**, puis les mots-clés de chacune dans leur ordre, et la première correspondance l'emporte. Faites glisser émissions et mots-clés pour changer leur ordre.
- Quand un dossier est choisi pour une émission, les fichiers qui s'y trouvent déjà sont ignorés (listés dans **Activité → Ignorés**) et seuls les fichiers ajoutés ensuite sont publiés. Exception : ajouter une émission sur un dossier déjà surveillé par une autre émission (ou y déplacer une émission) n'ignore rien ; les fichiers qui y attendaient un mot-clé sont publiés dès qu'ils correspondent aux mots-clés de cette émission.
- Un dossier introuvable (renommé, disque débranché…) n'arrête pas les autres émissions : vous recevez une seule notification **Dossier introuvable**, et le dossier est listé dans **Activité → À traiter** avec **Modifier l'émission**.
- Le menu **Ouvrir le dossier** de l'icône liste le dossier de chaque émission.
- Les fichiers restent dans leur dossier ; `%APPDATA%\SyncAusha\journal.db` mémorise ce qui a été publié (un fichier renommé, ou copié dans le dossier d'une autre émission, n'est pas renvoyé). Avant de publier, SyncAusha vérifie aussi qu'aucun épisode du même titre n'existe déjà sur Ausha.

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

- Réglages, dont les émissions, leurs dossiers et leurs mots-clés : `%APPDATA%\SyncAusha\config.json` (le jeton est dans le Gestionnaire d'identifiants Windows ; répondre « Oui » à la question posée à la désinstallation supprime ce dossier et le jeton)
- Journal : `%APPDATA%\SyncAusha\journal.db`
- Logs : `%APPDATA%\SyncAusha\logs\syncausha.log`
- Langue choisie à l'installation : `HKCU\Software\SyncAusha` (valeur `Language`, supprimée à la désinstallation)
