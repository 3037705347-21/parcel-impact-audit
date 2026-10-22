"""Validate spatial impact batches and atomically publish their report."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .model import ImpactEvent, solve_event, validate_event
from .pair import PairEvent, solve_pair_event, validate_pair_event


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


def _number(row: dict[str, str], name: str, row_number: int) -> float:
    """Parse one finite numeric field."""
    if row.get(name) is None or row[name].strip() == "":
        raise ValueError(f"row {row_number}: {name} is empty")
    value = float(row[name])
    if not math.isfinite(value):
        raise ValueError(f"row {row_number}: {name} must be finite")
    return value


def _event_from_row(row: dict[str, str], row_number: int) -> ImpactEvent:
    """Construct and validate one collision record."""
    try:
        event = ImpactEvent(
            event_id=(row.get("event_id") or "").strip(),
            mass_kg=_number(row, "mass_kg", row_number),
            ixx=_number(row, "ixx", row_number),
            iyy=_number(row, "iyy", row_number),
            izz=_number(row, "izz", row_number),
            ixy=_number(row, "ixy", row_number),
            ixz=_number(row, "ixz", row_number),
            iyz=_number(row, "iyz", row_number),
            vx=_number(row, "vx", row_number),
            vy=_number(row, "vy", row_number),
            vz=_number(row, "vz", row_number),
            wx=_number(row, "wx", row_number),
            wy=_number(row, "wy", row_number),
            wz=_number(row, "wz", row_number),
            rx=_number(row, "rx", row_number),
            ry=_number(row, "ry", row_number),
            rz=_number(row, "rz", row_number),
            nx=_number(row, "nx", row_number),
            ny=_number(row, "ny", row_number),
            nz=_number(row, "nz", row_number),
            restitution=_number(row, "restitution", row_number),
            friction_coefficient=_number(row, "friction_coefficient", row_number),
        )
        validate_event(event)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {exc}") from exc
    return event


def load_events(path: Path) -> list[ImpactEvent]:
    """Load and validate every event before any output is published."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [name for name in FIELDS if name not in fields]
        if missing:
            raise ValueError(f"missing required columns: {', '.join(missing)}")
        events = [
            _event_from_row(row, row_number)
            for row_number, row in enumerate(reader, start=2)
        ]
    if not events:
        raise ValueError("input has no events")
    return events


def build_report(events: list[ImpactEvent]) -> dict[str, Any]:
    """Resolve all events and aggregate their audit values."""
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


def _pair_event_from_row(row: dict[str, str], row_number: int) -> PairEvent:
    """Construct and validate one two-contact landing record."""
    try:
        event = PairEvent(
            event_id=(row.get("event_id") or "").strip(),
            mass_kg=_number(row, "mass_kg", row_number),
            inertia_kg_m2=_number(row, "inertia_kg_m2", row_number),
            vx_m_s=_number(row, "vx_m_s", row_number),
            vy_m_s=_number(row, "vy_m_s", row_number),
            omega_rad_s=_number(row, "omega_rad_s", row_number),
            r1x_m=_number(row, "r1x_m", row_number),
            r1y_m=_number(row, "r1y_m", row_number),
            r2x_m=_number(row, "r2x_m", row_number),
            r2y_m=_number(row, "r2y_m", row_number),
            nx=_number(row, "nx", row_number),
            ny=_number(row, "ny", row_number),
            restitution=_number(row, "restitution", row_number),
            friction_coefficient=_number(row, "friction_coefficient", row_number),
        )
        validate_pair_event(event)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {exc}") from exc
    return event


def load_pair_events(path: Path) -> list[PairEvent]:
    """Load and validate every two-contact event."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [name for name in PAIR_FIELDS if name not in fields]
        if missing:
            raise ValueError(f"missing required columns: {', '.join(missing)}")
        events = [
            _pair_event_from_row(row, row_number)
            for row_number, row in enumerate(reader, start=2)
        ]
    if not events:
        raise ValueError("input has no events")
    return events


def build_pair_report(events: list[PairEvent]) -> dict[str, Any]:
    """Resolve two-contact events and aggregate contact-level modes."""
    results = [solve_pair_event(event) for event in events]
    modes = [mode for result in results for mode in result["contact_modes"]]
    losses = [float(result["energy_loss_j"]) for result in results]
    return {
        "events": results,
        "summary": {
            "event_count": len(results),
            "stick_count": modes.count("stick"),
            "slide_count": modes.count("slide"),
            "inactive_count": modes.count("inactive"),
            "total_energy_loss_j": sum(losses),
            "maximum_energy_gain_j": max([0.0, *(-loss for loss in losses)]),
        },
    }


def _atomic_write(path: Path, content: str) -> None:
    """Replace the destination only after the complete JSON is on disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _run_single(argv: list[str]) -> int:
    """Run the single-contact command."""
    parser = argparse.ArgumentParser(description="Audit spatial parcel impacts")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_report(load_events(args.input))
        content = json.dumps(
            report,
            ensure_ascii=True,
            indent=2,
            allow_nan=False,
        ) + "\n"
        _atomic_write(args.output, content)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"impact audit failed: {exc}", file=sys.stderr)
        return 2
    return 0


def _run_pair(argv: list[str]) -> int:
    """Run the two-contact pallet landing command."""
    parser = argparse.ArgumentParser(description="Audit two-point pallet landings")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_pair_report(load_pair_events(args.input))
        content = json.dumps(
            report,
            ensure_ascii=True,
            indent=2,
            allow_nan=False,
        ) + "\n"
        _atomic_write(args.output, content)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"impact audit failed: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch single-contact or two-contact batch analysis."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "pair":
        return _run_pair(arguments[1:])
    return _run_single(arguments)
