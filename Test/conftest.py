"""시험이 `soundtool` 을 찾을 수 있게 src 를 경로에 넣는다."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
