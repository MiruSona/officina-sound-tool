"""바깥 프로그램(rfxgen)을 부르는 유일한 자리. 굽고 정규화하고 검수한다."""

import os
import shutil
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path

from soundtool import config
from soundtool.sfx import check, presets, rfx

FAILED_DIR = "_failed"
_MAX_INT16 = 32767


class RfxgenMissing(Exception):
    """rfxgen.exe 를 못 찾았다. 종료 코드 3 으로 이어진다."""


@dataclass
class Result:
    """소리 하나의 결과."""

    name: str
    preset: str
    seed: int
    tags: list = field(default_factory=list)
    ok: bool = False
    reasons: list = field(default_factory=list)
    metrics: check.Metrics | None = None
    raw_metrics: check.Metrics | None = None   # 정규화 전. 클리핑·DC 는 이걸로 본다
    expected_frames: int = 0
    wav_path: Path | None = None


def find_rfxgen(override=None):
    """인자 → 환경변수 → 기본 경로 순서로 찾는다. 없으면 RfxgenMissing.

    `--rfxgen` 로 직접 준 경로는 없으면 바로 실패한다. 오타를 냈는데 기본 경로로 조용히
    넘어가면 어느 판으로 구운 것인지 알 수 없다.
    """
    if override is not None:
        path = Path(override)
        if path.is_file():
            return path
        raise RfxgenMissing(_missing_message([str(path)]))
    tried = []
    for candidate in (os.environ.get(config.RFXGEN_ENV), config.RFXGEN_PATH):
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return path
        tried.append(str(path))
    raise RfxgenMissing(_missing_message(tried))


def _missing_message(tried):
    lines = ["rfxgen 실행파일을 못 찾았다. 찾아본 곳 :"]
    lines += [f"  - {where}" for where in tried]
    lines.append(f"받는 곳 : {config.RFXGEN_URL}")
    lines.append(f"--rfxgen <경로> 로 직접 알려주거나 {config.RFXGEN_ENV} 환경변수에 넣어도 된다.")
    return "\n".join(lines)


def burn(rfx_bytes, wav_path, rfxgen):
    """임시 `.rfx` 를 쓰고 rfxgen 을 부른다. 실패하면 RuntimeError."""
    wav_path = Path(wav_path)
    with tempfile.TemporaryDirectory(prefix="soundtool_") as tmp:
        rfx_path = Path(tmp) / "sound.rfx"
        rfx_path.write_bytes(rfx_bytes)
        command = [
            str(rfxgen),
            "--input", str(rfx_path),
            "--output", str(wav_path),
            "--format", f"{config.SAMPLE_RATE},{config.SAMPLE_BITS},{config.CHANNELS}",
        ]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, errors="replace",
                                   timeout=30)
        except subprocess.TimeoutExpired as err:
            raise RuntimeError("rfxgen 이 30초 안에 안 끝났다") from err
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-3:])
        raise RuntimeError(f"rfxgen exit {proc.returncode}\n{tail}")
    if not wav_path.is_file():
        raise RuntimeError("WAV 가 안 나왔다")


def normalize(wav_path, target_dbfs):
    """피크를 target_dbfs 에 맞추고 곱한 배수를 준다. 무음이면 1.0."""
    wav_path = Path(wav_path)
    with wave.open(str(wav_path), "rb") as handle:
        params = handle.getparams()
        raw = handle.readframes(handle.getnframes())
    values = _unpack_int16(raw)
    top = max((abs(v) for v in values), default=0)
    if top == 0:
        return 1.0
    wanted = (10.0 ** (target_dbfs / 20.0)) * _MAX_INT16
    gain = wanted / top
    scaled = [_clip_int16(round(v * gain)) for v in values]
    with wave.open(str(wav_path), "wb") as handle:
        handle.setparams(params)
        handle.writeframes(_pack_int16(scaled))
    return gain


def _unpack_int16(raw):
    return struct.unpack(f"<{len(raw) // 2}h", raw)


def _pack_int16(values):
    return struct.pack(f"<{len(values)}h", *values)


def _clip_int16(value):
    return max(-_MAX_INT16, min(_MAX_INT16, value))


def make_one(sound, out_dir, rfxgen, keep_failed=False):
    """소리 하나. 추첨 → 굽기 → 정규화 → 검수. 예외를 밖으로 안 던진다."""
    result = Result(
        name=sound["name"],
        preset=sound["preset"],
        seed=sound["seed"],
        tags=list(sound.get("tags", [])),
    )
    try:
        rand_seed, params = params_for(sound)
        rfx_bytes = rfx.pack(rand_seed, params)
    except ValueError as err:
        result.reasons = [str(err)]
        return result
    result.expected_frames = rfx.expected_frames(params)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="soundtool_wav_") as tmp:
        staged = Path(tmp) / f"{result.name}.wav"
        try:
            burn(rfx_bytes, staged, rfxgen)
        except RuntimeError as err:
            result.reasons = [str(err)]
            return result
        _finish(result, sound, staged, out_dir, keep_failed)
    return result


def _finish(result, sound, staged, out_dir, keep_failed):
    """정규화하고 검수한 뒤, 통과한 것만 산출 폴더로 옮긴다."""
    raw = check.measure(staged)          # 클리핑·DC 는 정규화 전에 재야 뜻이 있다
    normalize(staged, config.NORMALIZE_DBFS)
    metrics = check.measure(staged)
    result.raw_metrics = raw
    result.metrics = metrics
    result.reasons = check.check(metrics, _expect_for(result, sound, raw))
    result.ok = not result.reasons

    if result.ok:
        result.wav_path = _move(staged, out_dir / f"{result.name}.wav")
        return
    if keep_failed:
        failed_dir = out_dir / FAILED_DIR
        failed_dir.mkdir(parents=True, exist_ok=True)
        result.wav_path = _move(staged, failed_dir / f"{result.name}.wav")


def _move(staged, target):
    shutil.move(str(staged), str(target))
    return target


def params_for(sound):
    """추첨 → 스펙의 params 로 덮어쓰기. `--dry-run` 도 이걸 쓴다 (추첨과 결과가 갈리면 안 된다)."""
    rand_seed, params = presets.draw(sound["preset"], sound["seed"])
    params.update(sound.get("params", {}))
    return rand_seed, params


def _expect_for(result, sound, raw):
    limits = dict(sound.get("check", {}))
    expect = {
        "frames": result.expected_frames,
        "centroid_hz": tuple(limits.pop("centroid_hz", presets.centroid_range(result.preset))),
        "clip_run": raw.full_scale_run,
        "dc": raw.dc,
    }
    expect.update(limits)
    return expect


def make_all(spec_sounds, out_dir, rfxgen, keep_failed=False):
    """전부 굽는다. 하나가 실패해도 멈추지 않는다."""
    return [make_one(sound, out_dir, rfxgen, keep_failed) for sound in spec_sounds]
