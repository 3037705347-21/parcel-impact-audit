#!/usr/bin/env python3
"""Generate the bundled deterministic two-contact pallet landing batch."""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "solution"))

from oracle.pair import PairEvent, solve_pair_event  # noqa: E402


SEED = 73129
NORMALS = [(0.0, 1.0), (0.6, 0.8), (1.0, 0.0), (-0.8, 0.6)]
FIELDS = [
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
]


def _candidate(rng: random.Random, index: int) -> PairEvent:
    """Build one random admissible two-contact landing candidate."""
    nx, ny = NORMALS[index % len(NORMALS)]
    return PairEvent(
        event_id=f"LAND-{index + 1:03d}",
        mass_kg=rng.uniform(1.8, 6.0),
        inertia_kg_m2=rng.uniform(0.25, 1.25),
        vx_m_s=rng.uniform(-1.8, 1.8),
        vy_m_s=rng.uniform(-2.2, 1.0),
        omega_rad_s=rng.uniform(-2.0, 2.0),
        r1x_m=rng.uniform(-0.28, 0.28),
        r1y_m=rng.uniform(-0.26, 0.26),
        r2x_m=rng.uniform(-0.28, 0.28),
        r2y_m=rng.uniform(-0.26, 0.26),
        nx=nx,
        ny=ny,
        restitution=rng.uniform(0.08, 0.65),
        friction_coefficient=rng.uniform(0.04, 0.95),
    )


def main() -> None:
    """Write eight events covering one-sided and two-sided contacts."""
    rng = random.Random(SEED)
    events: list[PairEvent] = []
    attempts = 0
    while len(events) < 8 and attempts < 20000:
        attempts += 1
        candidate = _candidate(rng, len(events))
        try:
            result = solve_pair_event(candidate)
        except ValueError:
            continue
        modes = result["contact_modes"]
        if len(events) < 4 and modes.count("inactive") != 0:
            continue
        if len(events) in {4, 5} and "slide" not in modes:
            continue
        if len(events) == 6 and modes.count("inactive") != 1:
            continue
        events.append(candidate)
    if len(events) != 8:
        raise RuntimeError("could not generate eight admissible pair events")

    rows = [
        {
            "event_id": event.event_id,
            "mass_kg": f"{event.mass_kg:.6f}",
            "inertia_kg_m2": f"{event.inertia_kg_m2:.6f}",
            "vx_m_s": f"{event.vx_m_s:.6f}",
            "vy_m_s": f"{event.vy_m_s:.6f}",
            "omega_rad_s": f"{event.omega_rad_s:.6f}",
            "r1x_m": f"{event.r1x_m:.6f}",
            "r1y_m": f"{event.r1y_m:.6f}",
            "r2x_m": f"{event.r2x_m:.6f}",
            "r2y_m": f"{event.r2y_m:.6f}",
            "nx": f"{event.nx:.6f}",
            "ny": f"{event.ny:.6f}",
            "restitution": f"{event.restitution:.6f}",
            "friction_coefficient": f"{event.friction_coefficient:.6f}",
        }
        for event in events
    ]
    output = ROOT / "environment" / "workspace" / "data" / "pallet_landings.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
