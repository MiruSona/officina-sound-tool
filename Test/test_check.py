"""검수 판정 시험. 손으로 만든 파형을 쓴다. rfxgen 없이 돈다."""

import math
import struct
import wave

import pytest

from soundtool.sfx import check, presets

SR = 44100


def write_wav(path, ints):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", v) for v in ints))
    return path


def sine_ints(freq, frames, amp):
    return [int(amp * 32767 * math.sin(2 * math.pi * freq * i / SR)) for i in range(frames)]


def good_wav(tmp_path, frames=8000, freq=3000):
    # 피크가 -1.0 dBFS 가 되게 만든다 (정규화 뒤 모습)
    amp = 10 ** (-1.0 / 20.0)
    return write_wav(tmp_path / "good.wav", sine_ints(freq, frames, amp))


def base_expect(frames=8000):
    return {"frames": frames - 3, "centroid_hz": (1000.0, 12000.0)}


def test_good_wav_passes(tmp_path):
    metrics = check.measure(good_wav(tmp_path))
    assert check.check(metrics, base_expect()) == []


def test_metrics_values(tmp_path):
    metrics = check.measure(good_wav(tmp_path))
    assert metrics.frames == 8000
    assert metrics.seconds == pytest.approx(8000 / SR)
    assert metrics.peak_dbfs == pytest.approx(-1.0, abs=0.05)
    assert metrics.centroid_hz == pytest.approx(3000, rel=0.1)
    assert metrics.lead_seconds == pytest.approx(0.0, abs=0.001)


def test_silence_fails(tmp_path):
    path = write_wav(tmp_path / "quiet.wav", [0] * 8000)
    reasons = check.check(check.measure(path), base_expect())
    assert any("RMS" in r for r in reasons)


def test_wrong_frames_fails(tmp_path):
    path = write_wav(tmp_path / "short.wav", sine_ints(3000, 3, 0.9))
    reasons = check.check(check.measure(path), base_expect())
    assert any("프레임" in r for r in reasons)


def test_frames_tolerance(tmp_path):
    metrics = check.measure(good_wav(tmp_path))
    assert check.check(metrics, {"frames": 8000 - 3 + 10}) == []
    assert check.check(metrics, {"frames": 8000 - 3 + 200}) != []


def test_peak_off_target_fails(tmp_path):
    path = write_wav(tmp_path / "loud.wav", sine_ints(3000, 8000, 1.0))
    reasons = check.check(check.measure(path), base_expect())
    assert any("피크" in r for r in reasons)


def test_clipping_fails(tmp_path):
    amp = 10 ** (-1.0 / 20.0)
    ints = sine_ints(3000, 8000, amp)
    ints[100:106] = [32767] * 6
    path = write_wav(tmp_path / "clip.wav", ints)
    reasons = check.check(check.measure(path), base_expect())
    assert any("클리핑" in r for r in reasons)


def test_dc_offset_fails(tmp_path):
    amp = 10 ** (-1.0 / 20.0)
    shift = int(0.2 * 32767)
    ints = [min(32767, v // 2 + shift) for v in sine_ints(3000, 8000, amp)]
    path = write_wav(tmp_path / "dc.wav", ints)
    reasons = check.check(check.measure(path), base_expect())
    assert any("DC" in r for r in reasons)


def test_lead_silence_fails(tmp_path):
    amp = 10 ** (-1.0 / 20.0)
    ints = [0] * 4000 + sine_ints(3000, 8000, amp)
    path = write_wav(tmp_path / "lead.wav", ints)
    reasons = check.check(check.measure(path), {"frames": len(ints) - 3})
    assert any("앞머리" in r for r in reasons)


def test_centroid_out_of_range_fails(tmp_path):
    metrics = check.measure(good_wav(tmp_path))
    reasons = check.check(metrics, {"frames": 7997, "centroid_hz": (8000.0, 12000.0)})
    assert any("centroid" in r for r in reasons)


def test_skip_silences_a_check(tmp_path):
    path = write_wav(tmp_path / "quiet.wav", [0] * 8000)
    expect = dict(base_expect())
    expect["skip"] = ["rms", "peak", "lead", "centroid"]
    assert check.check(check.measure(path), expect) == []


def test_seconds_limits(tmp_path):
    metrics = check.measure(good_wav(tmp_path))
    expect = dict(base_expect())
    expect["max_seconds"] = 0.05
    assert any("max_seconds" in r for r in check.check(metrics, expect))
    expect = dict(base_expect())
    expect["min_seconds"] = 5.0
    assert any("min_seconds" in r for r in check.check(metrics, expect))


def test_clip_run_from_expect_wins(tmp_path):
    # 정규화 전 파형에서 잰 값을 넘겨주면 그것으로 판정한다
    metrics = check.measure(good_wav(tmp_path))
    reasons = check.check(metrics, {"frames": 7997, "clip_run": 9})
    assert any("클리핑" in r for r in reasons)


def test_short_sound_skips_centroid(tmp_path):
    amp = 10 ** (-1.0 / 20.0)
    path = write_wav(tmp_path / "tiny.wav", sine_ints(3000, 500, amp))
    metrics = check.measure(path)
    assert metrics.centroid_hz == 0.0
    reasons = check.check(metrics, {"frames": 497, "centroid_hz": (5000.0, 6000.0)})
    assert not any("centroid" in r for r in reasons)


def test_check_names_cover_thresholds():
    assert set(check.CHECK_NAMES) == {"frames", "rms", "peak", "clip", "lead", "dc", "centroid"}
    assert set(check.CENTROID_HZ) == set(presets.PRESET_NAMES)
