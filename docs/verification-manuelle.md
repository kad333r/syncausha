# Vérification manuelle de SyncAusha

À dérouler avant chaque diffusion de `SyncAusha-Setup.exe`. Sauf dans la section « Langues », l'installateur et l'app sont utilisés en français.

## Installation
- [ ] L'installateur propose « Lancer SyncAusha au démarrage de Windows » (cochée) et « Créer un raccourci sur le bureau » (décochée).
- [ ] Aucune demande de droits administrateur.
- [ ] L'app se lance en fin d'installation, fenêtre sur Réglages.

## Réglages
- [ ] Mauvais jeton + « Tester la connexion » → « Échec de la connexion : … (HTTP 401) ».
- [ ] Bon jeton → « Connexion réussie. Émissions : … ».
- [ ] « Enregistrer » affiche « Réglages enregistrés » ; le jeton n'apparaît pas dans `config.json`.
- [ ] La page n'a plus de champ de dossier : les dossiers se choisissent dans Émissions.
- [ ] Décocher « Lancer au démarrage » supprime la valeur `SyncAusha` de HKCU\...\Run ; la recocher la recrée.
- [ ] Un `config.json` corrompu est renommé en `config.json.illisible` et l'app démarre avec des réglages vides (pas de plantage).

## Page Émissions
- [ ] Jeton enregistré mais aucune émission : au lancement suivant, la fenêtre s'ouvre sur Émissions ; l'Activité affiche « Configuration incomplète » et « Ajoutez une émission et son dossier dans Émissions. ».
- [ ] « Ajouter une émission » : la liste « Émission Ausha » se remplit depuis Ausha, sans présélection (« Choisissez une émission ») ; les mots-clés restent inactifs avec « Enregistrez l'émission pour ajouter ses mots-clés. ».
- [ ] « Enregistrer » sans dossier → « Choisissez un dossier. » ; sans émission → « Choisissez une émission. ».
- [ ] Émission enregistrée : elle apparaît dans la liste avec son nom, « Mots-clés : 0 » et son dossier (chemin complet en info-bulle).
- [ ] « Ajouter un mot-clé » : la liste Playlist ne propose que les playlists de cette émission ; mot-clé vide → « Indiquez un mot-clé. ».
- [ ] Une image < 400×400 affiche « Image trop petite » et bloque l'enregistrement.
- [ ] Glisser une émission, ou un mot-clé, change l'ordre, conservé après redémarrage.
- [ ] Changer l'« Émission Ausha » d'une émission dont des mots-clés ont une playlist : question « Changer d'émission » ; « Non » ne change rien ; « Oui » garde les mots-clés mais leur retire la playlist.
- [ ] Supprimer un mot-clé demande confirmation (« Supprimer le mot-clé « … » ? »), avec des boutons « Oui » / « Non » en français.
- [ ] « Supprimer l'émission » demande confirmation (« Supprimer l'émission « … » et ses mots-clés ? Rien n'est supprimé dans son dossier ni sur Ausha. ») ; après « Oui », les fichiers du dossier et les épisodes sur Ausha sont intacts.

