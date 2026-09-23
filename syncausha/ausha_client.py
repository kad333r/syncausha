"""Client minimal de l'API publique Ausha (https://developers.ausha.co)."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from syncausha.config import DEFAULT_API_BASE_URL

log = logging.getLogger(__name__)

PAGE_SIZE = 50
DEFAULT_RETRY_AFTER = 60.0
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
    """Jeton absent, invalide ou sans droits (401/403)."""


class RejectedError(AushaError):
    """Requête refusée par Ausha : inutile de la renvoyer telle quelle."""


class TransientError(AushaError):
    """Problème passager : réseau, délai dépassé, 5xx, 429 persistant."""


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
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=httpx.Timeout(60.0),
            transport=transport,
        )
        self._sleep = sleep
        self._max_retries = max_rate_limit_retries

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> AushaClient:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def list_shows(self) -> list[Show]:
        return [Show(int(item["id"]), _name(item)) for item in self._get_all("/shows/granted")]

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
        return int(body["data"]["id"])

    def upload_episode_image(self, episode_id: int, image_path: Path) -> None:
        self._send("POST", f"/podcasts/{episode_id}/image", file_path=image_path)

    def add_to_playlist(self, playlist_id: int, episode_id: int) -> None:
        self._send("POST", f"/playlists/{playlist_id}/podcasts/{episode_id}")

    def _get_all(self, url: str, params: dict | None = None) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            body = self._send("GET", url, params={**(params or {}), "page": page, "per_page": PAGE_SIZE})
            items.extend(body.get("data") or [])
            pagination = (body.get("meta") or {}).get("pagination") or {}
            if page >= int(pagination.get("total_pages") or 1):
                return items
            page += 1

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
            log.info("Ausha demande une pause de %.0f s", delay)
            self._sleep(delay)
        return _parse(response)

    def _request_once(self, method, url, params, data, file_path, on_progress) -> httpx.Response:
        handle = None
        try:
            files = None
            if file_path is not None:
                handle = open(file_path, "rb")
                reader = _ProgressReader(handle, file_path.stat().st_size, on_progress)
                files = {"file": (file_path.name, reader, _MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream"))}
            return self._http.request(method, url, params=params, data=data, files=files)
        except httpx.TransportError as exc:
            raise TransientError(f"Connexion à Ausha impossible : {exc}") from exc
        finally:
            if handle is not None:
                handle.close()


class _ProgressReader:
    """Enveloppe un fichier ouvert et signale le pourcentage lu (donc envoyé)."""

    def __init__(self, handle, total: int, callback: ProgressCallback | None) -> None:
        self._handle = handle
        self._total = total
        self._callback = callback
        self._sent = 0
        self._last = -1

    def read(self, size: int = -1) -> bytes:
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
        return self._handle.seek(offset, whence)

    def __getattr__(self, name: str):
        return getattr(self._handle, name)


def _retry_after(response: httpx.Response) -> float:
    try:
        return max(0.0, float(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER)))
    except ValueError:
        return DEFAULT_RETRY_AFTER


def _parse(response: httpx.Response) -> dict[str, Any]:
    status = response.status_code
    if status < 400:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}
    message = _error_message(response)
    if status in (401, 403):
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
                parts.extend(messages if isinstance(messages, list) else [str(messages)])
        text = " ".join(p for p in parts if p).strip()
        if text:
            return f"{text} (HTTP {response.status_code})"
    return f"Ausha a répondu HTTP {response.status_code}"


def _name(item: dict) -> str:
    return str(item.get("name") or item.get("title") or item.get("id"))
