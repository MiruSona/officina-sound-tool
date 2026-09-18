"""CLI 와 골든 값 시험. rfxgen 이 있어야 도는 것들은 없으면 건너뛴다."""

import json
import math
import struct
import wave
from pathlib import Path

import pytest

from soundtool import cli, config, manifest as manifest_mod
from soundtool.sfx import make

SR = 44100

HERE = Path(__file__).resolve().parent
GOLDEN = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))

CENTROID_TOLERANCE = 0.05
EXPLOSION_TOLERANCE = 0.15   # 노이즈라 다른 OS·libc 에서 값이 달라질 수 있다


def has_rfxgen():
    try:
        make.find_rfxgen()
    except make.RfxgenMissing:
        return False
    return True


needs_rfxgen = pytest.mark.skipif(not has_rfxgen(), reason="rfxgen.exe 가 없다")


def write_sine_wav(path, seconds=0.2, freq=1000, channels=1):
    """rfxgen 없이 check 를 시험하려고 직접 만드는 WAV."""
    frames = int(SR * seconds)
    amp = 10 ** (-1.0 / 20.0) * 32767
    samples = [int(amp * math.sin(2 * math.pi * freq * i / SR)) for i in range(frames)]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(SR)
        if channels == 1:
            w.writeframes(b"".join(struct.pack("<h", v) for v in samples))
        else:
            w.writeframes(b"".join(struct.pack("<hh", v, v) for v in samples))
    return path


def write_spec(tmp_path, sounds):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"version": 1, "sounds": sounds}), encoding="utf-8")
    return path


def golden_spec():
    sounds = []
    for preset, rows in GOLDEN["presets"].items():
        for seed in rows:
            sounds.append({"name": f"g_{preset}_{seed}", "preset": preset, "seed": int(seed)})
    return sounds


def test_no_args_prints_usage(capsys):
    assert cli.main([]) == config.EXIT_USAGE
    assert "usage" in capsys.readouterr().out.lower()


def test_sfx_without_command_is_usage(capsys):
    assert cli.main(["sfx"]) == config.EXIT_USAGE
    assert "make" in capsys.readouterr().out


def test_presets_command(capsys):
    assert cli.main(["sfx", "presets"]) == config.EXIT_OK
    out = capsys.readouterr().out
    assert "coin" in out and "explosion" in out


def test_presets_json(capsys):
    assert cli.main(["sfx", "presets", "--json"]) == config.EXIT_OK
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 7
    assert rows[0]["centroid_hz"][0] > 0


def test_bad_spec_exits_one(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "BAD NAME", "preset": "nope", "seed": -1}])
    code = cli.main(["sfx", "make", str(spec), "--out", str(tmp_path / "out")])
    assert code == config.EXIT_FAIL
    assert "스펙이 어긋났다" in capsys.readouterr().out


def test_missing_rfxgen_exits_three(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "ui_click", "preset": "blip", "seed": 1}])
    code = cli.main(["sfx", "make", str(spec), "--out", str(tmp_path / "out"),
                     "--rfxgen", str(tmp_path / "없다.exe")])
    assert code == config.EXIT_NO_RFXGEN
    assert "못 찾았다" in capsys.readouterr().out


def test_dry_run_needs_no_rfxgen(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "ui_click", "preset": "blip", "seed": 1}])
    code = cli.main(["sfx", "make", str(spec), "--out", str(tmp_path / "out"),
                     "--rfxgen", str(tmp_path / "없다.exe"), "--dry-run"])
    assert code == config.EXIT_OK
    assert "기대 프레임" in capsys.readouterr().out


@needs_rfxgen
def test_make_writes_wav_and_manifest(tmp_path, capsys):
    spec = write_spec(tmp_path, [
        {"name": "ui_click", "preset": "blip", "seed": 1001, "tags": ["ui", "click"]},
        {"name": "coin_pickup", "preset": "coin", "seed": 2002, "tags": ["item"]},
    ])
    out = tmp_path / "out"
    assert cli.main(["sfx", "make", str(spec), "--out", str(out)]) == config.EXIT_OK
    capsys.readouterr()

    assert (out / "ui_click.wav").is_file()
    data = manifest_mod.read(out / config.MANIFEST_NAME)
    assert data["version"] == config.MANIFEST_VERSION
    assert data["kinds"]["sfx"]["sample_rate"] == 44100
    assert data["kinds"]["sfx"]["channels"] == 1
    assert len(data["items"]) == 2
    row = data["items"][0]
    assert list(row)[:6] == ["name", "file", "kind", "tags", "seconds", "seed"]
    assert row["kind"] == "sfx"
    assert row["preset"] == "blip"


@needs_rfxgen
def test_make_is_repeatable(tmp_path):
    spec = write_spec(tmp_path, [{"name": "ui_click", "preset": "blip", "seed": 1001}])
    first = tmp_path / "a"
    second = tmp_path / "b"
    cli.main(["sfx", "make", str(spec), "--out", str(first)])
    cli.main(["sfx", "make", str(spec), "--out", str(second)])
    assert (first / "ui_click.wav").read_bytes() == (second / "ui_click.wav").read_bytes()


