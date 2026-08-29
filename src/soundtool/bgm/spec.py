"""곡 스펙 JSON 을 읽고 검사하고, 빠진 값을 프리셋·seed 로 채운다.

`bgm.schema.json` 을 **읽어서** 검사한다 (설계 2-3). 스키마 파일이 곧 규칙이다.
"""

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from soundtool import schema as schema_mod
from soundtool.bgm import patterns, theory

SCHEMA_PATH = Path(__file__).resolve().parent / "bgm.schema.json"
SCHEMA = schema_mod.load(SCHEMA_PATH)

ROLES = ("drums", "bass", "chords", "melody")


class SpecError(Exception):
    """스펙 파일을 못 읽었다."""


@dataclass
class TrackSetting:
    on: bool
    program: int
    octave: int


@dataclass
class Song:
    """기본값이 다 채워진 곡 하나."""

    name: str
    style: str
    seed: int
    tags: list = field(default_factory=list)
    bpm: int = 120
    key: str = "C"
    mode: str = "major"
    bars: int = 16
    loop: bool = True
    progression: list = field(default_factory=list)
    tracks: dict = field(default_factory=dict)

    @property
    def beats(self):
        return self.bars * patterns.BEATS_PER_BAR

    @property
    def seconds(self):
        return self.beats * 60.0 / self.bpm


def load(path):
    """JSON 을 읽는다. 못 읽으면 SpecError."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as err:
        raise SpecError(f"스펙 파일을 못 읽었다 : {path} ({err.strerror})") from err
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise SpecError(f"스펙 JSON 이 깨졌다 : {path} {err.lineno}줄 {err.colno}칸 — {err.msg}") from err


def validate(spec):
    """어긋난 것을 사람 말로. 빈 목록이면 통과."""
    problems = schema_mod.validate(spec, SCHEMA)
    if problems:
        return problems
    _check_semantics(spec, problems)
    return problems


def load_spec(path):
    """파일을 읽고 검사해 Song 목록으로. 어긋나면 SpecError."""
    spec = load(path)
    problems = validate(spec)
    if problems:
        raise SpecError("\n".join(problems))
    return list(iter_songs(spec))


def iter_songs(spec):
    for row in spec.get("songs", []):
        yield build_song(row)


def validate_song(obj):
    """곡 하나만 검사한다."""
    return schema_mod.validate({"version": 1, "songs": [obj]}, SCHEMA)


def default_seed(name):
    """이름의 sha256 앞 4바이트. 같은 이름이면 늘 같은 곡."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def build_song(row):
    """빠진 값을 프리셋과 seed 로 채운 Song 을 만든다."""
    preset = patterns.STYLES[row["style"]]
    seed = row.get("seed", default_seed(row["name"]))
    bpm = row.get("bpm", _draw_bpm(preset, seed))
    progression = list(row.get("progression", _draw_progression(preset, seed)))
    return Song(
        name=row["name"],
        style=row["style"],
        seed=seed,
        tags=list(row.get("tags", [])),
        bpm=bpm,
        key=row.get("key", preset.key),
        mode=row.get("mode", preset.mode),
        bars=row.get("bars", preset.bars),
        loop=row.get("loop", preset.loop),
        progression=progression,
        tracks=_build_tracks(preset, row.get("tracks", {})),
    )


def stream(seed, role):
    """트랙마다 난수 흐름을 따로 쓴다 (설계 3-5)."""
    return random.Random(f"{seed}:{role}")


def _draw_bpm(preset, seed):
    low, high = preset.bpm_range
    return stream(seed, "bpm").randint(low, high)


def _draw_progression(preset, seed):
    return list(stream(seed, "progression").choice(preset.progressions))


def _build_tracks(preset, given):
    tracks = {}
    for role in ROLES:
        row = given.get(role, {})
        on = row.get("on", preset.has_role(role))
        tracks[role] = TrackSetting(
            on=on,
            program=row.get("program", preset.programs.get(role, 0)),
            octave=row.get("octave", 0),
        )
    return tracks


def _check_semantics(spec, problems):
    """스키마로는 못 잡는 것 — 이름 겹침, 있지도 않은 트랙 켜기."""
    seen = set()
    for index, row in enumerate(spec.get("songs", [])):
        where = f"스펙.songs[{index}]"
        name = row.get("name")
        if name in seen:
            problems.append(f"{where}.name : 이름이 겹친다 — {name}")
        seen.add(name)
        _check_progression(row, where, problems)
        _check_tracks(row, where, problems)


def _check_progression(row, where, problems):
    """조·선법과 진행이 아주 어긋나는 것만 잡는다 (음이 음계 밖으로 나가는 코드)."""
    mode = row.get("mode", patterns.STYLES[row["style"]].mode)
    key = row.get("key", patterns.STYLES[row["style"]].key)
    scale = set(theory.scale_pitches(key, mode))
    for roman in row.get("progression", []):
        outside = [p for p in theory.chord_pitches(roman, key) if p not in scale]
        if len(outside) >= 2:
            problems.append(f"{where}.progression : {roman} 는 {key} {mode} 음계에서 너무 벗어난다")


def _check_tracks(row, where, problems):
    preset = patterns.STYLES[row["style"]]
    for role, setting in row.get("tracks", {}).items():
        if setting.get("on") and not preset.has_role(role):
            problems.append(f"{where}.tracks.{role} : {row['style']} 스타일에는 {role} 패턴이 없다")