## Émissions et dossiers
- [ ] Ajouter une émission sur un dossier qui contient déjà des fichiers audio : notification « Dossier pris en compte » (« Fichiers déjà présents ignorés : N. Seuls les nouveaux fichiers seront publiés. »), rien n'est publié sur Ausha.
- [ ] Ces fichiers apparaissent dans Activité → « Ignorés — déjà présents au choix du dossier » (20 au plus, puis « … et N autres »).
- [ ] « Publier quand même » sur l'un d'eux (son nom contient un mot-clé de l'émission) : il est publié aussitôt, les autres restent ignorés.
- [ ] Un fichier ajouté au dossier après coup est publié au passage suivant.
- [ ] Ajouter une émission sur un dossier vide : pas de notification « Dossier pris en compte ».
- [ ] Changer le dossier d'une émission (« Choisir… » puis « Enregistrer ») : les fichiers déjà présents dans le nouveau dossier sont ignorés à leur tour, rien n'est publié ; un fichier ajouté ensuite est publié.
- [ ] Deux émissions dans deux dossiers : chaque fichier part dans l'émission de son dossier, avec la playlist, l'image et la description de son mot-clé.
- [ ] Fichier déposé dans le dossier de l'émission A dont le nom ne contient qu'un mot-clé de l'émission B (autre dossier) : il n'est pas envoyé (« Aucune règle »).
- [ ] Dossier partagé : deux émissions sur le même dossier, chacune avec son mot-clé ; un fichier de chacune part dans la bonne émission.
- [ ] Dossier partagé : un fichier dont le nom contient les mots-clés des deux émissions part dans la première de la liste ; après avoir glissé l'autre en tête, le fichier suivant de ce type part dans celle-ci.
- [ ] Ajouter une seconde émission sur un dossier déjà surveillé : pas de notification « Dossier pris en compte », aucun fichier ignoré ; un fichier qui y attendait (« Aucune règle ») et contient un mot-clé de la nouvelle émission est publié.
- [ ] Renommer le dossier d'une émission (ou débrancher son disque) : une seule notification « Dossier introuvable » ; icône orange ; Activité → « À traiter » affiche « Dossier introuvable : … (nom de l'émission) » avec « Modifier l'émission », qui ouvre cette émission.
- [ ] Pendant ce temps, un fichier déposé dans le dossier d'une autre émission est publié normalement.
- [ ] Le dossier reste introuvable plusieurs passages : pas de nouvelle notification. Une fois le dossier rétabli, la ligne disparaît au passage suivant.
- [ ] Conversion depuis la 1.0 (installer la 1.1 par-dessus une 1.0 dont les règles visent deux émissions) : la page Émissions liste deux émissions, dans l'ordre de leur première règle, chacune avec l'ancien dossier surveillé et les mots-clés de ses règles dans leur ordre d'origine (playlist, image et description inchangées).
- [ ] Après la conversion : pas de notification « Dossier pris en compte », rien n'est republié sur Ausha ; les fichiers ignorés en 1.0 restent dans « Ignorés », Activité → Récent garde les épisodes publiés en 1.0 ; un nouveau fichier part dans la bonne émission.
- [ ] Le log contient « Réglages 1.0 convertis : 2 émission(s) dans … » ; `config.json` garde l'ancien format jusqu'au premier enregistrement, puis contient `shows` (plus de `watch_folder` ni de `rules`).
- [ ] Conversion d'une 1.0 sans aucune règle : aucune émission créée, la fenêtre s'ouvre sur Émissions.

