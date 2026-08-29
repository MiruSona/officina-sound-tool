# 남의 것 쓰는 목록 (THIRD-PARTY)

SoundTool 이 같이 담거나 쓰는 남의 소프트웨어·자산이다.
근거는 `Docs/Research/2026-08-25-BGM배포조건조사.md` 1장.

| 항목 | 라이선스 | 키트 동봉 | 게임 배포 | 표기 의무 | 라이선스 파일 자리 |
| --- | --- | --- | --- | --- | --- |
| **GeneralUser GS 2.0.3** (사운드폰트) | GeneralUser GS License v2.0 (자체 허용) | 가능 | 가능 (구운 wav 도, sf2 자체도) | 없음 | `bin/soundfont/LICENSE.txt` |
| **FluidSynth 2.6.0** (신시사이저) | LGPL 2.1 이상 | 가능 (exe·dll 그대로, 고치지 않고) | 가능 | LGPL 사본 동봉 + 출처 표기 권장 | `bin/fluidsynth/LICENSE` |
| **mido 1.3.3** (Python MIDI 라이브러리) | MIT | 가능 (보통 `requirements.txt` 로 충분) | 가능 | 저작권 문구 동봉 | 아직 사본 없음. `.venv/Lib/site-packages/mido-*.dist-info/LICENSE` |
| **rfxgen** (SFX 갈래 도구) | zlib | 가능 | 가능 | 저작권 문구 동봉 | `bin/LICENSE` |

## 지킬 것 셋

1. **FluidSynth 의 exe·dll 을 고치지 않는다.** 고치면 그 고친 것을 LGPL 로 내놔야 한다.
   우리는 명령줄로 부르기만 하니 그대로 두면 의무가 사실상 사라진다.
2. **GeneralUser GS 는 사본을 키트 안에 둔다.** 만든 이가 "내 다운로드 파일로 직접 링크 걸지 말라" 고 부탁했다.
3. **GeneralUser GS 는 "자산 라이선스는 CC0·CC-BY·OGA-BY 만" 규칙의 예외다.** 사운드폰트는 게임에 실려
   나가는 자산이 아니라 자산을 만드는 도구다. 근거는 조사 문서 3장.

## 받은 자리

| 파일 | 받은 곳 | 크기 | SHA-256 |
| --- | --- | --- | --- |
| `fluidsynth-v2.6.0-win10-x64-cpp11.zip` | <https://github.com/FluidSynth/fluidsynth/releases/download/v2.6.0/fluidsynth-v2.6.0-win10-x64-cpp11.zip> | 2,722,370 바이트 | `817262deacaa748edb3af6731dffe1766b00146790becfccc949a9f701e76681` |
| `GeneralUser-GS.sf2` | <https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2> | 32,319,396 바이트 | `9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe` |

`bin/` 은 git 에서 뺀다 (`.gitignore`). 새로 받을 때 위 크기와 해시로 맞는지 본다.
zip 안에는 라이선스 파일이 없어서 FluidSynth 저장소 태그 `v2.6.0` 의 `LICENSE` 를 따로 받아 같이 뒀다.
