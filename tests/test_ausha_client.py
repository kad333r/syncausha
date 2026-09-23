import httpx
import pytest
import respx

from syncausha.ausha_client import (
    AushaClient,
    AuthError,
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
