# SyncAusha — Un dossier par émission

**Date :** 2026-10-15
**Statut :** validé en brainstorming, en attente de relecture
**S'appuie sur :** `2026-09-23-syncausha-design.md`, `2026-09-23-syncausha-i18n-design.md`
**Version visée :** 1.1.0

## 1. Objectif

Remplacer le dossier surveillé unique par **un dossier par émission**. Le dossier détermine l'émission Ausha ; à l'intérieur, des **mots-clés** (obligatoires) choisissent la playlist, l'image et la description.

## 2. Décisions validées

| Sujet | Décision |
|---|---|
| Rôle du dossier | Il fixe l'émission Ausha de tous les fichiers qu'il contient |
| Mots-clés | Toujours obligatoires : un fichier sans mot-clé reconnu n'est pas envoyé, il est signalé (« sans règle ») |
| Emplacement | Chaque dossier est choisi librement (n'importe où sur le PC) |
| Modèle | Des émissions qui contiennent leurs mots-clés (pas de liste de règles à plat) |
| Réglages communs | Intervalle, pause, essai à blanc, langue, adresse de l'API : communs à toutes les émissions |
| Fichiers déjà présents | Ignorés, émission par émission, quand un dossier est ajouté ou changé |
| Configuration existante | Convertie automatiquement, sans republication ni nouvel état des lieux |
| Dossier partagé | Autorisé : plusieurs émissions peuvent pointer vers le même dossier, leurs mots-clés départagent |

## 3. Modèle de réglages

```
KeywordRule
  keyword: str
  playlist_id: int | None
  playlist_name: str
  image_path: str
  description_template: str

ShowFolder
  show_id: int
  show_name: str
  folder: str
  baseline_folder: str        # dossier pour lequel l'état des lieux a été fait ; ≠ folder → à faire
  rules: list[KeywordRule]    # l'ordre est la priorité

Config
  shows: list[ShowFolder]     # l'ordre est la priorité entre émissions d'un même dossier
  language, interval_minutes, paused, dry_run, api_base_url   # inchangés
```

`watch_folder`, `baseline_folder` (niveau global) et `rules` disparaissent de `Config`. Validation champ par champ comme aujourd'hui : une émission invalide (pas d'`show_id` entier) est ignorée avec un avertissement ; un mot-clé invalide est ignoré, les autres sont gardés.

### 3.1 Conversion de l'ancienne configuration

Au chargement, si le JSON n'a pas de clé `shows` mais a des `rules` (format 1.0) :

1. Les anciennes règles sont regroupées par `show_id`, dans l'ordre de première apparition.
2. Chaque groupe devient un `ShowFolder` : `show_name` = celui de la première règle du groupe, `folder` = l'ancien `watch_folder`, `rules` = les mots-clés du groupe dans leur ordre d'origine (playlist, image, description repris tels quels).
3. `baseline_folder` de chaque émission = l'ancien `baseline_folder` global (si c'était le même que `watch_folder`, aucun nouvel état des lieux n'aura lieu).
4. La configuration convertie est réécrite au format 1.1 au premier enregistrement (pas d'écriture au chargement).

Un ancien `watch_folder` sans aucune règle ne produit aucune émission (rien à convertir) ; l'utilisateur en crée une depuis la page Émissions.

## 4. Journal

- Nouvelle colonne `folder TEXT NOT NULL DEFAULT ''` dans `files` : le dossier où le fichier a été vu pour la dernière fois.
- Migration : `PRAGMA user_version` passe de 1 à 2 ; à l'ouverture, si la version est 1, `ALTER TABLE files ADD COLUMN folder …`, puis version 2.
- `ensure()` met à jour `folder` comme il met à jour `filename`.
- L'identité par empreinte du contenu reste globale : un même fichier copié dans deux dossiers n'est publié qu'une fois.

## 5. Déroulé d'un cycle

1. Pause, jeton absent, aucune émission avec dossier → fin (états existants : `paused`, `not_configured`).
2. **État des lieux par émission :** pour chaque émission dont `folder ≠ baseline_folder`, les fichiers prêts de son dossier qui ne sont pas déjà dans un statut final passent en `ignore` (aucun appel à Ausha). Si plusieurs émissions partagent ce dossier, il n'est analysé qu'une fois. Le résultat du cycle (`baseline`) liste les émissions traitées ; le contrôleur enregistre leur `baseline_folder = folder`, notifie une fois (« {n} fichiers déjà présents ignorés »), puis relance un cycle normal.
3. **Dossiers :** chaque dossier distinct (comparaison insensible à la casse, chemin normalisé) est lu une fois. Un dossier introuvable n'arrête plus le cycle : les émissions concernées sont signalées (message « Dossier introuvable : {folder} ({show}) », une notification au changement d'état), les autres dossiers sont traités. L'état global est `attention` s'il y a un dossier introuvable ou des fichiers à traiter.
4. **Correspondance :** pour un fichier d'un dossier, on parcourt les émissions de ce dossier dans l'ordre de la liste, puis leurs mots-clés dans l'ordre ; la première correspondance (même normalisation qu'aujourd'hui : casse, accents, ponctuation) donne l'émission et la règle. Aucune → `sans_regle`.
5. Validation, anti-doublon, publication par étapes, reprise, essai à blanc, gestion des erreurs : inchangés, l'émission venant du `ShowFolder` et la playlist/image/description de la `KeywordRule`.
6. `forget_unresolved` reçoit l'union des noms présents dans tous les dossiers lus.

