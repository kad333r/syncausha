"""Icône de l'application et variantes avec pastille d'état pour la zone de notification."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

ASSETS = Path(__file__).resolve().parent.parent / "assets"
STATE_COLORS = {
    "ok": "#2E9E4F",
    "syncing": "#2F6FDB",
    "attention": "#E39B17",
    "not_configured": "#E39B17",
    "folder_missing": "#E39B17",
    "paused": "#8A8984",
    "auth_error": "#D93A2F",
    "offline": "#D93A2F",
}


def app_icon() -> QIcon:
    return QIcon(str(ASSETS / "icon.png"))


def state_icon(state: str) -> QIcon:
    pixmap = QPixmap(str(ASSETS / "icon.png")).scaled(
        64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("white"))
    painter.drawEllipse(36, 36, 28, 28)
    painter.setBrush(QColor(STATE_COLORS.get(state, "#8A8984")))
    painter.drawEllipse(40, 40, 20, 20)
    painter.end()
    return QIcon(pixmap)
