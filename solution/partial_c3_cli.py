"""Experiment variant that adds energy output without input gating."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .model import ImpactEvent, solve_event


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


def load_events(path: Path) -> list[ImpactEvent]:
    """Load records without the full physical validation layer."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(FIELDS).issubset(reader.fieldnames):
            raise ValueError("missing required columns")
        return [
            ImpactEvent(
                event_id=row["event_id"],
                mass_kg=float(row["mass_kg"]),
                ixx=float(row["ixx"]),
                iyy=float(row["iyy"]),
                izz=float(row["izz"]),
                ixy=float(row["ixy"]),
                ixz=float(row["ixz"]),
                iyz=float(row["iyz"]),
                vx=float(row["vx"]),
                vy=float(row["vy"]),
                vz=float(row["vz"]),
                wx=float(row["wx"]),
                wy=float(row["wy"]),
                wz=float(row["wz"]),
                rx=float(row["rx"]),
                ry=float(row["ry"]),
                rz=float(row["rz"]),
                nx=float(row["nx"]),
                ny=float(row["ny"]),
                nz=float(row["nz"]),
                restitution=float(row["restitution"]),
                friction_coefficient=float(row["friction_coefficient"]),
            )
            for row in reader
        ]


def build_report(events: list[ImpactEvent]) -> dict[str, object]:
    """Build event records and their energy summary."""
    results = [solve_event(event) for event in events]
    losses = [float(result["energy_loss_j"]) for result in results]
    return {
        "events": results,
        "summary": {
            "event_count": len(results),
            "stick_count": sum(result["contact_mode"] == "stick" for result in results),
            "slide_count": sum(result["contact_mode"] == "slide" for result in results),
            "total_energy_loss_j": sum(losses),
            "maximum_energy_gain_j": max([0.0, *(-loss for loss in losses)]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Write a complete valid-batch report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = build_report(load_events(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0
