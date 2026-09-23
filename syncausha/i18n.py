"""Langues de l'interface : langue active, traduction des textes et des messages stockés."""
from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable

from syncausha.translations import CATALOG

log = logging.getLogger(__name__)

LANGUAGES = {"en": "English", "fr": "Français", "ar": "العربية"}
DEFAULT_LANGUAGE = "en"
RTL_LANGUAGES = frozenset({"ar"})
REGISTRY_KEY = r"Software\SyncAusha"
_MESSAGE_PREFIX = '{"k":'

_current = DEFAULT_LANGUAGE


def set_language(code: str) -> None:
    global _current
    if code not in LANGUAGES:
        raise ValueError(f"Langue inconnue : {code}")
    _current = code


def current_language() -> str:
    return _current


def is_rtl(code: str | None = None) -> bool:
    return (code or _current) in RTL_LANGUAGES


def tr(key: str, *, lang: str | None = None, **params: object) -> str:
    """Texte de `key` dans la langue voulue (défaut : active ; repli : anglais, puis la clé)."""
    entry = CATALOG.get(key)
    if entry is None:
        log.warning("Clé de traduction inconnue : %s", key)
        return key
    text = entry.get(lang or _current) or entry.get(DEFAULT_LANGUAGE) or key
    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        log.warning("Variables invalides pour %s : %s", key, sorted(params))
        return text


def msg(key: str, **params: object) -> str:
    """Message traduisible à stocker (journal) ou à transporter (exceptions, événements)."""
    payload = {"k": key, "p": {name: str(value) for name, value in params.items()}}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def render(text: str, *, lang: str | None = None) -> str:
    """Traduit un message produit par `msg` ; tout autre texte est renvoyé tel quel."""
    if not text or not text.startswith(_MESSAGE_PREFIX):
        return text or ""
    try:
        data = json.loads(text)
        key, params = data["k"], data.get("p") or {}
    except (ValueError, KeyError, TypeError):
        return text
    if not isinstance(key, str) or not isinstance(params, dict):
        return text
    return tr(key, lang=lang, **{name: render(str(value), lang=lang) for name, value in params.items()})


def read_installer_language(key_path: str = REGISTRY_KEY) -> str | None:
    """Langue choisie dans l'installateur (HKCU\\<key_path>, valeur Language)."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, "Language")
    except OSError:
        return None
    return value if isinstance(value, str) else None


def resolve_language(
    config_language: str,
    registry_reader: Callable[[], str | None] = read_installer_language,
) -> str:
    """Réglages, puis installateur, puis anglais."""
    for candidate in (config_language, registry_reader()):
        if candidate in LANGUAGES:
            return candidate
    return DEFAULT_LANGUAGE
