"""Applique une langue à l'interface Qt : langue active, sens du texte, boîtes de dialogue standard."""
from __future__ import annotations

import logging

from PySide6.QtCore import QLibraryInfo, Qt, QTranslator
from PySide6.QtWidgets import QApplication

from syncausha import i18n

log = logging.getLogger(__name__)

_qt_translator: QTranslator | None = None


def apply_language(app: QApplication, code: str) -> None:
    """Langue des textes, sens de lecture (arabe de droite à gauche) et boutons Oui/Non/Annuler de Qt."""
    global _qt_translator
    i18n.set_language(code)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.is_rtl(code) else Qt.LayoutDirection.LeftToRight)
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator.deleteLater()
        _qt_translator = None
    if code == i18n.DEFAULT_LANGUAGE:  # textes d'origine de Qt
        return
    translator = QTranslator(app)
    if translator.load(f"qtbase_{code}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        _qt_translator = translator
    else:
        log.warning("Traductions Qt introuvables pour %s", code)
        translator.deleteLater()
