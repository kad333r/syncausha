import json
import logging

from syncausha import config as cfg
from syncausha.config import Config, KeywordRule, ShowFolder, folder_key, load_config, same_folder, save_config
from syncausha.i18n import msg, render


def test_missing_file_gives_defaults(tmp_path):
    config = load_config(tmp_path / "config.json")
    assert config == Config()
    assert config.interval_minutes == 15
    assert config.shows == []
    assert config.api_base_url == "https://api-content.ausha.co/v1"


def test_shows_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = Config(
        interval_minutes=30,
        dry_run=True,
        shows=[
            ShowFolder(
                show_id=1,
                show_name="Mars Attack",
                folder="D:/Podcasts/Mars",
                baseline_folder="D:/Podcasts/Mars",
                rules=[
                    KeywordRule(keyword="BONUS", playlist_id=9, playlist_name="Bonus"),
                    KeywordRule(
                        keyword="MARS",
                        playlist_id=7,
                        playlist_name="Saison 3",
                        image_path="C:/img.png",
                        description_template="Nouvel épisode",
                    ),
                ],
            ),
            ShowFolder(show_id=2, show_name="Silicon Talk", folder="E:/Silicon"),
        ],
    )
    save_config(config, path)
    assert load_config(path) == config
    assert "watch_folder" not in path.read_text(encoding="utf-8")


def test_v1_config_is_converted(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        """{
      "watch_folder": "D:/Podcasts", "baseline_folder": "D:/Podcasts", "interval_minutes": 30,
      "rules": [
        {"keyword": "MARS ATTACK", "show_id": 1, "show_name": "Mars Attack", "playlist_id": 7, "playlist_name": "Saison 3",
         "image_path": "C:/mars.png", "description_template": "Nouvel épisode"},
        {"keyword": "LE DEBRIEF", "show_id": 2, "show_name": "Silicon Talk"},
        {"keyword": "MARS BONUS", "show_id": 1, "show_name": "Mars Attack", "playlist_id": 9}
      ]}""",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.interval_minutes == 30
    assert [s.show_id for s in config.shows] == [1, 2]
    mars, silicon = config.shows
    assert (mars.show_name, mars.folder, mars.baseline_folder) == ("Mars Attack", "D:/Podcasts", "D:/Podcasts")
    assert [r.keyword for r in mars.rules] == ["MARS ATTACK", "MARS BONUS"]
    assert mars.rules[0] == KeywordRule(
        keyword="MARS ATTACK",
        playlist_id=7,
        playlist_name="Saison 3",
        image_path="C:/mars.png",
        description_template="Nouvel épisode",
    )
    assert silicon.rules == [KeywordRule(keyword="LE DEBRIEF")]
    assert not mars.needs_baseline()


def test_v1_config_without_rules_gives_no_show(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"watch_folder": "D:/Podcasts", "rules": []}', encoding="utf-8")
    assert load_config(path).shows == []


def test_v1_config_with_pending_baseline_keeps_it_per_show(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"watch_folder": "D:/Podcasts", "baseline_folder": "C:/Ancien", "rules": [{"keyword": "A", "show_id": 1}]}',
        encoding="utf-8",
    )
    (show,) = load_config(path).shows
    assert show.needs_baseline()


def test_invalid_v1_rules_are_skipped_individually(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"watch_folder": "D:/P", "rules": [1, {"keyword": "A", "show_id": 1}, {"keyword": "B"}]}),
        encoding="utf-8",
    )
    (show,) = load_config(path).shows
    assert show.rules == [KeywordRule(keyword="A")]


def test_shows_key_wins_over_legacy_rules(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"shows": [{"show_id": 3, "folder": "F:/A"}], "watch_folder": "D:/P", "rules": [{"keyword": "A", "show_id": 1}]}',
        encoding="utf-8",
    )
    assert [s.show_id for s in load_config(path).shows] == [3]