@needs_rfxgen
def test_failing_sound_exits_one_and_leaves_no_wav(tmp_path, capsys):
    spec = write_spec(tmp_path, [
        {"name": "too_long", "preset": "explosion", "seed": 3003,
         "check": {"max_seconds": 0.01}},
    ])
    out = tmp_path / "out"
    assert cli.main(["sfx", "make", str(spec), "--out", str(out)]) == config.EXIT_FAIL
    assert "max_seconds" in capsys.readouterr().out
    assert not (out / "too_long.wav").exists()
    assert manifest_mod.read(out / config.MANIFEST_NAME)["items"] == []


@needs_rfxgen
def test_keep_failed_puts_wav_aside(tmp_path):
    spec = write_spec(tmp_path, [
        {"name": "too_long", "preset": "explosion", "seed": 3003,
         "check": {"max_seconds": 0.01}},
    ])
    out = tmp_path / "out"
    cli.main(["sfx", "make", str(spec), "--out", str(out), "--keep-failed"])
    assert (out / make.FAILED_DIR / "too_long.wav").is_file()


@needs_rfxgen
def test_check_command_against_manifest(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "ui_click", "preset": "blip", "seed": 1001}])
    out = tmp_path / "out"
    cli.main(["sfx", "make", str(spec), "--out", str(out)])
    capsys.readouterr()
    code = cli.main(["sfx", "check", str(out), "--manifest", str(out / config.MANIFEST_NAME)])
    assert code == config.EXIT_OK
    assert "통과" in capsys.readouterr().out


@needs_rfxgen
def test_check_catches_manifest_mismatch(tmp_path, capsys):
    spec = write_spec(tmp_path, [{"name": "ui_click", "preset": "blip", "seed": 1001}])
    out = tmp_path / "out"
    cli.main(["sfx", "make", str(spec), "--out", str(out)])
    path = out / config.MANIFEST_NAME
    data = manifest_mod.read(path)
    data["items"][0]["frames"] += 500
    manifest_mod.write(data, path)
    capsys.readouterr()
    assert cli.main(["sfx", "check", str(out), "--manifest", str(path)]) == config.EXIT_FAIL


def test_check_missing_target(tmp_path, capsys):
    assert cli.main(["sfx", "check", str(tmp_path / "없다")]) == config.EXIT_FAIL


def test_check_folder_without_manifest(tmp_path, capsys):
    """manifest 없이 폴더만 줘도 잰다. rfxgen 이 필요 없게 사인파 WAV 를 직접 만든다."""
    write_sine_wav(tmp_path / "ok.wav")
    code = cli.main(["sfx", "check", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == config.EXIT_OK
    assert "통과" in out


def test_check_stereo_wav_fails_gracefully_instead_of_crashing(tmp_path, capsys):
    """모노만 지원한다 — 스테레오는 크래시가 아니라 실패 줄로 보고한다."""
    write_sine_wav(tmp_path / "stereo.wav", channels=2)
    code = cli.main(["sfx", "check", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == config.EXIT_FAIL
    assert "실패" in out


def test_check_bad_manifest_reports_failure(tmp_path, capsys):
    write_sine_wav(tmp_path / "ok.wav")
    bad_manifest = tmp_path / "manifest.json"
    bad_manifest.write_text("{ 깨진 json", encoding="utf-8")
    code = cli.main(["sfx", "check", str(tmp_path), "--manifest", str(bad_manifest)])
    assert code == config.EXIT_FAIL
    assert "manifest" in capsys.readouterr().out


@needs_rfxgen
def test_golden_values(tmp_path, capsys):
    spec = write_spec(tmp_path, golden_spec())
    out = tmp_path / "out"
    assert cli.main(["sfx", "make", str(spec), "--out", str(out)]) == config.EXIT_OK
    capsys.readouterr()

    rows = {r["name"]: r for r in manifest_mod.read(out / config.MANIFEST_NAME)["items"]}
    for preset, seeds in GOLDEN["presets"].items():
        for seed, want in seeds.items():
            got = rows[f"g_{preset}_{seed}"]
            assert got["frames"] == want["frames"], f"{preset} {seed} 프레임"
            assert got["peak_dbfs"] == pytest.approx(want["peak_dbfs"], abs=0.15)
            slack = EXPLOSION_TOLERANCE if preset == "explosion" else CENTROID_TOLERANCE
            assert got["centroid_hz"] == pytest.approx(want["centroid_hz"], rel=slack), \
                f"{preset} {seed} centroid"


def test_check_empty_wav_fails_gracefully_instead_of_crashing(tmp_path, capsys):
    """0 바이트 WAV 하나에 트레이스백이 아니라 실패 줄이 나와야 한다."""
    (tmp_path / "empty.wav").write_bytes(b"")
    write_sine_wav(tmp_path / "ok.wav")
    code = cli.main(["sfx", "check", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == config.EXIT_FAIL
    assert "실패" in out and "통과" in out
