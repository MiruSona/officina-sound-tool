"""곡 조립 — 음표 수 · 길이 · 음역 · 같은 seed 재현성."""

import hashlib
import json
from pathlib import Path

import pytest

from soundtool.bgm import check as check_mod
from soundtool.bgm import compose as compose_mod
from soundtool.bgm import patterns, spec as spec_mod

HERE = Path(__file__).resolve().parent
GOLDEN = json.loads((HERE / "golden_bgm.json").read_text(encoding="utf-8"))


def song_of(style, **extra):
    row = {"name": f"t_{style}", "style": style, "seed": 1}
    row.update(extra)
    return spec_mod.build_song(row)


def save(song, tmp_path, name="a.mid"):
    path = tmp_path / name
    compose_mod.compose(song).save(str(path))
    return path


@pytest.mark.parametrize("style", patterns.STYLE_NAMES)
def test_every_style_passes_midi_check(style, tmp_path):
    song = song_of(style)
    assert check_mod.check_midi(save(song, tmp_path), song) == []


@pytest.mark.parametrize("style", patterns.STYLE_NAMES)
def test_length_matches_bars_and_bpm(style, tmp_path):
    song = song_of(style)
    import mido
    midi = mido.MidiFile(str(save(song, tmp_path)))
    assert midi.length == pytest.approx(compose_mod.expected_seconds(song), abs=0.02)


@pytest.mark.parametrize("style", patterns.STYLE_NAMES)
def test_pitches_stay_in_range(style, tmp_path):
    _, pitches = check_mod.read_midi_notes(save(song_of(style), tmp_path))
    assert min(pitches) >= patterns.PITCH_LOW
    assert max(pitches) <= patterns.PITCH_HIGH


@pytest.mark.parametrize("style", patterns.STYLE_NAMES)
def test_same_seed_makes_same_bytes(style, tmp_path):
    first = save(song_of(style), tmp_path, "a.mid").read_bytes()
    second = save(song_of(style), tmp_path, "b.mid").read_bytes()
    assert first == second


def test_different_seed_makes_different_bytes(tmp_path):
    first = save(song_of("town", seed=1), tmp_path, "a.mid").read_bytes()
    second = save(song_of("town", seed=2), tmp_path, "b.mid").read_bytes()
    assert first != second


def test_turning_drums_off_keeps_melody(tmp_path):
    """트랙마다 난수 흐름이 따로라서 드럼을 꺼도 멜로디가 그대로다 (설계 3-5)."""
    full = compose_mod.make_notes(song_of("town"))
    without = compose_mod.make_notes(song_of("town", tracks={"drums": {"on": False}}))
    assert "drums" not in without
    assert full["melody"] == without["melody"]
    assert full["bass"] == without["bass"]


def test_octave_override_shifts_bass(tmp_path):
    plain = compose_mod.make_notes(song_of("town"))["bass"]
    lower = compose_mod.make_notes(song_of("town", tracks={"bass": {"octave": -1}}))["bass"]
    assert [n.pitch for n in lower] == [n.pitch - 12 for n in plain]


def test_loop_song_stops_before_the_end(tmp_path):
    song = song_of("town")
    limit = song.beats - compose_mod.LOOP_GAP_BEAT
    for notes in compose_mod.make_notes(song).values():
        for note in notes:
            assert note.start_beat + note.length_beat <= limit + 1e-9


def test_non_loop_song_has_two_second_tail():
    song = song_of("victory")
    assert song.loop is False
    assert compose_mod.expected_seconds(song) == pytest.approx(song.seconds + 2.0)


def test_chord_slots_cover_every_beat():
    song = song_of("town")
    slots = compose_mod.plan_chords(song)
    assert len(slots) == song.beats
    assert slots[0].roman == song.progression[0]


def test_drum_track_uses_channel_nine(tmp_path):
    import mido
    midi = mido.MidiFile(str(save(song_of("town"), tmp_path)))
    drums = [t for t in midi.tracks if t.name == "drums"][0]
    assert all(m.channel == 9 for m in drums if m.type == "note_on")
    assert not any(m.type == "program_change" for m in drums)


@pytest.mark.parametrize("style", patterns.STYLE_NAMES)
def test_golden_midi_hash(style, tmp_path):
    """패턴을 건드리면 이 시험이 먼저 깨진다."""
    data = save(song_of(style), tmp_path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == GOLDEN["styles"][style]
