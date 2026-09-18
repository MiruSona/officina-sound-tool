"""make.py 의 순수 함수 시험. rfxgen 없이 돈다."""

import math
import struct
import wave
from pathlib import Path

import pytest

from soundtool.sfx import make

SR = 44100
_MAX_INT16 = 32767


def write_sine_wav(path, amp, seconds=0.1, freq=1000):
    frames = int(SR * seconds)
    samples = [int(amp * _MAX_INT16 * math.sin(2 * math.pi * freq * i / SR)) for i in range(frames)]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", v) for v in samples))
    return path


def read_ints(path):
    with wave.open(str(path), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
    return struct.unpack(f"<{len(raw) // 2}h", raw)


@pytest.mark.parametrize("amp", [0.05, 0.5, 1.0])
def test_normalize_hits_target_peak(tmp_path, amp):
    path = write_sine_wav(tmp_path / "sound.wav", amp)
    make.normalize(path, -1.0)

    ints = read_ints(path)
    peak = max(abs(v) for v in ints)
    peak_dbfs = 20.0 * math.log10(peak / _MAX_INT16)
    assert peak_dbfs == pytest.approx(-1.0, abs=0.15)
    assert peak <= _MAX_INT16


def test_normalize_silence_keeps_gain_one(tmp_path):
    path = write_sine_wav(tmp_path / "silence.wav", amp=0.0)
    gain = make.normalize(path, -1.0)
    assert gain == 1.0


def test_make_one_reports_a_broken_wav_instead_of_raising(tmp_path, monkeypatch):
    """구운 WAV 가 깨졌어도 예외를 안 던지고 실패로 돌아온다 (나머지 소리는 계속 굽는다)."""
    def fake_burn(rfx_bytes, wav_path, rfxgen):
        Path(wav_path).write_bytes(b"")

    monkeypatch.setattr(make, "burn", fake_burn)
    result = make.make_one({"name": "a", "preset": "coin", "seed": 1},
                           tmp_path / "out", tmp_path / "rfxgen.exe")
    assert result.ok is False
    assert result.reasons
