"""Catalogue des textes de l'interface : clé → {"en", "fr", "ar"}.

Règles : voir docs/superpowers/plans/2026-09-23-syncausha-i18n.md (clés, glossaire, arabe).
"""

CATALOG: dict[str, dict[str, str]] = {
    # --- Validation des règles (rules.py) ---------------------------------------
    "rule_err_image_missing": {
        "en": "Cover image not found: {path}",
        "fr": "Image introuvable : {path}",
        "ar": "صورة الغلاف غير موجودة: {path}",
    },
    "rule_err_image_too_large": {
        "en": "Cover image too large (10 MB maximum)",
        "fr": "Image trop lourde (10 Mo maximum)",
        "ar": "حجم صورة الغلاف كبير جدًا (10 ميغابايت كحد أقصى)",
    },
    "rule_err_image_unreadable": {
        "en": "Unreadable cover image",
        "fr": "Image illisible",
        "ar": "تعذّرت قراءة صورة الغلاف",
    },
    "rule_err_image_format": {
        "en": "The cover image must be in JPEG or PNG format",
        "fr": "L'image doit être au format JPEG ou PNG",
        "ar": "يجب أن تكون صورة الغلاف بصيغة JPEG أو PNG",
    },
    "rule_err_image_too_small": {
        "en": "Cover image too small ({width}×{height}, minimum 400×400)",
        "fr": "Image trop petite ({width}×{height}, minimum 400×400)",
        "ar": "صورة الغلاف صغيرة جدًا ({width}×{height}، الحد الأدنى 400×400)",
    },
    "rule_err_show_missing": {
        "en": "Show not found on Ausha: {show}",
        "fr": "Émission introuvable sur Ausha : {show}",
        "ar": "البرنامج غير موجود على Ausha: {show}",
    },
    "rule_err_playlist_missing": {
        "en": "Playlist not found on Ausha: {playlist}",
        "fr": "Playlist introuvable sur Ausha : {playlist}",
        "ar": "قائمة التشغيل غير موجودة على Ausha: {playlist}",
    },
    # --- Erreurs de l'API Ausha (ausha_client.py) --------------------------------
    "err_token_invalid_chars": {
        "en": "Invalid Ausha token (it contains characters that aren't allowed).",
        "fr": "Jeton Ausha invalide (caractères non autorisés).",
        "ar": "رمز الوصول إلى Ausha غير صالح (أحرف غير مسموح بها).",
    },
    "err_missing_episode_id": {
        "en": "Unexpected response from Ausha: episode ID missing.",
        "fr": "Réponse inattendue d'Ausha : identifiant de l'épisode absent.",
        "ar": "استجابة غير متوقعة من Ausha: معرّف الحلقة مفقود.",
    },
    "err_upload_interrupted": {
        "en": "Upload interrupted.",
        "fr": "Envoi interrompu.",
        "ar": "تمت مقاطعة الإرسال.",
    },
    "err_rate_limited": {
        "en": "Ausha asked to wait {seconds} s; will retry at the next sync.",
        "fr": "Ausha demande de patienter {seconds} s : nouvel essai au prochain passage.",
        "ar": "يطلب Ausha الانتظار {seconds} ثانية: ستُعاد المحاولة في المزامنة التالية.",
    },
    "err_file_unreadable": {
        "en": "Unreadable file: {file} ({detail})",
        "fr": "Fichier illisible : {file} ({detail})",
        "ar": "تعذّرت قراءة الملف: {file} ({detail})",
    },
    "err_network": {
        "en": "Can't connect to Ausha: {detail}",
        "fr": "Connexion à Ausha impossible : {detail}",
        "ar": "تعذّر الاتصال بخدمة Ausha: {detail}",
    },
    "err_unexpected_response": {
        "en": "Unexpected response from Ausha (HTTP {status}).",
        "fr": "Réponse inattendue d'Ausha (HTTP {status}).",
        "ar": "استجابة غير متوقعة من Ausha (HTTP {status}).",
    },
    "err_redirect": {
        "en": "Ausha replied with a redirect (HTTP {status}): check the API address.",
        "fr": "Ausha a répondu par une redirection (HTTP {status}) : vérifiez l'adresse de l'API.",
        "ar": "ردّ Ausha بإعادة توجيه (HTTP {status}): تحقّق من عنوان API.",
    },
    "err_ausha": {
        "en": "{detail} (HTTP {status})",
        "fr": "{detail} (HTTP {status})",
        "ar": "{detail} (HTTP {status})",
    },
    "err_http_status": {
        "en": "Ausha returned HTTP {status}",
        "fr": "Ausha a répondu HTTP {status}",
        "ar": "ردّ Ausha بخطأ HTTP {status}",
    },
    # --- Moteur de synchronisation (sync_engine.py) ------------------------------
    "cycle_stop_requested": {
        "en": "Stop requested",
        "fr": "Arrêt demandé",
        "ar": "تم طلب الإيقاف",
    },
    "cycle_add_show": {
        "en": "Add a show and its folder in Shows.",
        "fr": "Ajoutez une émission et son dossier dans Émissions.",
        "ar": "أضف برنامجًا ومجلده في صفحة البرامج.",
    },
    "cycle_folder_missing_show": {
        "en": "Folder not found: {folder} ({show})",
        "fr": "Dossier introuvable : {folder} ({show})",
        "ar": "المجلد غير موجود: {folder} ({show})",
    },
    "cycle_enter_token": {
        "en": "Enter your Ausha token.",
        "fr": "Renseignez votre jeton Ausha.",
        "ar": "أدخل رمز الوصول إلى Ausha.",
    },
    "cycle_existing_files_ignored": {
        "en": "Existing files ignored: {n}",
        "fr": "Fichiers déjà présents ignorés : {n}",
        "ar": "الملفات الموجودة مسبقًا المتجاهَلة: {n}",
    },
    "cycle_files_need_attention": {
        "en": "Files needing attention: {n}",
        "fr": "Fichiers à traiter : {n}",
        "ar": "الملفات التي تحتاج إلى معالجة: {n}",
    },
    "err_no_rule": {
        "en": "No rule matches this file",
        "fr": "Aucune règle ne correspond",
        "ar": "لا توجد قاعدة تطابق هذا الملف",
    },
    "err_upload_being_checked": {
        "en": "Checking the previous upload on Ausha",
        "fr": "Envoi précédent en cours de vérification sur Ausha",
        "ar": "جارٍ التحقق من الإرسال السابق على Ausha",
    },
    "err_rule_show_changed": {
        "en": "The rule's show changed during publishing: check the episode on Ausha.",
        "fr": "La règle a changé d'émission pendant la publication : vérifiez l'épisode sur Ausha.",
        "ar": "تغيّر برنامج القاعدة أثناء النشر: تحقّق من الحلقة على Ausha.",
    },
    "err_unexpected": {
        "en": "Unexpected error: {detail}",
        "fr": "Erreur inattendue : {detail}",
        "ar": "خطأ غير متوقع: {detail}",
    },
    "err_partial_image": {
        "en": "Episode published, but the cover image couldn't be added: {detail}",
        "fr": "Épisode publié, mais l'image n'a pas pu être ajoutée : {detail}",
        "ar": "تم نشر الحلقة، لكن تعذّرت إضافة صورة الغلاف: {detail}",
    },
    "err_partial_playlist": {
        "en": "Episode published, but it couldn't be added to the playlist: {detail}",
        "fr": "Épisode publié, mais il n'a pas pu être ajouté à la playlist : {detail}",
        "ar": "تم نشر الحلقة، لكن تعذّرت إضافتها إلى قائمة التشغيل: {detail}",
    },
    "dry_already_on_ausha": {
        "en": "Already on Ausha, would not be published",
        "fr": "Déjà présent sur Ausha, ne serait pas publié",
        "ar": "موجودة مسبقًا على Ausha، لن تُنشر",
    },
    "dry_would_publish": {
        "en": "Would be published to {show}",
        "fr": "Serait publié dans {show}",
        "ar": "ستُنشر في {show}",
    },
    "dry_line": {
        "en": "{title} — {detail}",
        "fr": "{title} — {detail}",
        "ar": "{title} — {detail}",
    },
    # --- Interface : application, navigation, textes communs ---------------------
    "app_title": {
        "en": "SyncAusha",
        "fr": "SyncAusha",
        "ar": "SyncAusha",
    },
    "nav_activity": {
        "en": "Activity",
        "fr": "Activité",
        "ar": "النشاط",
    },
    "nav_shows": {
        "en": "Shows",
        "fr": "Émissions",
        "ar": "البرامج",
    },
    "nav_settings": {
        "en": "Settings",
        "fr": "Réglages",
        "ar": "الإعدادات",
    },
    "common_save": {
        "en": "Save",
        "fr": "Enregistrer",
        "ar": "حفظ",
    },
    "common_delete": {
        "en": "Delete",
        "fr": "Supprimer",
        "ar": "حذف",
    },
    "common_choose": {
        "en": "Choose…",
        "fr": "Choisir…",
        "ar": "اختيار…",
    },
    "common_retry": {
        "en": "Retry",
        "fr": "Réessayer",
        "ar": "إعادة المحاولة",
    },
    "common_list_separator": {
        "en": ", ",
        "fr": ", ",
        "ar": "، ",
    },
    # --- États (en-tête de l'Activité, info-bulle de l'icône) --------------------
    "state_ok": {
        "en": "Up to date",
        "fr": "À jour",
        "ar": "كل شيء محدَّث",
    },
    "state_syncing": {
        "en": "Syncing…",
        "fr": "Synchronisation…",
        "ar": "جارٍ المزامنة…",
    },
    "state_baseline": {
        "en": "Scanning the folder…",
        "fr": "Analyse du dossier…",
        "ar": "جارٍ فحص المجلد…",
    },
    "state_attention": {
        "en": "Some files need your attention",
        "fr": "Des fichiers demandent votre attention",
        "ar": "بعض الملفات تحتاج إلى انتباهك",
    },
    "state_paused": {
        "en": "Paused",
        "fr": "En pause",
        "ar": "المزامنة متوقفة مؤقتًا",
    },
    "state_not_configured": {
        "en": "Setup incomplete",
        "fr": "Configuration incomplète",
        "ar": "الإعداد غير مكتمل",
    },
    "state_auth_error": {
        "en": "Invalid Ausha token",
        "fr": "Jeton Ausha invalide",
        "ar": "رمز الوصول إلى Ausha غير صالح",
    },
    "state_offline": {
        "en": "Can't reach Ausha",
        "fr": "Ausha injoignable",
        "ar": "تعذّر الوصول إلى Ausha",
    },
    # --- Page Activité -----------------------------------------------------------
    "activity_sync": {
        "en": "Sync",
        "fr": "Synchroniser",
        "ar": "مزامنة",
    },
    "activity_section_attention": {
        "en": "Needs attention",
        "fr": "À traiter",
        "ar": "بحاجة إلى معالجة",
    },
    "activity_section_dry_run": {
        "en": "Dry run — nothing was published",
        "fr": "Essai à blanc — rien n'a été publié",
        "ar": "تشغيل تجريبي — لم يُنشر أي شيء",
    },
    "activity_section_recent": {
        "en": "Recent",
        "fr": "Récent",
        "ar": "الأحدث",
    },
    "activity_no_episodes": {
        "en": "No episodes published yet.",
        "fr": "Aucun épisode publié pour l'instant.",
        "ar": "لم تُنشر أي حلقة بعد.",
    },
    "activity_section_ignored": {
        "en": "Ignored — already there when the folder was chosen",
        "fr": "Ignorés — déjà présents au choix du dossier",
        "ar": "الملفات المتجاهَلة — كانت موجودة عند اختيار المجلد",
    },
    "activity_more_ignored": {
        "en": "… and {n} more",
        "fr": "… et {n} autres",
        "ar": "… وملفات أخرى: {n}",
    },
    "activity_shows_watched": {
        "en": "Shows watched: {n}",
        "fr": "Émissions surveillées : {n}",
        "ar": "البرامج المراقَبة: {n}",
    },
    "activity_sync_running": {
        "en": "sync in progress",
        "fr": "synchronisation en cours",
        "ar": "المزامنة جارية",
    },
    "activity_auto_sync_suspended": {
        "en": "automatic sync suspended (invalid token)",
        "fr": "synchro automatique suspendue (jeton invalide)",
        "ar": "المزامنة التلقائية معلّقة (رمز الوصول غير صالح)",
    },
    "activity_next_sync": {
        "en": "next sync in {minutes} min",
        "fr": "prochain passage dans {minutes} min",
        "ar": "المزامنة التالية خلال {minutes} د",
    },
    "activity_create_rule": {
        "en": "Create a rule",
        "fr": "Créer une règle",
        "ar": "إنشاء قاعدة",
    },
    "activity_edit_show": {
        "en": "Edit show",
        "fr": "Modifier l'émission",
        "ar": "تعديل البرنامج",
    },
    "activity_publish_anyway": {
        "en": "Publish anyway",
        "fr": "Publier quand même",
        "ar": "النشر رغم ذلك",
    },
    "activity_present_before": {
        "en": "Already there when the folder was chosen",
        "fr": "Présent avant le choix du dossier",
        "ar": "كان موجودًا قبل اختيار المجلد",
    },
    "activity_uploading": {
        "en": "Uploading {percent}%",
        "fr": "Envoi {percent} %",
        "ar": "جارٍ الإرسال {percent}%",
    },
    "activity_published": {
        "en": "Published",
        "fr": "Publié",
        "ar": "تم النشر",
    },
    "activity_already_on_ausha": {
        "en": "Already on Ausha",
        "fr": "Déjà sur Ausha",
        "ar": "موجودة مسبقًا على Ausha",
    },
    "activity_retry_next_sync": {
        "en": "Retrying at the next sync",
        "fr": "Nouvel essai au prochain passage",
        "ar": "إعادة المحاولة في المزامنة التالية",
    },
    "activity_waiting": {
        "en": "Waiting",
        "fr": "En attente",
        "ar": "في الانتظار",
    },
    # --- Page Émissions : émissions et leurs dossiers -----------------------------
    "shows_title": {
        "en": "Shows",
        "fr": "Émissions",
        "ar": "البرامج",
    },
    "shows_add": {
        "en": "Add a show",
        "fr": "Ajouter une émission",
        "ar": "إضافة برنامج",
    },
    "shows_help": {
        "en": "Each show has its own folder. Inside it, a file is published only if its name contains one of "
        "the show's keywords.",
        "fr": "Chaque émission a son propre dossier. Un fichier de ce dossier n'est publié que si son nom contient "
        "un des mots-clés de l'émission.",
        "ar": "لكل برنامج مجلده الخاص. لا يُنشر ملف من هذا المجلد إلا إذا احتوى اسمه على إحدى الكلمات المفتاحية "
        "للبرنامج.",
    },
    "shows_field_show": {
        "en": "Ausha show",
        "fr": "Émission Ausha",
        "ar": "برنامج Ausha",
    },
    "shows_show_placeholder": {
        "en": "Choose a show",
        "fr": "Choisissez une émission",
        "ar": "اختر برنامجًا",
    },
    "shows_fallback_name": {
        "en": "Show {id}",
        "fr": "Émission {id}",
        "ar": "البرنامج {id}",
    },
    "shows_field_folder": {
        "en": "Folder",
        "fr": "Dossier",
        "ar": "المجلد",
    },
    "shows_no_folder": {
        "en": "No folder chosen",
        "fr": "Aucun dossier choisi",
        "ar": "لم يُختر أي مجلد",
    },
    "shows_keyword_count": {
        "en": "Keywords: {n}",
        "fr": "Mots-clés : {n}",
        "ar": "الكلمات المفتاحية: {n}",
    },
    "shows_delete": {
        "en": "Delete show",
        "fr": "Supprimer l'émission",
        "ar": "حذف البرنامج",
    },
    "shows_err_folder": {
        "en": "Choose a folder.",
        "fr": "Choisissez un dossier.",
        "ar": "اختر مجلدًا.",
    },
    "shows_not_saved": {
        "en": "Show not saved.",
        "fr": "Émission non enregistrée.",
        "ar": "لم يُحفظ البرنامج.",
    },
    "shows_keyword_not_saved": {
        "en": "Keyword not saved.",
        "fr": "Mot-clé non enregistré.",
        "ar": "لم تُحفظ الكلمة المفتاحية.",
    },
    "shows_keywords": {
        "en": "Keywords",
        "fr": "Mots-clés",
        "ar": "الكلمات المفتاحية",
    },
    "shows_add_keyword": {
        "en": "Add a keyword",
        "fr": "Ajouter un mot-clé",
        "ar": "إضافة كلمة مفتاحية",
    },
    "shows_save_show_first": {
        "en": "Save the show to add its keywords.",
        "fr": "Enregistrez l'émission pour ajouter ses mots-clés.",
        "ar": "احفظ البرنامج لإضافة كلماته المفتاحية.",
    },
    # --- Page Émissions : mots-clés (règles) d'une émission -----------------------
    "rules_keyword_placeholder": {
        "en": "MARS ATTACK",
        "fr": "MARS ATTACK",
        "ar": "MARS ATTACK",
    },
    "rules_field_keyword": {
        "en": "File name contains",
        "fr": "Le nom du fichier contient",
        "ar": "اسم الملف يحتوي على",
    },
    "rules_field_playlist": {
        "en": "Playlist",
        "fr": "Playlist",
        "ar": "قائمة التشغيل",
    },
    "rules_field_description": {
        "en": "Description",
        "fr": "Description",
        "ar": "الوصف",
    },
    "rules_description_placeholder": {
        "en": "New episode of Mars Attack. Find us on…",
        "fr": "Nouvel épisode de Mars Attack. Retrouvez-nous sur…",
        "ar": "حلقة جديدة من Mars Attack. تابعونا على…",
    },
    "rules_image": {
        "en": "Cover image",
        "fr": "Image",
        "ar": "صورة الغلاف",
    },
    "rules_no_image": {
        "en": "No image",
        "fr": "Aucune image",
        "ar": "لا توجد صورة",
    },
    "rules_remove_image": {
        "en": "Remove",
        "fr": "Retirer",
        "ar": "إزالة",
    },
    "rules_image_filter": {
        "en": "Images (*.png *.jpg *.jpeg)",
        "fr": "Images (*.png *.jpg *.jpeg)",
        "ar": "الصور (*.png *.jpg *.jpeg)",
    },
    "rules_loading_shows": {
        "en": "Loading Ausha shows…",
        "fr": "Chargement des émissions Ausha…",
        "ar": "جارٍ تحميل برامج Ausha…",
    },
    "rules_shows_failed": {
        "en": "Can't load Ausha shows: {detail}",
        "fr": "Impossible de charger les émissions Ausha : {detail}",
        "ar": "تعذّر تحميل برامج Ausha: {detail}",
    },
    "rules_playlist_fallback": {
        "en": "Playlist {id}",
        "fr": "Playlist {id}",
        "ar": "قائمة التشغيل {id}",
    },
    "rules_no_playlist": {
        "en": "No playlist",
        "fr": "Aucune playlist",
        "ar": "بدون قائمة تشغيل",
    },
    "rules_err_keyword": {
        "en": "Enter a keyword.",
        "fr": "Indiquez un mot-clé.",
        "ar": "أدخل كلمة مفتاحية.",
    },
    "rules_err_show": {
        "en": "Choose a show.",
        "fr": "Choisissez une émission.",
        "ar": "اختر برنامجًا.",
    },
    "rules_err_image": {
        "en": "Fix the cover image before saving.",
        "fr": "Corrigez l'image avant d'enregistrer.",
        "ar": "صحّح صورة الغلاف قبل الحفظ.",
    },
    # --- Page Réglages -----------------------------------------------------------
    "settings_title": {
        "en": "Settings",
        "fr": "Réglages",
        "ar": "الإعدادات",
    },
    "settings_language": {
        "en": "Language",
        "fr": "Langue",
        "ar": "اللغة",
    },
    "settings_field_token": {
        "en": "Ausha token",
        "fr": "Jeton Ausha",
        "ar": "رمز الوصول إلى Ausha",
    },
    "settings_test_connection": {
        "en": "Test connection",
        "fr": "Tester la connexion",
        "ar": "اختبار الاتصال",
    },
    "settings_token_hint": {
        "en": "Create your token in Ausha: My account → Public API.",
        "fr": "Le jeton se crée dans Ausha : Mon compte → API publique.",
        "ar": "أنشئ رمز الوصول في Ausha: حسابي ← واجهة API العامة.",
    },
    "settings_token_saved_placeholder": {
        "en": "Token saved — leave blank to keep it",
        "fr": "Jeton enregistré — laissez vide pour le conserver",
        "ar": "رمز الوصول محفوظ — اتركه فارغًا للإبقاء عليه",
    },
    "settings_token_placeholder": {
        "en": "Paste your personal Ausha token",
        "fr": "Collez votre jeton personnel Ausha",
        "ar": "الصق رمز الوصول الشخصي إلى Ausha",
    },
    "settings_connecting": {
        "en": "Connecting to Ausha…",
        "fr": "Connexion à Ausha…",
        "ar": "جارٍ الاتصال بخدمة Ausha…",
    },
    "settings_connection_ok": {
        "en": "Connection successful. Shows: {shows}",
        "fr": "Connexion réussie. Émissions : {shows}",
        "ar": "تم الاتصال بنجاح. البرامج: {shows}",
    },
    "settings_no_shows": {
        "en": "no shows",
        "fr": "aucune émission",
        "ar": "لا توجد برامج",
    },
    "settings_test_failed": {
        "en": "Connection failed: {detail}",
        "fr": "Échec de la connexion : {detail}",
        "ar": "فشل الاتصال: {detail}",
    },
    "settings_field_interval": {
        "en": "Check every",
        "fr": "Vérifier toutes les",
        "ar": "التحقق كل",
    },
    "settings_interval_suffix": {
        "en": " min",
        "fr": " min",
        "ar": " دقيقة",
    },
    "settings_autostart": {
        "en": "Start with Windows",
        "fr": "Lancer au démarrage de Windows",
        "ar": "التشغيل مع بدء Windows",
    },
    "settings_pause": {
        "en": "Pause sync",
        "fr": "Mettre la synchronisation en pause",
        "ar": "إيقاف المزامنة مؤقتًا",
    },
    "settings_dry_run": {
        "en": "Dry run: publish nothing, show what would be uploaded",
        "fr": "Essai à blanc : ne publie rien, montre ce qui serait envoyé",
        "ar": "تشغيل تجريبي: لا يُنشر أي شيء، ويُعرض ما كان سيُرسَل",
    },
    "settings_open_logs": {
        "en": "Open the logs folder",
        "fr": "Ouvrir le dossier des logs",
        "ar": "فتح مجلد السجلات",
    },
    "settings_saved": {
        "en": "Settings saved",
        "fr": "Réglages enregistrés",
        "ar": "تم حفظ الإعدادات",
    },
    "settings_not_saved": {
        "en": "Settings not saved",
        "fr": "Réglages non enregistrés",
        "ar": "لم تُحفظ الإعدادات",
    },
    "settings_token_not_saved": {
        "en": "Token not saved: {detail}",
        "fr": "Jeton non enregistré : {detail}",
        "ar": "لم يُحفظ رمز الوصول: {detail}",
    },
    "settings_autostart_failed": {
        "en": "Couldn't change “Start with Windows”: {detail}",
        "fr": "Démarrage automatique non modifié : {detail}",
        "ar": "لم يُعدَّل خيار التشغيل مع بدء Windows: {detail}",
    },
    # --- Boîtes de dialogue ------------------------------------------------------
    "dialog_choose_show_folder": {
        "en": "Show folder",
        "fr": "Dossier de l'émission",
        "ar": "مجلد البرنامج",
    },
    "dialog_change_show": {
        "en": "Change show",
        "fr": "Changer d'émission",
        "ar": "تغيير البرنامج",
    },
    "dialog_change_show_question": {
        "en": "Playlists belong to a show: changing the show removes the playlist from its keywords "
        "(keywords with a playlist: {n}). Continue?",
        "fr": "Les playlists appartiennent à une émission : changer d'émission retire la playlist de ses mots-clés "
        "(mots-clés avec une playlist : {n}). Continuer ?",
        "ar": "قوائم التشغيل تابعة للبرنامج: تغيير البرنامج يزيل قائمة التشغيل من كلماته المفتاحية "
        "(الكلمات المفتاحية التي لها قائمة تشغيل: {n}). هل تريد المتابعة؟",
    },
    "dialog_delete_show": {
        "en": "Delete show",
        "fr": "Supprimer l'émission",
        "ar": "حذف البرنامج",
    },
    "dialog_delete_show_question": {
        "en": "Delete the show “{show}” and its keywords? Nothing is deleted from its folder or from Ausha.",
        "fr": "Supprimer l'émission « {show} » et ses mots-clés ? Rien n'est supprimé dans son dossier ni sur Ausha.",
        "ar": "هل تريد حذف البرنامج «{show}» وكلماته المفتاحية؟ لن يُحذف أي شيء من مجلده ولا من Ausha.",
    },
    "dialog_delete_keyword": {
        "en": "Delete keyword",
        "fr": "Supprimer le mot-clé",
        "ar": "حذف الكلمة المفتاحية",
    },
    "dialog_delete_keyword_question": {
        "en": "Delete the keyword “{keyword}”?",
        "fr": "Supprimer le mot-clé « {keyword} » ?",
        "ar": "هل تريد حذف الكلمة المفتاحية «{keyword}»؟",
    },
    "dialog_choose_image": {
        "en": "Choose a cover image",
        "fr": "Choisir l'image",
        "ar": "اختيار صورة الغلاف",
    },
    # --- Icône de la zone de notification ----------------------------------------
    "tray_tooltip": {
        "en": "SyncAusha — {state}",
        "fr": "SyncAusha — {state}",
        "ar": "SyncAusha — {state}",
    },
    "tray_sync_now": {
        "en": "Sync now",
        "fr": "Synchroniser maintenant",
        "ar": "المزامنة الآن",
    },
    "tray_pause": {
        "en": "Pause sync",
        "fr": "Mettre en pause",
        "ar": "إيقاف المزامنة مؤقتًا",
    },
    "tray_resume": {
        "en": "Resume sync",
        "fr": "Reprendre la synchronisation",
        "ar": "استئناف المزامنة",
    },
    "tray_open_folders": {
        "en": "Open folder",
        "fr": "Ouvrir le dossier",
        "ar": "فتح المجلد",
    },
    "tray_open_show_folder": {
        "en": "{show} — {folder}",
        "fr": "{show} — {folder}",
        "ar": "{show} — {folder}",
    },
    "tray_quit": {
        "en": "Quit",
        "fr": "Quitter",
        "ar": "خروج",
    },
    # --- Notifications Windows ---------------------------------------------------
    "notif_published": {
        "en": "Episode published",
        "fr": "Épisode publié",
        "ar": "تم نشر الحلقة",
    },
    "notif_published_body": {
        "en": "{title} · {detail}",
        "fr": "{title} · {detail}",
        "ar": "{title} · {detail}",
    },
    "notif_no_rule": {
        "en": "No matching rule",
        "fr": "Aucune règle",
        "ar": "لا توجد قاعدة",
    },
    "notif_no_rule_body": {
        "en": "{title} wasn't uploaded: no rule matches.",
        "fr": "{title} n'a pas été envoyé : aucune règle ne correspond.",
        "ar": "لم يُرسَل {title}: لا توجد قاعدة مطابقة.",
    },
    "notif_no_rule_grouped": {
        "en": "Files without a rule",
        "fr": "Fichiers sans règle",
        "ar": "ملفات بلا قاعدة",
    },
    "notif_no_rule_grouped_body": {
        "en": "{count} files weren't uploaded: no rule matches.",
        "fr": "{count} fichiers n'ont pas été envoyés : aucune règle ne correspond.",
        "ar": "ملفات لم تُرسَل لعدم وجود قاعدة مطابقة: {count}",
    },
    "notif_broken_rule": {
        "en": "Rule needs fixing",
        "fr": "Règle à corriger",
        "ar": "قاعدة تحتاج إلى تصحيح",
    },
    "notif_rejected": {
        "en": "Rejected by Ausha",
        "fr": "Refusé par Ausha",
        "ar": "رفض Ausha الملف",
    },
    "notif_partial": {
        "en": "Published with an issue",
        "fr": "Publié avec un problème",
        "ar": "تم النشر مع وجود مشكلة",
    },
    "notif_failed": {
        "en": "Upload failed",
        "fr": "Échec de l'envoi",
        "ar": "فشل الإرسال",
    },
    "notif_file_detail": {
        "en": "{title}: {detail}",
        "fr": "{title} : {detail}",
        "ar": "{title}: {detail}",
    },
    "notif_baseline": {
        "en": "Folder ready",
        "fr": "Dossier pris en compte",
        "ar": "تم اعتماد المجلد",
    },
    "notif_baseline_body": {
        "en": "Existing files ignored: {count}. Only new files will be published.",
        "fr": "Fichiers déjà présents ignorés : {count}. Seuls les nouveaux fichiers seront publiés.",
        "ar": "الملفات الموجودة مسبقًا المتجاهَلة: {count}. لن تُنشر إلا الملفات الجديدة.",
    },
    "notif_auth_error": {
        "en": "Invalid Ausha token",
        "fr": "Jeton Ausha invalide",
        "ar": "رمز الوصول إلى Ausha غير صالح",
    },
    "notif_auth_error_body": {
        "en": "Update your token in Settings.",
        "fr": "Mettez à jour votre jeton dans les réglages.",
        "ar": "حدِّث رمز الوصول في الإعدادات.",
    },
    "notif_folder_missing": {
        "en": "Folder not found",
        "fr": "Dossier introuvable",
        "ar": "المجلد غير موجود",
    },
    # --- Erreurs propres à l'interface -------------------------------------------
    "err_no_token": {
        "en": "No Ausha token saved.",
        "fr": "Aucun jeton Ausha enregistré.",
        "ar": "لم يُحفظ أي رمز وصول إلى Ausha.",
    },
}
