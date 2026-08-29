"""프리셋별 실측값을 재서 golden.json 과 centroid 구간을 낸다.

설계 5절의 문턱은 seed 24개 표본이었다. 이 스크립트로 256개를 다시 재서 덮는다.

    python SoundTool/Test/measure_presets.py [--seeds 256] [--stats <경로>]

- `Test/golden.json` 을 다시 쓴다 (test_cli.py 가 쓰는 기대값).
- centroid 구간은 실측 min~max 를 아래위 30% 넓힌 값이다. 표로 찍어 준다 — check.py 에 옮긴다.
"""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from soundtool import config                      # noqa: E402
from soundtool.sfx import check, make, presets    # noqa: E402

GOLDEN_PATH = HERE / "golden.json"
GOLDEN_SEEDS = (1, 2, 3)
WIDEN = 0.30


def bake(preset, seed, out_dir, rfxgen):
    """소리 하나를 굽고 잰 값을 준다."""
    sound = {"name": f"m_{preset}_{seed}", "preset": preset, "seed": seed}
    result = make.make_one(sound, out_dir, rfxgen, keep_failed=True)
    return result


def collect(preset, seeds, out_dir, rfxgen):
    rows = []
    for seed in range(seeds):
        result = bake(preset, seed, out_dir, rfxgen)
        if result.metrics is None:
            print(f"  ! {preset} seed {seed} : {result.reasons}")
            continue
        rows.append(result)
    return rows


def span(rows, pick):
    values = [pick(row) for row in rows]
    return min(values), max(values)


def widen(low, high):
    return round(low * (1 - WIDEN), -2), round(high * (1 + WIDEN), -2)


def summarize(preset, rows):
    frames = span(rows, lambda r: r.metrics.frames)
    # centroid 는 1024프레임 미만이면 0 이라 뜻이 없다. 그런 것은 뺀다.
    long_rows = [r for r in rows if r.metrics.frames >= check.THRESHOLDS["centroid_min_frames"]]
    centroid = span(long_rows or rows, lambda r: r.metrics.centroid_hz)
    rms = span(rows, lambda r: r.metrics.rms_dbfs)
    dc_raw = max(abs(r.raw_metrics.dc) for r in rows)
    dc_norm = max(abs(r.metrics.dc) for r in rows)
    clip = max(r.raw_metrics.full_scale_run for r in rows)
    low, high = widen(*centroid)
    return {
        "preset": preset,
        "count": len(rows),
        "failed": sum(1 for r in rows if not r.ok),
        "frames": list(frames),
        "seconds": [frames[0] / config.SAMPLE_RATE, frames[1] / config.SAMPLE_RATE],
        "rms_dbfs": list(rms),
        "centroid_hz": list(centroid),
        "centroid_range": [low, high],
        "dc_max_raw": dc_raw,
        "dc_max_normalized": dc_norm,
        "clip_run_max": clip,
    }


def golden_rows(preset, rows):
    out = {}
    by_seed = {row.seed: row for row in rows}
    for seed in GOLDEN_SEEDS:
        row = by_seed.get(seed)
        if row is None or row.metrics is None:
            continue
        out[str(seed)] = {
            "frames": row.metrics.frames,
            "expected_frames": row.expected_frames,
            "peak_dbfs": round(row.metrics.peak_dbfs, 3),
            "rms_dbfs": round(row.metrics.rms_dbfs, 3),
            "centroid_hz": round(row.metrics.centroid_hz, 1),
        }
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="프리셋 실측")
    parser.add_argument("--seeds", type=int, default=256)
    parser.add_argument("--stats", type=Path, default=None, help="전체 통계를 쓸 JSON 경로")
    parser.add_argument("--rfxgen", type=Path, default=None)
    args = parser.parse_args(argv)

    rfxgen = make.find_rfxgen(args.rfxgen)
    stats = {}
    golden = {"seeds": list(GOLDEN_SEEDS), "presets": {}}
    started = time.time()

    with tempfile.TemporaryDirectory(prefix="soundtool_measure_") as tmp:
        out_dir = Path(tmp)
        for preset in presets.PRESET_NAMES:
            mark = time.time()
            rows = collect(preset, args.seeds, out_dir, rfxgen)
            stats[preset] = summarize(preset, rows)
            golden["presets"][preset] = golden_rows(preset, rows)
            print(f"{preset:10s} {len(rows)}개 {time.time() - mark:.1f}초")

    print(f"\n전부 {time.time() - started:.1f}초\n")
    print("| 프리셋 | 프레임 | 초 | RMS dBFS | centroid 실측 | centroid 문턱 | DC 최대(정규화 전) | DC 최대(정규화 뒤) | 연속FS 최대 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for preset in presets.PRESET_NAMES:
        s = stats[preset]
        print(f"| {preset} | {s['frames'][0]} ~ {s['frames'][1]} "
              f"| {s['seconds'][0]:.2f} ~ {s['seconds'][1]:.2f} "
              f"| {s['rms_dbfs'][0]:.1f} ~ {s['rms_dbfs'][1]:.1f} "
              f"| {s['centroid_hz'][0]:.0f} ~ {s['centroid_hz'][1]:.0f} "
              f"| {s['centroid_range'][0]:.0f} ~ {s['centroid_range'][1]:.0f} "
              f"| {s['dc_max_raw']:.3f} | {s['dc_max_normalized']:.3f} | {s['clip_run_max']} |")

    print("\ncheck.py 에 옮길 CENTROID_HZ :")
    for preset in presets.PRESET_NAMES:
        low, high = stats[preset]["centroid_range"]
        print(f'    "{preset}": ({low:.1f}, {high:.1f}),')

    failed = {p: s["failed"] for p, s in stats.items() if s["failed"]}
    print(f"\n지금 문턱으로 떨어진 것 : {failed or '없음'}")

    GOLDEN_PATH.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"golden.json 을 다시 썼다 : {GOLDEN_PATH}")
    if args.stats:
        args.stats.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"통계 : {args.stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
