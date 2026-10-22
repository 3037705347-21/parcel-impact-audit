"""Spatial impact calculations used by the batch audit command."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImpactEvent:
    """One three-dimensional point-contact collision record."""

    event_id: str
    mass_kg: float
    ixx: float
    iyy: float
    izz: float
    ixy: float
    ixz: float
    iyz: float
    vx: float
    vy: float
    vz: float
    wx: float
    wy: float
    wz: float
    rx: float
    ry: float
    rz: float
    nx: float
    ny: float
    nz: float
    restitution: float
    friction_coefficient: float


def solve_event(event: ImpactEvent) -> dict[str, object]:
    """Resolve one collision into the current report shape."""
    normal_speed = event.vx * event.nx + event.vy * event.ny + event.vz * event.nz
    impulse = -(1.0 + event.restitution) * event.mass_kg * normal_speed
    return {
        "event_id": event.event_id,
        "normal_impulse_ns": impulse,
        "tangential_impulse_ns": {"x": 0.0, "y": 0.0, "z": 0.0},
        "contact_mode": "stick",
        "velocity_after_m_s": {
            "x": event.vx + impulse * event.nx / event.mass_kg,
            "y": event.vy + impulse * event.ny / event.mass_kg,
            "z": event.vz + impulse * event.nz / event.mass_kg,
        },
        "angular_velocity_after_rad_s": {
            "x": event.wx,
            "y": event.wy,
            "z": event.wz,
        },
    }
