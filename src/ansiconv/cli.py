"""Command-line entry point for ansiconv."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .core import ConversionError, ansi_to_html, html_to_ansi


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ansiconv",
        description="Convert between ANSI SGR escape sequences and HTML spans.",
    )
    parser.add_argument(
        "direction",
        choices=["to-html", "to-ansi"],
        help="to-html: ANSI text -> HTML. to-ansi: HTML -> ANSI text.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="input file (defaults to stdin)",
    )
    parser.add_argument(
        "-o", "--output",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="output file (defaults to stdout)",
    )
    parser.add_argument(
        "--lenient",
        action="store_true",
        help="skip unsupported escape sequences/tags instead of raising an error",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    text = args.input.read()

    convert = ansi_to_html if args.direction == "to-html" else html_to_ansi
    try:
        result = convert(text, lenient=args.lenient)
    except ConversionError as exc:
        print(f"ansiconv: {exc} (use --lenient to ignore)", file=sys.stderr)
        return 1

    args.output.write(result)
    if not result.endswith("\n"):
        args.output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
