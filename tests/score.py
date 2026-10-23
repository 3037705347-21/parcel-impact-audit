"""Score a completed JUnit report and publish verifier status."""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


GROUPS = {
    "C1": (0.14, "test_c1_"),
    "C2": (0.18, "test_c2_"),
    "C3": (0.10, "test_c3_"),
    "C4": (0.10, "test_c4_"),
    "C5": (0.30, "test_c5_"),
    "E2E": (0.18, "test_e2e_"),
}


def _write(path: Path, value: str) -> None:
    """Write a verifier file with the runtime-visible mode."""
    os.chmod(path, 0o644)
    path.write_text(value + "\n", encoding="utf-8")
    os.chmod(path, 0o444)


def main() -> int:
    """Compute the weighted score from the structured JUnit report."""
    report_path = Path(sys.argv[1])
    reward_path = Path(sys.argv[2])
    status_path = Path(sys.argv[3])
    statuses: dict[str, bool] = {}
    try:
        tree = ET.parse(report_path)
        for case in tree.findall(".//testcase"):
            name = case.attrib.get("name", "")
            failed = case.find("failure") is not None or case.find("error") is not None
            skipped = case.find("skipped") is not None
            statuses[name] = not failed and not skipped
    except (OSError, ET.ParseError):
        statuses = {}

    weighted_total = 0.0
    incomplete = not statuses
    for weight, prefix in GROUPS.values():
        relevant = [passed for name, passed in statuses.items() if name.startswith(prefix)]
        if not relevant:
            incomplete = True
        elif all(relevant):
            weighted_total += weight

    if incomplete:
        weighted_total = 0.0
        status = "INCOMPLETE: weighted scoring report is incomplete"
    else:
        status = f"COMPLETED: weighted scoring finished with reward={weighted_total:.6f}"
    weighted_total = min(1.0, max(0.0, weighted_total))
    _write(reward_path, f"{weighted_total:.6f}")
    _write(status_path, status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
