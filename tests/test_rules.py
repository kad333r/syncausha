from pathlib import Path

import pytest
from PIL import Image

from syncausha.config import KeywordRule, Rule, ShowFolder
from syncausha.i18n import render
from syncausha.rules import (
    episode_description,
    episode_title,
    find_match,
    validate_image,
    validate_rule,
)

MARS = ShowFolder(
    show_id=1,
    show_name="Mars Attack",
    folder="D:/P",
    rules=[
        KeywordRule("BONUS", playlist_id=9, playlist_name="Bonus"),
        KeywordRule(
            "MARS ATTACK",
            playlist_id=7,
            playlist_name="Saison 3",
            image_path="C:/m.png",
            description_template="Nouvel épisode",
        ),
    ],
)
SILICON = ShowFolder(show_id=2, show_name="Silicon Talk", folder="D:/P", rules=[KeywordRule("LE DEBRIEF")])


def show_with(keyword: str, show_id: int = 1) -> ShowFolder:
    return ShowFolder(show_id=show_id, folder="D:/P", rules=[KeywordRule(keyword)])


def test_match_builds_effective_rule():
    rule = find_match("MARS ATTACK - Épisode 12.mp3", [MARS, SILICON])
    assert rule == Rule(
        keyword="MARS ATTACK",
        show_id=1,
        show_name="Mars Attack",
        playlist_id=7,
        playlist_name="Saison 3",
        image_path="C:/m.png",
        description_template="Nouvel épisode",
    )


def test_keyword_order_and_show_order():
    assert find_match("MARS ATTACK BONUS 3.mp3", [MARS]).playlist_id == 9
    other = ShowFolder(show_id=5, show_name="Autre", folder="D:/P", rules=[KeywordRule("MARS")])
    assert find_match("MARS ATTACK 1.mp3", [other, MARS]).show_id == 5
    assert find_match("MARS ATTACK 1.mp3", [MARS, other]).show_id == 1


def test_keyword_is_required():
    assert find_match("Episode 12.mp3", [MARS, SILICON]) is None
    assert find_match("x.mp3", [ShowFolder(show_id=1, folder="D:/P")]) is None


def test_match_ignores_case_accents_and_punctuation():
    assert find_match("le_debrief-44.mp3", [SILICON]).show_id == 2


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
    assert find_match(filename, [MARS]).keyword == "MARS ATTACK"


def test_accents_are_ignored():
    assert find_match("LE DEBRIEF 44.mp3", [show_with("Le Débrief", 2)]).show_id == 2


def test_oe_ligature_matches_oe_keyword():
    assert find_match("Cœur de pirate 3.mp3", [show_with("coeur")]) is not None


def test_curly_apostrophe_matches_straight_keyword():
    assert find_match("L’Heure bleue.mp3", [show_with("L'Heure")]) is not None


def test_en_dash_matches_space_separated_keyword():
    assert find_match("MARS–ATTACK 2.mp3", [show_with("MARS ATTACK")]) is not None


def test_no_match_returns_none():
    assert find_match("interview_brut.mp3", [MARS, SILICON]) is None


def test_empty_keyword_never_matches():
    assert find_match("x.mp3", [show_with("  ")]) is None


def test_extension_is_not_part_of_match():
    assert find_match("episode.mp3", [show_with("mp3")]) is None


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
    assert "introuvable" in render(validate_image(tmp_path / "nope.png"), lang="fr")


def test_small_image(tmp_path):
    assert render(validate_image(make_image(tmp_path / "s.png", (300, 300))), lang="fr") == "Image trop petite (300×300, minimum 400×400)"


def test_wrong_format(tmp_path):
    assert "JPEG ou PNG" in render(validate_image(make_image(tmp_path / "a.gif", fmt="GIF")), lang="fr")


def test_not_an_image(tmp_path):
    path = tmp_path / "x.png"
    path.write_bytes(b"pas une image")
    assert render(validate_image(path), lang="fr") == "Image illisible"


def test_too_heavy(tmp_path, monkeypatch):
    monkeypatch.setattr("syncausha.rules.MAX_IMAGE_BYTES", 10)
    assert "trop lourde" in render(validate_image(make_image(tmp_path / "a.png")), lang="fr")


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
    assert render(validate_image(path), lang="fr") == "Image illisible"


def test_validate_rule_checks_show_playlist_and_image(tmp_path):
    rule = Rule(keyword="A", show_id=1, show_name="Mars", playlist_id=7, playlist_name="S3")
    assert validate_rule(rule, {1: {7}}) is None
    assert render(validate_rule(rule, {2: set()}), lang="fr") == "Émission introuvable sur Ausha : Mars"
    assert render(validate_rule(rule, {1: {8}}), lang="fr") == "Playlist introuvable sur Ausha : S3"
    rule.image_path = str(tmp_path / "missing.png")
    assert "Image introuvable" in render(validate_rule(rule, {1: {7}}), lang="fr")


def test_rule_without_playlist_or_image_is_valid():
    assert validate_rule(Rule(keyword="A", show_id=1), {1: set()}) is None


def test_validation_messages_are_translatable(tmp_path):
    problem = validate_rule(Rule(keyword="A", show_id=1, show_name="Mars"), {2: set()})
    assert render(problem, lang="en") == "Show not found on Ausha: Mars"
    assert render(problem, lang="fr") == "Émission introuvable sur Ausha : Mars"
    assert render(problem, lang="ar") == "البرنامج غير موجود على Ausha: \u2068Mars\u2069"  # nom isolé
    small = validate_image(make_image(tmp_path / "s.png", (300, 200)))
    assert render(small, lang="en") == "Cover image too small (300×200, minimum 400×400)"
