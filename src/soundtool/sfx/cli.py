"""SFX 갈래의 명령 세 개 — make · check · presets."""

import json
import wave
from pathlib import Path

from soundtool import config, manifest as manifest_mod, table
from soundtool.sfx import check as check_mod
from soundtool.sfx import make as make_mod
from soundtool.sfx import presets, rfx, spec as spec_mod

KIND = "sfx"
GENERATED_BY = "soundtool sfx make"


def register(subparsers):
    """최상위 parser 에 sfx 갈래를 붙인다."""
    parser = subparsers.add_parser(KIND, help="효과음 (rfxgen)")
    parser.set_defaults(handler=lambda args: _print_help(parser))
    commands = parser.add_subparsers(dest="command", metavar="명령")

    maker = commands.add_parser("make", help="스펙대로 굽고 검수하고 manifest 를 쓴다")
    maker.add_argument("spec", type=Path, help="소리 스펙 JSON")
    maker.add_argument("--out", type=Path, required=True, help="산출 폴더")
    maker.add_argument("--rfxgen", type=Path, default=None, help="rfxgen 실행파일 경로")
    maker.add_argument("--dry-run", action="store_true", help="추첨까지만 하고 안 굽는다")
    maker.add_argument("--keep-failed", action="store_true", help="떨어진 소리를 _failed/ 에 남긴다")
    maker.set_defaults(handler=run_make)

    checker = commands.add_parser("check", help="이미 있는 WAV 를 잰다")
    checker.add_argument("target", type=Path, help="WAV 파일 또는 폴더")
    checker.add_argument("--manifest", type=Path, default=None, help="이 기대치와 대조한다")
    checker.set_defaults(handler=run_check)

    lister = commands.add_parser("presets", help="프리셋 목록을 뱉는다")
    lister.add_argument("--json", action="store_true", help="JSON 으로")
    lister.set_defaults(handler=run_presets)


def _print_help(parser):
    parser.print_help()
    return config.EXIT_USAGE


def run_make(args):
    try:
        spec = spec_mod.load(args.spec)
    except spec_mod.SpecError as err:
        print(err)
        return config.EXIT_FAIL

    problems = spec_mod.validate(spec)
    if problems:
        print(f"스펙이 어긋났다 — {len(problems)}곳. 아무것도 안 구웠다.")
        for line in problems:
            print(f"  - {line}")
        return config.EXIT_FAIL

    sounds = list(spec_mod.iter_sounds(spec))
    if args.dry_run:
        return _dry_run(sounds)

    try:
        rfxgen = make_mod.find_rfxgen(args.rfxgen)
    except make_mod.RfxgenMissing as err:
        print(err)
        return config.EXIT_NO_RFXGEN

    results = make_mod.make_all(sounds, args.out, rfxgen, args.keep_failed)
    _print_results(results)
    _write_manifest(results, args.out)
    return config.EXIT_OK if all(r.ok for r in results) else config.EXIT_FAIL


def _dry_run(sounds):
    """굽지 않고 추첨 결과만 보여준다."""
    print(f"--dry-run — {len(sounds)}개. rfxgen 을 안 불렀다.\n")
    for sound in sounds:
        rand_seed, params = make_mod.params_for(sound)
        frames = rfx.expected_frames(params)
        shown = ", ".join(f"{k}={_number(v)}" for k, v in sorted(params.items()))
        print(f"{sound['name']} ({sound['preset']}, seed {sound['seed']}, randSeed {rand_seed})")
        print(f"  기대 프레임 {frames} ({frames / config.SAMPLE_RATE:.3f}초)")
        print(f"  {shown}")
    return config.EXIT_OK


def _number(value):
    if isinstance(value, int):
        return str(value)
    return f"{value:.3f}"


def _print_results(results):
    rows = [("이름", "프리셋", "seed", "초", "피크dBFS", "centroid", "결과")]
    for r in results:
        m = r.metrics
        rows.append((
            r.name,
            r.preset,
            str(r.seed),
            f"{m.seconds:.2f}" if m else "-",
            f"{m.peak_dbfs:.1f}" if m else "-",
            f"{m.centroid_hz:.0f}" if m else "-",
            "통과" if r.ok else "실패 · " + " / ".join(r.reasons),
        ))
    table.print_table(rows)
    passed = sum(1 for r in results if r.ok)
    print(f"\n{len(results)}개 중 {passed}개 통과, {len(results) - passed}개 실패")


