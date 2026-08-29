"""`.rfx` 104바이트를 만들고 되읽는다. 바깥을 모른다.

구조 근거 : Docs/Research/2026-08-25-rfx엔디안확인.md (리틀 엔디안, 헤더 8 + WaveParams 96).
"""

import struct

SIGNATURE = b"rFX "
VERSION = 200
DATA_LENGTH = 96
LAYOUT = "<4sHH2i22f"
SIZE = 104

RAND_SEED_MIN = 1
RAND_SEED_MAX = 0xFFFE

# rfxgen.h 79~124줄의 WaveParams 순서. randSeed 는 따로 받으므로 여기 없다.
FIELD_NAMES = (
    "wave_type",
    "attack_time",
    "sustain_time",
    "sustain_punch",
    "decay_time",
    "start_frequency",
    "min_frequency",
    "slide",
    "delta_slide",
    "vibrato_depth",
    "vibrato_speed",
    "change_amount",
    "change_speed",
    "square_duty",
    "duty_sweep",
    "repeat_speed",
    "phaser_offset",
    "phaser_sweep",
    "lpf_cutoff",
    "lpf_cutoff_sweep",
    "lpf_resonance",
    "hpf_cutoff",
    "hpf_cutoff_sweep",
)

# rfxgen.h ResetWaveParams() 값. lpf_cutoff 만 1.0 이다 — 0 이면 소리가 안 난다.
DEFAULTS = {
    "wave_type": 0,
    "attack_time": 0.0,
    "sustain_time": 0.3,
    "sustain_punch": 0.0,
    "decay_time": 0.4,
    "start_frequency": 0.3,
    "min_frequency": 0.0,
    "slide": 0.0,
    "delta_slide": 0.0,
    "vibrato_depth": 0.0,
    "vibrato_speed": 0.0,
    "change_amount": 0.0,
    "change_speed": 0.0,
    "square_duty": 0.0,
    "duty_sweep": 0.0,
    "repeat_speed": 0.0,
    "phaser_offset": 0.0,
    "phaser_sweep": 0.0,
    "lpf_cutoff": 1.0,
    "lpf_cutoff_sweep": 0.0,
    "lpf_resonance": 0.0,
    "hpf_cutoff": 0.0,
    "hpf_cutoff_sweep": 0.0,
}

# rfxgen.c 741~769줄 GuiSliderBar() 의 최소·최대.
_UNIT = (0.0, 1.0)
_SIGNED = (-1.0, 1.0)
RANGES = {
    "wave_type": (0, 3),
    "attack_time": _UNIT,
    "sustain_time": _UNIT,
    "sustain_punch": _UNIT,
    "decay_time": _UNIT,
    "start_frequency": _UNIT,
    "min_frequency": _UNIT,
    "slide": _SIGNED,
    "delta_slide": _SIGNED,
    "vibrato_depth": _UNIT,
    "vibrato_speed": _UNIT,
    "change_amount": _SIGNED,
    "change_speed": _UNIT,
    "square_duty": _UNIT,
    "duty_sweep": _SIGNED,
    "repeat_speed": _UNIT,
    "phaser_offset": _SIGNED,
    "phaser_sweep": _SIGNED,
    "lpf_cutoff": _UNIT,
    "lpf_cutoff_sweep": _SIGNED,
    "lpf_resonance": _UNIT,
    "hpf_cutoff": _UNIT,
    "hpf_cutoff_sweep": _SIGNED,
}

_TOLERANCE = 1e-6  # float32 로 갔다 오는 값이라 끝자리를 봐준다


def fill_defaults(params):
    """모르는 열쇠가 있으면 ValueError. 빠진 열쇠는 기본값으로 채운다."""
    unknown = sorted(set(params) - set(DEFAULTS))
    if unknown:
        raise ValueError(f"모르는 파라미터 : {', '.join(unknown)}")
    full = dict(DEFAULTS)
    full.update(params)
    return full


def check_range(name, value):
    low, high = RANGES[name]
    if value < low - _TOLERANCE or value > high + _TOLERANCE:
        raise ValueError(f"{name}={value} 는 {low}~{high} 밖이다")


def pack(rand_seed, params):
    """104바이트 `.rfx` 를 만든다. 범위 밖 값이면 ValueError."""
    if not RAND_SEED_MIN <= rand_seed <= RAND_SEED_MAX:
        raise ValueError(f"rand_seed={rand_seed} 는 {RAND_SEED_MIN}~{RAND_SEED_MAX} 밖이다")
    full = fill_defaults(params)
    for name in FIELD_NAMES:
        check_range(name, full[name])
    values = [int(round(full["wave_type"]))]
    values += [float(full[name]) for name in FIELD_NAMES[1:]]
    return struct.pack(LAYOUT, SIGNATURE, VERSION, DATA_LENGTH, rand_seed, *values)


def unpack(data):
    """되읽는다. 헤더가 틀리면 ValueError."""
    if len(data) != SIZE:
        raise ValueError(f".rfx 는 {SIZE}바이트여야 한다 (받은 것 {len(data)})")
    head = struct.unpack(LAYOUT, data)
    if head[0] != SIGNATURE:
        raise ValueError(f"시그니처가 다르다 : {head[0]!r}")
    if head[1] != VERSION or head[2] != DATA_LENGTH:
        raise ValueError(f"헤더가 다르다 : version={head[1]} dataLength={head[2]}")
    rand_seed = head[3]
    params = dict(zip(FIELD_NAMES, head[4:]))
    return rand_seed, params


def expected_frames(params):
    """rfxgen.h 346~348줄과 같은 식. int() 를 항마다 따로 건다.

    rfxgen 은 C float(32bit) 로 계산한다. float64 그대로 곱하면 끝자리가 달라질 수 있어
    각 값을 float32 를 한 번 거친 값으로 되돌린 뒤 셈한다.
    """
    full = fill_defaults(params)
    total = 0
    for name in ("attack_time", "sustain_time", "decay_time"):
        value = struct.unpack("<f", struct.pack("<f", float(full[name])))[0]
        total += int(value * value * 100000.0)
    return total
