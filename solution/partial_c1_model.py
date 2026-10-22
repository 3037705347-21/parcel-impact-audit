"""Experiment variant with spatial normal response only."""

from __future__ import annotations

from dataclasses import dataclass

from .linalg import Vector, add, cross, cross_matrix, dot, inverse, matmul, matvec, scale


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
    """Apply the spatial normal impulse without tangential or energy stages."""
    tensor = (
        (event.ixx, event.ixy, event.ixz),
        (event.ixy, event.iyy, event.iyz),
        (event.ixz, event.iyz, event.izz),
    )
    inverse_tensor = inverse(tensor)
    velocity: Vector = (event.vx, event.vy, event.vz)
    angular: Vector = (event.wx, event.wy, event.wz)
    arm: Vector = (event.rx, event.ry, event.rz)
    normal: Vector = (event.nx, event.ny, event.nz)
    cross_arm = cross_matrix(arm)
    coupled = matmul(matmul(cross_arm, inverse_tensor), cross_arm)
    contact_mass = tuple(
        tuple(
            (1.0 / event.mass_kg if row == column else 0.0) - coupled[row][column]
            for column in range(3)
        )
        for row in range(3)
    )
    contact_velocity = add(velocity, cross(angular, arm))
    normal_impulse = (
        -(1.0 + event.restitution)
        * dot(contact_velocity, normal)
        / dot(normal, matvec(contact_mass, normal))
    )
    impulse = scale(normal, normal_impulse)
    velocity_after = add(velocity, scale(impulse, 1.0 / event.mass_kg))
    angular_after = add(angular, matvec(inverse_tensor, cross(arm, impulse)))
    return {
        "event_id": event.event_id,
        "normal_impulse_ns": normal_impulse,
        "tangential_impulse_ns": {"x": 0.0, "y": 0.0, "z": 0.0},
        "contact_mode": "stick",
        "velocity_after_m_s": {
            "x": velocity_after[0],
            "y": velocity_after[1],
            "z": velocity_after[2],
        },
        "angular_velocity_after_rad_s": {
            "x": angular_after[0],
            "y": angular_after[1],
            "z": angular_after[2],
        },
    }
