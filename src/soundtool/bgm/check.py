"""검수. 판정만 하고 파일을 안 고친다 (설계 6절).

WAV 는 표준 `wave` 로 읽고 스펙트럼은 `numpy.fft.rfft` 로 본다.
스테레오는 **두 채널 평균 파형**으로 잰다.
설계에서 바뀐 것 둘 : ① 길이는 자른 뒤 잰다 ② 루프 이음매는 비 대신 양 끝이 무음이 아닌가만 본다.
"""

import math
import wave
from dataclasses import dataclass
from pathlib import Path

import mido
import numpy as np

from soundtool.bgm import compose, patterns

SILENT_DBFS = -999.0

THRESHOLDS = {
    "length_ratio_loop": 0.001,
    "length_ratio_plain": 0.03,
    "rms_min": 0.01,             # 약 −40 dBFS
    "clip_level": 0.99,
    "clip_ratio": 0.0001,        # 전체의 0.01%
    "edge_ms": 200,              # 앞뒤 무음 검사 구간
    "loop_edge_ms": 50,
    "loop_edge_dbfs": -45.0,
    "band_max": 0.80,
}

BAND_EDGES = (250.0, 4000.0)     # 저 / 중 / 고

# 대역별 아래 문턱. GM 사운드폰트로 구운 배경음은 4kHz 위가 원래 아주 적어서
# 설계의 「셋 다 2% 이상」은 못 쓴다. 스타일 6개를 실제로 구워 잰 값이
# 저 25~67% · 중 32~73% · 고 0.06~1.9% 라 그 아래로 넉넉히 잡았다.
BAND_MIN = (0.02, 0.10, 0.0002)


@dataclass
class Metrics:
    frames: int
    rate: int
    channels: int
    seconds: float
    peak_dbfs: float
    rms: float
    rms_dbfs: float
    clip_ratio: float
    head_rms_dbfs: float
    tail_rms_dbfs: float
    edge_head_silent: bool
    edge_tail_silent: bool
    bands: tuple


def to_dbfs(value):
    if value <= 0:
        return SILENT_DBFS
    return 20.0 * math.log10(value)


