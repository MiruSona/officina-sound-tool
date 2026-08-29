"""`.rfx` 패킹 시험. rfxgen 없이 돈다."""

import struct
from pathlib import Path

import pytest

from soundtool.sfx import rfx

HEADER = bytes.fromhex("72465820c8006000")
HERE = Path(__file__).resolve().parent


def _float32_term(value):
    """expected_frames 와 같은 식 — float32 를 거친 뒤 항 하나를 셈한다."""
    value = struct.unpack("<f", struct.pack("<f", value))[0]
    return int(value * value * 100000.0)


def test_field_count():
    assert len(rfx.FIELD_NAMES) == 23
    assert rfx.FIELD_NAMES[0] == "wave_type"
    assert set(rfx.DEFAULTS) == set(rfx.FIELD_NAMES)
    assert set(rfx.RANGES) == set(rfx.FIELD_NAMES)


def test_pack_size_and_header():
    data = rfx.pack(12345, {})
    assert len(data) == 104
    assert data[:8] == HEADER


def test_defaults_lpf_cutoff_is_one():
    assert rfx.DEFAULTS["lpf_cutoff"] == 1.0


def test_roundtrip():
    params = {"wave_type": 3, "attack_time": 0.1, "sustain_time": 0.5,
              "decay_time": 0.3, "slide": -0.25, "lpf_cutoff": 0.75}
    seed, back = rfx.unpack(rfx.pack(777, params))
    assert seed == 777
    for name, value in params.items():
        assert back[name] == pytest.approx(value, abs=1e-6)
    # 안 준 필드는 기본값이 들어간다
    assert back["hpf_cutoff"] == pytest.approx(rfx.DEFAULTS["hpf_cutoff"])


def test_unpack_rejects_bad_header():
    data = bytearray(rfx.pack(1, {}))
    data[4] = 0xC9
    with pytest.raises(ValueError):
        rfx.unpack(bytes(data))
    with pytest.raises(ValueError):
        rfx.unpack(b"nope")


def test_out_of_range_raises():
    with pytest.raises(ValueError):
        rfx.pack(1, {"lpf_cutoff": 1.4})
    with pytest.raises(ValueError):
        rfx.pack(1, {"slide": -1.5})
    with pytest.raises(ValueError):
        rfx.pack(1, {"wave_type": 4})


def test_unknown_field_raises():
    with pytest.raises(ValueError):
        rfx.pack(1, {"nope": 0.5})


def test_rand_seed_range():
    with pytest.raises(ValueError):
        rfx.pack(0, {})
    with pytest.raises(ValueError):
        rfx.pack(0xFFFF, {})


def test_expected_frames_matches_probe():
    # rfx_probe.py 가 실측한 값 : a=0.1 s=0.5 d=0.3 -> 35000 (WAV 는 +3)
    params = {"attack_time": 0.1, "sustain_time": 0.5, "decay_time": 0.3}
    assert rfx.expected_frames(params) == 35000


def test_expected_frames_truncates_each_term():
    # 항마다 따로 int() 를 건다 — 합친 뒤 자르는 것과 다르다
    params = {"attack_time": 0.3, "sustain_time": 0.3, "decay_time": 0.3}
    assert rfx.expected_frames(params) == 3 * _float32_term(0.3)


def test_expected_frames_uses_float32():
    # float64 로 그대로 셈하면 float32 경로와 끝자리가 달라진다 (0.11 이 그 경계)
    params = {"attack_time": 0.11, "sustain_time": 0.0, "decay_time": 0.0}
    float64_term = int(0.11 * 0.11 * 100000.0)
    assert rfx.expected_frames(params) == _float32_term(0.11)
    assert rfx.expected_frames(params) != float64_term


def test_unpack_probe_little():
    # rfx_probe.py 가 만든 실제 견본. randSeed 와 attack_time 을 확인한다
    data = (HERE / "probe_little.rfx").read_bytes()
    rand_seed, params = rfx.unpack(data)
    assert rand_seed == 12345
    assert params["attack_time"] == pytest.approx(0.1, abs=1e-4)
