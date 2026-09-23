"""Une seule instance par utilisateur : un second lancement ramène la fenêtre existante.

Le vrai verrou est un fichier (QLockFile) : sous Windows, QLocalServer.listen réussit même
si le nom est déjà pris. Le serveur local ne sert qu'à transmettre une demande à l'instance
en cours : « show » (afficher la fenêtre) ou « quit » (désinstallation, mise à jour).
"""
from __future__ import annotations

import getpass
import logging
import os
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger(__name__)

TIMEOUT_MS = 300
# Le tube n'a pas de tampon : l'envoi n'aboutit que quand l'instance en cours accepte la
# connexion depuis sa boucle d'événements, d'où un délai plus large.
WRITE_TIMEOUT_MS = 3000


class SingleInstance(QObject):
    show_requested = Signal()
    quit_requested = Signal()

    def __init__(self, lock_path: Path) -> None:
        super().__init__()
        self._name = f"SyncAusha-{getpass.getuser()}"
        self._lock = QLockFile(str(lock_path))
        self._server: QLocalServer | None = None

    def try_acquire(self) -> bool:
        """True si on est la première instance ; sinon réveille l'autre et renvoie False."""
        self._lock.setStaleLockTime(0)  # seul compte le processus qui tient le verrou, pas l'âge du fichier
        if not self._lock.tryLock(0) and not self._take_over_own_pid_lock():
            if self._lock.error() == QLockFile.LockError.LockFailedError:
                self.request("show")
                return False
            log.warning("Verrou d'instance unique inutilisable (%s) : démarrage quand même", self._lock.error())
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)
        if not self._server.listen(self._name):
            log.warning("Relais « afficher la fenêtre » indisponible : %s", self._server.errorString())
        return True

    def request(self, message: str) -> bool:
        """Transmet « show » ou « quit » à l'instance en cours ; False si aucune ne répond."""
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if not socket.waitForConnected(TIMEOUT_MS):
            return False
        socket.write(message.encode("ascii"))
        socket.waitForBytesWritten(WRITE_TIMEOUT_MS)
        socket.disconnectFromServer()
        return True

    def close(self) -> None:
        """Ferme le relais ; le verrou reste pris jusqu'à la fin du processus."""
        if self._server is not None:
            self._server.close()

    def _take_over_own_pid_lock(self) -> bool:
        """Verrou laissé par un arrêt brutal dont le numéro de processus est aujourd'hui le nôtre."""
        pid, _hostname, _appname = self._lock.getLockInfo()
        # Tant que l'autre processus tient le fichier ouvert, Windows en refuse la suppression.
        return pid == os.getpid() and self._lock.removeStaleLockFile() and self._lock.tryLock(0)

    def _on_connection(self) -> None:
        while (connection := self._server.nextPendingConnection()) is not None:
            if not connection.bytesAvailable():
                connection.waitForReadyRead(TIMEOUT_MS)
            message = bytes(connection.readAll()).strip()
            connection.disconnectFromServer()
            connection.deleteLater()
            if message == b"quit":
                log.info("Fermeture demandée (désinstallation ou mise à jour)")
                self.quit_requested.emit()
            else:
                self.show_requested.emit()
