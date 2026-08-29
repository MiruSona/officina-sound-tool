"""음계·화음. 반음 번호(pitch class 0~11)만 다루고 옥타브는 안 다룬다.

로마숫자는 설계 2-2 의 열넷으로 고정이다. 로마숫자 자체가 장·단조를 품고 있어서
화음을 뽑을 때 mode 를 안 본다 (mode 는 멜로디 음계에만 쓴다).
"""

KEY_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

MODE_STEPS = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
}

MAJOR_TRIAD = (0, 4, 7)
MINOR_TRIAD = (0, 3, 7)

# 로마숫자 → (으뜸음에서 몇 반음 위인가, 3화음 모양)
ROMANS = {
    "I": (0, MAJOR_TRIAD),
    "ii": (2, MINOR_TRIAD),
    "iii": (4, MINOR_TRIAD),
    "IV": (5, MAJOR_TRIAD),
    "V": (7, MAJOR_TRIAD),
    "vi": (9, MINOR_TRIAD),
    "i": (0, MINOR_TRIAD),
    "III": (3, MAJOR_TRIAD),
    "iv": (5, MINOR_TRIAD),
    "v": (7, MINOR_TRIAD),
    "VI": (8, MAJOR_TRIAD),
    "VII": (10, MAJOR_TRIAD),
    "bII": (1, MAJOR_TRIAD),
    "bVII": (10, MAJOR_TRIAD),
}

ROMAN_NAMES = tuple(ROMANS)


def key_pitch(key):
    """음이름 → 반음 번호."""
    if key not in KEY_NAMES:
        raise ValueError(f"모르는 조 : {key}")
    return KEY_NAMES.index(key)


def scale_pitches(key, mode):
    """음계 일곱 음의 반음 번호."""
    if mode not in MODE_STEPS:
        raise ValueError(f"모르는 선법 : {mode}")
    root = key_pitch(key)
    return [(root + step) % 12 for step in MODE_STEPS[mode]]


def chord_root(roman, key):
    if roman not in ROMANS:
        raise ValueError(f"모르는 로마숫자 : {roman}")
    return (key_pitch(key) + ROMANS[roman][0]) % 12


def chord_pitches(roman, key):
    """3화음 세 음의 반음 번호. 낮은 것부터."""
    root = chord_root(roman, key)
    return [(root + step) % 12 for step in ROMANS[roman][1]]


def fold_into(note, lo, hi):
    """음역 밖이면 옥타브 단위로 접어 넣는다. 못 넣으면 가장 가까운 끝."""
    if hi - lo < 12:
        return max(lo, min(hi, note))
    while note > hi:
        note -= 12
    while note < lo:
        note += 12
    return note


def nearest_pitch(pitch_class, near):
    """반음 번호를 `near` 에 가장 가까운 실제 음 번호로 편다."""
    base = near - (near % 12) + pitch_class
    best = base
    for candidate in (base - 12, base, base + 12):
        if abs(candidate - near) < abs(best - near):
            best = candidate
    return best


def stack_triad(pitch_classes, lowest):
    """세 반음 번호를 `lowest` 위로 차곡차곡 쌓아 실제 음 번호로."""
    out = []
    current = lowest
    for index, pitch_class in enumerate(pitch_classes):
        if index == 0:
            current = fold_into(nearest_pitch(pitch_class, lowest), lowest, lowest + 11)
            out.append(current)
            continue
        step = (pitch_class - out[-1]) % 12
        if step == 0:
            step = 12
        out.append(out[-1] + step)
    return out
