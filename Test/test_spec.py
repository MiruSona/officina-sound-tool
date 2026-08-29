"""스펙 검사 시험. rfxgen 없이 돈다."""

import json

import pytest

from soundtool.sfx import presets, rfx, spec

GOOD = {
    "version": 1,
    "sounds": [
        {"name": "ui_click", "preset": "blip", "seed": 1001, "tags": ["ui", "click"]},
        {"name": "boss_boom", "preset": "explosion", "seed": 3003,
         "params": {"decay_time": 0.9, "lpf_cutoff": 0.7},
         "check": {"max_seconds": 1.5}},
    ],
}


def test_good_spec_passes():
    assert spec.validate(GOOD) == []


def test_schema_enum_matches_presets():
    sound = spec.SCHEMA["properties"]["sounds"]["items"]
    assert tuple(sound["properties"]["preset"]["enum"]) == presets.PRESET_NAMES


def test_schema_params_match_rfx_fields():
    sound = spec.SCHEMA["properties"]["sounds"]["items"]
    assert set(sound["properties"]["params"]["properties"]) == set(rfx.FIELD_NAMES)


def _one(sound):
    return {"version": 1, "sounds": [sound]}


BAD_CASES = [
    ("필수 열쇠 없음", {"preset": "coin", "seed": 1}),
    ("이름 규칙 어김", {"name": "UI Click", "preset": "coin", "seed": 1}),
    ("모르는 프리셋", {"name": "ok_name", "preset": "meow", "seed": 1}),
    ("seed 범위 밖", {"name": "ok_name", "preset": "coin", "seed": -5}),
    ("params 범위 밖", {"name": "ok_name", "preset": "coin", "seed": 1,
                        "params": {"lpf_cutoff": 1.4}}),
    ("모르는 params 열쇠", {"name": "ok_name", "preset": "coin", "seed": 1,
                            "params": {"nope": 0.5}}),
]


@pytest.mark.parametrize("label,sound", BAD_CASES, ids=[c[0] for c in BAD_CASES])
def test_bad_specs_are_caught(label, sound):
    problems = spec.validate(_one(sound))
    assert problems, label


def test_duplicate_names_caught():
    doubled = {"version": 1, "sounds": [
        {"name": "same_one", "preset": "coin", "seed": 1},
        {"name": "same_one", "preset": "hit", "seed": 2},
    ]}
    problems = spec.validate(doubled)
    assert any("same_one" in p for p in problems)


def test_empty_sounds_caught():
    assert spec.validate({"version": 1, "sounds": []})


def test_not_an_object_caught():
    assert spec.validate([1, 2, 3])


def test_iter_sounds_fills_defaults():
    sounds = list(spec.iter_sounds(GOOD))
    assert sounds[0]["tags"] == ["ui", "click"]
    assert sounds[0]["params"] == {}
    assert sounds[0]["check"] == {}
    assert sounds[1]["tags"] == []


def test_load_reads_file(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(GOOD), encoding="utf-8")
    assert spec.load(path) == GOOD


def test_load_bad_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(spec.SpecError):
        spec.load(path)


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(spec.SpecError):
        spec.load(tmp_path / "없다.json")


def test_min_greater_than_max_seconds_caught():
    sound = {"name": "ok_name", "preset": "coin", "seed": 1,
             "check": {"min_seconds": 2.0, "max_seconds": 1.0}}
    assert spec.validate(_one(sound))
