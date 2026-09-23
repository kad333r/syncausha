"""Petits widgets partagés par les pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget


def make_label(text: str = "", object_name: str | None = None, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(wrap)
    return label


def section_label(text: str) -> QLabel:
    return make_label(text, "section")


def pill(text: str, kind: str) -> QLabel:
    """Badge coloré ; kind ∈ success, warning, danger, info, neutral."""
    label = QLabel(text)
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
        title_label = QLabel(title)
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
