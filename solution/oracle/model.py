"""Sequential impulse solution for three-dimensional point impacts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .linalg import (
    Matrix,
    Vector,
    add,
    cross,
    cross_matrix,
    dot,
    inverse,
    is_positive_definite,
    matmul,
    matvec,
    norm,
    scale,
    solve2,
    tangent_basis,
)


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


def inertia_matrix(event: ImpactEvent) -> Matrix:
    """Return the symmetric inertia tensor in world coordinates."""
    return (
        (event.ixx, event.ixy, event.ixz),
        (event.ixy, event.iyy, event.iyz),
        (event.ixz, event.iyz, event.izz),
    )


def _vectors(event: ImpactEvent) -> tuple[Vector, Vector, Vector, Vector]:
    """Return velocity, angular velocity, arm, and normal vectors."""
    return (
        (event.vx, event.vy, event.vz),
        (event.wx, event.wy, event.wz),
        (event.rx, event.ry, event.rz),
        (event.nx, event.ny, event.nz),
    )


def _contact_velocity(velocity: Vector, angular: Vector, arm: Vector) -> Vector:
    """Return the contact-point velocity in world coordinates."""
    return add(velocity, cross(angular, arm))


def validate_event(event: ImpactEvent) -> None:
    """Reject physically or numerically inadmissible event data."""
    if not isinstance(event.event_id, str) or not event.event_id.strip():
        raise ValueError("event_id must not be empty")
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
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ValueError("all event values must be numeric")
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("all event values must be finite")
    if event.mass_kg <= 0.0:
        raise ValueError("mass_kg must be positive")
    tensor = inertia_matrix(event)
    if not is_positive_definite(tensor):
        raise ValueError("inertia tensor must be positive definite")
    if not 0.0 <= event.restitution <= 1.0:
        raise ValueError("restitution is outside [0, 1]")
    if event.friction_coefficient < 0.0:
        raise ValueError("friction_coefficient must be nonnegative")

    velocity, angular, arm, normal = _vectors(event)
    if abs(norm(normal) - 1.0) > 1e-9:
        raise ValueError("contact normal is not unit length")
    contact_velocity = _contact_velocity(velocity, angular, arm)
    if dot(contact_velocity, normal) >= 0.0:
        raise ValueError("contact is not approaching the barrier")


def _kinetic_energy(tensor: Matrix, velocity: Vector, angular: Vector, mass: float) -> float:
    """Return translational plus rotational kinetic energy."""
    return 0.5 * mass * dot(velocity, velocity) + 0.5 * dot(angular, matvec(tensor, angular))


def _apply_impulse(
    velocity: Vector,
    angular: Vector,
    impulse: Vector,
    arm: Vector,
    mass: float,
    inverse_tensor: Matrix,
) -> tuple[Vector, Vector]:
    """Apply one impulse at the contact point."""
    velocity_after = add(velocity, scale(impulse, 1.0 / mass))
    angular_after = add(angular, matvec(inverse_tensor, cross(arm, impulse)))
    return velocity_after, angular_after


def solve_event(event: ImpactEvent) -> dict[str, Any]:
    """Resolve one collision with sequential normal and friction impulses."""
    validate_event(event)
    tensor = inertia_matrix(event)
    inverse_tensor = inverse(tensor)
    velocity, angular, arm, normal = _vectors(event)
    velocity_before = velocity
    angular_before = angular

    cross_arm = cross_matrix(arm)
    coupling = matmul(matmul(cross_arm, inverse_tensor), cross_arm)
    contact_mass = tuple(
        tuple(-coupling[row][column] for column in range(3))
        for row in range(3)
    )
    contact_mass = (
        (1.0 / event.mass_kg + contact_mass[0][0], contact_mass[0][1], contact_mass[0][2]),
        (contact_mass[1][0], 1.0 / event.mass_kg + contact_mass[1][1], contact_mass[1][2]),
        (contact_mass[2][0], contact_mass[2][1], 1.0 / event.mass_kg + contact_mass[2][2]),
    )

    contact_velocity = _contact_velocity(velocity, angular, arm)
    normal_speed = dot(contact_velocity, normal)
    normal_denominator = dot(normal, matvec(contact_mass, normal))
    normal_impulse = -(1.0 + event.restitution) * normal_speed / normal_denominator
    normal_vector = scale(normal, normal_impulse)
    velocity, angular = _apply_impulse(
        velocity,
        angular,
        normal_vector,
        arm,
        event.mass_kg,
        inverse_tensor,
    )

    contact_velocity = _contact_velocity(velocity, angular, arm)
    tangent_velocity = tuple(
        contact_velocity[index] - dot(contact_velocity, normal) * normal[index]
        for index in range(3)
    )
    tangent_speed = norm(tangent_velocity)
    tangent_impulse: Vector = (0.0, 0.0, 0.0)
    contact_mode = "stick"
    if tangent_speed > 1e-15:
        first, second = tangent_basis(normal)
        tangent_matrix = (
            (dot(first, matvec(contact_mass, first)), dot(first, matvec(contact_mass, second))),
            (dot(second, matvec(contact_mass, first)), dot(second, matvec(contact_mass, second))),
        )
        coefficient_1, coefficient_2 = solve2(
            tangent_matrix,
            (-dot(first, tangent_velocity), -dot(second, tangent_velocity)),
        )
        candidate = add(scale(first, coefficient_1), scale(second, coefficient_2))
        friction_limit = event.friction_coefficient * normal_impulse
        if norm(candidate) <= friction_limit + 1e-12:
            tangent_impulse = candidate
        else:
            tangent_impulse = scale(tangent_velocity, -friction_limit / tangent_speed)
            contact_mode = "slide"

    velocity_after, angular_after = _apply_impulse(
        velocity,
        angular,
        tangent_impulse,
        arm,
        event.mass_kg,
        inverse_tensor,
    )
    energy_before = _kinetic_energy(tensor, velocity_before, angular_before, event.mass_kg)
    energy_after = _kinetic_energy(tensor, velocity_after, angular_after, event.mass_kg)

    return {
        "event_id": event.event_id,
        "normal_impulse_ns": normal_impulse,
        "tangential_impulse_ns": {
            "x": tangent_impulse[0],
            "y": tangent_impulse[1],
            "z": tangent_impulse[2],
        },
        "contact_mode": contact_mode,
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
        "kinetic_energy_before_j": energy_before,
        "kinetic_energy_after_j": energy_after,
        "energy_loss_j": energy_before - energy_after,
    }
