"""BGM CLI — 종료 코드와 산출물."""

import json
from pathlib import Path

import pytest

from soundtool import cli, config, manifest as manifest_mod
from soundtool.bgm import cli as bgm_cli
from soundtool.bgm import render as render_mod

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE / "spec_bgm_example.json"


def has_tools():
    try:
        render_mod.find_tools()
    except render_mod.ToolsMissing:
        return False
    return True


needs_tools = pytest.mark.skipif(not has_tools(), reason="fluidsynth 나 사운드폰트가 없다")


def write_spec(tmp_path, songs):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"version": 1, "songs": songs}), encoding="utf-8")
    return path


def test_bgm_without_command_is_usage(capsys):
    assert cli.main(["bgm"]) == config.EXIT_USAGE
    assert "make" in capsys.readouterr().out


def test_presets_table(capsys):
    assert cli.main(["bgm", "presets"]) == config.EXIT_OK
    out = capsys.readouterr().out
    assert "town" in out and "ambient" in out and "bVII" in out


def test_presets_json(capsys):
    assert cli.main(["bgm", "presets", "--json"]) == config.EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert len(data["styles"]) == 6
    assert data["schema"]["title"]
    assert "phrygian" in data["modes"]


def test_bad_spec_exits_one(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "BAD NAME", "style": "nope"}])
    assert cli.main(["bgm", "make", str(spec), "--out", str(tmp_path / "out")]) == config.EXIT_FAIL
    assert "스펙이 어긋났다" in capsys.readouterr().out


def test_missing_fluidsynth_exits_three(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "a", "style": "town"}])
    code = cli.main(["bgm", "make", str(spec), "--out", str(tmp_path / "out"),
                     "--fluidsynth", str(tmp_path / "없다.exe")])
    assert code == config.EXIT_NO_RFXGEN
    assert "못 찾았다" in capsys.readouterr().out


def test_midi_only_needs_no_fluidsynth(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "a", "style": "town", "seed": 3}])
    out = tmp_path / "out"
    code = cli.main(["bgm", "make", str(spec), "--out", str(out),
                     "--fluidsynth", str(tmp_path / "없다.exe"), "--midi-only"])
    assert code == config.EXIT_OK
    assert (out / "a.mid").is_file()
    assert not (out / config.MANIFEST_NAME).exists()
    assert "--midi-only" in capsys.readouterr().out


def test_example_spec_is_valid():
    from soundtool.bgm import spec as spec_mod
    assert spec_mod.validate(json.loads(EXAMPLE.read_text(encoding="utf-8"))) == []


@needs_tools
def test_make_writes_wav_midi_and_manifest(tmp_path, capsys):
    spec = write_spec(tmp_path, [
        {"name": "town_market", "style": "town", "seed": 1041, "tags": ["town", "day"],
         "bars": 4},
    ])
    out = tmp_path / "out"
    assert cli.main(["bgm", "make", str(spec), "--out", str(out)]) == config.EXIT_OK
    capsys.readouterr()

    assert (out / "town_market.wav").is_file()
    assert (out / "town_market.mid").is_file()
    data = manifest_mod.read(out / config.MANIFEST_NAME)
    assert data["kinds"]["bgm"]["channels"] == 2
    assert data["kinds"]["bgm"]["sample_rate"] == 44100
    row = data["items"][0]
    assert list(row)[:6] == ["name", "file", "kind", "tags", "seconds", "seed"]
    assert row["kind"] == "bgm"
    assert row["style"] == "town"
    assert row["midi"] == "town_market.mid"
    assert row["gain"] == config.FLUIDSYNTH_GAIN


@needs_tools
def test_check_command_reruns_the_same_checks(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "a", "style": "town", "seed": 5, "bars": 4}])
    out = tmp_path / "out"
    cli.main(["bgm", "make", str(spec), "--out", str(out)])
    capsys.readouterr()
    assert cli.main(["bgm", "check", str(out)]) == config.EXIT_OK
    assert "통과" in capsys.readouterr().out


@needs_tools
def test_check_catches_a_broken_wav(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "a", "style": "town", "seed": 5, "bars": 4}])
    out = tmp_path / "out"
    cli.main(["bgm", "make", str(spec), "--out", str(out)])
    render_mod.trim(out / "a.wav", 44100)      # 1초로 잘라 길이를 깨뜨린다
    capsys.readouterr()
    assert cli.main(["bgm", "check", str(out)]) == config.EXIT_FAIL
    assert "길이" in capsys.readouterr().out


def test_check_without_manifest(tmp_path, capsys):
    assert cli.main(["bgm", "check", str(tmp_path)]) == config.EXIT_FAIL
    assert "manifest 를 못 찾았다" in capsys.readouterr().out


def test_song_from_manifest_round_trip():
    row = {"name": "a", "file": "a.wav", "kind": "bgm", "tags": [], "seconds": 8.0, "seed": 1,
           "midi": "a.mid", "style": "town", "bpm": 120, "key": "C", "mode": "major",
           "bars": 4, "loop": True, "gain": 1.2, "tracks": ["bass", "melody"]}
    song = bgm_cli.song_from_manifest(row)
    assert song.loop is True
    assert song.tracks["bass"].on is True
    assert song.tracks["drums"].on is False
    assert song.seconds == pytest.approx(8.0)
