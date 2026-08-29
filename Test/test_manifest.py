"""manifest 합치기 — 한 폴더에 sfx 와 bgm 을 같이 구워도 서로 안 지운다."""

import json

import pytest

from soundtool import config, manifest as manifest_mod

SFX_INFO = manifest_mod.kind_head("soundtool sfx make", 44100, 1)
BGM_INFO = manifest_mod.kind_head("soundtool bgm make", 44100, 2)


def sfx_items():
    return [manifest_mod.item("ui_click", "ui_click.wav", "sfx", ["ui"], 0.2, 1001)]


def bgm_items():
    return [manifest_mod.item("town_market", "town_market.wav", "bgm", ["town"], 8.0, 1041)]


def test_head_has_no_kind_specific_keys():
    """갈래마다 다른 값은 머리에 없다. 있으면 나중 갈래가 앞 갈래 값을 덮어쓴다."""
    assert set(manifest_mod.head()) == {"version", "bits"}


def test_second_kind_keeps_the_first(tmp_path):
    path = tmp_path / config.MANIFEST_NAME
    manifest_mod.merge_write(path, "sfx", sfx_items(), SFX_INFO)
    manifest_mod.merge_write(path, "bgm", bgm_items(), BGM_INFO)

    data = manifest_mod.read(path)
    assert sorted(data["kinds"]) == ["bgm", "sfx"]
    assert data["kinds"]["sfx"]["channels"] == 1
    assert data["kinds"]["bgm"]["channels"] == 2
    assert [row["kind"] for row in data["items"]] == ["sfx", "bgm"]


def test_same_kind_is_replaced_not_appended(tmp_path):
    path = tmp_path / config.MANIFEST_NAME
    manifest_mod.merge_write(path, "sfx", sfx_items(), SFX_INFO)
    manifest_mod.merge_write(path, "bgm", bgm_items(), BGM_INFO)
    manifest_mod.merge_write(path, "sfx", sfx_items(), SFX_INFO)

    data = manifest_mod.read(path)
    assert [row["kind"] for row in data["items"]] == ["bgm", "sfx"]


def test_empty_items_clears_only_that_kind(tmp_path):
    path = tmp_path / config.MANIFEST_NAME
    manifest_mod.merge_write(path, "sfx", sfx_items(), SFX_INFO)
    manifest_mod.merge_write(path, "bgm", bgm_items(), BGM_INFO)
    manifest_mod.merge_write(path, "bgm", [], BGM_INFO)

    data = manifest_mod.read(path)
    assert [row["kind"] for row in data["items"]] == ["sfx"]


@pytest.mark.parametrize("text", [
    "{ 깨진 json",
    json.dumps({"version": 1, "items": [{"name": "옛판"}]}),
    json.dumps([1, 2, 3]),
])
def test_unreadable_or_old_manifest_starts_fresh(tmp_path, text):
    path = tmp_path / config.MANIFEST_NAME
    path.write_text(text, encoding="utf-8")
    manifest_mod.merge_write(path, "sfx", sfx_items(), SFX_INFO)

    data = manifest_mod.read(path)
    assert data["version"] == config.MANIFEST_VERSION
    assert [row["name"] for row in data["items"]] == ["ui_click"]


def has_both():
    from soundtool.bgm import render as render_mod
    from soundtool.sfx import make as make_mod
    try:
        make_mod.find_rfxgen()
        render_mod.find_tools()
    except (make_mod.RfxgenMissing, render_mod.ToolsMissing):
        return False
    return True


needs_both = pytest.mark.skipif(not has_both(), reason="rfxgen 이나 fluidsynth 가 없다")


@needs_both
def test_cli_sfx_then_bgm_share_one_manifest(tmp_path, capsys):
    """실제 명령 두 개를 같은 --out 에 차례로 돌린다."""
    from soundtool import cli

    sfx_spec = tmp_path / "sfx.json"
    sfx_spec.write_text(json.dumps({"version": 1, "sounds": [
        {"name": "ui_click", "preset": "blip", "seed": 1001, "tags": ["ui"]},
    ]}), encoding="utf-8")
    bgm_spec = tmp_path / "bgm.json"
    bgm_spec.write_text(json.dumps({"version": 1, "songs": [
        {"name": "town_market", "style": "town", "seed": 1041, "tags": ["town"], "bars": 4},
    ]}), encoding="utf-8")

    out = tmp_path / "out"
    assert cli.main(["sfx", "make", str(sfx_spec), "--out", str(out)]) == config.EXIT_OK
    assert cli.main(["bgm", "make", str(bgm_spec), "--out", str(out)]) == config.EXIT_OK
    capsys.readouterr()

    data = manifest_mod.read(out / config.MANIFEST_NAME)
    assert sorted(row["kind"] for row in data["items"]) == ["bgm", "sfx"]
    assert data["kinds"]["sfx"]["channels"] == 1
    assert data["kinds"]["bgm"]["channels"] == 2
