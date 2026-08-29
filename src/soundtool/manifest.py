"""산출 폴더의 `manifest.json`. SFX 와 BGM 이 한 파일을 나눠 쓴다.

머리에는 두 갈래가 똑같은 것(`version` `bits`)만 두고, **갈래마다 다른 값은 `kinds[갈래]` 에 모은다.**
한 폴더에 sfx 와 bgm 을 같이 구워도 서로의 값을 안 덮어쓴다 (`merge_write`).

`items` 앞 여섯 열쇠(`name` `file` `kind` `tags` `seconds` `seed`)는 두 갈래가 똑같다.
그 뒤는 갈래마다 다르다. 실패한 것은 안 넣는다 — Unity 가 없는 파일을 집지 않게.
"""

import json
from pathlib import Path

from soundtool import config


def head():
    """맨 위 공통 열쇠. 갈래마다 다른 값은 여기 안 넣는다."""
    return {
        "version": config.MANIFEST_VERSION,
        "bits": config.SAMPLE_BITS,
    }


def kind_head(generated_by, sample_rate, channels):
    """`kinds[갈래]` 한 칸. 갈래마다 다른 값을 모은다."""
    return {
        "generated_by": generated_by,
        "sample_rate": sample_rate,
        "channels": channels,
    }


def item(name, file_name, kind, tags, seconds, seed, extra=None):
    """앞 여섯 열쇠를 순서대로 두고 갈래 고유 열쇠를 뒤에 붙인다."""
    row = {
        "name": name,
        "file": file_name,
        "kind": kind,
        "tags": list(tags),
        "seconds": round(seconds, 4),
        "seed": seed,
    }
    row.update(extra or {})
    return row


def merge_write(path, kind, items, info):
    """이 갈래 몫만 갈아끼우고 다른 갈래는 그대로 남긴다. 쓴 내용을 돌려준다."""
    path = Path(path)
    data = _read_or_new(path)
    data["kinds"][kind] = dict(info)
    others = [row for row in data["items"] if row.get("kind") != kind]
    data["items"] = others + list(items)
    write(data, path)
    return data


def _read_or_new(path):
    """기존 manifest 를 읽는다. 없거나 깨졌거나 판이 다르면 빈 것으로 시작한다."""
    empty = head()
    empty["kinds"] = {}
    empty["items"] = []
    if not path.is_file():
        return empty
    try:
        data = read(path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return empty
    if not isinstance(data, dict) or data.get("version") != config.MANIFEST_VERSION:
        return empty
    kinds = data.get("kinds")
    items = data.get("items")
    if isinstance(kinds, dict):
        empty["kinds"] = kinds
    if isinstance(items, list):
        empty["items"] = [row for row in items if isinstance(row, dict)]
    return empty


def write(manifest, path):
    """UTF-8, 들여쓰기 2. 열쇠 순서는 그대로 둔다 (읽는 사람이 앞 여섯을 먼저 본다)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
