"""Langues de l'interface : langue active, traduction des textes et des messages stockés."""
from __future__ import annotations

import json
import logging
import re
import sys
import unicodedata
from collections.abc import Callable

from syncausha.translations import CATALOG

log = logging.getLogger(__name__)

LANGUAGES = {"en": "English", "fr": "Français", "ar": "العربية"}
DEFAULT_LANGUAGE = "en"
RTL_LANGUAGES = frozenset({"ar"})
REGISTRY_KEY = r"Software\SyncAusha"
FSI, PDI = "\u2068", "\u2069"  # début d'isolat (sens deviné sur son contenu), fin d'isolat
_MESSAGE_PREFIX = '{"k":'
# Classes bidi d'une valeur à ne pas isoler : lettres de droite à gauche (arabe), isolat déjà posé.
_SKIP_ISOLATION = frozenset({"R", "AL", "LRI", "RLI", "FSI"})
_NUMBER = re.compile(r"[+-]?\d+(?:[.,]\d+)*")

_current = DEFAULT_LANGUAGE
_unknown_keys: set[str] = set()  # clés inconnues déjà signalées dans le log


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
    """Texte de `key` dans la langue voulue (défaut : active ; repli : anglais, puis la clé).

    En arabe, chaque valeur insérée est isolée (voir `_isolated`)."""
    return _translate(key, lang or _current, params, nested=frozenset())


def _translate(key: str, lang: str, params: dict[str, object], nested: frozenset[str]) -> str:
    """`nested` : variables qui sont déjà des messages traduits (render), à ne pas isoler une seconde fois."""
    entry = CATALOG.get(key)
    if entry is None:
        if key not in _unknown_keys:  # une fois par clé : render() peut la rencontrer à chaque rafraîchissement
            _unknown_keys.add(key)
            log.warning("Clé de traduction inconnue : %s", key)
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    if not params:
        return text
    if is_rtl(lang):
        params = {name: value if name in nested else _isolated(str(value)) for name, value in params.items()}
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        log.warning("Variables invalides pour %s : %s", key, sorted(params))
        return text


def _isolated(value: str) -> str:
    """Valeur (titre, nom d'émission, chemin, message d'Ausha) insérée dans une phrase de droite à gauche.

    Entre FSI et PDI, elle garde son propre sens : « 2024 Show » ne devient pas « Show 2024 ». Restent telles
    quelles une valeur vide, déjà en arabe, déjà isolée, ou un simple nombre (sans lettre, il suit la phrase ;
    isolé, il se détacherait du mot latin qui le précède : « HTTP 404 » affiché « 404 HTTP »)."""
    kinds = {unicodedata.bidirectional(char) for char in value}
    if not kinds or kinds & _SKIP_ISOLATION or _NUMBER.fullmatch(value):
        return value
    return f"{FSI}{value}{PDI}"


def msg(key: str, **params: object) -> str:
    """Message traduisible à stocker (journal) ou à transporter (exceptions, événements)."""
    payload = {"k": key, "p": {name: str(value) for name, value in params.items()}}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def render(text: str, *, lang: str | None = None) -> str:
    """Traduit un message produit par `msg` ; tout autre texte est renvoyé tel quel."""
    return _render(text, lang or _current)[0]


def _render(text: str, lang: str) -> tuple[str, bool]:
    """(texte, vrai si c'était un message produit par `msg`)."""
    if not text or not text.startswith(_MESSAGE_PREFIX):
        return text or "", False
    try:
        data = json.loads(text)
        key, params = data["k"], data.get("p") or {}
    except (ValueError, KeyError, TypeError):
        return text, False
    if not isinstance(key, str) or not isinstance(params, dict):
        return text, False
    values, nested = {}, set()
    for name, value in params.items():
        values[name], is_message = _render(str(value), lang)
        if is_message:
            nested.add(name)
    return _translate(key, lang, values, frozenset(nested)), True


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
    registry_reader: Callable[[], str | None] | None = None,
) -> str:
    """Réglages, puis installateur, puis anglais. Le registre n'est lu que si les réglages n'ont pas de langue."""
    if config_language in LANGUAGES:
        return config_language
    installer_language = (registry_reader or read_installer_language)()  # résolu à l'appel : remplaçable en test
    return installer_language if installer_language in LANGUAGES else DEFAULT_LANGUAGE