def read_mono(path):
    """16비트 WAV 를 −1~1 실수 한 줄로. 스테레오는 두 채널 평균."""
    with wave.open(str(Path(path)), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.getnframes()
        raw = handle.readframes(frames)
    if width != 2:
        raise ValueError(f"16비트만 잰다 (이 파일은 {width * 8}비트)")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate, frames, channels


def tail_skip_seconds(song):
    """loop 곡은 마지막 16분음표를 일부러 비워 둔다. 그 자리는 이음매로 안 본다."""
    if not song.loop:
        return 0.0
    return compose.LOOP_GAP_BEAT * 60.0 / song.bpm


def measure(path, tail_skip=0.0):
    mono, rate, frames, channels = read_mono(path)
    edge = max(1, rate * THRESHOLDS["edge_ms"] // 1000)
    loop_edge = max(1, rate * THRESHOLDS["loop_edge_ms"] // 1000)
    seam = mono[:mono.size - int(tail_skip * rate)] if tail_skip else mono
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    value = _rms(mono)
    clipped = int(np.count_nonzero(np.abs(mono) >= THRESHOLDS["clip_level"]))
    return Metrics(
        frames=frames,
        rate=rate,
        channels=channels,
        seconds=frames / rate,
        peak_dbfs=to_dbfs(peak),
        rms=value,
        rms_dbfs=to_dbfs(value),
        clip_ratio=clipped / mono.size if mono.size else 0.0,
        head_rms_dbfs=to_dbfs(_rms(mono[:loop_edge])),
        tail_rms_dbfs=to_dbfs(_rms(seam[-loop_edge:])),
        edge_head_silent=_rms(mono[:edge]) <= 0.0,
        edge_tail_silent=_rms(mono[-edge:]) <= 0.0,
        bands=band_energy(mono, rate),
    )


def _rms(x):
    if x.size == 0:
        return 0.0
    return float(math.sqrt(float(np.mean(x * x))))


def band_energy(mono, rate):
    """저(<250Hz) · 중(250~4k) · 고(>4k) 에너지 비."""
    if mono.size < 1024:
        return (0.0, 0.0, 0.0)
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(mono.size))) ** 2
    freqs = np.fft.rfftfreq(mono.size, 1.0 / rate)
    total = float(spectrum.sum())
    if total <= 0:
        return (0.0, 0.0, 0.0)
    low = float(spectrum[freqs < BAND_EDGES[0]].sum())
    mid = float(spectrum[(freqs >= BAND_EDGES[0]) & (freqs < BAND_EDGES[1])].sum())
    high = float(spectrum[freqs >= BAND_EDGES[1]].sum())
    return (low / total, mid / total, high / total)


def check_wav(wav_path, song, metrics=None):
    """1·2·3·4·7·8 번. 걸린 이유 목록을 준다."""
    m = metrics or measure(wav_path, tail_skip_seconds(song))
    reasons = []
    _check_length(m, song, reasons)
    _check_level(m, reasons)
    _check_edges(m, reasons)
    _check_loop_edges(m, song, reasons)
    _check_bands(m, reasons)
    return reasons


def _check_length(m, song, reasons):
    wanted = compose.expected_seconds(song)
    ratio = THRESHOLDS["length_ratio_loop"] if song.loop else THRESHOLDS["length_ratio_plain"]
    if abs(m.seconds - wanted) <= wanted * ratio:
        return
    reasons.append(f"길이 {m.seconds:.3f}초 (기대 {wanted:.3f}초 ±{ratio * 100:g}%)")


def _check_level(m, reasons):
    if m.rms < THRESHOLDS["rms_min"]:
        reasons.append(f"RMS {m.rms_dbfs:.1f} dBFS — 너무 조용하다 (문턱 −40)")
    if m.clip_ratio >= THRESHOLDS["clip_ratio"]:
        reasons.append(f"클리핑 {m.clip_ratio * 100:.3f}% (문턱 0.01%)")


def _check_edges(m, reasons):
    if m.edge_head_silent:
        reasons.append(f"앞 {THRESHOLDS['edge_ms']}ms 가 통째로 무음이다")
    if m.edge_tail_silent:
        reasons.append(f"끝 {THRESHOLDS['edge_ms']}ms 가 통째로 무음이다")


def _check_loop_edges(m, song, reasons):
    """루프 이음매 — 양 끝 50ms 가 무음이 아니면 된다 (비 검사는 뺐다)."""
    if not song.loop:
        return
    floor = THRESHOLDS["loop_edge_dbfs"]
    if m.head_rms_dbfs < floor:
        reasons.append(f"루프 첫 50ms RMS {m.head_rms_dbfs:.1f} dBFS (문턱 {floor:.0f})")
    if m.tail_rms_dbfs < floor:
        reasons.append(f"루프 끝 50ms RMS {m.tail_rms_dbfs:.1f} dBFS (문턱 {floor:.0f})")


def _check_bands(m, reasons):
    names = ("저", "중", "고")
    high = THRESHOLDS["band_max"]
    for name, share, low in zip(names, m.bands, BAND_MIN):
        if low <= share <= high:
            continue
        reasons.append(f"{name}역 에너지 {share * 100:.3f}% (기대 {low * 100:g}~{high * 100:g}%)")


def check_midi(mid_path, song):
    """5·6 번. fluidsynth 없이도 돈다."""
    counts, pitches = read_midi_notes(mid_path)
    reasons = []
    for role, setting in song.tracks.items():
        if not setting.on:
            continue
        got = counts.get(role, 0)
        if got < song.bars:
            reasons.append(f"{role} 음표 {got}개 (마디 {song.bars}개보다 적다)")
    outside = [p for p in pitches if not patterns.PITCH_LOW <= p <= patterns.PITCH_HIGH]
    if outside:
        reasons.append(f"음높이가 {patterns.PITCH_LOW}..{patterns.PITCH_HIGH} 를 벗어났다 : "
                       f"{sorted(set(outside))[:5]}")
    return reasons


def read_midi_notes(mid_path):
    """트랙 이름 → 음표 수, 그리고 나온 음높이 전부."""
    midi = mido.MidiFile(str(Path(mid_path)))
    counts = {}
    pitches = []
    for track in midi.tracks:
        name = track.name
        for message in track:
            if message.type != "note_on" or message.velocity == 0:
                continue
            counts[name] = counts.get(name, 0) + 1
            pitches.append(message.note)
    return counts, pitches
