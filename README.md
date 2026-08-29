# SoundTool

**짧은 JSON 을 받아 게임용 효과음(SFX)과 배경음(BGM) WAV 를 굽고, 코드가 검수해서 통과한 것만 내보내는 명령줄 툴이다.**
SFX 는 rfxgen, BGM 은 mido → FluidSynth → GeneralUser GS 로 굽는다.

**상태 : 구현 끝 (2026-08-25) · 시험 248개 통과 · 소리는 아직 사람이 안 들어 봤다.**
문턱은 전부 실측으로 잡았지만, 「좋은 소리인가」는 사람 귀가 판정해야 한다. 남은 일은 `Docs/Todo/사운드툴.md`.

## 설치

```powershell
py -3.14 -m venv SoundTool/.venv
SoundTool/.venv/Scripts/python -m pip install -r SoundTool/requirements.txt
```

`numpy` · `mido` 는 **BGM 갈래만** 쓴다. **SFX 갈래는 표준 라이브러리만으로 돈다.**

바깥 프로그램 셋은 `bin/` 에 둔다. **`bin/` 은 git 에서 뺀다** (용량·라이선스). 아래 자리에 그대로 놓으면 툴이 알아서 찾는다.

| 자리 | 무엇 | 받는 곳 |
| --- | --- | --- |
| `bin/rfxgen.exe` | rfxgen v5.0 Windows x64 | <https://github.com/raysan5/rfxgen/releases> |
| `bin/fluidsynth/bin/fluidsynth.exe` | FluidSynth 2.6.0 zip 을 통째로 푼 것 | <https://github.com/FluidSynth/fluidsynth/releases> |
| `bin/soundfont/GeneralUser-GS.sf2` | GeneralUser GS 2.0.3 | <https://github.com/mrbumpy409/GeneralUser-GS> |

`--rfxgen` · `--fluidsynth` · `--soundfont` 로 다른 경로를 줄 수도 있다.
**라이선스와 받은 파일의 크기·SHA-256 은 `THIRD-PARTY.md` 에 있다.** 새로 받으면 그것과 맞는지 본다.

## 쓰는 법

```powershell
$env:PYTHONPATH = "SoundTool/src"
SoundTool/.venv/Scripts/python -m soundtool sfx make SoundTool/Test/spec_example.json --out Out/sfx
SoundTool/.venv/Scripts/python -m soundtool bgm make SoundTool/Test/spec_bgm_example.json --out Out/bgm
```

| 명령 | 하는 일 |
| --- | --- |
| `sfx make <스펙> --out <폴더>` | 스펙대로 굽고 검수하고 `manifest.json` 을 쓴다. `--dry-run` 은 추첨만, `--keep-failed` 는 떨어진 소리를 `_failed/` 에 남긴다 |
| `sfx check <WAV 또는 폴더>` | 이미 있는 WAV 를 잰다. `--manifest <경로>` 를 주면 그 기대치와 대조한다 |
| `sfx presets [--json]` | 프리셋 7개(coin·laser·explosion·powerup·hit·jump·blip)를 표로 뱉는다. LLM 프롬프트에 붙일 용도 |
| `bgm make <스펙> --out <폴더>` | 곡을 굽는다. `--midi-only` 는 MIDI 까지만 (FluidSynth 를 안 부른다), `--gain` 은 FluidSynth `-g` |
| `bgm check <폴더>` | 그 폴더의 `manifest.json` 을 읽어 같은 검사를 다시 돈다 |
| `bgm presets [--json]` | 스타일·조·선법·코드 표를 뱉는다 |

**스펙 예시는 `Test/spec_example.json`(SFX) 과 `Test/spec_bgm_example.json`(BGM) 이다.**
스펙의 규칙 자체는 `src/soundtool/sfx/spec_schema.json` · `src/soundtool/bgm/bgm.schema.json` 에 있다.

**같은 `--out` 에 두 갈래를 구워도 된다.** `manifest.json` 은 갈래(`kind`)별로 자기 몫만 갈아끼운다.

### 종료 코드

| 코드 | 뜻 |
| --- | --- |
| 0 | 전부 통과 |
| 1 | 하나라도 실패 (스펙이 어긋났다 · 검수에 떨어졌다 · 굽다 실패했다) |
| 2 | 쓰는 법이 틀렸다 (인자 문제) |
| 3 | 바깥 프로그램을 못 찾았다 (`rfxgen.exe` · `fluidsynth.exe` · `.sf2`) |

## 시험

```powershell
SoundTool/.venv/Scripts/python -m pytest SoundTool/Test -q
```

`bin/` 이 없으면 바깥 프로그램이 필요한 시험은 건너뛴다. 나머지는 어디서나 돈다.

## 폴더 지도

| 경로 | 내용 |
| --- | --- |
| `src/soundtool/` | `cli.py` 갈래 가르기 · `config.py` 상수 · `manifest.py` · `schema.py` 스키마 검사기 · `table.py` 표 찍기 |
| `src/soundtool/sfx/` | `rfx.py` `.rfx` 패킹 · `presets.py` · `spec.py` · `make.py` rfxgen 호출 · `dsp.py` FFT · `check.py` 검수 |
| `src/soundtool/bgm/` | `theory.py` 음계·화음 · `patterns.py` 스타일 · `compose.py` MIDI · `render.py` FluidSynth 호출 · `check.py` 검수 |
| `Test/` | pytest 248개 · 스펙 예시 · 골든 값 표(`golden.json` `golden_bgm.json`) |
| `bin/` | 바깥 프로그램. git 제외 |
| `Docs/` | 조사 · 설계 · 할 일 |

## 문서

| 문서 | 내용 |
| --- | --- |
| `Docs/Design/2026-08-25-SFX툴설계.md` | SFX 설계 + 「구현 뒤 달라진 것」 |
| `Docs/Design/2026-08-25-BGM툴설계.md` | BGM 설계 + 「구현 뒤 달라진 것」 |
| `Docs/Design/2026-08-20-사운드툴결정사항.md` | 엔진을 고른 결정 |
| `Docs/Research/` | rfx 엔디안 확인 · BGM 배포 조건 · SFX 엔진 재조사 |
| `Docs/Todo/사운드툴.md` | **남은 일은 여기를 본다** |
| `THIRD-PARTY.md` | 남의 것 라이선스와 지킬 것 |
