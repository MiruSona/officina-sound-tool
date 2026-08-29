"""툴 전체가 쓰는 상수. 설정 파일을 따로 두지 않는다 (AGENTS 10)."""

from pathlib import Path

# src/soundtool/config.py -> SoundTool/
TOOL_ROOT = Path(__file__).resolve().parent.parent.parent

RFXGEN_PATH = TOOL_ROOT / "bin" / "rfxgen.exe"
RFXGEN_ENV = "SOUNDTOOL_RFXGEN"
RFXGEN_URL = "https://github.com/raysan5/rfxgen/releases"

SAMPLE_RATE = 44100
SAMPLE_BITS = 16
CHANNELS = 1
NORMALIZE_DBFS = -1.0

MANIFEST_VERSION = 2
MANIFEST_NAME = "manifest.json"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_NO_RFXGEN = 3

# BGM 갈래
FLUIDSYNTH_PATH = TOOL_ROOT / "bin" / "fluidsynth" / "bin" / "fluidsynth.exe"
SOUNDFONT_PATH = TOOL_ROOT / "bin" / "soundfont" / "GeneralUser-GS.sf2"
FLUIDSYNTH_GAIN = 1.35   # 스타일 6개를 1.2·1.35·1.5 로 구워 재고 고른 값 (피크 대부분 -3~-1 dBFS)
BGM_SAMPLE_RATE = 44100
BGM_CHANNELS = 2
