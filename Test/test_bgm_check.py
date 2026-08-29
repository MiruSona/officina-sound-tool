"""검수 여덟 개를 **일부러 깨뜨린** WAV·MIDI 로 하나씩 잡히는지 본다."""

import wave

import mido
import numpy as np
import pytest

from soundtool import config
from soundtool.bgm import check as check_mod
from soundtool.bgm import compose as compose_mod
from soundtool.bgm import spec as spec_mod

RATE = config.BGM_SAMPLE_RATE


def a_song(**extra):
    row = {"name": "probe", "style": "town", "seed": 1, "bpm": 120, "bars": 4}
    row.update(extra)
    return spec_mod.build_song(row)


def good_wave(seconds, amplitude=0.4):
    """저·중·고가 고르게 든 파형. 검수 여덟 개를 다 통과한다."""
    t = np.arange(int(seconds * RATE)) / RATE
    tone = np.sin(2 * np.pi * 100 * t) + np.sin(2 * np.pi * 1000 * t) + np.sin(2 * np.pi * 8000 * t)
    return tone / 3.0 * amplitude


def write_wav(path, mono, channels=2):
    data = np.clip(mono, -1.0, 1.0)
    ints = np.round(data * 32767).astype("<i2")
    if channels == 2:
        ints = np.repeat(ints, 2)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(ints.tobytes())
    return path


def make_wav(tmp_path, mono, name="probe.wav"):
    return write_wav(tmp_path / name, mono)


def test_good_wav_passes(tmp_path):
    song = a_song()
    path = make_wav(tmp_path, good_wave(song.seconds))
    assert check_mod.check_wav(path, song) == []


def test_1_length_is_caught(tmp_path):
    song = a_song()
    path = make_wav(tmp_path, good_wave(song.seconds * 0.8))
    assert any("길이" in line for line in check_mod.check_wav(path, song))


def test_1_length_tolerance_is_tight_for_loop(tmp_path):
    song = a_song()
    assert song.loop is True
    path = make_wav(tmp_path, good_wave(song.seconds + 0.05))
    assert any("길이" in line for line in check_mod.check_wav(path, song))


def test_2_silence_is_caught(tmp_path):
    song = a_song()
    path = make_wav(tmp_path, good_wave(song.seconds, amplitude=0.001))
    reasons = check_mod.check_wav(path, song)
    assert any("RMS" in line and "조용" in line for line in reasons)


def test_3_clipping_is_caught(tmp_path):
    song = a_song()
    mono = good_wave(song.seconds, amplitude=3.0)
    path = make_wav(tmp_path, mono)
    assert any("클리핑" in line for line in check_mod.check_wav(path, song))


def test_4_silent_head_is_caught(tmp_path):
    song = a_song()
    mono = good_wave(song.seconds)
    mono[:int(0.25 * RATE)] = 0.0
    path = make_wav(tmp_path, mono)
    assert any("앞 200ms" in line for line in check_mod.check_wav(path, song))


def test_4_silent_tail_is_caught(tmp_path):
    song = a_song()
    mono = good_wave(song.seconds)
    mono[-int(0.25 * RATE):] = 0.0
    path = make_wav(tmp_path, mono)
    assert any("끝 200ms" in line for line in check_mod.check_wav(path, song))


def test_7_quiet_loop_seam_is_caught(tmp_path):
    """루프 곡은 이음매 양 끝 50ms 가 무음에 가까우면 안 된다.

    끝쪽 자리는 **일부러 비워 둔 마지막 16분음표 앞**이다 (check.tail_skip_seconds).
    """
    song = a_song()
    mono = good_wave(song.seconds)
    stop = mono.size - int(check_mod.tail_skip_seconds(song) * RATE)
    mono[stop - int(0.05 * RATE):stop] *= 0.0005
    reasons = check_mod.check_wav(make_wav(tmp_path, mono), song)
    assert any("루프 끝 50ms" in line for line in reasons)


