"""Point d'entrée : assemble réglages, journal, contrôleur, fenêtre et icône.

Options : --minimized (démarrage de Windows), --quit et --forget-token (désinstallation,
mise à jour : fermer l'instance en cours, retirer le jeton), sans interface.
"""
from __future__ import annotations

import logging
import os
import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from syncausha import __version__
from syncausha.config import app_data_dir, set_token
from syncausha.i18n import resolve_language
from syncausha.journal import open_journal
from syncausha.logging_setup import setup_logging
from syncausha.ui.controller import AppController
from syncausha.ui.icons import app_icon
from syncausha.ui.language import apply_language
from syncausha.ui.main_window import MainWindow
from syncausha.ui.single_instance import SingleInstance
from syncausha.ui.style import apply_style, watch_color_scheme
from syncausha.ui.tray import Tray

log = logging.getLogger(__name__)

# Guetté par l'installateur (AppMutex) : SyncAusha doit être fermé avant de remplacer ses fichiers.
RUNNING_MUTEX = "SyncAushaRunning"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    if "--forget-token" in argv:
        return _forget_token()
    if "--quit" in argv:
        SingleInstance(app_data_dir() / "syncausha.lock").request("quit")  # sans effet si aucune ne tourne
        return 0
    app = QApplication(argv)
    app.setApplicationName("SyncAusha")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    data_dir = app_data_dir()
    setup_logging(data_dir / "logs")
    sys.excepthook = lambda *exc_info: log.critical("Erreur non gérée", exc_info=exc_info)
    instance = SingleInstance(data_dir / "syncausha.lock")
    if not instance.try_acquire():
        return 0
    _create_mutex(RUNNING_MUTEX)
    log.info("Démarrage de SyncAusha %s", __version__)

    apply_style(app)
    watch_color_scheme(app)
    journal = open_journal(data_dir / "journal.db")
    controller = AppController(data_dir / "config.json", journal)
    language = resolve_language(controller.config.language)  # réglages, puis installateur, puis anglais
    apply_language(app, language)
    log.info("Langue de l'interface : %s", language)
    window = MainWindow(controller)
    tray = Tray(controller, window)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()
    instance.show_requested.connect(window.show_and_raise)
    instance.quit_requested.connect(app.quit)
    if "--minimized" not in argv or window.needs_setup():
        window.show_and_raise()
    controller.start()

    code = app.exec()
    instance.close()
    if not controller.shutdown():
        # Détruire un QThread encore actif tue le processus (0xC0000409) : on sort sans
        # fermer le journal, l'entrée « uploading » fera vérifier l'épisode au redémarrage.
        log.warning("Arrêt forcé : un envoi était en cours, il reprendra au prochain démarrage")
        logging.shutdown()
        os._exit(code)
    journal.close()
    return code


def _forget_token() -> int:
    """Retire le jeton du Gestionnaire d'identifiants Windows (désinstallation)."""
    try:
        set_token("")
    except Exception:  # Gestionnaire d'identifiants indisponible : la désinstallation continue
        return 1
    return 0


def _create_mutex(name: str) -> int | None:
    """Mutex nommé Windows, jamais refermé : Windows le libère à la fin du processus."""
    if sys.platform != "win32":
        return None
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    return kernel32.CreateMutexW(None, False, name)
