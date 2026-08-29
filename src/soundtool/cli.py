"""`python -m soundtool` 의 최상위 갈래 가르기.

갈래별 명령은 각 갈래가 스스로 등록한다.
"""

import argparse

from soundtool import config
from soundtool.bgm import cli as bgm_cli
from soundtool.sfx import cli as sfx_cli

PROG = "soundtool"


def build_parser():
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="게임 소리를 만들고 검수한다.",
    )
    subparsers = parser.add_subparsers(dest="kind", metavar="갈래")
    sfx_cli.register(subparsers)
    bgm_cli.register(subparsers)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return config.EXIT_USAGE
    return handler(args)
