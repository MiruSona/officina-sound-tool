"""BGM 갈래의 명령 세 개 — make · check · presets."""

import json
import wave
from dataclasses import dataclass, field
from pathlib import Path

from soundtool import config, manifest as manifest_mod, table
from soundtool.bgm import check as check_mod
from soundtool.bgm import compose as compose_mod
from soundtool.bgm import patterns, render as render_mod, spec as spec_mod
from soundtool.bgm import theory

KIND = "bgm"
GENERATED_BY = "soundtool bgm make"


@dataclass
class SongResult:
    song: object
    ok: bool = False
    reasons: list = field(default_factory=list)
    metrics: check_mod.Metrics | None = None
    gain: float = 0.0
    retried: bool = False
    wav_name: str = ""
    mid_name: str = ""


def register(subparsers):
    """최상위 parser 에 bgm 갈래를 붙인다."""
    parser = subparsers.add_parser(KIND, help="배경음 (mido + fluidsynth)")
    parser.set_defaults(handler=lambda args: _print_help(parser))
    commands = parser.add_subparsers(dest="command", metavar="명령")

    maker = commands.add_parser("make", help="스펙대로 굽고 검수하고 manifest 를 쓴다")
    maker.add_argument("spec", type=Path, help="곡 스펙 JSON")
    maker.add_argument("--out", type=Path, required=True, help="산출 폴더")
    maker.add_argument("--fluidsynth", type=Path, default=None, help="fluidsynth 실행파일 경로")
    maker.add_argument("--soundfont", type=Path, default=None, help="사운드폰트(.sf2) 경로")
    maker.add_argument("--rate", type=int, default=config.BGM_SAMPLE_RATE, help="표본율")
    maker.add_argument("--gain", type=float, default=config.FLUIDSYNTH_GAIN, help="fluidsynth -g")
    maker.add_argument("--midi-only", action="store_true", help="MIDI 까지만 만든다")
    maker.set_defaults(handler=run_make)

    checker = commands.add_parser("check", help="이미 구운 폴더를 다시 검사한다")
    checker.add_argument("target", type=Path, help="manifest.json 이 있는 폴더")
    checker.set_defaults(handler=run_check)

    lister = commands.add_parser("presets", help="스타일·모드·코드 표를 뱉는다")
    lister.add_argument("--json", action="store_true", help="JSON 으로")
    lister.set_defaults(handler=run_presets)


def _print_help(parser):
    parser.print_help()
    return config.EXIT_USAGE


def run_make(args):
    try:
        songs = spec_mod.load_spec(args.spec)
    except spec_mod.SpecError as err:
        print(f"스펙이 어긋났다. 아무것도 안 구웠다.\n{err}")
        return config.EXIT_FAIL

    tools = None
    if not args.midi_only:
        try:
            tools = render_mod.find_tools(args.fluidsynth, args.soundfont)
        except render_mod.ToolsMissing as err:
            print(err)
            return config.EXIT_NO_RFXGEN

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [_make_one(song, out_dir, tools, args) for song in songs]
    _print_results(results, args.midi_only)
    if not args.midi_only:
        _write_manifest(results, out_dir, args.rate)
    return config.EXIT_OK if all(r.ok for r in results) else config.EXIT_FAIL


def _make_one(song, out_dir, tools, args):
    result = SongResult(song=song, mid_name=f"{song.name}.mid", wav_name=f"{song.name}.wav")
    mid_path = out_dir / result.mid_name
    compose_mod.compose(song).save(str(mid_path))
    result.reasons = check_mod.check_midi(mid_path, song)
    if result.reasons:
        return result
    if tools is None:
        result.ok = True
        return result

    rendered = render_mod.render(mid_path, out_dir / result.wav_name, song, tools,
                                 gain=args.gain, rate=args.rate)
    result.ok = rendered.ok
    result.reasons = rendered.reasons
    result.metrics = rendered.metrics
    result.gain = rendered.gain
    result.retried = rendered.retried
    return result


def _print_results(results, midi_only):
    head = ("이름", "스타일", "bpm", "마디", "초", "피크dBFS", "RMS dBFS", "gain", "결과")
    rows = [head]
    for r in results:
        m = r.metrics
        rows.append((
            r.song.name,
            r.song.style,
            str(r.song.bpm),
            str(r.song.bars),
            f"{m.seconds:.2f}" if m else "-",
            f"{m.peak_dbfs:.1f}" if m else "-",
            f"{m.rms_dbfs:.1f}" if m else "-",
            f"{r.gain:.2f}{'*' if r.retried else ''}" if m else "-",
            "통과" if r.ok else "실패 · " + " / ".join(r.reasons),
        ))
    table.print_table(rows)
    passed = sum(1 for r in results if r.ok)
    print(f"\n{len(results)}개 중 {passed}개 통과, {len(results) - passed}개 실패")
    if midi_only:
        print("--midi-only — fluidsynth 를 안 불렀다. MIDI 검사(5·6번)만 돌았다.")


