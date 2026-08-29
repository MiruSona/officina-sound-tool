"""음계·화음 값을 손으로 적은 표와 맞춰본다."""

import pytest

from soundtool.bgm import theory

SCALES = {
    ("C", "major"): [0, 2, 4, 5, 7, 9, 11],
    ("A", "minor"): [9, 11, 0, 2, 4, 5, 7],
    ("D", "phrygian"): [2, 3, 5, 7, 9, 10, 0],
    ("E", "dorian"): [4, 6, 7, 9, 11, 1, 2],
    ("G", "mixolydian"): [7, 9, 11, 0, 2, 4, 5],
}

CHORDS = {
    ("I", "C"): [0, 4, 7],
    ("V", "C"): [7, 11, 2],
    ("vi", "C"): [9, 0, 4],
    ("i", "A"): [9, 0, 4],
    ("VI", "A"): [5, 9, 0],
    ("bII", "D"): [3, 7, 10],
    ("bVII", "C"): [10, 2, 5],
}


@pytest.mark.parametrize("pair,want", SCALES.items())
def test_scale_pitches(pair, want):
    key, mode = pair
    assert theory.scale_pitches(key, mode) == want


@pytest.mark.parametrize("pair,want", CHORDS.items())
def test_chord_pitches(pair, want):
    roman, key = pair
    assert theory.chord_pitches(roman, key) == want


def test_unknown_names_raise():
    with pytest.raises(ValueError):
        theory.scale_pitches("H", "major")
    with pytest.raises(ValueError):
        theory.scale_pitches("C", "lydian")
    with pytest.raises(ValueError):
        theory.chord_pitches("X", "C")


@pytest.mark.parametrize("note,want", [(60, 60), (95, 83), (40, 64), (108, 84), (12, 60)])
def test_fold_into(note, want):
    assert theory.fold_into(note, 60, 84) == want


def test_fold_into_narrow_range_clamps():
    assert theory.fold_into(90, 60, 65) == 65
    assert theory.fold_into(10, 60, 65) == 60


def test_nearest_pitch():
    assert theory.nearest_pitch(0, 60) == 60
    assert theory.nearest_pitch(11, 60) == 59
    assert theory.nearest_pitch(1, 60) == 61


def test_stack_triad_goes_up():
    stack = theory.stack_triad([0, 4, 7], 48)
    assert stack == [48, 52, 55]
    stack = theory.stack_triad([9, 0, 4], 48)
    assert stack[0] >= 48 and stack == sorted(stack)


def test_every_roman_makes_three_notes():
    for roman in theory.ROMAN_NAMES:
        pitches = theory.chord_pitches(roman, "C")
        assert len(set(pitches)) == 3
