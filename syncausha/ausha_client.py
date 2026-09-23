"""Client minimal de l'API publique Ausha (https://developers.ausha.co)."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from syncausha.config import DEFAULT_API_BASE_URL

log = logging.getLogger(__name__)

PAGE_SIZE = 50
MAX_PAGES = 200
DEFAULT_RETRY_AFTER = 60.0
MAX_RETRY_AFTER = 300.0
DEFAULT_TIMEOUT = httpx.Timeout(60.0)
# Après un envoi de 500 Mo, Ausha peut mettre longtemps à répondre.
UPLOAD_TIMEOUT = httpx.Timeout(60.0, read=900.0)
_GRANTED_SHOWS_URL = "/shows/granted"
_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/x-m4a",
    ".wav": "audio/x-wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/x-flac",
    ".mp4": "video/mp4",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

ProgressCallback = Callable[[int], None]


class AushaError(Exception):
    """Erreur renvoyée par Ausha ou par le réseau."""


class AuthError(AushaError):
    """Jeton absent, invalide ou sans accès à l'API (401, ou 403 sur la liste des émissions)."""


class RejectedError(AushaError):
    """Requête refusée par Ausha : inutile de la renvoyer telle quelle."""


class TransientError(AushaError):
    """Problème passager : réseau, délai dépassé, 5xx, 429 persistant."""


class Cancelled(AushaError):
    """Envoi interrompu à la demande (fermeture de l'application)."""


@dataclass(frozen=True)
class Show:
    id: int
    name: str


@dataclass(frozen=True)
class Playlist:
    id: int
    name: str


@dataclass(frozen=True)
class Episode:
    id: int
    name: str


