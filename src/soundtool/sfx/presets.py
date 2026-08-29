"""프리셋 7개. 범위 + seed 결정론적 추첨.

근거는 rfxgen.h 712~919줄의 Gen* 일곱 함수 (설계 3절 표).
rfxgen 의 RFXGEN_RAND(min,max) 매크로에는 0 이 안 나오는 버그가 있는데, 우리는 따라 하지 않는다
(설계 10절 3번). 그래서 소스에서 죽어 있는 갈래도 여기서는 살아 있다.
"""

import random

from soundtool.sfx import rfx
from soundtool.sfx.check import CENTROID_HZ

RAND_SEED_MAX = rfx.RAND_SEED_MAX


def _coin(rng, p):
    p["start_frequency"] = 0.4 + rng.uniform(0, 0.5)
    p["attack_time"] = 0.0
    p["sustain_time"] = rng.uniform(0, 0.1)
    p["decay_time"] = 0.1 + rng.uniform(0, 0.4)
    p["sustain_punch"] = 0.3 + rng.uniform(0, 0.3)
    if rng.random() < 0.5:
        p["change_speed"] = 0.5 + rng.uniform(0, 0.2)
        p["change_amount"] = 0.2 + rng.uniform(0, 0.4)


def _laser(rng, p):
    wave_type = rng.randint(0, 2)
    if wave_type == 2 and rng.random() < 0.5:
        wave_type = rng.randint(0, 1)
    p["wave_type"] = wave_type

    if rng.randint(0, 2) == 0:
        p["start_frequency"] = 0.3 + rng.uniform(0, 0.6)
        p["min_frequency"] = rng.uniform(0, 0.1)
        p["slide"] = -0.35 - rng.uniform(0, 0.3)
    else:
        p["start_frequency"] = 0.5 + rng.uniform(0, 0.5)
        p["min_frequency"] = max(0.2, p["start_frequency"] - 0.2 - rng.uniform(0, 0.6))
        p["slide"] = -0.15 - rng.uniform(0, 0.2)

    if rng.random() < 0.5:
        p["square_duty"] = rng.uniform(0, 0.5)
        p["duty_sweep"] = rng.uniform(0, 0.2)
    else:
        p["square_duty"] = 0.4 + rng.uniform(0, 0.5)
        p["duty_sweep"] = -rng.uniform(0, 0.7)

    p["attack_time"] = 0.0
    p["sustain_time"] = 0.1 + rng.uniform(0, 0.2)
    p["decay_time"] = rng.uniform(0, 0.4)
    if rng.random() < 0.5:
        p["sustain_punch"] = rng.uniform(0, 0.3)
    if rng.randint(0, 2) == 0:
        p["phaser_offset"] = rng.uniform(0, 0.2)
        p["phaser_sweep"] = -rng.uniform(0, 0.2)
    if rng.random() < 0.5:
        p["hpf_cutoff"] = rng.uniform(0, 0.3)


def _explosion(rng, p):
    p["wave_type"] = 3
    if rng.random() < 0.5:
        p["start_frequency"] = 0.1 + rng.uniform(0, 0.4)
        p["slide"] = -0.1 + rng.uniform(0, 0.4)
    else:
        p["start_frequency"] = 0.2 + rng.uniform(0, 0.7)
        p["slide"] = -0.2 - rng.uniform(0, 0.2)
    p["start_frequency"] *= p["start_frequency"]

    if rng.randint(0, 4) == 0:
        p["slide"] = 0.0
    if rng.random() < 0.5:
        p["repeat_speed"] = 0.3 + rng.uniform(0, 0.5)

    p["attack_time"] = 0.0
    p["sustain_time"] = 0.1 + rng.uniform(0, 0.3)
    p["decay_time"] = rng.uniform(0, 0.5)

    if rng.random() < 0.5:
        p["phaser_offset"] = -0.3 + rng.uniform(0, 0.9)
        p["phaser_sweep"] = -rng.uniform(0, 0.3)
    p["sustain_punch"] = 0.2 + rng.uniform(0, 0.6)
    if rng.random() < 0.5:
        p["vibrato_depth"] = rng.uniform(0, 0.7)
        p["vibrato_speed"] = rng.uniform(0, 0.6)
    if rng.random() < 0.5:
        p["change_speed"] = 0.6 + rng.uniform(0, 0.3)
        p["change_amount"] = 0.8 - rng.uniform(0, 1.6)


