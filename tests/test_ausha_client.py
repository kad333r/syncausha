import threading

import httpx
import pytest
import respx

from syncausha.ausha_client import (
    AushaClient,
    AuthError,
    Cancelled,
    Episode,
    Playlist,
    RejectedError,
    Show,
    TransientError,
)

BASE = "https://api.test/v1"


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def client(sleeps):
    c = AushaClient("secret-token", BASE, sleep=sleeps.append)
    yield c
    c.close()


@pytest.fixture
def api():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "MARS ATTACK 12.mp3"
    path.write_bytes(b"ID3" + b"x" * 5000)
    return path


def test_list_shows_sends_token_and_follows_pages(api, client):
    route = api.get("/shows/granted")
    route.side_effect = [
        httpx.Response(200, json={"data": [{"id": 1, "name": "Mars Attack"}], "meta": {"pagination": {"total_pages": 2}}}),
        httpx.Response(200, json={"data": [{"id": 2, "name": "Silicon Talk"}], "meta": {"pagination": {"total_pages": 2}}}),
    ]
    assert client.list_shows() == [Show(1, "Mars Attack"), Show(2, "Silicon Talk")]
    first = route.calls[0].request
    assert first.headers["Authorization"] == "Bearer secret-token"
    assert first.url.params["page"] == "1"
    assert route.calls[1].request.url.params["page"] == "2"


def test_list_playlists(api, client):
    api.get("/shows/1/playlists").respond(200, json={"data": [{"id": 7, "name": "Saison 3"}]})
    assert client.list_playlists(1) == [Playlist(7, "Saison 3")]


def test_find_episodes_passes_query(api, client):
    route = api.get("/shows/1/podcasts").respond(200, json={"data": [{"id": 99, "name": "MARS ATTACK 12"}]})
    assert client.find_episodes(1, "MARS ATTACK 12") == [Episode(99, "MARS ATTACK 12")]
    assert route.calls.last.request.url.params["q"] == "MARS ATTACK 12"


def test_create_episode_uploads_multipart_and_publishes(api, client, audio):
    route = api.post("/shows/1/podcasts").respond(201, json={"data": {"id": 321}})
    progress = []
    assert client.create_episode(1, "MARS ATTACK 12", "Nouvel épisode", audio, on_progress=progress.append) == 321
    request = route.calls.last.request
    body = request.read()
    assert request.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="state"\r\n\r\nactive' in body
    assert b'name="name"\r\n\r\nMARS ATTACK 12' in body
    assert 'name="description"\r\n\r\nNouvel épisode'.encode() in body
    assert b'filename="MARS ATTACK 12.mp3"' in body
    assert b"audio/mpeg" in body
    assert progress and progress[-1] == 100


def test_description_is_omitted_when_empty(api, client, audio):
    route = api.post("/shows/1/podcasts").respond(201, json={"data": {"id": 1}})
    client.create_episode(1, "T", "", audio)
    assert b'name="description"' not in route.calls.last.request.read()


def test_upload_image_and_add_to_playlist(api, client, tmp_path):
    image = tmp_path / "cover.png"
    image.write_bytes(b"\x89PNG fake")
    image_route = api.post("/podcasts/321/image").respond(200, json={"data": {"url": "x"}})
    playlist_route = api.post("/playlists/7/podcasts/321").respond(201, json={})
    client.upload_episode_image(321, image)
    client.add_to_playlist(7, 321)
    assert b'filename="cover.png"' in image_route.calls.last.request.read()
    assert playlist_route.called


def test_rate_limit_waits_then_retries(api, client, sleeps):
    api.get("/shows/granted").side_effect = [
        httpx.Response(429, headers={"Retry-After": "3"}),
        httpx.Response(200, json={"data": []}),
    ]
    assert client.list_shows() == []
    assert sleeps == [3.0]


def test_rate_limit_gives_up_after_max_retries(api, sleeps):
    limited = AushaClient("t", BASE, sleep=sleeps.append, max_rate_limit_retries=2)
    api.get("/shows/granted").respond(429)
    with pytest.raises(TransientError):
        limited.list_shows()
    assert sleeps == [60.0, 60.0]
    limited.close()


@pytest.mark.parametrize(
    "status,error",
    [(401, AuthError), (403, AuthError), (404, RejectedError), (422, RejectedError), (500, TransientError), (503, TransientError)],
)
def test_http_errors_are_typed(api, client, status, error):
    api.get("/shows/granted").respond(status, json={"message": "Nope"})
    with pytest.raises(error, match="Nope"):
        client.list_shows()


def test_validation_errors_are_readable(api, client, audio):
    api.post("/shows/1/podcasts").respond(
        422,
        json={"message": "The given data was invalid.", "errors": {"file": ["The file may not be greater than 500000 kilobytes."]}},
    )
    with pytest.raises(RejectedError, match="500000 kilobytes"):
        client.create_episode(1, "T", "", audio)


def test_network_error_is_transient(api, client):
    api.get("/shows/granted").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(TransientError):
        client.list_shows()


def test_forbidden_on_granted_shows_is_auth_error(api, client):
    api.get("/shows/granted").respond(403, json={"message": "Forbidden"})
    with pytest.raises(AuthError):
        client.list_shows()


