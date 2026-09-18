"""곡 하나를 조립해 mido.MidiFile 로 만든다 (설계 4).

박은 float 로 다루다가 **여기서 한 번만** tick 정수로 바꾼다. 반올림 오차가 한 자리에만 생긴다.
"""

from dataclasses import dataclass

import mido

from soundtool.bgm import patterns, spec as spec_mod, theory

TICKS_PER_BEAT = 480
BEATS_PER_PHRASE = patterns.BARS_PER_PHRASE * patterns.BEATS_PER_BAR
TAIL_SECONDS = 2.0          # loop 이 거짓일 때 뒤에 두는 빈 자리
LOOP_GAP_BEAT = 0.25        # loop 이면 마지막 마디 음을 16분음표 하나 앞에서 끊는다

# 역할 → (채널, 만드는 함수 이름). 드럼 채널 9 는 GM 에서 타악기 고정이다.
CHANNELS = {"melody": 0, "chords": 1, "bass": 2, "drums": 9}
TRACK_ORDER = ("melody", "chords", "bass", "drums")


@dataclass
class ChordSlot:
    roman: str
    pitches: list


def plan_chords(song):
    """진행을 마디에 깐다. 박 하나에 슬롯 하나를 준다 (설계 3-1).

    진행 하나가 4마디 악구를 채운다. 길이가 4면 마디마다, 2면 두 마디씩, 8이면 반 마디씩이다.
    길이가 4 이하면 마디 경계에서만 코드를 바꾼다. 안 그러면 온마디 셀이 가운데 코드를 못 친다.
    """
    romans = song.progression
    slots = []
    for beat in range(song.beats):
        inside = beat % BEATS_PER_PHRASE
        if len(romans) <= patterns.BARS_PER_PHRASE:
            bar = inside // patterns.BEATS_PER_BAR
            index = min(len(romans) - 1, int(bar * len(romans) / patterns.BARS_PER_PHRASE))
        else:
            index = min(len(romans) - 1, int(inside * len(romans) / BEATS_PER_PHRASE))
        roman = romans[index]
        slots.append(ChordSlot(roman, theory.chord_pitches(roman, song.key)))
    return slots


def make_notes(song):
    """켠 트랙의 음표를 역할별로 만든다. 트랙마다 난수 흐름이 따로다."""
    preset = patterns.STYLES[song.style]
    slots = plan_chords(song)
    made = {}
    if _on(song, "drums"):
        made["drums"] = patterns.make_drums(preset, spec_mod.stream(song.seed, "drums"), song.bars)
    if _on(song, "bass"):
        made["bass"] = patterns.make_bass(preset, spec_mod.stream(song.seed, "bass"), slots)
    if _on(song, "chords"):
        made["chords"] = patterns.make_chords(preset, spec_mod.stream(song.seed, "chords"), slots)
    if _on(song, "melody"):
        made["melody"] = patterns.make_melody(preset, spec_mod.stream(song.seed, "melody"),
                                              slots, song)
    for role, notes in made.items():
        made[role] = _finish_notes(song, role, notes)
    if made.get("melody"):
        # 루프 여백으로 마지막 음을 버렸을 수 있어 규칙 5 를 여기서 한 번 더 건다.
        patterns.resolve_ending(preset, made["melody"], song, song.tracks["melody"].octave * 12)
    return made


def compose(song):
    """MIDI 한 판. 트랙 0 은 메타만, 1~4 는 역할별이다."""
    made = make_notes(song)
    midi = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    midi.tracks.append(_meta_track(song))
    end_tick = _end_tick(song)
    for role in TRACK_ORDER:
        notes = made.get(role)
        if not notes:
            continue
        midi.tracks.append(_role_track(song, role, notes, end_tick))
    return midi


def expected_seconds(song):
    """구운 WAV 를 잘라 맞출 길이. loop 이 거짓이면 뒤에 빈 2초가 붙는다."""
    if song.loop:
        return song.seconds
    return song.seconds + TAIL_SECONDS


def _on(song, role):
    setting = song.tracks.get(role)
    return bool(setting and setting.on)


def _finish_notes(song, role, notes):
    """옥타브 덮어쓰기 · 음역 접기 · loop 끝 다듬기를 한 자리에서 한다."""
    shift = song.tracks[role].octave * 12
    limit = song.beats - LOOP_GAP_BEAT if song.loop else song.beats
    out = []
    for note in notes:
        if note.start_beat >= limit:
            continue
        pitch = note.pitch if role == "drums" else note.pitch + shift
        note.pitch = theory.fold_into(pitch, patterns.PITCH_LOW, patterns.PITCH_HIGH)
        note.length_beat = min(note.length_beat, limit - note.start_beat)
        out.append(note)
    return out


def _end_tick(song):
    beats = song.beats
    if not song.loop:
        beats += TAIL_SECONDS * song.bpm / 60.0
    return round(beats * TICKS_PER_BEAT)


def _meta_track(song):
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=song.name, time=0))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.bpm), time=0))
    track.append(mido.MetaMessage("end_of_track", time=_end_tick(song)))
    return track


def _role_track(song, role, notes, end_tick):
    channel = CHANNELS[role]
    events = []
    if role != "drums":
        events.append((0, 0, mido.Message("program_change", channel=channel,
                                          program=song.tracks[role].program, time=0)))
    for note in notes:
        start = round(note.start_beat * TICKS_PER_BEAT)
        stop = max(start + 1, round((note.start_beat + note.length_beat) * TICKS_PER_BEAT))
        events.append((start, 1, mido.Message("note_on", channel=channel, note=note.pitch,
                                              velocity=note.velocity, time=0)))
        events.append((stop, 0, mido.Message("note_off", channel=channel, note=note.pitch,
                                             velocity=64, time=0)))
    return _to_track(events, end_tick, role)


def _to_track(events, end_tick, name):
    """절대 tick 을 delta 로 바꾼다. 같은 자리면 note_off 를 먼저 보낸다."""
    events.sort(key=lambda row: (row[0], row[1]))
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    previous = 0
    for tick, _, message in events:
        message.time = tick - previous
        previous = tick
        track.append(message)
    track.append(mido.MetaMessage("end_of_track", time=max(0, end_tick - previous)))
    return track
