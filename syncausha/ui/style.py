"""Thème sobre, clair ou sombre selon le réglage de Windows."""
from __future__ import annotations

from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

LIGHT = {
    "bg": "#F7F7F5", "surface": "#FFFFFF", "sidebar": "#F0EFEA", "text": "#1F1F1E", "muted": "#6B6A66",
    "border": "#E3E1DA", "hover": "#ECEAE4", "accent": "#2F6FDB", "accent_hover": "#285FBD", "accent_text": "#FFFFFF",
    "success_bg": "#E6F3E6", "success": "#2E7D32", "warning_bg": "#FDF1DC", "warning": "#9A6200",
    "danger_bg": "#FBE9E9", "danger": "#B3261E", "info_bg": "#E6EEFB", "info": "#1F5BB5",
}
DARK = {
    "bg": "#1E1E1D", "surface": "#262625", "sidebar": "#1A1A19", "text": "#ECECEA", "muted": "#A3A29E",
    "border": "#3A3A38", "hover": "#302F2D", "accent": "#5B8DEF", "accent_hover": "#709CF1", "accent_text": "#FFFFFF",
    "success_bg": "#1F3322", "success": "#7BC47F", "warning_bg": "#3A2E14", "warning": "#E0B35C",
    "danger_bg": "#3D1F1D", "danger": "#F08A80", "info_bg": "#1D2B45", "info": "#8AB0F5",
}

_QSS = Template("""
QWidget { background: $bg; color: $text; font-family: "Segoe UI"; font-size: 10pt; }
QListWidget#sidebar { background: $sidebar; border: none; border-right: 1px solid $border; padding: 16px 8px; outline: 0; }
QListWidget#sidebar::item { padding: 8px 12px; margin: 1px 0; border-radius: 6px; color: $muted; }
QListWidget#sidebar::item:hover { background: $hover; }
QListWidget#sidebar::item:selected { background: $hover; color: $text; }
QLabel#pageTitle { font-size: 15pt; font-weight: 600; }
QLabel#section { color: $muted; font-size: 9pt; padding-top: 14px; }
QLabel#muted { color: $muted; font-size: 9pt; }
QLabel#error { color: $danger; font-size: 9pt; }
QFrame#row { border: none; border-bottom: 1px solid $border; }
QFrame#card { background: $surface; border: 1px solid $border; border-radius: 8px; }
QFrame#card QLabel, QFrame#card QCheckBox { background: transparent; }
QPushButton { background: $surface; border: 1px solid $border; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover { background: $hover; }
QPushButton:disabled { color: $muted; }
QPushButton#primary { background: $accent; color: $accent_text; border: 1px solid $accent; }
QPushButton#primary:hover { background: $accent_hover; }
QPushButton#danger { color: $danger; }
QPushButton#link { border: none; background: transparent; color: $accent; padding: 0; text-align: left; }
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox { background: $surface; border: 1px solid $border; border-radius: 6px; padding: 5px 8px; selection-background-color: $accent; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid $accent; }
QListWidget#rules { background: $surface; border: 1px solid $border; border-radius: 8px; outline: 0; padding: 4px; }
QListWidget#rules::item { padding: 6px; border-radius: 6px; }
QListWidget#rules::item:selected { background: $hover; color: $text; }
QLabel#imagePreview { background: $hover; border-radius: 8px; color: $muted; }
QLabel[pill="success"] { background: $success_bg; color: $success; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="warning"] { background: $warning_bg; color: $warning; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="danger"] { background: $danger_bg; color: $danger; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="info"] { background: $info_bg; color: $info; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="neutral"] { background: $hover; color: $muted; border-radius: 6px; padding: 2px 8px; }
QScrollArea { border: none; }
QMenu { background: $surface; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: $hover; color: $text; }
""")


def palette() -> dict[str, str]:
    return DARK if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else LIGHT


def apply_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(_QSS.substitute(palette()))


def watch_color_scheme(app: QApplication) -> None:
    app.styleHints().colorSchemeChanged.connect(lambda _scheme: apply_style(app))
