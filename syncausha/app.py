"""Point d'entrée : assemble réglages, journal, contrôleur, fenêtre et icône."""
from __future__ import annotations

import logging
import os
import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from syncausha import __version__
from syncausha.config import app_data_dir
from syncausha.journal import open_journal
from syncausha.logging_setup import setup_logging
from syncausha.ui.controller import AppController
from syncausha.ui.icons import app_icon
from syncausha.ui.main_window import MainWindow
from syncausha.ui.single_instance import SingleInstance
from syncausha.ui.style import apply_style, watch_color_scheme
from syncausha.ui.tray import Tray

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("SyncAusha")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    instance = SingleInstance()
    if not instance.try_acquire():
        return 0

    data_dir = app_data_dir()
    setup_logging(data_dir / "logs")
    sys.excepthook = lambda *exc_info: log.critical("Erreur non gérée", exc_info=exc_info)
    log.info("Démarrage de SyncAusha %s", __version__)

    apply_style(app)
    watch_color_scheme(app)
    journal = open_journal(data_dir / "journal.db")
    controller = AppController(data_dir / "config.json", journal)
    window = MainWindow(controller)
    tray = Tray(controller, window)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()
    instance.show_requested.connect(window.show_and_raise)
    if "--minimized" not in argv or window.needs_setup():
        window.show_and_raise()
    controller.start()

    code = app.exec()
    if not controller.shutdown():
        # Détruire un QThread encore actif tue le processus (0xC0000409) : on sort sans
        # fermer le journal, l'entrée « uploading » fera vérifier l'épisode au redémarrage.
        log.warning("Arrêt forcé : un envoi était en cours, il reprendra au prochain démarrage")
        logging.shutdown()
        os._exit(code)
    journal.close()
    return code
