"""fluidsynth 호출. exe 가 있을 때만 실제로 굽는다."""

import wave

import numpy as np
import pytest

from soundtool import config
from soundtool.bgm import check as check_mod
from soundtool.bgm import compose as compose_mod
from soundtool.bgm import render as render_mod
from soundtool.bgm import spec as spec_mod


def has_tools():
    try:
        render_mod.find_tools()
    except render_mod.ToolsMissing:
        return False
    return True


needs_tools = pytest.mark.skipif(not has_tools(), reason="fluidsynth 나 사운드폰트가 없다")


def a_song(**extra):
    row = {"name": "probe", "style": "town", "seed": 1, "bpm": 120, "bars": 4}
    row.update(extra)
    return spec_mod.build_song(row)


def test_missing_exe_says_where(tmp_path):
    with pytest.raises(render_mod.ToolsMissing) as caught:
        render_mod.find_tools(tmp_path / "없다.exe", tmp_path / "없다.sf2")
    text = str(caught.value)
    assert "못 찾았다" in text
    assert "없다.exe" in text
    assert "없다.sf2" in text


def test_command_shape(tmp_path):
    tools = render_mod.ToolPaths(tmp_path / "f.exe", tmp_path / "g.sf2")
    command = render_mod.command_for(tmp_path / "a.mid", tmp_path / "a.wav", tools,
                                     1.2, 44100, reverb_off=True)
    assert command[0] == str(tmp_path / "f.exe")
    assert command[-2:] == [str(tmp_path / "g.sf2"), str(tmp_path / "a.mid")]
    assert "-R" in command and "-C" in command
    assert command[command.index("-g") + 1] == "1.200"
    assert command[command.index("-O") + 1] == "s16"


def test_command_keeps_reverb_for_non_loop(tmp_path):
    tools = render_mod.ToolPaths(tmp_path / "f.exe", tmp_path / "g.sf2")
    command = render_mod.command_for(tmp_path / "a.mid", tmp_path / "a.wav", tools,
                                     1.0, 44100, reverb_off=False)
    assert "-R" not in command


def test_expected_frames():
    song = a_song()
    assert render_mod.expected_frames(song) == round(song.seconds * config.BGM_SAMPLE_RATE)
    jingle = a_song(style="victory", bars=8, bpm=120)
    assert render_mod.expected_frames(jingle) == round((jingle.seconds + 2.0) * 44100)


def test_trim_cuts_the_tail(tmp_path):
    path = tmp_path / "a.wav"
    data = np.zeros(44100 * 2, dtype="<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(data.tobytes())
    render_mod.trim(path, 22050)
    with wave.open(str(path), "rb") as handle:
        assert handle.getnframes() == 22050
        assert handle.getnchannels() == 2


def test_trim_refuses_when_too_short(tmp_path):
    path = tmp_path / "a.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(np.zeros(2000, dtype="<i2").tobytes())
    with pytest.raises(RuntimeError, match="짧다"):
        render_mod.trim(path, 44100)


@needs_tools
@pytest.mark.parametrize("style", ["town", "victory"])
def test_render_makes_a_wav_of_the_right_length(style, tmp_path):
    song = a_song(style=style, bars=8, bpm=120)
    mid = tmp_path / "a.mid"
    compose_mod.compose(song).save(str(mid))
    result = render_mod.render(mid, tmp_path / "a.wav", song, render_mod.find_tools())
    assert result.ok, result.reasons
    assert result.metrics.channels == 2
    assert result.metrics.rate == config.BGM_SAMPLE_RATE
    assert result.metrics.seconds == pytest.approx(compose_mod.expected_seconds(song), abs=0.01)


@needs_tools
def test_render_retries_once_when_clipping(tmp_path):
    """gain 을 크게 주면 클리핑이 잡히고 0.7배로 한 번 다시 굽는다."""
    song = a_song(style="battle", bars=8)
    mid = tmp_path / "a.mid"
    compose_mod.compose(song).save(str(mid))
    result = render_mod.render(mid, tmp_path / "a.wav", song, render_mod.find_tools(), gain=9.0)
    assert result.retried is True
    assert result.gain == pytest.approx(6.3)


@needs_tools
def test_render_is_repeatable(tmp_path):
    song = a_song(bars=4)
    mid = tmp_path / "a.mid"
    compose_mod.compose(song).save(str(mid))
    tools = render_mod.find_tools()
    render_mod.render(mid, tmp_path / "a.wav", song, tools)
    render_mod.render(mid, tmp_path / "b.wav", song, tools)
    assert (tmp_path / "a.wav").read_bytes() == (tmp_path / "b.wav").read_bytes()


@needs_tools
def test_rendered_song_passes_every_check(tmp_path):
    song = a_song(bars=8)
    mid = tmp_path / "a.mid"
    compose_mod.compose(song).save(str(mid))
    wav = tmp_path / "a.wav"
    render_mod.render(mid, wav, song, render_mod.find_tools())
    assert check_mod.check_wav(wav, song) == []
    assert check_mod.check_midi(mid, song) == []
