"""바깥 프로그램(fluidsynth)을 부르는 유일한 자리. 굽고 꼬리를 자른다.

FluidSynth 는 MIDI 가 끝나도 **내용과 상관없이 3.03초 꼬리**를 늘 붙인다 (`-R 0 -C 0` 이어도 같다).
그래서 loop 이든 아니든 **모든 곡을 표준 `wave` 로 기대 길이에 맞춰 자른다**.
"""

import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

from soundtool import config
from soundtool.bgm import check as check_mod, compose

TIMEOUT_SECONDS = 120
RETRY_GAIN_RATIO = 0.7       # 클리핑이면 딱 한 번 이 배수로 다시 굽는다
STDERR_HEAD = 200


class ToolsMissing(Exception):
    """fluidsynth 나 사운드폰트를 못 찾았다. 종료 코드 3 으로 이어진다."""


@dataclass
class ToolPaths:
    fluidsynth: Path
    soundfont: Path


@dataclass
class RenderResult:
    ok: bool = False
    gain: float = 0.0
    retried: bool = False
    metrics: check_mod.Metrics | None = None
    reasons: list = field(default_factory=list)


def find_tools(fluidsynth=None, soundfont=None):
    """인자 → 기본 경로 순서로 찾는다. 없으면 ToolsMissing."""
    exe = Path(fluidsynth) if fluidsynth else config.FLUIDSYNTH_PATH
    sf2 = Path(soundfont) if soundfont else config.SOUNDFONT_PATH
    missing = []
    if not exe.is_file():
        missing.append(f"fluidsynth 실행파일 : {exe}")
    if not sf2.is_file():
        missing.append(f"사운드폰트 : {sf2}")
    if missing:
        raise ToolsMissing(_missing_message(missing))
    return ToolPaths(exe, sf2)


def _missing_message(missing):
    lines = ["fluidsynth 굽기 도구를 못 찾았다 :"]
    lines += [f"  - {where}" for where in missing]
    lines.append("--fluidsynth <exe> · --soundfont <sf2> 로 알려주거나")
    lines.append("Docs/Design/2026-08-25-BGM툴설계.md 8장대로 설치해라.")
    return "\n".join(lines)


def command_for(mid_path, wav_path, tools, gain, rate, reverb_off):
    command = [
        str(tools.fluidsynth), "-ni", "-q", "-T", "wav", "-O", "s16",
        "-r", str(rate), "-g", f"{gain:.3f}",
    ]
    if reverb_off:
        command += ["-R", "0", "-C", "0"]
    command += ["-F", str(wav_path), str(tools.soundfont), str(mid_path)]
    return command


def burn(mid_path, wav_path, tools, gain, rate, reverb_off):
    """fluidsynth 한 번. 실패하면 RuntimeError."""
    command = command_for(mid_path, wav_path, tools, gain, rate, reverb_off)
    try:
        proc = subprocess.run(command, capture_output=True, text=True, errors="replace",
                              shell=False, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as err:
        raise RuntimeError(f"fluidsynth 가 {TIMEOUT_SECONDS}초를 넘겼다") from err
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[:STDERR_HEAD]
        raise RuntimeError(f"fluidsynth exit {proc.returncode} — {tail}")
    if not Path(wav_path).is_file():
        raise RuntimeError("WAV 가 안 나왔다 (exit 0 이어도 안 믿는다)")


def trim(wav_path, wanted_frames):
    """앞에서부터 wanted_frames 만큼만 남기고 다시 쓴다. 모자라면 RuntimeError."""
    wav_path = Path(wav_path)
    with wave.open(str(wav_path), "rb") as handle:
        params = handle.getparams()
        frames = handle.getnframes()
        raw = handle.readframes(frames)
    if frames < wanted_frames:
        raise RuntimeError(f"구운 것이 짧다 — {frames}프레임 (기대 {wanted_frames})")
    width = params.sampwidth * params.nchannels
    with wave.open(str(wav_path), "wb") as handle:
        handle.setparams(params._replace(nframes=wanted_frames))
        handle.writeframes(raw[:wanted_frames * width])


def render(mid_path, wav_path, song, tools, gain=None, rate=None):
    """굽고 자르고 잰다. 클리핑이면 gain 을 0.7배로 딱 한 번만 다시 굽는다."""
    gain = config.FLUIDSYNTH_GAIN if gain is None else gain
    rate = config.BGM_SAMPLE_RATE if rate is None else rate
    result = RenderResult(gain=gain)
    for attempt in range(2):
        try:
            burn(mid_path, wav_path, tools, result.gain, rate, song.loop)
            trim(wav_path, expected_frames(song, rate))
        except RuntimeError as err:
            result.reasons = [str(err)]
            return result
        result.metrics = check_mod.measure(wav_path, check_mod.tail_skip_seconds(song))
        if not _clipped(result.metrics) or attempt == 1:
            break
        result.gain = round(result.gain * RETRY_GAIN_RATIO, 3)
        result.retried = True
    result.reasons = check_mod.check_wav(wav_path, song, result.metrics)
    result.ok = not result.reasons
    return result


def expected_frames(song, rate=None):
    rate = config.BGM_SAMPLE_RATE if rate is None else rate
    return round(compose.expected_seconds(song) * rate)


def _clipped(metrics):
    return metrics.clip_ratio >= check_mod.THRESHOLDS["clip_ratio"]