def test_7_quiet_head_is_caught(tmp_path):
    song = a_song()
    mono = good_wave(song.seconds)
    mono[:int(0.05 * RATE)] *= 0.0005
    assert any("루프 첫 50ms" in line for line in check_mod.check_wav(make_wav(tmp_path, mono), song))


def test_7_ignores_the_deliberate_loop_gap(tmp_path):
    """마지막 16분음표를 비워 둔 것만으로는 안 걸려야 한다."""
    song = a_song()
    mono = good_wave(song.seconds)
    mono[mono.size - int(check_mod.tail_skip_seconds(song) * RATE):] = 0.0
    assert not any("루프" in line for line in check_mod.check_wav(make_wav(tmp_path, mono), song))


def test_7_is_skipped_for_non_loop(tmp_path):
    song = a_song(style="victory", bars=8, bpm=120)
    assert song.loop is False
    mono = good_wave(compose_mod.expected_seconds(song))
    edge = int(0.05 * RATE)
    mono[-edge:] *= 0.0005
    assert not any("루프" in line for line in check_mod.check_wav(make_wav(tmp_path, mono), song))


def test_8_low_only_is_caught(tmp_path):
    song = a_song()
    t = np.arange(int(song.seconds * RATE)) / RATE
    path = make_wav(tmp_path, 0.4 * np.sin(2 * np.pi * 60 * t))
    reasons = check_mod.check_wav(path, song)
    assert any("역 에너지" in line for line in reasons)


def test_8_high_only_is_caught(tmp_path):
    song = a_song()
    t = np.arange(int(song.seconds * RATE)) / RATE
    path = make_wav(tmp_path, 0.4 * np.sin(2 * np.pi * 9000 * t))
    assert any("역 에너지" in line for line in check_mod.check_wav(path, song))


def test_stereo_and_mono_measure_the_same(tmp_path):
    mono = good_wave(1.0)
    left = check_mod.measure(write_wav(tmp_path / "s.wav", mono, channels=2))
    right = check_mod.measure(write_wav(tmp_path / "m.wav", mono, channels=1))
    assert left.channels == 2 and right.channels == 1
    assert left.rms == pytest.approx(right.rms, rel=1e-6)


def bare_midi(path, notes, name="melody"):
    midi = mido.MidiFile(type=1, ticks_per_beat=compose_mod.TICKS_PER_BEAT)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    for pitch in notes:
        track.append(mido.Message("note_on", note=pitch, velocity=90, time=0))
        track.append(mido.Message("note_off", note=pitch, velocity=64, time=120))
    midi.tracks.append(track)
    midi.save(str(path))
    return path


def test_5_too_few_notes_is_caught(tmp_path):
    song = a_song(bars=16, tracks={"drums": {"on": False}, "bass": {"on": False},
                                   "chords": {"on": False}})
    path = bare_midi(tmp_path / "few.mid", [60, 62, 64])
    reasons = check_mod.check_midi(path, song)
    assert any("melody 음표 3개" in line for line in reasons)


def test_5_passes_when_enough(tmp_path):
    song = a_song(bars=4, tracks={"drums": {"on": False}, "bass": {"on": False},
                                  "chords": {"on": False}})
    path = bare_midi(tmp_path / "ok.mid", [60] * 8)
    assert check_mod.check_midi(path, song) == []


def test_6_pitch_out_of_range_is_caught(tmp_path):
    song = a_song(bars=4, tracks={"drums": {"on": False}, "bass": {"on": False},
                                  "chords": {"on": False}})
    path = bare_midi(tmp_path / "low.mid", [12] * 8)
    assert any("음높이" in line for line in check_mod.check_midi(path, song))


def test_real_song_passes_midi_check(tmp_path):
    song = a_song()
    path = tmp_path / "real.mid"
    compose_mod.compose(song).save(str(path))
    assert check_mod.check_midi(path, song) == []