def test_forbidden_elsewhere_is_rejected_not_auth(api, client):
    api.post("/playlists/7/podcasts/1").respond(403, json={"message": "Forbidden"})
    with pytest.raises(RejectedError, match="Forbidden"):
        client.add_to_playlist(7, 1)


def test_redirect_is_rejected_with_clear_message(api, client):
    api.get("/shows/granted").respond(302, headers={"Location": "https://ailleurs.test/"})
    with pytest.raises(RejectedError, match="redirection"):
        client.list_shows()


def test_success_with_non_object_json_is_transient(api, client):
    api.get("/shows/granted").respond(200, json=[1, 2])
    with pytest.raises(TransientError, match="inattendue"):
        client.list_shows()


def test_success_with_invalid_json_is_transient(api, client):
    api.get("/shows/granted").respond(200, text="<html>maintenance</html>")
    with pytest.raises(TransientError, match="inattendue"):
        client.list_shows()


def test_success_with_empty_body_is_empty(api, client):
    route = api.post("/playlists/7/podcasts/1").respond(204)
    client.add_to_playlist(7, 1)
    assert route.called


def test_create_without_episode_id_is_transient(api, client, audio):
    api.post("/shows/1/podcasts").respond(201, json={"data": {}})
    with pytest.raises(TransientError):
        client.create_episode(1, "T", "", audio)


def test_error_list_with_non_string_entries(api, client):
    api.get("/shows/granted").respond(422, json={"message": "Invalide", "errors": {"x": [{"code": 1}, 42, "texte"]}})
    with pytest.raises(RejectedError, match="42 texte"):
        client.list_shows()


def test_excessive_retry_after_is_transient_without_waiting(api, client, sleeps):
    route = api.get("/shows/granted")
    route.respond(429, headers={"Retry-After": "3600"})
    with pytest.raises(TransientError):
        client.list_shows()
    assert sleeps == []
    assert route.call_count == 1


def test_pagination_stops_on_empty_page(api, client):
    route = api.get("/shows/granted")
    route.side_effect = [
        httpx.Response(200, json={"data": [{"id": 1, "name": "A"}], "meta": {"pagination": {"total_pages": 5}}}),
        httpx.Response(200, json={"data": [], "meta": {"pagination": {"total_pages": 5}}}),
    ]
    assert client.list_shows() == [Show(1, "A")]
    assert route.call_count == 2


def test_pagination_stops_when_next_link_is_null(api, client):
    route = api.get("/shows/granted")
    route.side_effect = [
        httpx.Response(200, json={"data": [{"id": 1, "name": "A"}], "meta": {"pagination": {"total_pages": 5}}, "links": {"next": "p2"}}),
        httpx.Response(200, json={"data": [{"id": 2, "name": "B"}], "meta": {"pagination": {"total_pages": 5}}, "links": {"next": None}}),
    ]
    assert client.list_shows() == [Show(1, "A"), Show(2, "B")]
    assert route.call_count == 2


def test_pagination_has_a_hard_cap(api, client):
    route = api.get("/shows/granted").respond(
        200, json={"data": [{"id": 1, "name": "A"}], "meta": {"pagination": {"total_pages": 10_000}}}
    )
    client.list_shows()
    assert route.call_count == 200


@pytest.mark.parametrize("token", ["", "jeton avec espace", "jeton\n", "jeton-é", "jeton\x00"])
def test_invalid_token_is_refused_without_leaking_it(token):
    with pytest.raises(AuthError, match="caractères non autorisés") as info:
        AushaClient(token, BASE)
    if token:
        assert token not in str(info.value)


def test_missing_audio_file_is_transient(api, client, tmp_path):
    api.post("/shows/1/podcasts").respond(201, json={"data": {"id": 1}})
    with pytest.raises(TransientError, match="Fichier illisible : absent.mp3"):
        client.create_episode(1, "T", "", tmp_path / "absent.mp3")


def test_upload_has_content_length_and_long_read_timeout(api, client, audio):
    route = api.post("/shows/1/podcasts").respond(201, json={"data": {"id": 1}})
    client.create_episode(1, "T", "", audio)
    request = route.calls.last.request
    assert int(request.headers["Content-Length"]) > audio.stat().st_size
    assert "Transfer-Encoding" not in request.headers
    assert request.extensions["timeout"]["read"] == 900.0


def test_simple_request_keeps_default_timeout(api, client):
    route = api.get("/shows/granted").respond(200, json={"data": []})
    client.list_shows()
    assert route.calls.last.request.extensions["timeout"]["read"] == 60.0


def test_cancel_interrupts_upload(api, audio):
    cancel = threading.Event()
    cancel.set()
    api.post("/shows/1/podcasts").respond(201, json={"data": {"id": 1}})
    with AushaClient("t", BASE, cancel=cancel) as cancellable:
        with pytest.raises(Cancelled):
            cancellable.create_episode(1, "T", "", audio)


def test_cancel_interrupts_rate_limit_wait(api, sleeps):
    cancel = threading.Event()
    cancel.set()
    api.get("/shows/granted").respond(429, headers={"Retry-After": "30"})
    with AushaClient("t", BASE, sleep=sleeps.append, cancel=cancel) as cancellable:
        with pytest.raises(Cancelled):
            cancellable.list_shows()
    assert sleeps == []
