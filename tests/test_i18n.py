import string

import pytest

from syncausha import i18n
from syncausha.i18n import LANGUAGES, msg, render, resolve_language, tr
from syncausha.translations import CATALOG

FSI, PDI = "\u2068", "\u2069"  # début et fin d'isolat (valeur insérée dans une phrase arabe)


@pytest.fixture(autouse=True)
def reset_language():
    yield
    i18n.set_language("en")


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_catalog_is_complete_and_consistent():
    for key, entry in CATALOG.items():
        assert set(entry) == set(LANGUAGES), key
        for lang, text in entry.items():
            assert text.strip(), (key, lang)
        assert placeholders(entry["fr"]) == placeholders(entry["en"]) == placeholders(entry["ar"]), key


def test_default_language_is_english():
    assert i18n.DEFAULT_LANGUAGE == "en"
    assert i18n.current_language() == "en"


def test_tr_uses_current_language_and_params(monkeypatch):
    monkeypatch.setitem(CATALOG, "t_hello", {"en": "Hello {name}", "fr": "Bonjour {name}", "ar": "مرحبا {name}"})
    assert tr("t_hello", name="Kader") == "Hello Kader"
    i18n.set_language("fr")
    assert tr("t_hello", name="Kader") == "Bonjour Kader"
    assert tr("t_hello", lang="ar", name="K") == f"مرحبا {FSI}K{PDI}"


def test_tr_fallbacks(monkeypatch):
    assert tr("does_not_exist") == "does_not_exist"
    monkeypatch.setitem(CATALOG, "t_x", {"en": "Hi {name}", "fr": "Salut {name}", "ar": "أهلا {name}"})
    assert tr("t_x") == "Hi {name}"  # variable absente : texte brut, pas de plantage


def test_unknown_key_is_logged_once(monkeypatch, caplog):
    monkeypatch.setattr(i18n, "_unknown_keys", set())
    with caplog.at_level("WARNING", logger="syncausha.i18n"):
        assert tr("does_not_exist") == "does_not_exist"
        assert tr("does_not_exist") == "does_not_exist"
        assert render(msg("does_not_exist")) == "does_not_exist"
        tr("also_missing")
    warnings = [record.getMessage() for record in caplog.records]
    assert len(warnings) == 2
    assert "does_not_exist" in warnings[0] and "also_missing" in warnings[1]


def test_arabic_isolates_inserted_values():
    """En arabe, une valeur latine (titre, nom d'émission, chemin, message d'Ausha) garde son ordre de lecture,
    même quand elle commence par des chiffres ; le français et l'anglais ne changent pas."""
    sentence = tr("dry_would_publish", lang="ar", show="2024 Show")
    assert f"{FSI}2024 Show{PDI}" in sentence
    assert sentence == f"ستُنشر في {FSI}2024 Show{PDI}"
    assert tr("dry_would_publish", lang="en", show="2024 Show") == "Would be published to 2024 Show"
    assert tr("dry_would_publish", lang="fr", show="2024 Show") == "Serait publié dans 2024 Show"
    i18n.set_language("ar")
    assert tr("rule_err_show_missing", show="Mars") == f"البرنامج غير موجود على Ausha: {FSI}Mars{PDI}"


def test_arabic_leaves_arabic_empty_numeric_and_isolated_values_alone():
    """Valeur déjà arabe, vide ou déjà isolée : telle quelle. Un simple nombre non plus : isolé, il se
    détacherait du mot latin qui le précède (« HTTP 404 » affiché « 404 HTTP »)."""
    assert tr("dry_would_publish", lang="ar", show="برنامج الصباح") == "ستُنشر في برنامج الصباح"
    assert tr("dry_would_publish", lang="ar", show="") == "ستُنشر في "
    assert tr("err_http_status", lang="ar", status=404) == "ردّ Ausha بخطأ HTTP 404"
    assert tr("activity_uploading", lang="ar", percent=64) == "جارٍ الإرسال 64%"
    already = f"{FSI}Mars Attack{PDI}"
    assert tr("dry_would_publish", lang="ar", show=already) == f"ستُنشر في {already}"


def test_nested_messages_are_isolated_once_in_arabic():
    stored = msg("dry_line", title="LE DEBRIEF 45", detail=msg("dry_would_publish", show="Silicon Talk"))
    assert render(stored, lang="ar") == f"{FSI}LE DEBRIEF 45{PDI} — ستُنشر في {FSI}Silicon Talk{PDI}"
    # Message imbriqué sans lettre arabe (détail d'Ausha) : ses valeurs sont isolées, lui ne l'est pas en plus.
    stored = msg("notif_file_detail", title="Ep 1", detail=msg("err_ausha", detail="Too big", status=422))
    assert render(stored, lang="ar") == f"{FSI}Ep 1{PDI}: {FSI}Too big{PDI} (HTTP 422)"
    # Journal (français) et anglais : aucune marque de sens.
    assert render(stored, lang="fr") == "Ep 1 : Too big (HTTP 422)"
    assert render(stored, lang="en") == "Ep 1: Too big (HTTP 422)"


def test_set_language_rejects_unknown():
    with pytest.raises(ValueError):
        i18n.set_language("de")


def test_is_rtl():
    i18n.set_language("ar")
    assert i18n.is_rtl()
    assert not i18n.is_rtl("fr")


def test_msg_roundtrip_and_nested(monkeypatch):
    monkeypatch.setitem(CATALOG, "t_outer", {"en": "{title}: {detail}", "fr": "{title} : {detail}", "ar": "{title}: {detail}"})
    monkeypatch.setitem(CATALOG, "t_inner", {"en": "missing {n}", "fr": "manque {n}", "ar": "ينقص {n}"})
    stored = msg("t_outer", title="Ep 1", detail=msg("t_inner", n=3))
    assert render(stored) == "Ep 1: missing 3"
    assert render(stored, lang="fr") == "Ep 1 : manque 3"
    i18n.set_language("ar")
    assert render(stored) == f"{FSI}Ep 1{PDI}: ينقص 3"


def test_render_plain_text_and_garbage():
    assert render("") == ""
    assert render("File too large (HTTP 422)") == "File too large (HTTP 422)"
    assert render('{"k": broken') == '{"k": broken'
    assert render(msg("unknown_key_xyz")) == "unknown_key_xyz"


def test_resolve_language_priority():
    assert resolve_language("fr", lambda: "ar") == "fr"
    assert resolve_language("", lambda: "ar") == "ar"
    assert resolve_language("", lambda: None) == "en"
    assert resolve_language("de", lambda: "xx") == "en"


def test_resolve_language_reads_the_installer_choice_when_called(monkeypatch):
    monkeypatch.setattr(i18n, "read_installer_language", lambda: "ar")
    assert resolve_language("") == "ar"
    assert resolve_language("fr") == "fr"
    monkeypatch.setattr(i18n, "read_installer_language", lambda: None)
    assert resolve_language("") == "en"


def test_read_installer_language_from_registry():
    winreg = pytest.importorskip("winreg")
    path = r"Software\SyncAushaTest"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, "Language", 0, winreg.REG_SZ, "ar")
        assert i18n.read_installer_language(path) == "ar"
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    assert i18n.read_installer_language(path) is None
