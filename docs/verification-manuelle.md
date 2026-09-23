# Vérification manuelle de SyncAusha

À dérouler avant chaque diffusion de `SyncAusha-Setup.exe`. Sauf dans la section « Langues », l'installateur et l'app sont utilisés en français.

## Installation
- [ ] L'installateur propose « Lancer SyncAusha au démarrage de Windows » (cochée) et « Créer un raccourci sur le bureau » (décochée).
- [ ] Aucune demande de droits administrateur.
- [ ] L'app se lance en fin d'installation, fenêtre sur Réglages.

## Réglages
- [ ] Mauvais jeton + « Tester la connexion » → « Échec : … (HTTP 401) ».
- [ ] Bon jeton → « Connexion réussie. Émissions : … ».
- [ ] « Enregistrer » affiche « Réglages enregistrés » ; le jeton n'apparaît pas dans `config.json`.
- [ ] Décocher « Lancer au démarrage » supprime la valeur `SyncAusha` de HKCU\...\Run ; la recocher la recrée.
- [ ] Un `config.json` corrompu est renommé en `config.json.illisible` et l'app démarre avec des réglages vides (pas de plantage).

## Choix du dossier
- [ ] Choisir un dossier qui contient déjà des fichiers audio : notification « Dossier pris en compte » (« N fichier(s) déjà présent(s) ignoré(s). Seuls les nouveaux fichiers seront publiés. »), rien n'est publié sur Ausha.
- [ ] Ces fichiers apparaissent dans Activité → « Ignorés — déjà présents au choix du dossier » (20 au plus, puis « … et N autres »).
- [ ] « Publier quand même » sur l'un d'eux : il est publié aussitôt, les autres restent ignorés.
- [ ] Un fichier ajouté au dossier après ce choix est publié au passage suivant.
- [ ] Choisir un autre dossier : ses fichiers déjà présents sont ignorés à leur tour.

## Règles
- [ ] Les listes Émission / Playlist se remplissent depuis Ausha.
- [ ] Une image < 400×400 affiche « Image trop petite » et bloque l'enregistrement.
- [ ] Glisser une règle change l'ordre, conservé après redémarrage.
- [ ] Supprimer demande confirmation, avec des boutons « Oui » / « Non » en français.

## Synchro (sur une émission de test)
- [ ] Essai à blanc : Activité liste « … — Serait publié dans … », rien n'apparaît sur Ausha.
- [ ] Fichier sans règle : notification « Aucune règle » une seule fois, bouton « Créer une règle » pré-remplit le mot-clé ; une fois la règle enregistrée, le fichier part aussitôt.
- [ ] Trois fichiers sans règle déposés ensemble : une seule notification « Fichiers sans règle » (« 3 fichiers n'ont pas été envoyés : aucune règle ne correspond. »).
- [ ] Fichier avec règle : badge « Envoi xx % » pendant l'upload, puis notification « Épisode publié » ; sur Ausha l'épisode est publié, avec l'image et dans la playlist.
- [ ] Renommer le fichier publié : il n'est pas renvoyé.
- [ ] Couper le réseau pendant un envoi : Activité affiche « Envoi précédent en cours de vérification sur Ausha » ; le fichier est renvoyé une fois la fenêtre de vérification de 15 min écoulée, et un seul épisode existe sur Ausha.
- [ ] Quitter (menu de l'icône) pendant un envoi : l'app se ferme en 15 s au plus ; au redémarrage, le fichier est renvoyé après la fenêtre de vérification de 15 min, et un seul épisode existe sur Ausha.
- [ ] Fichier refusé ou en échec → « Réessayer » : relancé aussitôt, il reprend à l'étape interrompue (pas de second épisode sur Ausha).
- [ ] Jeton révoqué, avec un fichier en attente de publication (ou « Synchroniser » avec un fichier à publier) : icône rouge, notification « Jeton Ausha invalide », Activité affiche « synchro automatique suspendue (jeton invalide) », plus de cycle automatique jusqu'à un nouveau jeton.

## Icône et fenêtre
- [ ] Couleurs : vert (à jour), bleu (synchro), orange (à traiter), rouge (erreur), gris (pause).
- [ ] Clic gauche ouvre la fenêtre ; fermer la fenêtre ne quitte pas l'app.
- [ ] Menu : Synchroniser maintenant, Mettre en pause / Reprendre, Ouvrir le dossier, Quitter.
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
- [ ] Réglages → Langue, puis « Enregistrer » : la fenêtre change aussitôt de langue, sans redémarrage, et reste sur Réglages ; le menu et l'info-bulle de l'icône suivent.
- [ ] Après redémarrage, l'app reste dans la langue choisie dans Réglages, même si l'installateur a été relancé dans une autre langue.
- [ ] Les lignes déjà présentes dans Activité (erreurs, fichiers à traiter) s'affichent dans la nouvelle langue.
- [ ] Arabe : toute l'interface de droite à gauche (barre latérale à droite, textes alignés à droite, flèches des listes déroulantes du bon côté), aucun texte coupé, chiffres occidentaux.
- [ ] Boutons standard (Oui / Non de la confirmation de suppression d'une règle) dans la langue active.
- [ ] Notifications (« Épisode publié », « Aucune règle »…) dans la langue active, y compris juste après un changement de langue.
- [ ] La désinstallation supprime la clé `HKCU\Software\SyncAusha`.
