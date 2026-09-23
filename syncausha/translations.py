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
        "en": "Invalid Ausha token (characters not allowed).",
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
        "en": "Ausha asks to wait {seconds} s: retrying at the next sync.",
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
    "cycle_choose_folder": {
        "en": "Choose the folder to watch.",
        "fr": "Choisissez le dossier à surveiller.",
        "ar": "اختر المجلد المراد مراقبته.",
    },
    "cycle_folder_missing": {
        "en": "Folder not found: {folder}",
        "fr": "Dossier introuvable : {folder}",
        "ar": "المجلد غير موجود: {folder}",
    },
    "cycle_enter_token": {
        "en": "Enter your Ausha token.",
        "fr": "Renseignez votre jeton Ausha.",
        "ar": "أدخل رمز الوصول إلى Ausha.",
    },
    "cycle_existing_files_ignored": {
        "en": "Existing files ignored: {n}",
        "fr": "{n} fichier(s) déjà présent(s) ignoré(s)",
        "ar": "الملفات الموجودة مسبقًا المتجاهَلة: {n}",
    },
    "cycle_files_need_attention": {
        "en": "Files needing attention: {n}",
        "fr": "{n} fichier(s) à traiter",
        "ar": "الملفات التي تحتاج إلى معالجة: {n}",
    },
    "err_no_rule": {
        "en": "No rule matches this file",
        "fr": "Aucune règle ne correspond",
        "ar": "لا توجد قاعدة تطابق هذا الملف",
    },
    "err_upload_being_checked": {
        "en": "Previous upload being checked on Ausha",
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
        "en": "Already on Ausha — would not be published",
        "fr": "Déjà présent sur Ausha — ne serait pas publié",
        "ar": "الحلقة موجودة مسبقًا على Ausha — لن تُنشر",
    },
    "dry_would_publish": {
        "en": "Would be published to {show}",
        "fr": "Serait publié dans {show}",
        "ar": "ستُنشر في {show}",
    },
}
