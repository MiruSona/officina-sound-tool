"""`.rfx` 엔디안 실물 확인용 프로브.

리틀/빅 엔디안으로 각각 .rfx 를 만들어 rfxgen 으로 굽고, 나온 WAV 를 읽어 비교한다.
실행 : python SoundTool/Test/rfx_probe.py
"""

import struct
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
RFXGEN = HERE.parent / "external" / "rfxgen.exe"

SAMPLE_RATE = 44100  # rfxgen 생성 샘플레이트 고정값

# WaveParams 필드 순서 (rfxgen.h 79~124줄). 앞 2개는 int, 나머지 22개는 float.
FIELDS = [
    ("randSeed", 12345),
    ("waveTypeValue", 0),
    ("attackTimeValue", 0.1),
    ("sustainTimeValue", 0.5),
    ("sustainPunchValue", 0.0),
    ("decayTimeValue", 0.3),
    ("startFrequencyValue", 0.5),
    ("minFrequencyValue", 0.0),
    ("slideValue", 0.0),
    ("deltaSlideValue", 0.0),
    ("vibratoDepthValue", 0.0),
    ("vibratoSpeedValue", 0.0),
    ("changeAmountValue", 0.0),
    ("changeSpeedValue", 0.0),
    ("squareDutyValue", 0.0),
    ("dutySweepValue", 0.0),
    ("repeatSpeedValue", 0.0),
    ("phaserOffsetValue", 0.0),
    ("phaserSweepValue", 0.0),
    ("lpfCutoffValue", 1.0),
    ("lpfCutoffSweepValue", 0.0),
    ("lpfResonanceValue", 0.0),
    ("hpfCutoffValue", 0.0),
    ("hpfCutoffSweepValue", 0.0),
]

LAYOUT = "4sHH2i22f"  # 시그니처 + 버전 + 길이 + WaveParams


def pack_rfx(values, endian):
    """endian 은 '<' 또는 '>'."""
    return struct.pack(endian + LAYOUT, b"rFX ", 200, 96, *values)


def parse_rfx(data, endian):
    head = struct.unpack(endian + LAYOUT, data)
    return {
        "signature": head[0],
        "version": head[1],
        "length": head[2],
        "params": dict(zip([n for n, _ in FIELDS], head[3:])),
    }


def envelope_frames(values):
    """rfxgen.h GenerateWave 346~348줄과 같은 식."""
    attack, sustain, decay = values[2], values[3], values[5]
    return sum(int(v * v * 100000.0) for v in (attack, sustain, decay))


def burn(rfx_path, wav_path):
    proc = subprocess.run(
        [str(RFXGEN), "--input", str(rfx_path), "--output", str(wav_path)],
        capture_output=True,
        text=True,
    )
    return proc


def read_wav(path):
    if not path.exists():
        return None
    with wave.open(str(path), "rb") as w:
        frames = w.getnframes()
        return {
            "channels": w.getnchannels(),
            "bits": w.getsampwidth() * 8,
            "rate": w.getframerate(),
            "frames": frames,
            "seconds": frames / w.getframerate(),
        }


def main():
    if not RFXGEN.exists():
        print(f"rfxgen 이 없다: {RFXGEN}")
        return 1

    values = [v for _, v in FIELDS]
    expected = envelope_frames(values)
    print(f"기대 프레임 수 = {expected} ({expected / SAMPLE_RATE:.4f}초)\n")

    for tag, endian in (("little", "<"), ("big", ">")):
        rfx_path = HERE / f"probe_{tag}.rfx"
        wav_path = HERE / f"probe_{tag}.wav"
        wav_path.unlink(missing_ok=True)

        data = pack_rfx(values, endian)
        rfx_path.write_bytes(data)

        proc = burn(rfx_path, wav_path)
        info = read_wav(wav_path)

        print(f"[{tag} endian] {len(data)}바이트, 헤더={data[:8].hex(' ')}")
        print(f"  rfxgen exit={proc.returncode}")
        for line in proc.stdout.splitlines():
            if "rFX" in line or "WARNING" in line or "INFO" in line:
                print(f"  | {line.strip()}")
        print(f"  WAV = {info}\n")

    # 방금 쓴 리틀엔디안 파일을 되읽어 값이 그대로인지 본다.
    back = parse_rfx((HERE / "probe_little.rfx").read_bytes(), "<")
    print("리틀엔디안 되읽기:", back["signature"], back["version"], back["length"])
    print("  params:", {k: round(v, 4) for k, v in back["params"].items() if v})
    return 0


if __name__ == "__main__":
    sys.exit(main())
