import string

import pytest

from syncausha import i18n
from syncausha.i18n import LANGUAGES, msg, render, resolve_language, tr
from syncausha.translations import CATALOG


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
    assert tr("t_hello", lang="ar", name="K") == "مرحبا K"


def test_tr_fallbacks(monkeypatch):
    assert tr("does_not_exist") == "does_not_exist"
    monkeypatch.setitem(CATALOG, "t_x", {"en": "Hi {name}", "fr": "Salut {name}", "ar": "أهلا {name}"})
    assert tr("t_x") == "Hi {name}"  # variable absente : texte brut, pas de plantage


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
    assert render(stored) == "Ep 1: ينقص 3"


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
