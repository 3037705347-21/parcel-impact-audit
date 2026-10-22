"""Two-point unilateral impact and box-constrained friction solver."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any

from .linalg import solve2


@dataclass(frozen=True)
class PairEvent:
    """One planar body contacting a common surface at two points."""

    event_id: str
    mass_kg: float
    inertia_kg_m2: float
    vx_m_s: float
    vy_m_s: float
    omega_rad_s: float
    r1x_m: float
    r1y_m: float
    r2x_m: float
    r2y_m: float
    nx: float
    ny: float
    restitution: float
    friction_coefficient: float


def _dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Return a planar dot product."""
    return a[0] * b[0] + a[1] * b[1]


def _cross(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Return the scalar z component of a planar cross product."""
    return a[0] * b[1] - a[1] * b[0]


def _contact_velocity(
    velocity: tuple[float, float],
    omega: float,
    arm: tuple[float, float],
) -> tuple[float, float]:
    """Return planar contact-point velocity."""
    return (
        velocity[0] - omega * arm[1],
        velocity[1] + omega * arm[0],
    )


def _moments(
    event: PairEvent,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return both contact arms."""
    return (event.r1x_m, event.r1y_m), (event.r2x_m, event.r2y_m)


def _contact_matrices(
    event: PairEvent,
) -> tuple[tuple[tuple[float, float], tuple[float, float]], tuple[tuple[float, float], tuple[float, float]]]:
    """Build coupled normal and tangent inverse-mass matrices."""
    first, second = _moments(event)
    arms = (first, second)
    normal = (event.nx, event.ny)
    tangent = (-event.ny, event.nx)
    normal_matrix = tuple(
        tuple(
            1.0 / event.mass_kg
            + _cross(arms[i], normal) * _cross(arms[j], normal) / event.inertia_kg_m2
            for j in range(2)
        )
        for i in range(2)
    )
    tangent_matrix = tuple(
        tuple(
            1.0 / event.mass_kg
            + _cross(arms[i], tangent) * _cross(arms[j], tangent) / event.inertia_kg_m2
            for j in range(2)
        )
        for i in range(2)
    )
    return normal_matrix, tangent_matrix  # type: ignore[return-value]


def validate_pair_event(event: PairEvent) -> None:
    """Validate a two-contact landing record."""
    values = (
        event.mass_kg,
        event.inertia_kg_m2,
        event.vx_m_s,
        event.vy_m_s,
        event.omega_rad_s,
        event.r1x_m,
        event.r1y_m,
        event.r2x_m,
        event.r2y_m,
        event.nx,
        event.ny,
        event.restitution,
        event.friction_coefficient,
    )
    if not isinstance(event.event_id, str) or not event.event_id.strip():
        raise ValueError("event_id must not be empty")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ValueError("all event values must be numeric")
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("all event values must be finite")
    if event.mass_kg <= 0.0 or event.inertia_kg_m2 <= 0.0:
        raise ValueError("mass and inertia must be positive")
    if not 0.0 <= event.restitution <= 1.0:
        raise ValueError("restitution is outside [0, 1]")
    if event.friction_coefficient < 0.0:
        raise ValueError("friction_coefficient must be nonnegative")
    normal = (event.nx, event.ny)
    if abs(math.hypot(event.nx, event.ny) - 1.0) > 1e-9:
        raise ValueError("contact normal is not unit length")
    first, second = _moments(event)
    if math.hypot(first[0] - second[0], first[1] - second[1]) <= 1e-12:
        raise ValueError("contact points must be distinct")
    velocity = (event.vx_m_s, event.vy_m_s)
    speeds = (
        _dot(_contact_velocity(velocity, event.omega_rad_s, first), normal),
        _dot(_contact_velocity(velocity, event.omega_rad_s, second), normal),
    )
    if min(speeds) >= 0.0:
        raise ValueError("neither contact is approaching the surface")


def _apply(
    event: PairEvent,
    velocity: tuple[float, float],
    omega: float,
    impulses: tuple[float, float],
    direction: tuple[float, float],
) -> tuple[tuple[float, float], float]:
    """Apply one scalar impulse at each contact."""
    first, second = _moments(event)
    velocity_x = velocity[0] + (impulses[0] + impulses[1]) * direction[0] / event.mass_kg
    velocity_y = velocity[1] + (impulses[0] + impulses[1]) * direction[1] / event.mass_kg
    torque = (
        _cross(first, (impulses[0] * direction[0], impulses[0] * direction[1]))
        + _cross(second, (impulses[1] * direction[0], impulses[1] * direction[1]))
    )
    return (velocity_x, velocity_y), omega + torque / event.inertia_kg_m2


def _solve_normal(
    event: PairEvent,
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Enumerate unilateral normal active sets and return the admissible one."""
    normal = (event.nx, event.ny)
    velocity = (event.vx_m_s, event.vy_m_s)
    first, second = _moments(event)
    arms = (first, second)
    pre_speeds = tuple(
        _dot(_contact_velocity(velocity, event.omega_rad_s, arm), normal)
        for arm in arms
    )
    approaching = [index for index, value in enumerate(pre_speeds) if value < 0.0]
    normal_matrix, _ = _contact_matrices(event)
    candidates: list[tuple[float, tuple[float, float], tuple[float, float], float]] = []
    for size in (1, 2):
        for subset in itertools.combinations(approaching, size):
            impulses = [0.0, 0.0]
            if len(subset) == 1:
                index = subset[0]
                impulses[index] = (
                    -(1.0 + event.restitution) * pre_speeds[index] / normal_matrix[index][index]
                )
            else:
                impulses[0], impulses[1] = solve2(
                    normal_matrix,
                    (
                        -(1.0 + event.restitution) * pre_speeds[0],
                        -(1.0 + event.restitution) * pre_speeds[1],
                    ),
                )
            if any(impulses[index] < -1e-10 for index in subset):
                continue
            moments = (max(0.0, impulses[0]), max(0.0, impulses[1]))
            velocity_after, omega_after = _apply(event, velocity, event.omega_rad_s, moments, normal)
            post_speeds = tuple(
                _dot(_contact_velocity(velocity_after, omega_after, arm), normal)
                for arm in arms
            )
            inactive = {0, 1} - set(subset)
            if any(post_speeds[index] < -1e-9 for index in inactive):
                continue
            if all(
                abs(post_speeds[index] + event.restitution * pre_speeds[index]) <= 1e-8
                for index in subset
            ):
                candidates.append((sum(moments), moments, velocity_after, omega_after))
    if not candidates:
        raise ValueError("no admissible nonnegative normal impulse set")
    return min(candidates, key=lambda item: item[0])[1:]


def _solve_box_qp(
    matrix: tuple[tuple[float, float], tuple[float, float]],
    linear: tuple[float, float],
    limits: tuple[float, float],
    count: int,
) -> tuple[float, ...]:
    """Enumerate free and active bounds for a two-variable convex QP."""
    options = tuple(
        (0,) if limits[index] <= 1e-15 else (-1, 0, 1)
        for index in range(count)
    )
    best: tuple[float, tuple[float, ...]] | None = None
    for statuses in itertools.product(*options):
        values = [0.0] * count
        free = [
            index
            for index, status in enumerate(statuses)
            if status == 0
        ]
        for index, status in enumerate(statuses):
            if status == -1:
                values[index] = -limits[index]
            elif status == 1:
                values[index] = limits[index]
        if free:
            rhs = []
            for row in free:
                fixed_sum = sum(
                    matrix[row][column] * values[column]
                    for column in range(count)
                    if column not in free
                )
                rhs.append(-(linear[row] + fixed_sum))
            if len(free) == 1:
                row = free[0]
                solved = [rhs[0] / matrix[row][row]]
            else:
                solved = list(
                    solve2(
                        (
                            (matrix[free[0]][free[0]], matrix[free[0]][free[1]]),
                            (matrix[free[1]][free[0]], matrix[free[1]][free[1]]),
                        ),
                        (rhs[0], rhs[1]),
                    )
                )
            for index, value in zip(free, solved, strict=True):
                values[index] = value
        if any(
            values[index] < -limits[index] - 1e-8
            or values[index] > limits[index] + 1e-8
            for index in range(count)
        ):
            continue
        gradient = tuple(
            sum(matrix[row][column] * values[column] for column in range(count))
            + linear[row]
            for row in range(count)
        )
        feasible = True
        for index, status in enumerate(statuses):
            if status == -1 and gradient[index] < -1e-8:
                feasible = False
            if status == 1 and gradient[index] > 1e-8:
                feasible = False
        if not feasible:
            continue
        objective = 0.5 * sum(
            values[row] * matrix[row][column] * values[column]
            for row in range(count)
            for column in range(count)
        ) + sum(values[index] * linear[index] for index in range(count))
        if best is None or objective < best[0] - 1e-12:
            best = (objective, tuple(values))
    if best is None:
        raise ValueError("no admissible friction impulse")
    return best[1]


def solve_pair_event(event: PairEvent) -> dict[str, Any]:
    """Resolve a two-point landing with unilateral normal and friction impulses."""
    validate_pair_event(event)
    normal = (event.nx, event.ny)
    tangent = (-event.ny, event.nx)
    first, second = _moments(event)
    arms = (first, second)
    velocity_before = (event.vx_m_s, event.vy_m_s)
    omega_before = event.omega_rad_s
    normal_impulses, velocity, omega = _solve_normal(event)
    active = [index for index, value in enumerate(normal_impulses) if value > 1e-10]
    _, tangent_matrix = _contact_matrices(event)
    tangent_speeds = tuple(
        _dot(_contact_velocity(velocity, omega, arms[index]), tangent)
        for index in active
    )
    reduced = tuple(
        tuple(tangent_matrix[row][column] for column in active)
        for row in active
    )
    linear = tangent_speeds
    limits = tuple(
        event.friction_coefficient * normal_impulses[index]
        for index in active
    )
    friction_values = _solve_box_qp(reduced, linear, limits, len(active))
    tangent_world = [(0.0, 0.0), (0.0, 0.0)]
    tangent_totals = [0.0, 0.0]
    for slot, index in enumerate(active):
        tangent_totals[index] = friction_values[slot]
        tangent_world[index] = (
            friction_values[slot] * tangent[0],
            friction_values[slot] * tangent[1],
        )
    velocity_after, omega_after = _apply(
        event,
        velocity,
        omega,
        tuple(tangent_totals),
        tangent,
    )
    modes = ["inactive", "inactive"]
    for slot, index in enumerate(active):
        value = abs(friction_values[slot])
        limit = limits[slot]
        modes[index] = "slide" if limit <= 1e-15 or value >= limit - 1e-8 else "stick"
    energy_before = 0.5 * event.mass_kg * _dot(velocity_before, velocity_before) + 0.5 * event.inertia_kg_m2 * omega_before * omega_before
    energy_after = 0.5 * event.mass_kg * _dot(velocity_after, velocity_after) + 0.5 * event.inertia_kg_m2 * omega_after * omega_after
    return {
        "event_id": event.event_id,
        "contact_normal_impulses_ns": [normal_impulses[0], normal_impulses[1]],
        "contact_tangent_impulses_ns": [
            {"x": tangent_world[0][0], "y": tangent_world[0][1]},
            {"x": tangent_world[1][0], "y": tangent_world[1][1]},
        ],
        "contact_modes": modes,
        "velocity_after_m_s": {"x": velocity_after[0], "y": velocity_after[1]},
        "angular_velocity_after_rad_s": omega_after,
        "kinetic_energy_before_j": energy_before,
        "kinetic_energy_after_j": energy_after,
        "energy_loss_j": energy_before - energy_after,
    }
