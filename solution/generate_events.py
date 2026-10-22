#!/usr/bin/env python3
"""Generate the bundled deterministic simulated spatial impact batch."""

from __future__ import annotations

import csv
import math
import random
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "solution"))

from oracle.linalg import add, cross, dot, is_positive_definite, scale, tangent_basis  # noqa: E402
from oracle.model import ImpactEvent, solve_event  # noqa: E402


SEED = 41729
NORMALS = [
    (1.0, 0.0, 0.0),
    (0.48, 0.6, 0.64),
    (0.0, 1.0, 0.0),
    (-0.6, 0.48, 0.64),
    (0.8, 0.0, 0.6),
    (0.36, -0.48, 0.8),
]
SLIDING = {1, 3, 4, 6, 8, 10}
FIELDS = [
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
]


def _tensor(rng: random.Random) -> tuple[float, float, float, float, float, float]:
    """Generate a positive-definite asymmetric rigid-body inertia tensor."""
    while True:
        ixx = rng.uniform(0.35, 1.1)
        iyy = rng.uniform(0.35, 1.1)
        izz = rng.uniform(0.35, 1.2)
        limit = min(ixx, iyy, izz) * 0.18
        ixy = rng.uniform(-limit, limit)
        ixz = rng.uniform(-limit, limit)
        iyz = rng.uniform(-limit, limit)
        matrix = ((ixx, ixy, ixz), (ixy, iyy, iyz), (ixz, iyz, izz))
        if is_positive_definite(matrix):
            return ixx, iyy, izz, ixy, ixz, iyz


def _event(index: int, rng: random.Random) -> ImpactEvent:
    """Generate one event with the intended contact mode."""
    nx, ny, nz = NORMALS[index % len(NORMALS)]
    normal = (nx, ny, nz)
    first, second = tangent_basis(normal)
    ixx, iyy, izz, ixy, ixz, iyz = _tensor(rng)
    arm = (
        rng.uniform(-0.15, 0.15),
        rng.uniform(-0.15, 0.15),
        rng.uniform(-0.15, 0.15),
    )
    angular = (
        rng.uniform(-1.4, 1.4),
        rng.uniform(-1.4, 1.4),
        rng.uniform(-1.4, 1.4),
    )
    angle = rng.uniform(0.0, 2.0 * math.pi)
    magnitude = rng.uniform(1.5, 2.8) if index in SLIDING else rng.uniform(0.04, 0.12)
    tangent_velocity = add(
        scale(first, magnitude * math.cos(angle)),
        scale(second, magnitude * math.sin(angle)),
    )
    contact_velocity = add(scale(normal, -rng.uniform(0.7, 3.0)), tangent_velocity)
    velocity = tuple(
        contact_velocity[axis] - cross(angular, arm)[axis]
        for axis in range(3)
    )
    restitution = rng.uniform(0.12, 0.68)
    friction = rng.uniform(0.04, 0.14) if index in SLIDING else rng.uniform(0.82, 0.99)
    event = ImpactEvent(
        event_id=f"IMP-{index + 1:03d}",
        mass_kg=rng.uniform(1.8, 7.5),
        ixx=ixx,
        iyy=iyy,
        izz=izz,
        ixy=ixy,
        ixz=ixz,
        iyz=iyz,
        vx=velocity[0],
        vy=velocity[1],
        vz=velocity[2],
        wx=angular[0],
        wy=angular[1],
        wz=angular[2],
        rx=arm[0],
        ry=arm[1],
        rz=arm[2],
        nx=nx,
        ny=ny,
        nz=nz,
        restitution=restitution,
        friction_coefficient=friction,
    )
    result = solve_event(event)
    intended = "slide" if index in SLIDING else "stick"
    if result["contact_mode"] != intended:
        raise RuntimeError(f"event {index} obtained {result['contact_mode']}, expected {intended}")
    return event


def main() -> None:
    """Write twelve reproducible events with balanced contact modes."""
    rng = random.Random(SEED)
    events = [_event(index, rng) for index in range(12)]
    rows = [
        {
            "event_id": event.event_id,
            "mass_kg": f"{event.mass_kg:.6f}",
            "ixx": f"{event.ixx:.6f}",
            "iyy": f"{event.iyy:.6f}",
            "izz": f"{event.izz:.6f}",
            "ixy": f"{event.ixy:.6f}",
            "ixz": f"{event.ixz:.6f}",
            "iyz": f"{event.iyz:.6f}",
            "vx": f"{event.vx:.6f}",
            "vy": f"{event.vy:.6f}",
            "vz": f"{event.vz:.6f}",
            "wx": f"{event.wx:.6f}",
            "wy": f"{event.wy:.6f}",
            "wz": f"{event.wz:.6f}",
            "rx": f"{event.rx:.6f}",
            "ry": f"{event.ry:.6f}",
            "rz": f"{event.rz:.6f}",
            "nx": f"{event.nx:.6f}",
            "ny": f"{event.ny:.6f}",
            "nz": f"{event.nz:.6f}",
            "restitution": f"{event.restitution:.6f}",
            "friction_coefficient": f"{event.friction_coefficient:.6f}",
        }
        for event in events
    ]
    output = ROOT / "environment" / "workspace" / "data" / "impact_events.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
