"""Command-line entry point: python -m app.cli FILE"""

import argparse
import json
import sys

from app.core import word_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Count words, lines and characters.")
    parser.add_argument("path", help="file to read, or - for stdin")
    args = parser.parse_args(argv)
    text = sys.stdin.read() if args.path == "-" else open(args.path, encoding="utf-8").read()
    print(json.dumps(word_count(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