## 6. Interface

- **Barre latérale :** « Règles » devient « Émissions ».
- **Page Émissions :**
  - liste des émissions configurées (nom, dossier, nombre de mots-clés), réordonnable ; bouton « Ajouter une émission » ;
  - carte de l'émission sélectionnée : émission Ausha (liste chargée depuis Ausha), dossier + « Choisir… », « Supprimer l'émission » (confirmation) ;
  - liste des mots-clés de cette émission (réordonnable) et éditeur actuel sans le choix d'émission : mot-clé, playlist (de cette émission), image, description ; « Ajouter un mot-clé », « Enregistrer », « Supprimer ».
  - Changer le dossier d'une émission remet son `baseline_folder` à faire (les fichiers déjà présents du nouveau dossier seront ignorés).
- **Réglages :** le champ « Dossier surveillé » est retiré.
- **Activité :**
  - en-tête : « {n} émissions surveillées · prochaine synchronisation … » au lieu du chemin ;
  - lignes : nom de l'émission (depuis le journal) ;
  - « Créer une règle » sur un fichier sans règle ouvre l'émission du dossier du fichier (première émission de ce dossier) avec le mot-clé pré-rempli ;
  - dossier introuvable affiché dans « À traiter » avec un bouton « Modifier l'émission ».
- **Icône de notification :** « Ouvrir le dossier » devient un sous-menu (une entrée par émission avec dossier).
- **Premier lancement :** configuration complète = jeton + au moins une émission avec dossier.
- **Langues :** tous les nouveaux textes en anglais, français et arabe (règles et glossaire du plan i18n ; « émission » = show / برنامج).

## 7. Documentation

README (EN/FR/AR) : installation et fonctionnement réécrits pour « un dossier par émission + mots-clés ». `docs/verification-manuelle.md` : section mise à jour (conversion depuis 1.0, dossier partagé, dossier introuvable, changement de dossier). Notes de la release 1.1.0 en trois langues.

## 8. Tests

- Configuration : conversion 1.0 → 1.1 (regroupement, ordre, dossier, baseline), validation des émissions et mots-clés, aller-retour JSON.
- Journal : migration de la version 1 à 2, colonne `folder` renseignée par `ensure`.
- Moteur : plusieurs dossiers ; dossier partagé (priorité entre émissions) ; mot-clé obligatoire dans le bon dossier ; dossier introuvable qui ne bloque pas les autres ; état des lieux par émission (nouvelle émission, dossier changé, dossier partagé analysé une fois) ; aucune republication après conversion.
- UI (offscreen) : page Émissions (ajout, changement de dossier, mots-clés), Activité (« Créer une règle » vers la bonne émission), sous-menu de l'icône, garde-fous de textes.
- Captures réelles des écrans en anglais, français et arabe.
- Installateur : mise à jour par-dessus la 1.0 sur ce PC avec une configuration 1.0 de test → conversion vérifiée, rien de republié.

## 9. Hors périmètre

- Sous-dossiers à l'intérieur du dossier d'une émission (toujours le premier niveau seulement).
- Détection automatique des émissions à partir des noms de dossiers.
- Réglages (intervalle, pause, essai à blanc) propres à chaque émission.