def _write_manifest(results, out_dir):
    items = []
    for r in results:
        if not r.ok:
            continue
        m = r.metrics
        items.append(manifest_mod.item(
            r.name, f"{r.name}.wav", KIND, r.tags, m.seconds, r.seed,
            extra={
                "preset": r.preset,
                "frames": m.frames,
                "peak_dbfs": round(m.peak_dbfs, 2),
                "rms_dbfs": round(m.rms_dbfs, 2),
                "centroid_hz": round(m.centroid_hz, 1),
            },
        ))
    path = Path(out_dir) / config.MANIFEST_NAME
    info = manifest_mod.kind_head(GENERATED_BY, config.SAMPLE_RATE, config.CHANNELS)
    manifest_mod.merge_write(path, KIND, items, info)
    print(f"manifest : {path} ({len(items)}개)")


def run_check(args):
    paths = _wav_paths(args.target)
    if not paths:
        print(f"WAV 를 못 찾았다 : {args.target}")
        return config.EXIT_FAIL

    try:
        expected = _manifest_expectations(args.manifest)
    except (json.JSONDecodeError, OSError) as err:
        print(f"manifest 를 못 읽었다 : {args.manifest} ({err})")
        return config.EXIT_FAIL

    rows = [("이름", "프레임", "초", "피크dBFS", "RMS dBFS", "centroid", "결과")]
    bad = 0
    for path in paths:
        try:
            metrics = check_mod.measure(path)
        except (ValueError, wave.Error) as err:
            bad += 1
            rows.append((path.stem, "-", "-", "-", "-", "-", f"실패 · {err}"))
            continue
        reasons = _compare(path.stem, metrics, expected)
        if reasons:
            bad += 1
        rows.append((
            path.stem,
            str(metrics.frames),
            f"{metrics.seconds:.2f}",
            f"{metrics.peak_dbfs:.1f}",
            f"{metrics.rms_dbfs:.1f}",
            f"{metrics.centroid_hz:.0f}",
            "실패 · " + " / ".join(reasons) if reasons else "통과",
        ))
    table.print_table(rows)
    print(f"\n{len(paths)}개 중 {len(paths) - bad}개 통과, {bad}개 실패")
    return config.EXIT_FAIL if bad else config.EXIT_OK


def _wav_paths(target):
    target = Path(target)
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(p for p in target.glob("*.wav"))
    return []


def _manifest_expectations(path):
    """manifest 의 sfx 항목을 이름 → 기대치로 바꾼다. 경로가 없으면 빈 사전."""
    if path is None:
        return {}
    data = manifest_mod.read(path)
    out = {}
    for row in data.get("items", []):
        if row.get("kind") != KIND:
            continue
        name = row.get("name")
        if name is None:
            continue
        out[name] = row
    return out


def _compare(name, metrics, expected):
    """manifest 기대치와 대조한다. 기대치가 없으면 아무 말도 안 한다."""
    row = expected.get(name)
    if row is None:
        return []
    reasons = []
    if "frames" in row and metrics.frames != row["frames"]:
        reasons.append(f"프레임 {metrics.frames} (manifest {row['frames']})")
    if "peak_dbfs" in row and abs(metrics.peak_dbfs - row["peak_dbfs"]) > 0.15:
        reasons.append(f"피크 {metrics.peak_dbfs:.2f} (manifest {row['peak_dbfs']})")
    if "centroid_hz" in row and not _near(metrics.centroid_hz, row["centroid_hz"], 0.05):
        reasons.append(f"centroid {metrics.centroid_hz:.0f} (manifest {row['centroid_hz']:.0f})")
    return reasons


def _near(got, want, ratio):
    if want == 0:
        return got == 0
    return abs(got - want) / abs(want) <= ratio


def run_presets(args):
    rows = [presets.describe(name) for name in presets.PRESET_NAMES]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return config.EXIT_OK
    rows_out = [("프리셋", "쓰임", "centroid Hz")]
    for row in rows:
        low, high = row["centroid_hz"]
        rows_out.append((row["name"], row["summary"], f"{low:.0f} ~ {high:.0f}"))
    table.print_table(rows_out)
    return config.EXIT_OK