class AushaClient:
    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_API_BASE_URL,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_rate_limit_retries: int = 5,
        cancel: threading.Event | None = None,
    ) -> None:
        # Jamais le jeton dans le message : il finirait dans les logs.
        if not token or not all("!" <= c <= "~" for c in token):
            raise AuthError("Jeton Ausha invalide (caractères non autorisés).")
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT,
            transport=transport,
        )
        self._sleep = sleep
        self._max_retries = max_rate_limit_retries
        self._cancel = cancel

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> AushaClient:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def list_shows(self) -> list[Show]:
        return [Show(int(item["id"]), _name(item)) for item in self._get_all(_GRANTED_SHOWS_URL)]

    def list_playlists(self, show_id: int) -> list[Playlist]:
        return [Playlist(int(item["id"]), _name(item)) for item in self._get_all(f"/shows/{show_id}/playlists")]

    def find_episodes(self, show_id: int, query: str) -> list[Episode]:
        items = self._get_all(f"/shows/{show_id}/podcasts", {"q": query})
        return [Episode(int(item["id"]), _name(item)) for item in items]

    def create_episode(
        self,
        show_id: int,
        name: str,
        description: str,
        audio_path: Path,
        on_progress: ProgressCallback | None = None,
    ) -> int:
        """Crée et publie immédiatement l'épisode (state=active). Renvoie son id."""
        data = {"name": name, "state": "active"}
        if description:
            data["description"] = description
        body = self._send("POST", f"/shows/{show_id}/podcasts", data=data, file_path=audio_path, on_progress=on_progress)
        try:
            return int(body["data"]["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TransientError("Réponse inattendue d'Ausha : identifiant de l'épisode absent.") from exc

    def upload_episode_image(self, episode_id: int, image_path: Path) -> None:
        self._send("POST", f"/podcasts/{episode_id}/image", file_path=image_path)

    def add_to_playlist(self, playlist_id: int, episode_id: int) -> None:
        self._send("POST", f"/playlists/{playlist_id}/podcasts/{episode_id}")

    def _get_all(self, url: str, params: dict | None = None) -> list[dict]:
        """Toutes les pages : s'arrête à la dernière annoncée, sur une page vide ou un lien « next » nul."""
        items: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            body = self._send("GET", url, params={**(params or {}), "page": page, "per_page": PAGE_SIZE})
            data = body.get("data") or []
            items.extend(data)
            pagination = (body.get("meta") or {}).get("pagination") or {}
            links = body.get("links") or {}
            if not data or page >= int(pagination.get("total_pages") or 1) or ("next" in links and links["next"] is None):
                return items
        log.warning("Pagination de %s arrêtée après %d pages", url, MAX_PAGES)
        return items

    def _send(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        file_path: Path | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            response = self._request_once(method, url, params, data, file_path, on_progress)
            if response.status_code != 429 or attempt == self._max_retries:
                break
            delay = _retry_after(response)
            if delay > MAX_RETRY_AFTER:
                raise TransientError(f"Ausha demande de patienter {delay:.0f} s : nouvel essai au prochain passage.")
            log.info("Ausha demande une pause de %.0f s", delay)
            self._wait(delay)
        return _parse(response, auth_probe=method == "GET" and url == _GRANTED_SHOWS_URL, strict=method == "GET")

    def _wait(self, delay: float) -> None:
        if self._cancel is None:
            self._sleep(delay)
        elif self._cancel.wait(delay):
            raise Cancelled("Envoi interrompu.")

    def _request_once(self, method, url, params, data, file_path, on_progress) -> httpx.Response:
        handle = None
        try:
            files = None
            timeout = httpx.USE_CLIENT_DEFAULT
            if file_path is not None:
                try:
                    handle = open(file_path, "rb")
                    size = file_path.stat().st_size
                except OSError as exc:
                    raise TransientError(f"Fichier illisible : {file_path.name} ({exc})") from exc
                reader = _ProgressReader(handle, size, on_progress, self._cancel)
                files = {"file": (file_path.name, reader, _MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream"))}
                timeout = UPLOAD_TIMEOUT
            return self._http.request(method, url, params=params, data=data, files=files, timeout=timeout)
        except httpx.TransportError as exc:
            raise TransientError(f"Connexion à Ausha impossible : {exc}") from exc
        finally:
            if handle is not None:
                handle.close()


class _ProgressReader:
    """Enveloppe un fichier ouvert, signale le pourcentage lu (donc envoyé) et permet d'interrompre l'envoi."""

    def __init__(self, handle, total: int, callback: ProgressCallback | None, cancel: threading.Event | None = None) -> None:
        self._handle = handle
        self._total = total
        self._callback = callback
        self._cancel = cancel
        self._sent = 0
        self._last = -1

    def read(self, size: int = -1) -> bytes:
        if self._cancel is not None and self._cancel.is_set():
            raise Cancelled("Envoi interrompu.")
        chunk = self._handle.read(size)
        if self._callback and self._total:
            self._sent += len(chunk)
            percent = min(100, self._sent * 100 // self._total)
            if percent != self._last:
                self._last = percent
                self._callback(percent)
        return chunk

    def seek(self, offset: int, whence: int = 0) -> int:
        if offset == 0 and whence == 0:
            self._sent = 0
            self._last = -1
        return self._handle.seek(offset, whence)

    def __getattr__(self, name: str):
        return getattr(self._handle, name)


def _retry_after(response: httpx.Response) -> float:
    try:
        return max(0.0, float(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER)))
    except ValueError:
        return DEFAULT_RETRY_AFTER


def _parse(response: httpx.Response, *, auth_probe: bool = False, strict: bool = True) -> dict[str, Any]:
    """Corps JSON d'une réponse 2xx, ou erreur typée.

    Un 403 n'invalide le jeton que sur la liste des émissions (auth_probe) : ailleurs, c'est
    un refus ponctuel (une émission, une playlist) qui ne doit pas bloquer toute la synchro.
    Hors lecture (strict=False), un 2xx au corps inattendu (`true`, `[]`…) reste un succès :
    l'action a été faite, la réessayer risquerait de la refaire ou de finir en échec.
    """
    status = response.status_code
    if 200 <= status < 300:
        if not response.content.strip():
            return {}
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            if not strict:
                return {}
            raise TransientError(f"Réponse inattendue d'Ausha (HTTP {status}).")
        return body
    if 300 <= status < 400:
        raise RejectedError(f"Ausha a répondu par une redirection (HTTP {status}) : vérifiez l'adresse de l'API.")
    message = _error_message(response)
    if status == 401 or (status == 403 and auth_probe):
        raise AuthError(message)
    if status in (408, 429) or status >= 500:
        raise TransientError(message)
    raise RejectedError(message)


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        parts = [str(body.get("message") or "")]
        errors = body.get("errors")
        if isinstance(errors, dict):
            for messages in errors.values():
                if isinstance(messages, list):
                    parts.extend(str(m) for m in messages)
                else:
                    parts.append(str(messages))
        text = " ".join(p for p in parts if p).strip()
        if text:
            return f"{text} (HTTP {response.status_code})"
    return f"Ausha a répondu HTTP {response.status_code}"


def _name(item: dict) -> str:
    return str(item.get("name") or item.get("title") or item.get("id"))
