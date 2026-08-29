"""시험용 MIDI 를 표준 라이브러리만으로 만든다 (mido 없이).

4마디 · 4/4 · 120bpm · ticks_per_beat 480 → 4마디 = 7680 tick.
트랙 0 메타, 1 피아노, 2 베이스, 3 드럼.
쓰는 곳 : fluidsynth 굽기 시험 (SoundTool/Test/probe_bgm.mid)
"""

import struct
from pathlib import Path

TPB = 480
BEATS_PER_BAR = 4
BARS = 4
END_TICK = TPB * BEATS_PER_BAR * BARS  # 7680
BPM = 120


def vlq(n: int) -> bytes:
    """가변 길이 수 (MIDI delta time)."""
    if n < 0:
        raise ValueError("음수 delta")
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def track_chunk(events: list[tuple[int, bytes]]) -> bytes:
    """(절대 tick, 이벤트 바이트) 목록을 트랙 청크로. end_of_track 은 여기서 붙인다."""
    events = sorted(events, key=lambda e: e[0])
    body = bytearray()
    prev = 0
    for tick, data in events:
        body += vlq(tick - prev)
        body += data
        prev = tick
    body += vlq(END_TICK - prev) + b"\xff\x2f\x00"  # end_of_track
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def note(channel: int, pitch: int, velocity: int) -> bytes:
    return struct.pack("BBB", 0x90 | channel, pitch, velocity)


def note_off(channel: int, pitch: int) -> bytes:
    return struct.pack("BBB", 0x80 | channel, pitch, 0x40)


def program(channel: int, prog: int) -> bytes:
    return struct.pack("BB", 0xC0 | channel, prog)


def meta_track() -> bytes:
    usec = round(60_000_000 / BPM)
    ev = [
        (0, b"\xff\x03" + vlq(len(b"probe_bgm")) + b"probe_bgm"),  # track_name
        (0, b"\xff\x58\x04\x04\x02\x18\x08"),                      # 4/4
        (0, b"\xff\x51\x03" + usec.to_bytes(3, "big")),            # set_tempo
    ]
    return track_chunk(ev)


def piano_track() -> bytes:
    """채널 0, program 0, C4-E4-G4-C5 4분음표 반복 (16개)."""
    ev = [(0, program(0, 0))]
    cycle = [60, 64, 67, 72]
    for i in range(BEATS_PER_BAR * BARS):
        t = i * TPB
        p = cycle[i % 4]
        ev.append((t, note(0, p, 95)))
        ev.append((t + TPB, note_off(0, p)))
    return track_chunk(ev)


def bass_track() -> bytes:
    """채널 1, program 33, C2(36) 온음표 마디마다."""
    ev = [(0, program(1, 33))]
    for bar in range(BARS):
        t = bar * TPB * BEATS_PER_BAR
        ev.append((t, note(1, 36, 85)))
        ev.append((t + TPB * BEATS_PER_BAR, note_off(1, 36)))
    return track_chunk(ev)


def drum_track() -> bytes:
    """채널 9, 킥 36 · 스네어 38 번갈아 4분음표. program_change 안 보낸다."""
    ev = []
    for i in range(BEATS_PER_BAR * BARS):
        t = i * TPB
        p = 36 if i % 2 == 0 else 38
        ev.append((t, note(9, p, 100 if p == 36 else 95)))
        ev.append((t + TPB, note_off(9, p)))
    return track_chunk(ev)


def main() -> None:
    tracks = [meta_track(), piano_track(), bass_track(), drum_track()]
    head = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), TPB)
    out = Path(__file__).with_name("probe_bgm.mid")
    out.write_bytes(head + b"".join(tracks))
    print(f"{out} : {out.stat().st_size} bytes, 끝 tick {END_TICK}")


if __name__ == "__main__":
    main()
