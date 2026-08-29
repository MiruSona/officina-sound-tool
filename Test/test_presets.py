"""프리셋 추첨 시험. rfxgen 없이 돈다."""

import random

import pytest

from soundtool.sfx import presets, rfx


def test_seven_presets():
    assert len(presets.PRESET_NAMES) == 7
    assert set(presets.PRESET_NAMES) == {
        "coin", "laser", "explosion", "powerup", "hit", "jump", "blip"}


@pytest.mark.parametrize("name", presets.PRESET_NAMES)
def test_draw_is_deterministic(name):
    first = presets.draw(name, 7)
    second = presets.draw(name, 7)
    assert first == second


@pytest.mark.parametrize("name", presets.PRESET_NAMES)
def test_draw_stays_in_ranges(name):
    # _clamp() 를 거치기 전 값으로 본다 — 추첨 식 자체가 범위를 지키는지 보려는 시험이다.
    for seed in range(64):
        rng = random.Random(seed)
        params = {}
        presets._DRAWS[name](rng, params)
        for field, value in params.items():
            low, high = rfx.RANGES[field]
            assert low <= value <= high, f"{name}.{field}={value}"

        rand_seed, drawn = presets.draw(name, seed)
        assert rfx.RAND_SEED_MIN <= rand_seed <= rfx.RAND_SEED_MAX
        assert set(drawn) <= set(rfx.FIELD_NAMES)
        rfx.pack(rand_seed, drawn)  # 패킹까지 통과해야 한다


@pytest.mark.parametrize("name", presets.PRESET_NAMES)
def test_different_seeds_differ(name):
    drawn = {repr(presets.draw(name, seed)) for seed in range(32)}
    assert len(drawn) > 16


def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        presets.draw("nope", 1)


@pytest.mark.parametrize("name", presets.PRESET_NAMES)
def test_describe_has_centroid(name):
    info = presets.describe(name)
    low, high = info["centroid_hz"]
    assert 0 < low < high
    assert info["name"] == name
    assert info["summary"]


def test_fixed_wave_types():
    for seed in range(32):
        assert presets.draw("explosion", seed)[1]["wave_type"] == 3
        assert presets.draw("jump", seed)[1]["wave_type"] == 0
        assert presets.draw("blip", seed)[1]["wave_type"] in (0, 1)
        assert presets.draw("hit", seed)[1]["wave_type"] in (0, 1, 3)
