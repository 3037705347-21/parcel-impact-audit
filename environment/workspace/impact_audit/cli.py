"""CSV-to-JSON command for three-dimensional impact records."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

from .model import ImpactEvent, solve_event
from .pair import PairEvent, solve_pair_event


FIELDS = (
    "event_id",
    "mass_kg",
    "ixx",
    "iyy",
    "izz",
    "ixy",
    "ixz",
    "iyz",
    "vx",
    "vy",
    "vz",
    "wx",
    "wy",
    "wz",
    "rx",
    "ry",
    "rz",
    "nx",
    "ny",
    "nz",
    "restitution",
    "friction_coefficient",
)
PAIR_FIELDS = (
    "event_id",
    "mass_kg",
    "inertia_kg_m2",
    "vx_m_s",
    "vy_m_s",
    "omega_rad_s",
    "r1x_m",
    "r1y_m",
    "r2x_m",
    "r2y_m",
    "nx",
    "ny",
    "restitution",
    "friction_coefficient",
)


def _number(row: dict[str, str], name: str) -> float:
    """Parse a finite CSV number."""
    value = float(row[name])
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def load_events(path: Path) -> list[ImpactEvent]:
    """Load collision events from a headed CSV file."""
    events: list[ImpactEvent] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(FIELDS).issubset(reader.fieldnames):
            raise ValueError("missing required columns")
        for row in reader:
            events.append(
                ImpactEvent(
                    event_id=row["event_id"],
                    mass_kg=_number(row, "mass_kg"),
                    ixx=_number(row, "ixx"),
                    iyy=_number(row, "iyy"),
                    izz=_number(row, "izz"),
                    ixy=_number(row, "ixy"),
                    ixz=_number(row, "ixz"),
                    iyz=_number(row, "iyz"),
                    vx=_number(row, "vx"),
                    vy=_number(row, "vy"),
                    vz=_number(row, "vz"),
                    wx=_number(row, "wx"),
                    wy=_number(row, "wy"),
                    wz=_number(row, "wz"),
                    rx=_number(row, "rx"),
                    ry=_number(row, "ry"),
                    rz=_number(row, "rz"),
                    nx=_number(row, "nx"),
                    ny=_number(row, "ny"),
                    nz=_number(row, "nz"),
                    restitution=_number(row, "restitution"),
                    friction_coefficient=_number(row, "friction_coefficient"),
                )
            )
    if not events:
        raise ValueError("input has no events")
    return events


def build_report(events: list[ImpactEvent]) -> dict[str, object]:
    """Convert loaded events into report data."""
    results = [solve_event(event) for event in events]
    return {"events": results, "summary": {"event_count": len(results)}}


def load_pair_events(path: Path) -> list[PairEvent]:
    """Load two-contact landing records."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(PAIR_FIELDS).issubset(reader.fieldnames):
            raise ValueError("missing required pair columns")
        events = [
            PairEvent(
                event_id=row["event_id"],
                mass_kg=_number(row, "mass_kg"),
                inertia_kg_m2=_number(row, "inertia_kg_m2"),
                vx_m_s=_number(row, "vx_m_s"),
                vy_m_s=_number(row, "vy_m_s"),
                omega_rad_s=_number(row, "omega_rad_s"),
                r1x_m=_number(row, "r1x_m"),
                r1y_m=_number(row, "r1y_m"),
                r2x_m=_number(row, "r2x_m"),
                r2y_m=_number(row, "r2y_m"),
                nx=_number(row, "nx"),
                ny=_number(row, "ny"),
                restitution=_number(row, "restitution"),
                friction_coefficient=_number(row, "friction_coefficient"),
            )
            for row in reader
        ]
    if not events:
        raise ValueError("input has no events")
    return events


def build_pair_report(events: list[PairEvent]) -> dict[str, object]:
    """Convert pair events into report data."""
    results = [solve_pair_event(event) for event in events]
    return {"events": results, "summary": {"event_count": len(results)}}


def _run_single(argv: list[str]) -> int:
    """Run the single-contact command."""
    parser = argparse.ArgumentParser(description="Audit spatial parcel impacts")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_report(load_events(args.input))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"impact audit failed: {exc}", file=sys.stderr)
        return 2
    return 0


def _run_pair(argv: list[str]) -> int:
    """Run the two-contact landing command."""
    parser = argparse.ArgumentParser(description="Audit two-point pallet landings")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_pair_report(load_pair_events(args.input))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"impact audit failed: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the batch command."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "pair":
        return _run_pair(arguments[1:])
    return _run_single(arguments)
