"""측정 시험. rfxgen 없이 돈다."""

import math
import struct
import wave

import pytest

from soundtool.sfx import dsp

SR = 44100


def sine(freq, seconds, amp=1.0, sr=SR):
    count = int(sr * seconds)
    return [amp * math.sin(2 * math.pi * freq * i / sr) for i in range(count)]


def test_rms_of_full_sine():
    assert dsp.rms(sine(440, 0.5)) == pytest.approx(0.7071, abs=0.01)


def test_peak_and_dc():
    x = sine(440, 0.2, amp=0.5)
    assert dsp.peak(x) == pytest.approx(0.5, abs=0.01)
    assert dsp.dc(x) == pytest.approx(0.0, abs=0.01)


def test_dc_offset_is_seen():
    x = [v + 0.25 for v in sine(440, 0.2, amp=0.5)]
    assert dsp.dc(x) == pytest.approx(0.25, abs=0.01)


def test_empty_is_safe():
    assert dsp.rms([]) == 0.0
    assert dsp.peak([]) == 0.0
    assert dsp.dc([]) == 0.0
    assert dsp.spectral_centroid([], SR) == 0.0


def test_centroid_of_440_sine():
    got = dsp.spectral_centroid(sine(440, 0.5), SR)
    assert got == pytest.approx(440, rel=0.15)


def test_centroid_of_5000_sine():
    got = dsp.spectral_centroid(sine(5000, 0.5), SR)
    assert got == pytest.approx(5000, rel=0.05)


def test_centroid_short_sound_is_zero():
    assert dsp.spectral_centroid(sine(440, 0.01), SR) == 0.0


def test_lead_silence():
    quiet = [0.0] * int(SR * 0.05)
    assert dsp.lead_silence(quiet + sine(440, 0.1), SR) == pytest.approx(0.05, abs=0.002)
    assert dsp.lead_silence(sine(440, 0.1), SR) == pytest.approx(0.0, abs=0.001)
    assert dsp.lead_silence(quiet, SR) is None


def test_max_full_scale_run():
    full = dsp.FULL_SCALE
    x = [100, full, full, 200, full, full, full, -full, 0]
    assert dsp.max_full_scale_run(x) == 4
    assert dsp.max_full_scale_run([0, 1, 2]) == 0


def test_fft_matches_naive():
    x = [math.sin(i * 0.3) + 0.2 * math.cos(i * 1.7) for i in range(64)]
    fast = dsp.fft(x)
    for k in (0, 1, 7, 31, 63):
        naive = sum(v * complex(math.cos(-2 * math.pi * k * n / 64),
                                math.sin(-2 * math.pi * k * n / 64))
                    for n, v in enumerate(x))
        assert fast[k].real == pytest.approx(naive.real, abs=1e-6)
        assert fast[k].imag == pytest.approx(naive.imag, abs=1e-6)


def test_fft_python_path_matches_numpy(monkeypatch):
    """numpy 가 없다고 속여도(_np = None) 순수 파이썬 FFT 가 naive DFT 와 같은 값을 낸다."""
    x = [math.sin(i * 0.3) + 0.2 * math.cos(i * 1.7) for i in range(64)]
    monkeypatch.setattr(dsp, "_np", None)
    without_np = dsp.fft(x)
    for k in (0, 1, 7, 31, 63):
        naive = sum(v * complex(math.cos(-2 * math.pi * k * n / 64),
                                math.sin(-2 * math.pi * k * n / 64))
                    for n, v in enumerate(x))
        assert without_np[k].real == pytest.approx(naive.real, abs=1e-9)
        assert without_np[k].imag == pytest.approx(naive.imag, abs=1e-9)


def test_read_samples(tmp_path):
    path = tmp_path / "a.wav"
    x = sine(1000, 0.05, amp=0.5)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(v * 32767)) for v in x))
    back = dsp.read_samples(path)
    assert len(back) == len(x)
    assert dsp.peak(back) == pytest.approx(0.5, abs=0.01)


def test_read_samples_rejects_stereo(tmp_path):
    path = tmp_path / "s.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"\x00" * 400)
    with pytest.raises(ValueError):
        dsp.read_samples(path)


def test_dbfs():
    assert dsp.to_dbfs(1.0) == pytest.approx(0.0)
    assert dsp.to_dbfs(0.5) == pytest.approx(-6.02, abs=0.05)
    assert dsp.to_dbfs(0.0) == dsp.SILENT_DBFS
