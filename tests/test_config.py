import json

from syncausha import config as cfg
from syncausha.config import Config, Rule, load_config, save_config


def test_missing_file_gives_defaults(tmp_path):
    config = load_config(tmp_path / "config.json")
    assert config == Config()
    assert config.interval_minutes == 15
    assert config.rules == []
    assert config.api_base_url == "https://api-content.ausha.co/v1"


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = Config(
        watch_folder="D:/Podcasts",
        baseline_folder="D:/Podcasts",
        interval_minutes=30,
        dry_run=True,
        rules=[
            Rule(
                keyword="MARS ATTACK",
                show_id=12,
                show_name="Mars Attack",
                playlist_id=7,
                playlist_name="Saison 3",
                image_path="C:/images/mars.png",
                description_template="Nouvel épisode de Mars Attack",
            )
        ],
    )
    save_config(config, path)
    assert load_config(path) == config


def test_interval_is_clamped():
    assert Config(interval_minutes=1).interval_minutes == 5
    assert Config(interval_minutes=500).interval_minutes == 120


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"watch_folder": "X", "future": 1,'
        ' "rules": [{"keyword": "A", "show_id": 1, "extra": true}]}',
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.watch_folder == "X"
    assert config.rules == [Rule(keyword="A", show_id=1)]


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{pas du json", encoding="utf-8")
    assert load_config(path) == Config()


def test_bom_file_loads(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b"\xef\xbb\xbf" + '{"watch_folder": "D:/Podcasts"}'.encode("utf-8"))
    config = load_config(path)
    assert config.watch_folder == "D:/Podcasts"


def test_top_level_list_gives_defaults_and_quarantines_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    config = load_config(path)
    assert config == Config()
    assert not path.exists()
    assert (tmp_path / "config.json.illisible").exists()


def test_invalid_rules_are_skipped_individually(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"rules": [1, {"keyword": "A", "show_id": 1}, {"keyword": "B"}]}),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.rules == [Rule(keyword="A", show_id=1)]


def test_wrong_type_field_keeps_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"paused": "false", "baseline_folder": 3}', encoding="utf-8")
    config = load_config(path)
    assert config.paused is False
    assert config.baseline_folder == ""


def test_token_roundtrip(monkeypatch):
    store = {}

    def delete(service, user):
        if (service, user) not in store:
            raise cfg.PasswordDeleteError()
        del store[(service, user)]

    monkeypatch.setattr(cfg.keyring, "get_password", lambda s, u: store.get((s, u)))
    monkeypatch.setattr(cfg.keyring, "set_password", lambda s, u, p: store.__setitem__((s, u), p))
    monkeypatch.setattr(cfg.keyring, "delete_password", delete)

    assert cfg.get_token() is None
    cfg.set_token("  abc  ")
    assert cfg.get_token() == "abc"
    cfg.set_token("")
    assert cfg.get_token() is None
    cfg.set_token("")  # supprimer un jeton absent ne plante pas

    long_token = "x" * 2500
    cfg.set_token(long_token)
    assert cfg.get_token() == long_token
    chunk_keys = [
        key for key in store if key[1].startswith(f"{cfg.KEYRING_USERNAME}.") and not key[1].endswith(".count")
    ]
    assert len(chunk_keys) == 3
    assert all(len(store[key]) <= 1000 for key in chunk_keys)
    cfg.set_token("")
    assert store == {}
