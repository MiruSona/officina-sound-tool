"""JSON Schema 파일을 읽어 값을 검사하는 작은 검사기.

쓰는 문법은 type · enum · pattern · minimum/maximum · multipleOf · required ·
items · additionalProperties · minItems/maxItems · $ref 열 가지뿐이다.
스키마 파일이 곧 규칙이라 코드와 스키마가 어긋날 자리가 없다 (설계 2-3).
"""

import json
import re
from pathlib import Path

TYPE_NAMES = {
    "object": "객체",
    "array": "배열",
    "string": "글",
    "integer": "정수",
    "number": "숫자",
    "boolean": "참거짓",
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(value, schema, where="스펙"):
    """어긋난 곳을 사람 말로 준다. 빈 목록이면 통과."""
    problems = []
    _check(value, schema, where, problems, schema)
    return problems


def _resolve(schema, root):
    """`#/$defs/이름` 꼴만 푼다. 바깥 파일은 안 본다."""
    ref = schema.get("$ref")
    if ref is None:
        return schema
    node = root
    for step in ref.lstrip("#/").split("/"):
        node = node[step]
    return node


def _check(value, schema, where, problems, root):
    schema = _resolve(schema, root)
    if not _check_type(value, schema, where, problems):
        return
    _check_enum(value, schema, where, problems)
    _check_pattern(value, schema, where, problems)
    _check_bounds(value, schema, where, problems)
    if isinstance(value, dict):
        _check_object(value, schema, where, problems, root)
    if isinstance(value, list):
        _check_array(value, schema, where, problems, root)


def _check_type(value, schema, where, problems):
    wanted = schema.get("type")
    if wanted is None:
        return True
    if _matches_type(value, wanted):
        return True
    problems.append(f"{where} : {TYPE_NAMES.get(wanted, wanted)} 여야 한다")
    return False


def _matches_type(value, wanted):
    if wanted == "boolean" or isinstance(value, bool):
        return isinstance(value, bool) and wanted == "boolean"
    if wanted == "object":
        return isinstance(value, dict)
    if wanted == "array":
        return isinstance(value, list)
    if wanted == "string":
        return isinstance(value, str)
    if wanted == "integer":
        return isinstance(value, int)
    if wanted == "number":
        return isinstance(value, (int, float))
    return True


def _check_enum(value, schema, where, problems):
    allowed = schema.get("enum")
    if allowed is None or value in allowed:
        return
    problems.append(f"{where} : {value!r} 는 못 쓴다 (쓸 수 있는 것 : {', '.join(map(str, allowed))})")


def _check_pattern(value, schema, where, problems):
    pattern = schema.get("pattern")
    if pattern is None or not isinstance(value, str):
        return
    if re.fullmatch(pattern, value):
        return
    problems.append(f"{where} : {value!r} 가 규칙 {pattern} 에 안 맞는다")


def _check_bounds(value, schema, where, problems):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return
    low = schema.get("minimum")
    high = schema.get("maximum")
    step = schema.get("multipleOf")
    if low is not None and value < low:
        problems.append(f"{where} : {value} 는 {low} 보다 작다")
    if high is not None and value > high:
        problems.append(f"{where} : {value} 는 {high} 보다 크다")
    if step is not None and value % step != 0:
        problems.append(f"{where} : {value} 는 {step} 의 배수가 아니다")


def _check_object(value, schema, where, problems, root):
    properties = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in value:
            problems.append(f"{where} : {name} 이(가) 없다")
    if schema.get("additionalProperties") is False:
        for name in sorted(set(value) - set(properties)):
            problems.append(f"{where} : 모르는 열쇠 {name}")
    for name, child in value.items():
        if name in properties:
            _check(child, properties[name], f"{where}.{name}", problems, root)


def _check_array(value, schema, where, problems, root):
    least = schema.get("minItems")
    most = schema.get("maxItems")
    if least is not None and len(value) < least:
        problems.append(f"{where} : 항목이 {least}개는 있어야 한다 (지금 {len(value)}개)")
    if most is not None and len(value) > most:
        problems.append(f"{where} : 항목이 {most}개를 넘었다 (지금 {len(value)}개)")
    item_schema = schema.get("items")
    if not item_schema:
        return
    for index, child in enumerate(value):
        _check(child, item_schema, f"{where}[{index}]", problems, root)
