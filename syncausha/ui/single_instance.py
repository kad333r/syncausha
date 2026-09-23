"""Une seule instance par utilisateur : un second lancement ramène la fenêtre existante."""
from __future__ import annotations

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    show_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._name = f"SyncAusha-{getpass.getuser()}"
        self._server: QLocalServer | None = None

    def try_acquire(self) -> bool:
        """True si on est la première instance ; sinon réveille l'autre et renvoie False."""
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if socket.waitForConnected(300):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(300)
            socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._server.listen(self._name)
        return True

    def _on_connection(self) -> None:
        connection = self._server.nextPendingConnection()
        if connection is not None:
            connection.disconnectFromServer()
        self.show_requested.emit()
