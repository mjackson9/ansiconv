"""Command-line entry point for ansiconv."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .core import (
    _DEFAULT_CLASS_PREFIX,
    ConversionError,
    ansi_to_html,
    ansi_to_plain,
    html_to_ansi,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ansiconv",
        description="Convert between ANSI SGR escape sequences and HTML spans.",
    )
    parser.add_argument(
        "direction",
        choices=["to-html", "to-ansi", "to-plain"],
        help=(
            "to-html: ANSI text -> HTML. to-ansi: HTML -> ANSI text. "
            "to-plain: ANSI text -> bare text with all styling stripped."
        ),
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
    parser.add_argument(
        "--self-closing-br",
        action="store_true",
        help="emit <br /> instead of <br> for newlines (to-html only)",
    )
    parser.add_argument(
        "--class-prefix",
        default=_DEFAULT_CLASS_PREFIX,
        help=f"prefix for generated/expected CSS class names (default: {_DEFAULT_CLASS_PREFIX!r})",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    text = args.input.read()

    try:
        if args.direction == "to-html":
            result = ansi_to_html(
                text,
                lenient=args.lenient,
                self_closing_br=args.self_closing_br,
                class_prefix=args.class_prefix,
            )
        elif args.direction == "to-ansi":
            result = html_to_ansi(text, lenient=args.lenient, class_prefix=args.class_prefix)
        else:
            result = ansi_to_plain(text, lenient=args.lenient)
    except ConversionError as exc:
        print(f"ansiconv: {exc} (use --lenient to ignore)", file=sys.stderr)
        return 1

    args.output.write(result)
    if not result.endswith("\n"):
        args.output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
