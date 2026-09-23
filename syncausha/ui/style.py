"""Thème sobre, clair ou sombre selon le réglage de Windows."""
from __future__ import annotations

from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from syncausha.ui.icons import ASSETS

LIGHT = {
    "bg": "#F7F7F5", "surface": "#FFFFFF", "sidebar": "#F0EFEA", "text": "#1F1F1E", "muted": "#6B6A66",
    "border": "#E3E1DA", "border_strong": "#9C998F", "hover": "#ECEAE4", "selected": "#E4E2DA",
    "accent": "#2F6FDB", "accent_hover": "#285FBD", "accent_text": "#FFFFFF",
    "success_bg": "#E6F3E6", "success": "#2E7D32", "warning_bg": "#FDF1DC", "warning": "#9A6200",
    "danger_bg": "#FBE9E9", "danger": "#B3261E", "info_bg": "#E6EEFB", "info": "#1F5BB5",
}
DARK = {
    "bg": "#1E1E1D", "surface": "#262625", "sidebar": "#1A1A19", "text": "#ECECEA", "muted": "#A3A29E",
    "border": "#3A3A38", "border_strong": "#77756F", "hover": "#302F2D", "selected": "#383734",
    "accent": "#5B8DEF", "accent_hover": "#709CF1", "accent_text": "#0E1726",
    "success_bg": "#1F3322", "success": "#7BC47F", "warning_bg": "#3A2E14", "warning": "#E0B35C",
    "danger_bg": "#3D1F1D", "danger": "#F08A80", "info_bg": "#1D2B45", "info": "#8AB0F5",
}
# Pictogrammes de la feuille de style (générés par tools/make_icon.py). Chemins absolus à
# barres obliques, entre guillemets : un dossier d'installation peut contenir des espaces.
IMAGES = {name: (ASSETS / f"{name}.png").as_posix() for name in ("check", "chevron_down", "chevron_up")}

_QSS = Template("""
QWidget { background: $bg; color: $text; font-family: "Segoe UI"; font-size: 10pt; }
QListWidget#sidebar { background: $sidebar; border: none; border-right: 1px solid $border; padding: 16px 8px; outline: 0; }
QListWidget#sidebar::item { padding: 8px 12px; margin: 1px 0; border-radius: 6px; color: $muted; }
QListWidget#sidebar::item:hover { background: $hover; color: $text; }
QListWidget#sidebar::item:selected { background: $selected; color: $text; }
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
QPushButton#primary:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton#primary:disabled { background: $hover; color: $muted; border-color: $border; }
QPushButton#danger { color: $danger; }
QPushButton#link { border: none; background: transparent; color: $accent; padding: 0; text-align: left; }
QPushButton#link:hover { text-decoration: underline; }
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox { background: $surface; border: 1px solid $border; border-radius: 6px; padding: 5px 8px; selection-background-color: $accent; selection-color: $accent_text; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid $accent; }
QComboBox { padding-right: 24px; }
QComboBox:hover, QSpinBox:hover { border-color: $border_strong; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; border: none; width: 24px; }
QComboBox::down-arrow { image: url("$chevron_down"); width: 12px; height: 12px; }
QComboBoxPrivateContainer { background: $surface; border: 1px solid $border; }
QComboBox QAbstractItemView { background: $surface; color: $text; border: none; padding: 4px; outline: 0; selection-background-color: $hover; selection-color: $text; }
QComboBox QAbstractItemView::item { min-height: 24px; padding: 2px 8px; border: none; border-radius: 4px; }
QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected { background: $hover; color: $text; }
QSpinBox { padding-right: 24px; }
QSpinBox::up-button, QSpinBox::down-button { subcontrol-origin: border; width: 20px; border: none; background: transparent; }
QSpinBox::up-button { subcontrol-position: top right; margin: 3px 3px 0 0; border-top-right-radius: 4px; }
QSpinBox::down-button { subcontrol-position: bottom right; margin: 0 3px 3px 0; border-bottom-right-radius: 4px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: $hover; }
QSpinBox::up-arrow { image: url("$chevron_up"); width: 10px; height: 10px; }
QSpinBox::down-arrow { image: url("$chevron_down"); width: 10px; height: 10px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid $border_strong; border-radius: 4px; background: $surface; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url("$check"); }
QCheckBox::indicator:checked:hover { background: $accent_hover; border-color: $accent_hover; }
QListWidget#rules { background: $surface; border: 1px solid $border; border-radius: 8px; outline: 0; padding: 4px; }
QListWidget#rules::item { padding: 6px; border-radius: 6px; }
QListWidget#rules::item:hover { background: $hover; }
QListWidget#rules::item:selected { background: $selected; color: $text; }
QFrame#card QLabel#imagePreview { background: $hover; border: 1px solid $border; border-radius: 8px; color: $muted; }
QLabel[pill="success"] { background: $success_bg; color: $success; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="warning"] { background: $warning_bg; color: $warning; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="danger"] { background: $danger_bg; color: $danger; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="info"] { background: $info_bg; color: $info; border-radius: 6px; padding: 2px 8px; }
QLabel[pill="neutral"] { background: $hover; color: $muted; border-radius: 6px; padding: 2px 8px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $border; border-radius: 3px; min-height: 32px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: $border_strong; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QMenu { background: $surface; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: $hover; color: $text; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 4px 6px; }
""")

_forced: dict[str, str] | None = None


def palette() -> dict[str, str]:
    if _forced is not None:
        return _forced
    return DARK if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else LIGHT


def stylesheet(colors: dict[str, str]) -> str:
    return _QSS.substitute(colors, **IMAGES)


def apply_style(app: QApplication, colors: dict[str, str] | None = None) -> None:
    """Applique le thème de Windows, ou la palette colors (LIGHT ou DARK) si elle est donnée."""
    global _forced
    _forced = colors
    colors = palette()
    app.setStyle("Fusion")
    app.setPalette(_qt_palette(colors))  # pour ce que la feuille de style ne couvre pas
    app.setStyleSheet(stylesheet(colors))


def watch_color_scheme(app: QApplication) -> None:
    app.styleHints().colorSchemeChanged.connect(lambda _scheme: apply_style(app))


def _qt_palette(colors: dict[str, str]) -> QPalette:
    role = QPalette.ColorRole
    qt_palette = QPalette()
    for name, key in (
        (role.Window, "bg"), (role.WindowText, "text"), (role.Base, "surface"), (role.AlternateBase, "hover"),
        (role.Text, "text"), (role.Button, "surface"), (role.ButtonText, "text"), (role.PlaceholderText, "muted"),
        (role.Highlight, "accent"), (role.HighlightedText, "accent_text"), (role.ToolTipBase, "surface"),
        (role.ToolTipText, "text"), (role.Link, "accent"), (role.Light, "surface"), (role.Midlight, "hover"),
        (role.Mid, "border"), (role.Dark, "border_strong"), (role.Shadow, "border_strong"),
    ):
        qt_palette.setColor(name, QColor(colors[key]))
    for name in (role.WindowText, role.Text, role.ButtonText):
        qt_palette.setColor(QPalette.ColorGroup.Disabled, name, QColor(colors["muted"]))
    return qt_palette