def _powerup(rng, p):
    if rng.random() < 0.5:
        p["wave_type"] = 1
    else:
        p["square_duty"] = rng.uniform(0, 0.6)

    if rng.random() < 0.5:
        p["start_frequency"] = 0.2 + rng.uniform(0, 0.3)
        p["slide"] = 0.1 + rng.uniform(0, 0.4)
        p["repeat_speed"] = 0.4 + rng.uniform(0, 0.4)
    else:
        p["start_frequency"] = 0.2 + rng.uniform(0, 0.3)
        p["slide"] = 0.05 + rng.uniform(0, 0.2)
        if rng.random() < 0.5:
            p["vibrato_depth"] = rng.uniform(0, 0.7)
            p["vibrato_speed"] = rng.uniform(0, 0.6)

    p["attack_time"] = 0.0
    p["sustain_time"] = rng.uniform(0, 0.4)
    p["decay_time"] = 0.1 + rng.uniform(0, 0.4)


def _hit(rng, p):
    wave_type = rng.randint(0, 2)
    if wave_type == 2:
        wave_type = 3
    p["wave_type"] = wave_type
    if wave_type == 0:
        p["square_duty"] = rng.uniform(0, 0.6)

    p["start_frequency"] = 0.2 + rng.uniform(0, 0.6)
    p["slide"] = -0.3 - rng.uniform(0, 0.4)
    p["attack_time"] = 0.0
    p["sustain_time"] = rng.uniform(0, 0.1)
    p["decay_time"] = 0.1 + rng.uniform(0, 0.2)
    if rng.random() < 0.5:
        p["hpf_cutoff"] = rng.uniform(0, 0.3)


def _jump(rng, p):
    p["wave_type"] = 0
    p["square_duty"] = rng.uniform(0, 0.6)
    p["start_frequency"] = 0.3 + rng.uniform(0, 0.3)
    p["slide"] = 0.1 + rng.uniform(0, 0.2)
    p["attack_time"] = 0.0
    p["sustain_time"] = 0.1 + rng.uniform(0, 0.3)
    p["decay_time"] = 0.1 + rng.uniform(0, 0.2)
    if rng.random() < 0.5:
        p["hpf_cutoff"] = rng.uniform(0, 0.3)
    if rng.random() < 0.5:
        p["lpf_cutoff"] = 1.0 - rng.uniform(0, 0.6)


def _blip(rng, p):
    p["wave_type"] = rng.randint(0, 1)
    if p["wave_type"] == 0:
        p["square_duty"] = rng.uniform(0, 0.6)
    p["start_frequency"] = 0.2 + rng.uniform(0, 0.4)
    p["attack_time"] = 0.0
    p["sustain_time"] = 0.1 + rng.uniform(0, 0.1)
    p["decay_time"] = rng.uniform(0, 0.2)
    p["hpf_cutoff"] = 0.1


_DRAWS = {
    "coin": _coin,
    "laser": _laser,
    "explosion": _explosion,
    "powerup": _powerup,
    "hit": _hit,
    "jump": _jump,
    "blip": _blip,
}

_SUMMARIES = {
    "coin": "동전·아이템 줍기. 높은 음이 짧게 튀고 살짝 올라간다",
    "laser": "레이저·총알. 음이 빠르게 아래로 미끄러진다",
    "explosion": "폭발·충격. 노이즈 파형에 긴 꼬리",
    "powerup": "강화·획득. 음이 위로 올라가며 반복된다",
    "hit": "맞음·타격. 아주 짧고 아래로 떨어진다",
    "jump": "점프. 사각파가 위로 올라간다",
    "blip": "UI 클릭·선택. 아주 짧은 딸깍",
}

PRESET_NAMES = tuple(_DRAWS)


def centroid_range(preset):
    """설계 5절 스펙트럼 중심 허용 구간 (Hz)."""
    _require(preset)
    return CENTROID_HZ[preset]


def draw(preset, seed):
    """(rand_seed, params) 를 준다. 같은 seed 면 늘 같은 값이다."""
    _require(preset)
    rng = random.Random(seed)
    params = {}
    _DRAWS[preset](rng, params)
    rand_seed = rng.randint(rfx.RAND_SEED_MIN, rfx.RAND_SEED_MAX)
    return rand_seed, _clamp(params)


def describe(preset):
    """`presets` 명령이 뱉을 설명. LLM 프롬프트에 붙일 용도."""
    _require(preset)
    low, high = CENTROID_HZ[preset]
    return {
        "name": preset,
        "summary": _SUMMARIES[preset],
        "centroid_hz": [low, high],
    }


def _require(preset):
    if preset not in _DRAWS:
        raise ValueError(f"모르는 프리셋 : {preset} (쓸 수 있는 것 : {', '.join(PRESET_NAMES)})")


def _clamp(params):
    """범위를 벗어나면 잘라서 준다. rfx.pack() 이 ValueError 로 죽지 않게 하는 안전망이다."""
    out = {}
    for name, value in params.items():
        low, high = rfx.RANGES[name]
        out[name] = min(max(value, low), high)
    return out