## Synchro (sur une émission de test)
- [ ] Essai à blanc : Activité liste « … — Serait publié dans … », rien n'apparaît sur Ausha.
- [ ] Fichier dont le nom ne contient aucun mot-clé de son émission : notification « Aucune règle » une seule fois ; le bouton « Créer une règle » ouvre l'émission de ce dossier avec le mot-clé pré-rempli d'après le nom du fichier ; une fois le mot-clé enregistré, le fichier part aussitôt.
- [ ] Trois fichiers sans mot-clé reconnu déposés ensemble : une seule notification « Fichiers sans règle » (« 3 fichiers n'ont pas été envoyés : aucune règle ne correspond. »).
- [ ] Fichier avec un mot-clé : badge « Envoi xx % » pendant l'upload, puis notification « Épisode publié » ; sur Ausha l'épisode est publié dans l'émission du dossier, avec l'image et dans la playlist du mot-clé.
- [ ] Renommer le fichier publié : il n'est pas renvoyé.
- [ ] Copier le fichier publié dans le dossier d'une autre émission : il n'est pas renvoyé.
- [ ] Couper le réseau pendant un envoi : Activité affiche « Envoi précédent en cours de vérification sur Ausha » ; le fichier est renvoyé une fois la fenêtre de vérification de 15 min écoulée, et un seul épisode existe sur Ausha.
- [ ] Quitter (menu de l'icône) pendant un envoi : l'app se ferme en 15 s au plus ; au redémarrage, le fichier est renvoyé après la fenêtre de vérification de 15 min, et un seul épisode existe sur Ausha.
- [ ] Fichier refusé ou en échec → « Réessayer » : relancé aussitôt, il reprend à l'étape interrompue (pas de second épisode sur Ausha).
- [ ] Jeton révoqué, avec un fichier en attente de publication (ou « Synchroniser » avec un fichier à publier) : icône rouge, notification « Jeton Ausha invalide », Activité affiche « synchro automatique suspendue (jeton invalide) », plus de cycle automatique jusqu'à un nouveau jeton.

## Icône et fenêtre
- [ ] Couleurs : vert (à jour), bleu (synchro), orange (à traiter), rouge (erreur), gris (pause).
- [ ] Clic gauche ouvre la fenêtre ; fermer la fenêtre ne quitte pas l'app.
- [ ] Menu : Synchroniser maintenant, Mettre en pause / Reprendre la synchronisation, Ouvrir le dossier, Quitter.
- [ ] « Ouvrir le dossier » est un sous-menu avec une entrée « émission — dossier » par émission, qui ouvre ce dossier ; il est grisé quand aucune émission n'a de dossier, et suit les ajouts et suppressions d'émissions.
- [ ] En-tête de l'Activité : « Émissions surveillées : N · prochain passage dans … min ».
- [ ] Mettre en pause depuis l'icône : la case « Mettre la synchronisation en pause » des Réglages se coche.
- [ ] Thème sombre de Windows → fenêtre en thème sombre.
- [ ] Redémarrage du PC : l'app démarre réduite dans la zone de notification.

## Mise à jour et désinstallation
- [ ] Relancer `SyncAusha-Setup.exe` pendant que l'app tourne : elle se ferme d'elle-même (pas de message « … est en cours d'exécution »), les réglages et l'historique sont conservés.
- [ ] Désinstaller depuis Paramètres → Applications pendant que l'app tourne : elle se ferme d'elle-même.
- [ ] La question « Supprimer aussi vos réglages, l'historique et le jeton Ausha de SyncAusha ? » s'affiche ; « Non » conserve `%APPDATA%\SyncAusha` et le jeton.
- [ ] « Oui » supprime `%APPDATA%\SyncAusha` et retire le jeton : plus d'entrée SyncAusha dans Gestionnaire d'identifiants → Informations d'identification Windows.
- [ ] La valeur `SyncAusha` de HKCU\...\Run a disparu.

## Langues
- [ ] Au lancement, l'installateur demande la langue : English (présélectionné), Français, العربية.
- [ ] Dans chaque langue, les pages de l'installateur, les cases « Options », la case de lancement final et la question de désinstallation sont traduites ; en arabe, l'assistant s'affiche de droite à gauche.
- [ ] L'app démarre dans la langue choisie à l'installation (valeur `Language` de `HKCU\Software\SyncAusha` = `en` / `fr` / `ar`).
- [ ] Réglages → Langue, puis « Enregistrer » : la fenêtre change aussitôt de langue, sans redémarrage, et reste sur Réglages ; le menu, son sous-menu « Ouvrir le dossier » et l'info-bulle de l'icône suivent.
- [ ] Après redémarrage, l'app reste dans la langue choisie dans Réglages, même si l'installateur a été relancé dans une autre langue.
- [ ] Enregistrer les Réglages sans toucher à la Langue ne la fige pas : après réinstallation dans une autre langue, l'app démarre dans celle de l'installateur.
- [ ] Activité → Récent : dates au format de la langue (chiffres 0-9 en arabe).
- [ ] Les lignes déjà présentes dans Activité (erreurs, fichiers à traiter, dossiers introuvables) s'affichent dans la nouvelle langue.
- [ ] Arabe : toute l'interface de droite à gauche (barre latérale à droite, textes alignés à droite, flèches des listes déroulantes du bon côté), aucun texte coupé, chiffres occidentaux.
- [ ] Arabe, page Émissions : un nom d'émission ou de playlist qui commence par des chiffres (« 2024 Le Debrief ») garde son ordre dans les listes ; un long chemin de dossier est coupé au milieu, chemin complet en info-bulle.
- [ ] Boutons standard (Oui / Non des confirmations de suppression d'une émission ou d'un mot-clé) dans la langue active.
- [ ] Notifications (« Épisode publié », « Aucune règle », « Dossier introuvable »…) dans la langue active, y compris juste après un changement de langue.
- [ ] La désinstallation supprime la clé `HKCU\Software\SyncAusha`.
