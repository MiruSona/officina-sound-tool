"""스타일 표(설계 3-2)와 역할별 패턴 만들기(3-3 · 3-4).

패턴은 **1마디짜리 셀**로 적고 4마디 악구 안에서 `A A B A` 로 깐다.
적은 재료로 곡처럼 들리게 하는 가장 싼 방법이다.
"""

from dataclasses import dataclass

from soundtool.bgm import theory

BEATS_PER_BAR = 4
BARS_PER_PHRASE = 4

# 드럼 음 번호 (설계 4-2)
KICK, SNARE, HAT_CLOSED, HAT_OPEN, RIDE, CRASH, TOM_LOW, TOM_HIGH = 36, 38, 42, 46, 51, 49, 45, 47

# 세기 기준값과 흔들기 (설계 4-3)
VELOCITY = {
    "kick": (100, 4),
    "snare": (95, 5),
    "hat": (68, 8),
    "bass": (85, 5),
    "chords": (65, 5),
    "melody": (95, 6),
}

REST_CHANCE = {"sparse": 0.40, "normal": 0.20, "dense": 0.08}
LEAP_CHANCE = 0.12          # 악구마다 한 번만 허락하는 옥타브 도약
MAX_STEP = 7                # 완전5도
PITCH_LOW, PITCH_HIGH = 21, 108


@dataclass
class Note:
    role: str
    start_beat: float
    length_beat: float
    pitch: int
    velocity: int


@dataclass
class StylePreset:
    name: str
    bpm_range: tuple
    key: str
    mode: str
    bars: int
    loop: bool
    progressions: tuple
    drum_cells: tuple
    drum_fill: tuple
    bass_cells: tuple
    chord_cells: tuple
    melody_cells: tuple
    density: str
    programs: dict
    melody_range: tuple
    bass_low: int = 36
    chord_low: int = 48
    summary: str = ""

    def has_role(self, role):
        """드럼만 스타일에 따라 없다. 나머지 셋은 늘 있다."""
        if role == "drums":
            return bool(self.drum_cells)
        return True


def _hats(pitch, count, velocity=None):
    """한 마디를 count 등분해 하이햇을 깐다."""
    step = BEATS_PER_BAR / count
    base = VELOCITY["hat"][0] if velocity is None else velocity
    return [(i * step, pitch, base + (10 if (i * step) % 1 == 0 else 0)) for i in range(count)]


_TOWN_BACKBEAT = [(0, KICK, 100), (1, SNARE, 95), (2, KICK, 100), (3, SNARE, 95)]
_TOWN_A = tuple(_TOWN_BACKBEAT + _hats(HAT_CLOSED, 8))
_TOWN_B = tuple(_TOWN_BACKBEAT + [(2.5, KICK, 92)] + _hats(HAT_CLOSED, 8))
_TOWN_FILL = tuple([(0, KICK, 100), (1, SNARE, 95)]
                   + [(2 + i * 0.25, SNARE, 80 + i * 4) for i in range(8)])

_BATTLE_BASE = [(i, KICK, 100) for i in range(BEATS_PER_BAR)] + [(1, SNARE, 95), (3, SNARE, 95)]
_BATTLE_A = tuple(_BATTLE_BASE + _hats(HAT_CLOSED, 16))
_BATTLE_B = tuple(_BATTLE_BASE + [(2.5, KICK, 95)] + _hats(HAT_CLOSED, 16))
_BATTLE_FILL = tuple([(0, CRASH, 105), (0, KICK, 100)]
                     + [(1 + i * 0.25, SNARE, 78 + i * 3) for i in range(12)])

_DUNGEON_A = ((0, KICK, 96), (2.5, TOM_LOW, 78), (3.5, TOM_HIGH, 74))
_DUNGEON_B = ((0, KICK, 96), (1.5, TOM_LOW, 76), (3, TOM_HIGH, 72))
_DUNGEON_FILL = ((0, KICK, 96), (2, TOM_LOW, 84), (2.5, TOM_LOW, 86),
                 (3, TOM_HIGH, 88), (3.5, TOM_HIGH, 92))

_VICTORY_A = tuple([(0, CRASH, 108), (0, KICK, 100), (2, KICK, 100)]
                   + [(1 + i * 0.25, SNARE, 74 + i * 5) for i in range(4)])
