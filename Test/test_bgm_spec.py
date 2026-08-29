"""스펙 검사와 기본값 채우기."""

import json

import pytest

from soundtool.bgm import patterns, spec as spec_mod, theory

GOOD = [
    {"name": "town_market", "style": "town", "tags": ["town", "day"], "seed": 1041},
    {"name": "boss_1", "style": "battle", "key": "A", "mode": "minor", "bpm": 152,
     "bars": 32, "seed": 7, "progression": ["i", "VI", "III", "VII"]},
    {"name": "cave", "style": "dungeon"},
    {"name": "title-screen", "style": "title", "loop": False},
    {"name": "win", "style": "victory", "bars": 8},
    {"name": "calm", "style": "ambient", "tracks": {"melody": {"on": False},
                                                    "bass": {"program": 39, "octave": -1}}},
]

BAD = [
    ({"name": "BAD NAME", "style": "town"}, "규칙"),
    ({"name": "ok", "style": "nope"}, "못 쓴다"),
    ({"style": "town"}, "name"),
    ({"name": "ok"}, "style"),
    ({"name": "ok", "style": "town", "bpm": 300}, "240"),
    ({"name": "ok", "style": "town", "bars": 6}, "배수"),
    ({"name": "ok", "style": "town", "bars": 100}, "64"),
    ({"name": "ok", "style": "town", "key": "H"}, "못 쓴다"),
    ({"name": "ok", "style": "town", "mode": "lydian"}, "못 쓴다"),
    ({"name": "ok", "style": "town", "seed": -1}, "작다"),
    ({"name": "ok", "style": "town", "progression": ["I"]}, "2개는"),
    ({"name": "ok", "style": "town", "progression": ["I", "Q"]}, "못 쓴다"),
    ({"name": "ok", "style": "town", "loop": "yes"}, "참거짓"),
    ({"name": "ok", "style": "town", "몰라": 1}, "모르는 열쇠"),
    ({"name": "ok", "style": "town", "tracks": {"drums": {"program": 200}}}, "127"),
    ({"name": "ok", "style": "ambient", "tracks": {"drums": {"on": True}}}, "패턴이 없다"),
]


def wrap(song):
    return {"version": 1, "songs": [song]}


@pytest.mark.parametrize("song", GOOD)
def test_good_specs_pass(song):
    assert spec_mod.validate(wrap(song)) == []


@pytest.mark.parametrize("song,word", BAD)
def test_bad_specs_are_caught(song, word):
    problems = spec_mod.validate(wrap(song))
    assert problems, f"안 걸렸다 : {song}"
    assert any(word in line for line in problems), problems


def test_duplicate_names_are_caught():
    spec = {"version": 1, "songs": [{"name": "a", "style": "town"},
                                    {"name": "a", "style": "battle"}]}
    assert any("겹친다" in line for line in spec_mod.validate(spec))


def test_defaults_come_from_preset():
    song = spec_mod.build_song({"name": "cave", "style": "dungeon"})
    preset = patterns.STYLES["dungeon"]
    assert song.key == preset.key
    assert song.mode == preset.mode
    assert song.bars == preset.bars
    assert song.loop is preset.loop
    assert preset.bpm_range[0] <= song.bpm <= preset.bpm_range[1]
    assert list(song.progression) in [list(p) for p in preset.progressions]


def test_seed_defaults_to_name_hash():
    first = spec_mod.build_song({"name": "town_market", "style": "town"})
    second = spec_mod.build_song({"name": "town_market", "style": "town"})
    assert first.seed == second.seed == spec_mod.default_seed("town_market")
    assert 0 <= first.seed <= 2147483647


def test_seconds_and_beats():
    song = spec_mod.build_song({"name": "a", "style": "town", "bpm": 120, "bars": 16})
    assert song.beats == 64
    assert song.seconds == pytest.approx(32.0)


def test_schema_and_code_agree():
    """스키마 파일과 코드 표가 어긋나지 않았나."""
    props = spec_mod.SCHEMA["properties"]["songs"]["items"]["properties"]
    assert set(props["style"]["enum"]) == set(patterns.STYLE_NAMES)
    assert set(props["mode"]["enum"]) == set(theory.MODE_STEPS)
    assert tuple(props["key"]["enum"]) == theory.KEY_NAMES
    assert set(props["progression"]["items"]["enum"]) == set(theory.ROMAN_NAMES)
    assert set(props["tracks"]["properties"]) == set(spec_mod.ROLES)


def test_load_reports_broken_json(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(spec_mod.SpecError):
        spec_mod.load(path)


def test_load_spec_returns_songs(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"version": 1, "songs": GOOD[:2]}), encoding="utf-8")
    songs = spec_mod.load_spec(path)
    assert [s.name for s in songs] == ["town_market", "boss_1"]