def _write_manifest(results, out_dir, rate):
    items = []
    for r in results:
        if not r.ok:
            continue
        song = r.song
        items.append(manifest_mod.item(
            song.name, r.wav_name, KIND, song.tags, r.metrics.seconds, song.seed,
            extra={
                "midi": r.mid_name,
                "style": song.style,
                "bpm": song.bpm,
                "key": song.key,
                "mode": song.mode,
                "bars": song.bars,
                "loop": song.loop,
                "gain": r.gain,
                "tracks": [role for role in spec_mod.ROLES if song.tracks[role].on],
                "peak_dbfs": round(r.metrics.peak_dbfs, 2),
                "rms_dbfs": round(r.metrics.rms_dbfs, 2),
            },
        ))
    path = Path(out_dir) / config.MANIFEST_NAME
    info = manifest_mod.kind_head(GENERATED_BY, rate, config.BGM_CHANNELS)
    manifest_mod.merge_write(path, KIND, items, info)
    print(f"manifest : {path} ({len(items)}개)")


def run_check(args):
    path = Path(args.target) / config.MANIFEST_NAME
    if not path.is_file():
        print(f"manifest 를 못 찾았다 : {path}")
        return config.EXIT_FAIL
    try:
        data = manifest_mod.read(path)
    except (json.JSONDecodeError, OSError, ValueError) as err:
        print(f"manifest 를 못 읽었다 : {path} ({err})")
        return config.EXIT_FAIL
    rows_in = [r for r in data.get("items", []) if r.get("kind") == KIND]
    if not rows_in:
        print(f"manifest 에 bgm 항목이 없다 : {path}")
        return config.EXIT_FAIL

    rows = [("이름", "초", "피크dBFS", "RMS dBFS", "저/중/고 %", "결과")]
    bad = 0
    for row in rows_in:
        try:
            reasons, metrics = _recheck(Path(args.target), row)
        except (KeyError, TypeError, ValueError, wave.Error, EOFError, OSError) as err:
            bad += 1
            reason = str(err) if str(err) else err.__class__.__name__
            rows.append((row.get("name", "?"), "-", "-", "-", "-",
                         f"실패 · manifest 가 이상하다 ({reason})"))
            continue
        if reasons:
            bad += 1
        rows.append((
            row.get("name", "?"),
            f"{metrics.seconds:.2f}" if metrics else "-",
            f"{metrics.peak_dbfs:.1f}" if metrics else "-",
            f"{metrics.rms_dbfs:.1f}" if metrics else "-",
            "/".join(f"{v * 100:.0f}" for v in metrics.bands) if metrics else "-",
            "실패 · " + " / ".join(reasons) if reasons else "통과",
        ))
    table.print_table(rows)
    print(f"\n{len(rows_in)}개 중 {len(rows_in) - bad}개 통과, {bad}개 실패")
    return config.EXIT_FAIL if bad else config.EXIT_OK


def _recheck(folder, row):
    """manifest 한 줄을 Song 으로 되살려 같은 검사를 다시 돈다."""
    song = song_from_manifest(row)
    wav_path = folder / row["file"]
    if not wav_path.is_file():
        return [f"WAV 가 없다 : {wav_path.name}"], None
    metrics = check_mod.measure(wav_path, check_mod.tail_skip_seconds(song))
    reasons = check_mod.check_wav(wav_path, song, metrics)
    mid_path = folder / row.get("midi", "")
    if row.get("midi") and mid_path.is_file():
        reasons = check_mod.check_midi(mid_path, song) + reasons
    return reasons, metrics


def song_from_manifest(row):
    on = set(row.get("tracks", spec_mod.ROLES))
    tracks = {role: spec_mod.TrackSetting(on=role in on, program=0, octave=0)
              for role in spec_mod.ROLES}
    return spec_mod.Song(
        name=row["name"], style=row["style"], seed=row["seed"], tags=row.get("tags", []),
        bpm=row["bpm"], key=row["key"], mode=row["mode"], bars=row["bars"],
        loop=row["loop"], progression=[], tracks=tracks,
    )


def describe_styles():
    rows = []
    for name in patterns.STYLE_NAMES:
        preset = patterns.STYLES[name]
        rows.append({
            "name": name,
            "summary": preset.summary,
            "bpm": list(preset.bpm_range),
            "key": preset.key,
            "mode": preset.mode,
            "bars": preset.bars,
            "loop": preset.loop,
            "drums": preset.has_role("drums"),
            "progressions": [list(p) for p in preset.progressions],
            "programs": dict(preset.programs),
            "melody_range": list(preset.melody_range),
        })
    return rows


def run_presets(args):
    styles = describe_styles()
    if args.json:
        print(json.dumps({
            "styles": styles,
            "modes": list(theory.MODE_STEPS),
            "keys": list(theory.KEY_NAMES),
            "romans": list(theory.ROMAN_NAMES),
            "schema": spec_mod.SCHEMA,
        }, indent=2, ensure_ascii=False))
        return config.EXIT_OK

    rows = [("스타일", "쓰임", "bpm", "조/선법", "마디", "루프", "드럼", "진행 보기")]
    for row in styles:
        rows.append((
            row["name"], row["summary"], f"{row['bpm'][0]}~{row['bpm'][1]}",
            f"{row['key']} {row['mode']}", str(row["bars"]),
            "참" if row["loop"] else "거짓", "있음" if row["drums"] else "없음",
            " ".join(row["progressions"][0]),
        ))
    table.print_table(rows)
    print("\n조 : " + " ".join(theory.KEY_NAMES))
    print("선법 : " + " ".join(theory.MODE_STEPS))
    print("로마숫자 : " + " ".join(theory.ROMAN_NAMES))
    return config.EXIT_OK