_VICTORY_B = ((0, KICK, 100), (1, SNARE, 98), (2, KICK, 100), (3, SNARE, 98), (3.5, SNARE, 92))
_VICTORY_FILL = tuple([(0, CRASH, 108)] + [(i * 0.25, SNARE, 70 + i * 4) for i in range(1, 16)])

_QUARTER_ROOT = ((0, 0.9, 0), (1, 0.9, 0), (2, 0.9, 0), (3, 0.9, 0))
_QUARTER_WALK = ((0, 0.9, 0), (1, 0.9, 0), (2, 0.9, 1), (3, 0.9, 0))
_EIGHTH_OCTAVE = tuple((i * 0.5, 0.45, (i % 2) * 2) for i in range(8))
_EIGHTH_FIFTH = tuple((i * 0.5, 0.45, (0, 0, 1, 0, 2, 0, 1, 0)[i]) for i in range(8))
_WHOLE_ROOT = ((0, 4.0, 0),)
_HALF_ROOT = ((0, 1.9, 0), (2, 1.9, 0))

_PAD_HALF = ((0, 1.9, -1), (2, 1.9, -1))
_PAD_WHOLE = ((0, 4.0, -1),)
_STAB_EIGHTH = tuple((i * 0.5, 0.25, -1) for i in range(8))
_STAB_OFFBEAT = tuple((i * 0.5 + 0.5, 0.25, -1) for i in range(7))
_ARP_EIGHTH = tuple((i * 0.5, 0.45, (0, 1, 2, 1, 0, 1, 2, 1)[i]) for i in range(8))
_ARP_UP = tuple((i * 0.5, 0.45, (0, 1, 2, 0, 1, 2, 1, 0)[i]) for i in range(8))
_QUARTER_CHORD = ((0, 0.9, -1), (1, 0.9, -1), (2, 0.9, -1), (3, 0.9, -1))

_MEL_EIGHTH_A = ((0, 0.45), (0.5, 0.45), (1, 0.9), (2, 0.45), (2.5, 0.45), (3, 0.9))
_MEL_EIGHTH_B = ((0, 0.9), (1, 0.45), (1.5, 0.45), (2, 0.9), (3, 0.45), (3.5, 0.45))
_MEL_SIXTEENTH_A = tuple((i * 0.25, 0.22) for i in range(16))
_MEL_SIXTEENTH_B = tuple((i * 0.25, 0.22) for i in range(8)) + ((2, 0.9), (3, 0.45), (3.5, 0.45))
_MEL_HALF = ((0, 1.8), (2, 1.8))
_MEL_LONG = ((0, 2.9), (3, 0.9))
_MEL_FANFARE_A = ((0, 0.45), (0.5, 0.45), (1, 0.9), (2, 1.9))
_MEL_FANFARE_B = ((0, 0.9), (1, 0.45), (1.5, 0.45), (2, 0.45), (2.5, 0.45), (3, 0.9))

