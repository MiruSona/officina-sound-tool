"""검수. 판정만 하고 파일을 안 고친다.

문턱 근거는 Docs/Design/2026-08-25-SFX툴설계.md 5절.
CENTROID_HZ 는 프리셋 7개 × seed 256개를 실제로 구워 잰 min~max 를 아래위 30% 넓힌 값이다
(Test/measure_presets.py).
"""

from dataclasses import dataclass

from soundtool import config
from soundtool.sfx import dsp

CHECK_NAMES = ("frames", "rms", "peak", "clip", "lead", "dc", "centroid")

THRESHOLDS = {
    "frames_offset": 3,        # rfxgen 이 늘 기대치보다 3프레임 더 준다
    "frames_abs": 16,          # ±16 프레임 또는 ±1% 중 큰 쪽
    "frames_ratio": 0.01,
    "rms_min_dbfs": -30.0,
    "peak_dbfs": config.NORMALIZE_DBFS,
    "peak_tolerance_db": 0.15,
    "clip_run": 4,             # 정규화 전 파형에서 풀스케일 연속 4샘플부터 실패
    "lead_seconds": 0.030,
    "dc_max": 0.10,
    "centroid_min_frames": 1024,   # 이보다 짧으면 centroid 검사를 건너뛴다
}

# 프리셋별 스펙트럼 중심 허용 구간 (Hz).
CENTROID_HZ = {
    "coin": (3200.0, 9900.0),
    "laser": (500.0, 12200.0),
    "explosion": (1700.0, 13800.0),
    "powerup": (2600.0, 12400.0),
    "hit": (2300.0, 13900.0),
    "jump": (1600.0, 13700.0),
    "blip": (2400.0, 8800.0),
}


@dataclass
class Metrics:
    """WAV 하나를 재서 나온 값."""

    frames: int
    seconds: float
    peak_dbfs: float
    rms_dbfs: float
    dc: float
    lead_seconds: float | None
    full_scale_run: int
    centroid_hz: float


def measure(wav_path):
    """WAV 하나를 잰다. 파일을 안 고친다."""
    samples = dsp.read_samples(wav_path)
    ints = dsp.read_ints(wav_path)
    frames = len(samples)
    return Metrics(
        frames=frames,
        seconds=frames / config.SAMPLE_RATE,
        peak_dbfs=dsp.to_dbfs(dsp.peak(samples)),
        rms_dbfs=dsp.to_dbfs(dsp.rms(samples)),
        dc=dsp.dc(samples),
        lead_seconds=dsp.lead_silence(samples, config.SAMPLE_RATE),
        full_scale_run=dsp.max_full_scale_run(ints),
        centroid_hz=dsp.spectral_centroid(samples, config.SAMPLE_RATE),
    )


def check(m, expect):
    """걸린 이유 목록. 빈 목록이면 합격.

    `expect` 열쇠 : frames(기대 프레임, +3 전 값) · centroid_hz · min_seconds ·
    max_seconds · skip · clip_run·dc(정규화 전에 잰 값).
    """
    skip = set(expect.get("skip", []))
    reasons = []
    _check_frames(m, expect, skip, reasons)
    _check_levels(m, skip, reasons)
    _check_shape(m, expect, skip, reasons)
    _check_seconds(m, expect, reasons)
    _check_centroid(m, expect, skip, reasons)
    return reasons


def _check_frames(m, expect, skip, reasons):
    wanted = expect.get("frames")
    if wanted is None or "frames" in skip:
        return
    target = wanted + THRESHOLDS["frames_offset"]
    slack = max(THRESHOLDS["frames_abs"], target * THRESHOLDS["frames_ratio"])
    if abs(m.frames - target) <= slack:
        return
    message = f"프레임 {m.frames} (기대 {target})"
    if m.frames < 16:
        message += " — rfxgen 이 .rfx 를 거부했다"
    reasons.append(message)


def _check_levels(m, skip, reasons):
    if "rms" not in skip and m.rms_dbfs < THRESHOLDS["rms_min_dbfs"]:
        reasons.append(f"RMS {m.rms_dbfs:.1f} dBFS (기대 {THRESHOLDS['rms_min_dbfs']:.0f} 이상)")
    if "peak" in skip:
        return
    gap = abs(m.peak_dbfs - THRESHOLDS["peak_dbfs"])
    if gap > THRESHOLDS["peak_tolerance_db"]:
        reasons.append(f"피크 {m.peak_dbfs:.2f} dBFS (기대 {THRESHOLDS['peak_dbfs']:.1f} ±"
                       f"{THRESHOLDS['peak_tolerance_db']})")


def _check_shape(m, expect, skip, reasons):
    run = expect.get("clip_run", m.full_scale_run)
    if "clip" not in skip and run >= THRESHOLDS["clip_run"]:
        reasons.append(f"클리핑 — 풀스케일이 {run}샘플 이어졌다 (문턱 {THRESHOLDS['clip_run']})")

    if "lead" not in skip:
        _check_lead(m, reasons)

    offset = expect.get("dc", m.dc)
    if "dc" not in skip and abs(offset) > THRESHOLDS["dc_max"]:
        reasons.append(f"DC 오프셋 {offset:.3f} (문턱 {THRESHOLDS['dc_max']})")


def _check_lead(m, reasons):
    if m.lead_seconds is None:
        reasons.append("앞머리 — 소리가 한 번도 안 나온다")
        return
    if m.lead_seconds > THRESHOLDS["lead_seconds"]:
        reasons.append(f"앞머리 무음 {m.lead_seconds * 1000:.0f} ms "
                       f"(문턱 {THRESHOLDS['lead_seconds'] * 1000:.0f} ms)")


def _check_seconds(m, expect, reasons):
    low = expect.get("min_seconds")
    high = expect.get("max_seconds")
    if low is not None and m.seconds < low:
        reasons.append(f"{m.seconds:.2f}초 < min_seconds {low}")
    if high is not None and m.seconds > high:
        reasons.append(f"{m.seconds:.2f}초 > max_seconds {high}")


def _check_centroid(m, expect, skip, reasons):
    span = expect.get("centroid_hz")
    if span is None or "centroid" in skip:
        return
    if m.frames < THRESHOLDS["centroid_min_frames"]:
        return
    low, high = span
    if low <= m.centroid_hz <= high:
        return
    reasons.append(f"centroid {m.centroid_hz:.0f}Hz (기대 {low:.0f}~{high:.0f})")
