"""WAV 를 표준 라이브러리만으로 재서 값을 찍는다 (numpy 없이).

쓰기 : python measure_wav.py <wav> [<wav> ...]
찍는 것 : 프레임 수 · 길이(초) · 피크(dBFS) · RMS(dBFS) · |x|>=0.99 샘플 수
        · 앞 50ms RMS · 끝 50ms RMS · 그 비 (루프 이음매 검수 7번)
"""

import array
import math
import sys
import wave
from pathlib import Path

CLIP = 0.99
EDGE_MS = 50


def read_mono_floats(path: Path):
    with wave.open(str(path), "rb") as w:
        nch, width, rate, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nframes)
    if width != 2:
        raise ValueError(f"16비트만 잰다 (이 파일은 {width * 8}비트)")
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder == "big":
        samples.byteswap()
    scale = 1.0 / 32768.0
    if nch == 1:
        mono = [s * scale for s in samples]
    else:
        mono = [sum(samples[i:i + nch]) * scale / nch for i in range(0, len(samples), nch)]
    return mono, rate, nframes, nch


def rms(xs) -> float:
    if not xs:
        return 0.0
    return math.sqrt(sum(x * x for x in xs) / len(xs))


def db(v: float) -> float:
    return -999.0 if v <= 0 else 20 * math.log10(v)


def measure(path: Path) -> dict:
    mono, rate, nframes, nch = read_mono_floats(path)
    edge = max(1, rate * EDGE_MS // 1000)
    head, tail = rms(mono[:edge]), rms(mono[-edge:])
    return {
        "file": path.name,
        "rate": rate,
        "ch": nch,
        "frames": nframes,
        "seconds": nframes / rate,
        "peak_db": db(max((abs(x) for x in mono), default=0.0)),
        "rms_db": db(rms(mono)),
        "clip": sum(1 for x in mono if abs(x) >= CLIP),
        "head_rms": head,
        "tail_rms": tail,
        "ratio": (tail / head) if head > 0 else float("inf"),
    }


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        print(__doc__)
        return 2
    print("| 파일 | 프레임 | 초 | 피크 dBFS | RMS dBFS | 클리핑 | 끝/첫 50ms 비 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for p in paths:
        m = measure(p)
        print(f"| {m['file']} | {m['frames']} | {m['seconds']:.3f} | {m['peak_db']:.2f} "
              f"| {m['rms_db']:.2f} | {m['clip']} | {m['ratio']:.3f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