STYLES = {
    "town": StylePreset(
        name="town", bpm_range=(96, 116), key="C", mode="major", bars=16, loop=True,
        progressions=(("I", "V", "vi", "IV"), ("I", "vi", "IV", "V"), ("IV", "V", "I", "vi")),
        drum_cells=(_TOWN_A, _TOWN_B), drum_fill=_TOWN_FILL,
        bass_cells=(_QUARTER_ROOT, _QUARTER_WALK),
        chord_cells=(_PAD_HALF, _QUARTER_CHORD),
        melody_cells=(_MEL_EIGHTH_A, _MEL_EIGHTH_B),
        density="normal", programs={"chords": 4, "bass": 33, "melody": 73},
        melody_range=(60, 84), summary="마을 · 낮"),
    "battle": StylePreset(
        name="battle", bpm_range=(140, 168), key="A", mode="minor", bars=16, loop=True,
        progressions=(("i", "VI", "III", "VII"), ("i", "iv", "V", "i"), ("i", "VII", "VI", "V")),
        drum_cells=(_BATTLE_A, _BATTLE_B), drum_fill=_BATTLE_FILL,
        bass_cells=(_EIGHTH_OCTAVE, _EIGHTH_FIFTH),
        chord_cells=(_STAB_EIGHTH, _STAB_OFFBEAT),
        melody_cells=(_MEL_SIXTEENTH_A, _MEL_SIXTEENTH_B),
        density="dense", programs={"chords": 81, "bass": 38, "melody": 80},
        melody_range=(60, 88), summary="전투 · 보스"),
    "dungeon": StylePreset(
        name="dungeon", bpm_range=(72, 90), key="D", mode="phrygian", bars=16, loop=True,
        progressions=(("i", "VI", "i", "VII"), ("i", "iv", "i", "v"), ("i", "bII", "i", "v")),
        drum_cells=(_DUNGEON_A, _DUNGEON_B), drum_fill=_DUNGEON_FILL,
        bass_cells=(_WHOLE_ROOT,),
        chord_cells=(_PAD_WHOLE,),
        melody_cells=(_MEL_HALF, _MEL_LONG),
        density="sparse", programs={"chords": 89, "bass": 43, "melody": 71},
        melody_range=(55, 79), bass_low=33, chord_low=45, summary="던전 · 동굴"),
    "title": StylePreset(
        name="title", bpm_range=(80, 100), key="C", mode="major", bars=16, loop=True,
        progressions=(("I", "IV", "V", "I"), ("vi", "IV", "I", "V")),
        drum_cells=(), drum_fill=(),
        bass_cells=(_HALF_ROOT,),
        chord_cells=(_ARP_EIGHTH, _ARP_UP),
        melody_cells=(_MEL_LONG, _MEL_HALF),
        density="sparse", programs={"chords": 48, "bass": 33, "melody": 40},
        melody_range=(62, 84), summary="타이틀 · 메뉴"),
    "victory": StylePreset(
        name="victory", bpm_range=(120, 140), key="C", mode="major", bars=8, loop=False,
        progressions=(("I", "IV", "V", "I"), ("I", "V", "I")),
        drum_cells=(_VICTORY_A, _VICTORY_B), drum_fill=_VICTORY_FILL,
        bass_cells=(_QUARTER_ROOT,),
        chord_cells=(_QUARTER_CHORD,),
        melody_cells=(_MEL_FANFARE_A, _MEL_FANFARE_B),
        density="normal", programs={"chords": 61, "bass": 33, "melody": 56},
        melody_range=(65, 86), summary="승리 징글"),
    "ambient": StylePreset(
        name="ambient", bpm_range=(60, 76), key="E", mode="dorian", bars=16, loop=True,
        progressions=(("i", "IV", "i", "IV"), ("i", "VII", "i", "VII")),
        drum_cells=(), drum_fill=(),
        bass_cells=(_WHOLE_ROOT,),
        chord_cells=(_PAD_WHOLE,),
        melody_cells=(_MEL_LONG, _MEL_HALF),
        density="sparse", programs={"chords": 89, "bass": 43, "melody": 52},
        melody_range=(60, 81), bass_low=33, chord_low=48, summary="분위기 · 배경"),
}

STYLE_NAMES = tuple(STYLES)


def jitter(rng, kind):
    base, spread = VELOCITY[kind]
    return max(1, min(127, base + rng.randint(-spread, spread)))


def phrase_cells(cells, rng):
    """악구 하나에 깔 셀 넷을 `A A B A` 로 뽑는다."""
    first = rng.choice(cells)
    second = rng.choice(cells) if len(cells) > 1 else first
    return [first, first, second, first]


def _bar_cells(cells, rng, bars):
    """마디 수만큼 셀을 깐다."""
    out = []
    while len(out) < bars:
        out += phrase_cells(cells, rng)
    return out[:bars]


def make_drums(preset, rng, bars):
    if not preset.drum_cells:
        return []
    cells = _bar_cells(preset.drum_cells, rng, bars)
    notes = []
    for bar, cell in enumerate(cells):
        used = preset.drum_fill if (bar + 1) % 8 == 0 and preset.drum_fill else cell
        for beat, pitch, velocity in used:
            wobble = rng.randint(-4, 4)
            notes.append(Note("drums", bar * BEATS_PER_BAR + beat, 0.25, pitch,
                              max(1, min(127, velocity + wobble))))
    return notes


