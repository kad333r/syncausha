from pathlib import Path

import pytest
from PIL import Image

from syncausha.config import Rule
from syncausha.rules import (
    episode_description,
    episode_title,
    find_rule,
    validate_image,
    validate_rule,
)

MARS = Rule(keyword="MARS ATTACK", show_id=1, show_name="Mars Attack")
DEBRIEF = Rule(keyword="Le Débrief", show_id=2)


@pytest.mark.parametrize(
    "filename",
    [
        "MARS ATTACK - Épisode 12.mp3",
        "mars attack 12.mp3",
        "Mars_Attack_ep12.wav",
        "Replay MARS-ATTACK.m4a",
    ],
)
def test_keyword_matches_ignoring_case_and_separators(filename):
    assert find_rule(filename, [MARS]) is MARS


def test_accents_are_ignored():
    assert find_rule("LE DEBRIEF 44.mp3", [DEBRIEF]) is DEBRIEF


def test_oe_ligature_matches_oe_keyword():
    rule = Rule(keyword="coeur", show_id=1)
    assert find_rule("Cœur de pirate 3.mp3", [rule]) is rule


def test_curly_apostrophe_matches_straight_keyword():
    rule = Rule(keyword="L'Heure", show_id=1)
    assert find_rule("L’Heure bleue.mp3", [rule]) is rule


def test_en_dash_matches_space_separated_keyword():
    rule = Rule(keyword="MARS ATTACK", show_id=1)
    assert find_rule("MARS–ATTACK 2.mp3", [rule]) is rule


def test_first_matching_rule_wins():
    generic = Rule(keyword="ATTACK", show_id=9)
    assert find_rule("MARS ATTACK 1.mp3", [generic, MARS]) is generic
    assert find_rule("MARS ATTACK 1.mp3", [MARS, generic]) is MARS


def test_no_match_returns_none():
    assert find_rule("interview_brut.mp3", [MARS, DEBRIEF]) is None


def test_empty_keyword_never_matches():
    assert find_rule("x.mp3", [Rule(keyword="  ", show_id=1)]) is None


def test_extension_is_not_part_of_match():
    assert find_rule("episode.mp3", [Rule(keyword="mp3", show_id=1)]) is None


def test_episode_title_strips_extension_and_extra_spaces():
    assert episode_title(Path("D:/p/MARS ATTACK  -  Épisode 12.mp3")) == "MARS ATTACK - Épisode 12"


def test_episode_title_is_truncated():
    assert len(episode_title(Path("x" * 200 + ".mp3"))) == 140


def test_episode_title_truncation_strips_trailing_space():
    stem = "x" * 139 + " abc"
    title = episode_title(Path(f"D:/p/{stem}.mp3"))
    assert title == "x" * 139
    assert not title.endswith(" ")


def test_episode_description_from_template():
    assert episode_description(Rule(keyword="A", show_id=1, description_template="  Bonjour \n")) == "Bonjour"
    long_rule = Rule(keyword="A", show_id=1, description_template="y" * 5000)
    assert len(episode_description(long_rule)) == 3900


def make_image(path: Path, size=(1400, 1400), fmt="PNG") -> Path:
    Image.new("RGB", size, "purple").save(path, fmt)
    return path


def test_valid_png_and_jpeg(tmp_path):
    assert validate_image(make_image(tmp_path / "a.png")) is None
    assert validate_image(make_image(tmp_path / "a.jpg", fmt="JPEG")) is None


def test_missing_image(tmp_path):
    assert "introuvable" in validate_image(tmp_path / "nope.png")


def test_small_image(tmp_path):
    assert "trop petite" in validate_image(make_image(tmp_path / "s.png", (300, 300)))


def test_wrong_format(tmp_path):
    assert "JPEG ou PNG" in validate_image(make_image(tmp_path / "a.gif", fmt="GIF"))


def test_not_an_image(tmp_path):
    path = tmp_path / "x.png"
    path.write_bytes(b"pas une image")
    assert validate_image(path) == "Image illisible"


def test_too_heavy(tmp_path, monkeypatch):
    monkeypatch.setattr("syncausha.rules.MAX_IMAGE_BYTES", 10)
    assert "trop lourde" in validate_image(make_image(tmp_path / "a.png"))


def test_mpo_format_is_accepted(tmp_path, monkeypatch):
    """Les JPEG multi-images produits par certains appareils photo sont détectés en MPO par Pillow."""
    path = make_image(tmp_path / "a.jpg", fmt="JPEG")

    class FakeMpoImage:
        format = "MPO"
        size = (1400, 1400)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(Image, "open", lambda p: FakeMpoImage())
    assert validate_image(path) is None


def test_decompression_bomb_is_rejected(tmp_path, monkeypatch):
    path = make_image(tmp_path / "bomb.png")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    assert validate_image(path) == "Image illisible"


def test_validate_rule_checks_show_playlist_and_image(tmp_path):
    rule = Rule(keyword="A", show_id=1, show_name="Mars", playlist_id=7, playlist_name="S3")
    assert validate_rule(rule, {1: {7}}) is None
    assert "Émission introuvable" in validate_rule(rule, {2: set()})
    assert "Playlist introuvable" in validate_rule(rule, {1: {8}})
    rule.image_path = str(tmp_path / "missing.png")
    assert "Image introuvable" in validate_rule(rule, {1: {7}})


def test_rule_without_playlist_or_image_is_valid():
    assert validate_rule(Rule(keyword="A", show_id=1), {1: set()}) is None
