"""셈만 한다. 재는 법은 설계 5절 「재는 법」 그대로다.

numpy 가 있으면 FFT 만 numpy 로 돌린다. 없으면 순수 파이썬 radix-2 FFT 로 떨어진다.
둘 다 결과가 같고, 없다고 못 도는 자리는 없다.
"""

import array
import cmath
import math
import sys
import wave
from pathlib import Path

try:
    import numpy as _np
except ImportError:
    _np = None

WINDOW = 1024
HOP = 512
FULL_SCALE = 32767
SILENT_DBFS = -999.0
LEAD_THRESHOLD = 0.01

_HANNING = [0.5 - 0.5 * math.cos(2 * math.pi * i / WINDOW) for i in range(WINDOW)]


def read_samples(path):
    """16bit 모노 WAV → −1~1 실수 목록."""
    path = Path(path)
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        if channels != 1 or width != 2:
            raise ValueError(f"{path.name} : 16bit 모노가 아니다 (채널 {channels}, {width * 8}bit)")
        raw = handle.readframes(handle.getnframes())
    return [value / FULL_SCALE for value in _to_ints(raw)]


def read_ints(path):
    """정규화 전 클리핑을 보려면 정수 그대로가 필요하다."""
    path = Path(path)
    with wave.open(str(path), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
    return _to_ints(raw)


def _to_ints(raw):
    out = array.array("h")
    out.frombytes(raw)
    if sys.byteorder == "big":
        out.byteswap()
    return out


def rms(x):
    if not x:
        return 0.0
    return math.sqrt(sum(v * v for v in x) / len(x))


def peak(x):
    if not x:
        return 0.0
    return max(abs(v) for v in x)


def dc(x):
    if not x:
        return 0.0
    return sum(x) / len(x)


def lead_silence(x, sample_rate):
    """처음 |x| > 0.01 이 나올 때까지의 초. 끝까지 조용하면 None."""
    for index, value in enumerate(x):
        if abs(value) > LEAD_THRESHOLD:
            return index / sample_rate
    return None


def max_full_scale_run(values, limit=FULL_SCALE):
    """|x| >= limit 인 샘플이 이어진 최대 길이. 정수 표본을 받는다."""
    best = 0
    run = 0
    for value in values:
        if abs(value) >= limit:
            run += 1
            if run > best:
                best = run
            continue
        run = 0
    return best


def to_dbfs(value):
    if value <= 0:
        return SILENT_DBFS
    return 20.0 * math.log10(value)


def spectral_centroid(x, sample_rate):
    """1024점 해닝창을 512점씩 밀며 FFT. 소리 전체를 훑어 합산한다.

    1024프레임보다 짧으면 0 을 준다 (검사를 건너뛰라는 뜻).
    """
    if len(x) < WINDOW:
        return 0.0
    weighted = 0.0
    total = 0.0
    step = sample_rate / WINDOW
    for start in range(0, len(x) - WINDOW + 1, HOP):
        frame = [x[start + i] * _HANNING[i] for i in range(WINDOW)]
        spectrum = fft(frame)
        for k in range(1, WINDOW // 2):
            size = abs(spectrum[k])
            weighted += size * k * step
            total += size
    if total == 0.0:
        return 0.0
    return weighted / total


def fft(x):
    """radix-2 FFT. 길이는 2의 거듭제곱이어야 한다."""
    if _np is not None:
        return list(_np.fft.fft(_np.asarray(x, dtype=float)))
    return _fft_python(list(x))


def _fft_python(values):
    count = len(values)
    if count & (count - 1):
        raise ValueError(f"FFT 길이는 2의 거듭제곱이어야 한다 (받은 것 {count})")
    out = _bit_reverse(values)
    size = 2
    while size <= count:
        step = cmath.exp(-2j * math.pi / size)
        half = size // 2
        for start in range(0, count, size):
            twiddle = 1 + 0j
            for offset in range(half):
                left = out[start + offset]
                right = out[start + offset + half] * twiddle
                out[start + offset] = left + right
                out[start + offset + half] = left - right
                twiddle *= step
        size *= 2
    return out


def _bit_reverse(values):
    count = len(values)
    out = [complex(v) for v in values]
    target = 0
    for index in range(1, count):
        bit = count >> 1
        while target & bit:
            target ^= bit
            bit >>= 1
        target |= bit
        if index < target:
            out[index], out[target] = out[target], out[index]
    return out