def make_bass(preset, rng, slots):
    bars = len(slots) // BEATS_PER_BAR
    cells = _bar_cells(preset.bass_cells, rng, bars)
    notes = []
    for bar, cell in enumerate(cells):
        for beat, length, tone in cell:
            start = bar * BEATS_PER_BAR + beat
            root = _root_pitch(preset, slots, start)
            pitch = root + (0, 7, 12)[tone]
            notes.append(Note("bass", start, length, pitch, jitter(rng, "bass")))
    return notes


def make_chords(preset, rng, slots):
    bars = len(slots) // BEATS_PER_BAR
    cells = _bar_cells(preset.chord_cells, rng, bars)
    notes = []
    for bar, cell in enumerate(cells):
        for beat, length, tone in cell:
            start = bar * BEATS_PER_BAR + beat
            stack = theory.stack_triad(slots[int(start)].pitches, preset.chord_low)
            wanted = stack if tone < 0 else [stack[tone]]
            for pitch in wanted:
                notes.append(Note("chords", start, length, pitch, jitter(rng, "chords")))
    return notes


def make_melody(preset, rng, slots, song):
    """설계 3-4 규칙 다섯이 여기 있다."""
    bars = len(slots) // BEATS_PER_BAR
    cells = _bar_cells(preset.melody_cells, rng, bars)
    scale = theory.scale_pitches(song.key, song.mode)
    rest_chance = REST_CHANCE[preset.density]
    low, high = preset.melody_range
    notes = []
    previous = None
    leap_used = False
    for bar, cell in enumerate(cells):
        if bar % BARS_PER_PHRASE == 0:
            leap_used = False
        for index, (beat, length) in enumerate(cell):
            start = bar * BEATS_PER_BAR + beat
            if index == 0:
                previous = _chord_tone(slots[int(start)], previous, low, high)
                notes.append(Note("melody", start, length, previous, jitter(rng, "melody")))
                continue
            if rng.random() < rest_chance:
                continue
            previous, leap_used = _next_pitch(rng, scale, previous, low, high, leap_used)
            notes.append(Note("melody", start, length, previous, jitter(rng, "melody")))
    resolve_ending(preset, notes, song)
    return notes


def _root_pitch(preset, slots, beat):
    slot = slots[int(beat)]
    base = theory.nearest_pitch(slot.pitches[0], preset.bass_low)
    return theory.fold_into(base, preset.bass_low, preset.bass_low + 11)


def _chord_tone(slot, previous, low, high):
    """마디 첫 음은 그 자리 코드의 화음음 (규칙 2)."""
    middle = (low + high) // 2
    near = middle if previous is None else previous
    best = None
    for pitch_class in slot.pitches:
        candidate = theory.fold_into(theory.nearest_pitch(pitch_class, near), low, high)
        if best is None or abs(candidate - near) < abs(best - near):
            best = candidate
    return best


def _next_pitch(rng, scale, previous, low, high, leap_used):
    """규칙 1·3·4 — 음계 안에서, 5도 이내로, 음역 밖이면 접는다."""
    span = MAX_STEP
    leap = not leap_used and rng.random() < LEAP_CHANCE
    if leap:
        span = 12
    candidates = []
    for delta in range(-span, span + 1):
        pitch = previous + delta
        if pitch % 12 in scale and low <= pitch <= high:
            candidates.append(pitch)
    if not candidates:
        return theory.fold_into(previous, low, high), leap_used
    return rng.choice(candidates), leap_used or leap


def resolve_ending(preset, notes, song, shift=0):
    """규칙 5 — 마지막 음은 으뜸화음의 화음음. loop 이면 1도나 5도.

    루프 여백으로 마지막 음을 버린 뒤에도 맞아야 하므로 다듬기가 끝난 뒤 한 번 더 부른다.
    """
    low = max(PITCH_LOW, preset.melody_range[0] + shift)
    high = min(PITCH_HIGH, preset.melody_range[1] + shift)
    if not notes or low > high:
        return
    tonic = theory.tonic_pitches(song.key, song.mode)
    wanted = (tonic[0], tonic[2]) if song.loop else tonic
    last = notes[-1]
    best = None
    for pitch_class in wanted:
        candidate = theory.fold_into(theory.nearest_pitch(pitch_class, last.pitch), low, high)
        if best is None or abs(candidate - last.pitch) < abs(best - last.pitch):
            best = candidate
    last.pitch = best
