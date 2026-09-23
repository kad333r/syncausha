# Vérification manuelle de SyncAusha

À dérouler avant chaque diffusion de `SyncAusha-Setup.exe`.

## Installation
- [ ] L'installateur est en français, propose « Lancer au démarrage » (cochée) et « Raccourci bureau » (décochée).
- [ ] Aucune demande de droits administrateur.
- [ ] L'app se lance en fin d'installation, fenêtre sur Réglages.

## Réglages
- [ ] Mauvais jeton + « Tester la connexion » → « Échec : … (HTTP 401) ».
- [ ] Bon jeton → « Connexion réussie. Émissions : … ».
- [ ] « Enregistrer » affiche « Réglages enregistrés » ; le jeton n'apparaît pas dans `config.json`.
- [ ] Décocher « Lancer au démarrage » supprime la valeur `SyncAusha` de HKCU\...\Run ; la recocher la recrée.
- [ ] Un `config.json` corrompu est renommé en `config.json.illisible` et l'app démarre avec des réglages vides (pas de plantage).

## Règles
- [ ] Les listes Émission / Playlist se remplissent depuis Ausha.
- [ ] Une image < 400×400 affiche « Image trop petite » et bloque l'enregistrement.
- [ ] Glisser une règle change l'ordre, conservé après redémarrage.
- [ ] Supprimer demande confirmation.

## Synchro (sur une émission de test)
- [ ] Essai à blanc : Activité liste « … — Serait publié dans … », rien n'apparaît sur Ausha.
- [ ] Fichier sans règle : notification « Aucune règle » une seule fois, bouton « Créer une règle » pré-remplit le mot-clé.
- [ ] Fichier avec règle : badge « Envoi xx % » pendant l'upload, puis notification « Épisode publié » ; sur Ausha l'épisode est publié, avec l'image et dans la playlist.
- [ ] Renommer le fichier publié : il n'est pas renvoyé.
- [ ] Couper le réseau pendant un envoi : l'épisode reprend au cycle suivant sans doublon sur Ausha.
- [ ] Jeton révoqué : icône rouge, notification « Jeton Ausha invalide », plus de cycle automatique jusqu'à un nouveau jeton.

## Icône et fenêtre
- [ ] Couleurs : vert (à jour), bleu (synchro), orange (à traiter), rouge (erreur), gris (pause).
- [ ] Clic gauche ouvre la fenêtre ; fermer la fenêtre ne quitte pas l'app.
- [ ] Menu : Synchroniser maintenant, Mettre en pause / Reprendre, Ouvrir le dossier, Quitter.
- [ ] Thème sombre de Windows → fenêtre en thème sombre.
- [ ] Redémarrage du PC : l'app démarre réduite dans la zone de notification.

## Désinstallation
- [ ] Depuis Paramètres → Applications : la question sur les réglages s'affiche ; « Non » conserve `%APPDATA%\SyncAusha`.
- [ ] La valeur `SyncAusha` de HKCU\...\Run a disparu.
