"""Correspondance fichier → règle, titre/description d'épisode, validation des règles."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from syncausha.config import Rule
from syncausha.i18n import msg

MAX_TITLE_LENGTH = 140
MAX_DESCRIPTION_LENGTH = 3900
MIN_IMAGE_SIDE = 400
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_LIGATURES = {"œ": "oe", "æ": "ae"}
_NON_ALNUM = re.compile(r"[\W_]+")


def normalize(text: str) -> str:
    """Minuscules, sans accents, ligatures développées, séparateurs → espaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    folded = stripped.casefold()
    for ligature, expansion in _LIGATURES.items():
        folded = folded.replace(ligature, expansion)
    return _NON_ALNUM.sub(" ", folded).strip()


def find_rule(filename: str, rules: list[Rule]) -> Rule | None:
    """Première règle dont le mot-clé apparaît dans le nom du fichier (sans extension)."""
    name = normalize(Path(filename).stem)
    for rule in rules:
        keyword = normalize(rule.keyword)
        if keyword and keyword in name:
            return rule
    return None


def episode_title(path: Path) -> str:
    return " ".join(path.stem.split())[:MAX_TITLE_LENGTH].rstrip()


def episode_description(rule: Rule) -> str:
    return rule.description_template.strip()[:MAX_DESCRIPTION_LENGTH]


def validate_image(path: str | Path) -> str | None:
    """Renvoie un message d'erreur (traduisible, voir i18n.msg) si l'image ne convient pas à Ausha, sinon None."""
    image_path = Path(path)
    if not image_path.is_file():
        return msg("rule_err_image_missing", path=image_path)
    if image_path.stat().st_size > MAX_IMAGE_BYTES:
        return msg("rule_err_image_too_large")
    try:
        with Image.open(image_path) as image:
            fmt, (width, height) = image.format, image.size
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return msg("rule_err_image_unreadable")
    if fmt not in ("JPEG", "PNG", "MPO"):
        return msg("rule_err_image_format")
    if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
        return msg("rule_err_image_too_small", width=width, height=height)
    return None


def validate_rule(rule: Rule, playlists_by_show: dict[int, set[int]]) -> str | None:
    """Vérifie que l'émission, la playlist et l'image de la règle sont utilisables."""
    if rule.show_id not in playlists_by_show:
        return msg("rule_err_show_missing", show=rule.show_name or rule.show_id)
    if rule.playlist_id is not None and rule.playlist_id not in playlists_by_show[rule.show_id]:
        return msg("rule_err_playlist_missing", playlist=rule.playlist_name or rule.playlist_id)
    if rule.image_path:
        return validate_image(rule.image_path)
    return None
