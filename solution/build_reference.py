#!/usr/bin/env python3
"""Build the checked reference report from the bundled simulated batch."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "solution"))

from oracle.cli import build_pair_report, build_report, load_events, load_pair_events  # noqa: E402


def main() -> None:
    """Write solution/reference-answer.json."""
    events = load_events(ROOT / "environment" / "workspace" / "data" / "impact_events.csv")
    report = build_report(events)
    output = ROOT / "solution" / "reference-answer.json"
    output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    pair_events = load_pair_events(
        ROOT / "environment" / "workspace" / "data" / "pallet_landings.csv"
    )
    pair_report = build_pair_report(pair_events)
    pair_output = ROOT / "solution" / "reference-pair-answer.json"
    pair_output.write_text(
        json.dumps(pair_report, ensure_ascii=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"events={report['summary']['event_count']} "
        f"stick={report['summary']['stick_count']} "
        f"slide={report['summary']['slide_count']} "
        f"loss_j={report['summary']['total_energy_loss_j']:.12g}"
    )
    print(
        f"pair_events={pair_report['summary']['event_count']} "
        f"pair_loss_j={pair_report['summary']['total_energy_loss_j']:.12g}"
    )


if __name__ == "__main__":
    main()