def test_invalid_shows_and_keywords_are_skipped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"shows": [1, {"show_name": "x"}, {"show_id": 3, "folder": "F:/A", '
        '"rules": [{"keyword": "OK"}, {"keyword": 5}, "bad"]}]}',
        encoding="utf-8",
    )
    (show,) = load_config(path).shows
    assert show.show_id == 3 and [r.keyword for r in show.rules] == ["OK"]


def test_invalid_show_fields_skip_the_show_and_invalid_keyword_fields_skip_the_keyword(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"shows": [
            {"show_id": True},
            {"show_id": 1, "folder": 3},
            {"show_id": 2, "rules": [{"keyword": "A", "playlist_id": "x"}, {"keyword": "B", "playlist_name": 4},
                                     {"keyword": "C", "playlist_id": None}]},
        ]}),
        encoding="utf-8",
    )
    (show,) = load_config(path).shows
    assert show.show_id == 2 and [r.keyword for r in show.rules] == ["C"]


def test_needs_baseline_and_same_folder():
    assert same_folder("D:\\Podcasts\\Mars", "d:/podcasts/mars/")
    assert not same_folder("D:/A", "")
    assert not same_folder("", "")
    assert ShowFolder(show_id=1, folder="D:/A").needs_baseline()
    assert not ShowFolder(show_id=1, folder="D:/A", baseline_folder="d:\\a").needs_baseline()
    assert not ShowFolder(show_id=1, folder="").needs_baseline()


def test_folder_key_ignores_case_separators_and_trailing_slash():
    assert folder_key(r"D:\Podcasts\Mars") ==folder_key("d:/podcasts/mars/") == folder_key("D:/Podcasts/./Mars")
    assert folder_key("D:/Podcasts/Mars") != folder_key("D:/Podcasts/Mars 2")


def test_show_label_is_its_name_or_a_translatable_fallback():
    assert ShowFolder(show_id=1, show_name="Mars Attack").label() == "Mars Attack"
    unnamed = ShowFolder(show_id=12).label()
    assert unnamed == msg("shows_fallback_name", id=12)
    assert render(unnamed, lang="en") == "Show 12"
    assert render(unnamed, lang="fr") == "Émission 12"


def test_interval_is_clamped():
    assert Config(interval_minutes=1).interval_minutes == 5
    assert Config(interval_minutes=500).interval_minutes == 120


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"future": 1, "shows": [{"show_id": 1, "folder": "X", "extra": 2,'
        ' "rules": [{"keyword": "A", "extra": true}]}]}',
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.shows == [ShowFolder(show_id=1, folder="X", rules=[KeywordRule(keyword="A")])]


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{pas du json", encoding="utf-8")
    assert load_config(path) == Config()


def test_bom_file_loads(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b"\xef\xbb\xbf" + '{"shows": [{"show_id": 1, "folder": "D:/Podcasts"}]}'.encode("utf-8"))
    config = load_config(path)
    assert config.shows == [ShowFolder(show_id=1, folder="D:/Podcasts")]


def test_top_level_list_gives_defaults_and_quarantines_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    config = load_config(path)
    assert config == Config()
    assert not path.exists()
    assert (tmp_path / "config.json.illisible").exists()


def test_wrong_type_field_keeps_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"paused": "false", "api_base_url": 3}', encoding="utf-8")
    config = load_config(path)
    assert config.paused is False
    assert config.api_base_url == cfg.DEFAULT_API_BASE_URL


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


def test_language_roundtrip_and_validation(tmp_path):
    path = tmp_path / "config.json"
    save_config(Config(language="ar"), path)
    assert load_config(path).language == "ar"
    path.write_text('{"language": "de"}', encoding="utf-8")
    assert load_config(path).language == ""
    path.write_text('{"language": 3}', encoding="utf-8")
    assert load_config(path).language == ""
    assert Config().language == ""


def test_unchosen_language_is_kept_without_warning(tmp_path, caplog):
    path = tmp_path / "config.json"
    save_config(Config(), path)  # language "" : pas encore choisie, écrite telle quelle
    with caplog.at_level(logging.WARNING, logger="syncausha.config"):
        assert load_config(path).language == ""
    assert caplog.records == []
