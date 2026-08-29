"""스펙 JSON 을 읽고 검사한다.

`spec_schema.json` 을 **읽어서** 검사한다. 스키마와 코드가 어긋날 자리를 안 만든다 (설계 10절 10번).
검사기는 BGM 과 같은 공용 `soundtool.schema` 를 쓴다. 여기는 스키마로 못 잡는 것만 본다.
"""

import json
from pathlib import Path

from soundtool import schema as schema_mod

SCHEMA_PATH = Path(__file__).resolve().parent / "spec_schema.json"
SCHEMA = schema_mod.load(SCHEMA_PATH)


class SpecError(Exception):
    """스펙 파일을 못 읽었다."""


def load(path):
    """JSON 을 읽는다. 못 읽으면 SpecError."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as err:
        raise SpecError(f"스펙 파일을 못 읽었다 : {path} ({err.strerror})") from err
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise SpecError(f"스펙 JSON 이 깨졌다 : {path} {err.lineno}줄 {err.colno}칸 — {err.msg}") from err


def validate(spec):
    """어긋난 것을 사람 말로 준다. 빈 목록이면 통과."""
    problems = schema_mod.validate(spec, SCHEMA)
    if problems:
        return problems
    _check_semantics(spec, problems)
    return problems


def iter_sounds(spec):
    """소리 하나씩. 선택 열쇠를 기본값으로 채워서 준다."""
    for sound in spec.get("sounds", []):
        filled = dict(sound)
        filled.setdefault("tags", [])
        filled.setdefault("params", {})
        filled.setdefault("check", {})
        yield filled


def _check_semantics(spec, problems):
    """스키마로는 못 잡는 것 — 이름 겹침, 문턱 뒤집힘."""
    seen = set()
    for index, sound in enumerate(spec.get("sounds", [])):
        where = f"sounds[{index}]"
        name = sound.get("name")
        if name in seen:
            problems.append(f"{where}.name : 이름이 겹친다 — {name}")
        seen.add(name)

        limits = sound.get("check", {})
        low = limits.get("min_seconds")
        high = limits.get("max_seconds")
        if low is not None and high is not None and low > high:
            problems.append(f"{where}.check : min_seconds {low} 가 max_seconds {high} 보다 크다")

        span = limits.get("centroid_hz")
        if span and span[0] > span[1]:
            problems.append(f"{where}.check.centroid_hz : 앞이 뒤보다 크다 — {span}")
