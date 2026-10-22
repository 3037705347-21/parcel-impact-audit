"""Experiment variant with validation but without the complete physics report."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .linalg import dot, is_positive_definite


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


def validate_event(event: ImpactEvent) -> None:
    """Validate inertia and contact admission conditions."""
    values = (
        event.mass_kg,
        event.ixx,
        event.iyy,
        event.izz,
        event.ixy,
        event.ixz,
        event.iyz,
        event.vx,
        event.vy,
        event.vz,
        event.wx,
        event.wy,
        event.wz,
        event.rx,
        event.ry,
        event.rz,
        event.nx,
        event.ny,
        event.nz,
        event.restitution,
        event.friction_coefficient,
    )
    if not event.event_id.strip() or not all(math.isfinite(value) for value in values):
        raise ValueError("invalid event values")
    tensor = (
        (event.ixx, event.ixy, event.ixz),
        (event.ixy, event.iyy, event.iyz),
        (event.ixz, event.iyz, event.izz),
    )
    if event.mass_kg <= 0.0 or not is_positive_definite(tensor):
        raise ValueError("invalid mass or inertia")
    if not 0.0 <= event.restitution <= 1.0 or event.friction_coefficient < 0.0:
        raise ValueError("invalid coefficient")
    normal = (event.nx, event.ny, event.nz)
    if abs(math.sqrt(dot(normal, normal)) - 1.0) > 1e-9:
        raise ValueError("invalid normal")
    contact_velocity = (
        event.vx - event.wy * event.rz + event.wz * event.ry,
        event.vy - event.wz * event.rx + event.wx * event.rz,
        event.vz - event.wx * event.ry + event.wy * event.rx,
    )
    if dot(contact_velocity, normal) >= 0.0:
        raise ValueError("contact is separating")


def solve_event(event: ImpactEvent) -> dict[str, object]:
    """Return a placeholder state used only by the admission experiment."""
    return {
        "event_id": event.event_id,
        "contact_mode": "stick",
        "velocity_after_m_s": {"x": event.vx, "y": event.vy, "z": event.vz},
        "angular_velocity_after_rad_s": {"x": event.wx, "y": event.wy, "z": event.wz},
    }
