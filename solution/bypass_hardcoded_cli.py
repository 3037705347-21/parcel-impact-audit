"""Experiment variant that replays the bundled sample regardless of input."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Copy the previously captured sample report for every command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1] / "reference-answer.json"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, args.output)
    return 0
