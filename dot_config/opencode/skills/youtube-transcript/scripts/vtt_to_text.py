#!/usr/bin/env python3
"""Convert WebVTT cues to text without globally dropping repeated speech."""

import argparse
import html
import re
import sys
from pathlib import Path


TIMESTAMP = r"(?:\d+:)?\d{2}:\d{2}\.\d{3}"
TIMING = re.compile(rf"^({TIMESTAMP})\s+-->\s+({TIMESTAMP})(?:\s+.*)?$")


def seconds(timestamp: str) -> float:
    result = 0.0
    for part in timestamp.split(":"):
        result = result * 60 + float(part)
    return result


def convert_vtt(source: str) -> str:
    source = source.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not re.match(r"^WEBVTT(?:[ \t].*)?(?:\n|$)", source):
        raise ValueError("input must start with a WEBVTT header")

    output: list[str] = []
    history: list[str] = []
    previous_end = -1.0
    for block in re.split(r"\n[ \t]*\n", source):
        lines = block.splitlines()
        if not lines or re.match(r"^(?:WEBVTT|NOTE|STYLE|REGION)(?:[ \t]|$)", lines[0]):
            continue
        # A cue may have a single identifier before its timing line.
        timing_index = 0 if TIMING.match(lines[0]) else 1
        if timing_index >= len(lines):
            continue
        match = TIMING.match(lines[timing_index])
        if match is None:
            continue
        start, end = map(seconds, match.groups())
        if end <= start:
            raise ValueError("cue end must be later than its start")
        body = " ".join(lines[timing_index + 1 :])
        words = html.unescape(re.sub(r"<[^>]*>", "", body)).split()
        if not words:
            continue

        # Shared suffix/prefix text is only redundant within overlapping cues.
        if start < previous_end:
            shared = 0
            for size in range(min(len(history), len(words)), 0, -1):
                if history[-size:] == words[:size]:
                    shared = size
                    break
            new_words = words[shared:]
            history.extend(new_words)
        else:
            new_words = words
            history = words.copy()
        if new_words:
            output.append(" ".join(new_words))
        previous_end = end

    if not output:
        raise ValueError("no caption text found in WebVTT cues")
    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="WebVTT caption file")
    parser.add_argument("--output", type=Path, help="new text file; defaults to stdout")
    args = parser.parse_args()
    try:
        text = convert_vtt(args.input.read_text(encoding="utf-8-sig"))
        if args.output is None:
            sys.stdout.write(text)
        else:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
