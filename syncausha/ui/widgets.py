"""Petits widgets partagés par les pages."""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget

from syncausha import i18n

RLM, FSI, PDI = "\u200f", "\u2068", "\u2069"  # marque droite-à-gauche, isolat, fin d'isolat


def leading_alignment() -> Qt.AlignmentFlag:
    """Bord où commence la lecture (droite en arabe), quel que soit le texte saisi : sinon Qt aligne un
    champ selon son contenu, et un nom latin partirait à gauche dans l'interface arabe."""
    rtl = QGuiApplication.layoutDirection() == Qt.LayoutDirection.RightToLeft
    return (Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignAbsolute


def isolate(text: str) -> str:
    """Valeur brute (chemin, nom d'émission) glissée dans un texte arabe : elle garde son propre sens de lecture."""
    return f"{FSI}{text}{PDI}" if text and i18n.is_rtl() else text


def joined(parts: list[str]) -> str:
    """« a · b · c » dans l'ordre de lecture de l'interface (de droite à gauche en arabe, même si tous les
    morceaux sont latins). Les valeurs brutes (chemin, nom d'émission) sont à isoler avant."""
    text = " · ".join(parts)
    return RLM + text if text and i18n.is_rtl() else text


def bidi_text(text: str) -> str:
    """Texte d'un libellé, lu dans le sens de l'interface.

    Qt donne à un libellé le sens de son premier caractère fort : en arabe, un texte qui commence par un
    nom latin (fichier, chemin, « titre — verdict ») serait lu de gauche à droite, aligné à gauche, les
    mots dans le désordre. Une marque RLM en tête le remet de droite à gauche ; un texte sans lettre arabe
    (nom de fichier, message d'Ausha) est en plus isolé pour rester lisible tel quel."""
    if not text or not i18n.is_rtl() or _starts_right_to_left(text):
        return text
    if any(unicodedata.bidirectional(char) in ("R", "AL") for char in text):
        return RLM + text
    return f"{RLM}{FSI}{text}{PDI}"


def _starts_right_to_left(text: str) -> bool:
    """Premier caractère fort hors isolats de droite à gauche (comme Qt pour choisir le sens d'un texte)."""
    depth = 0
    for char in text:
        kind = unicodedata.bidirectional(char)
        if kind in ("LRI", "RLI", "FSI"):
            depth += 1
        elif kind == "PDI":
            depth = max(depth - 1, 0)
        elif depth == 0 and kind in ("L", "R", "AL"):
            return kind != "L"
    return False


def make_label(text: str = "", object_name: str | None = None, wrap: bool = False) -> QLabel:
    label = QLabel(bidi_text(text))
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(wrap)
    return label


def section_label(text: str) -> QLabel:
    return make_label(text, "section")


def pill(text: str, kind: str) -> QLabel:
    """Badge coloré ; kind ∈ success, warning, danger, info, neutral."""
    label = QLabel(bidi_text(text))
    label.setProperty("pill", kind)
    return label


class Row(QFrame):
    """Ligne de liste : titre, sous-titre discret, et un widget à droite (badge ou bouton)."""

    def __init__(self, title: str, subtitle: str = "", trailing: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title_label = QLabel(bidi_text(title))
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        texts.addWidget(title_label)
        if subtitle:
            texts.addWidget(make_label(subtitle, "muted", wrap=True))
        layout.addLayout(texts, 1)
        if trailing is not None:
            layout.addWidget(trailing, 0, Qt.AlignmentFlag.AlignVCenter)


def set_tone(label: QLabel, object_name: str) -> None:
    """Change le style d'un libellé (muted, error…) déjà affiché."""
    if label.objectName() != object_name:
        label.setObjectName(object_name)
        label.style().unpolish(label)
        label.style().polish(label)


def clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            # Masqué tout de suite : sinon il reste affiché, hors mise en page, jusqu'à sa destruction
            # (différée, car le bouton cliqué qui a lancé le rafraîchissement peut en faire partie).
            widget.hide()
            widget.deleteLater()
