"""Behavior checks for the three-dimensional parcel impact report."""

from __future__ import annotations

import csv
import itertools
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest


WORKSPACE = Path(os.environ.get("IMPACT_WORKSPACE", "/workspace"))
TEST_ROOT = Path(tempfile.mkdtemp(prefix="parcel-impact-checks-"))
Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]
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
PAIR_FIELDS = [
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


def _row(
    event_id: str,
    mass: float = 2.0,
    ixx: float = 0.5,
    iyy: float = 0.55,
    izz: float = 0.6,
    ixy: float = 0.01,
    ixz: float = -0.008,
    iyz: float = 0.006,
    vx: float = -1.5,
    vy: float = 0.1,
    vz: float = -0.2,
    wx: float = 0.3,
    wy: float = -0.2,
    wz: float = 0.1,
    rx: float = 0.05,
    ry: float = -0.04,
    rz: float = 0.03,
    nx: float = 1.0,
    ny: float = 0.0,
    nz: float = 0.0,
    restitution: float = 0.3,
    friction: float = 0.5,
) -> dict[str, object]:
    """Build a complete spatial collision row."""
    return {
        "event_id": event_id,
        "mass_kg": mass,
        "ixx": ixx,
        "iyy": iyy,
        "izz": izz,
        "ixy": ixy,
        "ixz": ixz,
        "iyz": iyz,
        "vx": vx,
        "vy": vy,
        "vz": vz,
        "wx": wx,
        "wy": wy,
        "wz": wz,
        "rx": rx,
        "ry": ry,
        "rz": rz,
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "restitution": restitution,
        "friction_coefficient": friction,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write rows using the documented column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_pair_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write two-contact rows using the documented column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _run_cli(input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the workspace command without a shell."""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "impact_audit",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=WORKSPACE,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _run_pair_cli(input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the workspace two-contact command without a shell."""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "impact_audit",
            "pair",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=WORKSPACE,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _report_for(
    tmp_path: Path,
    rows: list[dict[str, object]],
    stem: str = "events",
) -> dict[str, Any]:
    """Create a batch, invoke the entry point, and load its report."""
    input_path = tmp_path / f"{stem}.csv"
    output_path = tmp_path / f"{stem}.json"
    _write_csv(input_path, rows)
    completed = _run_cli(input_path, output_path)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    return json.loads(output_path.read_text(encoding="utf-8"))


def _pair_report_for(
    tmp_path: Path,
    rows: list[dict[str, object]],
    stem: str = "landings",
) -> dict[str, Any]:
    """Create a pair batch, invoke the entry point, and load its report."""
    input_path = tmp_path / f"{stem}.csv"
    output_path = tmp_path / f"{stem}.json"
    _write_pair_csv(input_path, rows)
    completed = _run_pair_cli(input_path, output_path)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    return json.loads(output_path.read_text(encoding="utf-8"))


def _dot(a: Vector, b: Vector) -> float:
    """Return a Euclidean dot product."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vector, b: Vector) -> Vector:
    """Return a right-handed cross product."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _add(a: Vector, b: Vector) -> Vector:
    """Add two vectors."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(vector: Vector, factor: float) -> Vector:
    """Scale a vector."""
    return (vector[0] * factor, vector[1] * factor, vector[2] * factor)


def _norm(vector: Vector) -> float:
    """Return vector length."""
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: Vector) -> Vector:
    """Return a unit vector."""
    return _scale(vector, 1.0 / _norm(vector))


def _matvec(matrix: Matrix, vector: Vector) -> Vector:
    """Multiply a matrix by a vector."""
    return tuple(_dot(row, vector) for row in matrix)  # type: ignore[return-value]


def _matmul(left: Matrix, right: Matrix) -> Matrix:
    """Multiply two matrices."""
    columns = tuple(zip(*right, strict=True))
    return tuple(
        tuple(_dot(row, column) for column in columns)
        for row in left
    )  # type: ignore[return-value]


def _determinant(matrix: Matrix) -> float:
    """Return a three-by-three determinant."""
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _inverse(matrix: Matrix) -> Matrix:
    """Return a three-by-three inverse."""
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    det = _determinant(matrix)
    return (
        ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det),
        ((f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det),
        ((d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det),
    )


def _cross_matrix(vector: Vector) -> Matrix:
    """Return the matrix form of vector cross multiplication."""
    x, y, z = vector
    return ((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0))


def _basis(normal: Vector) -> tuple[Vector, Vector]:
    """Build an independent contact-plane basis."""
    reference: Vector = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
    first = _normalize(_cross(normal, reference))
    return first, _normalize(_cross(normal, first))


def _solve2(matrix: tuple[tuple[float, float], tuple[float, float]], rhs: tuple[float, float]) -> tuple[float, float]:
    """Solve an independent two-by-two system."""
    a, b = matrix[0]
    c, d = matrix[1]
    det = a * d - b * c
    return ((d * rhs[0] - b * rhs[1]) / det, (-c * rhs[0] + a * rhs[1]) / det)


def _contact_velocity(velocity: Vector, angular: Vector, arm: Vector) -> Vector:
    """Return contact velocity."""
    return _add(velocity, _cross(angular, arm))


def _apply(
    velocity: Vector,
    angular: Vector,
    impulse: Vector,
    arm: Vector,
    mass: float,
    inverse_tensor: Matrix,
) -> tuple[Vector, Vector]:
    """Apply an impulse independently."""
    return (
        _add(velocity, _scale(impulse, 1.0 / mass)),
        _add(angular, _matvec(inverse_tensor, _cross(arm, impulse))),
    )


def _reference(row: dict[str, object]) -> dict[str, Any]:
    """Solve one row independently from the stated sequential model."""
    mass = float(row["mass_kg"])
    tensor: Matrix = (
        (float(row["ixx"]), float(row["ixy"]), float(row["ixz"])),
        (float(row["ixy"]), float(row["iyy"]), float(row["iyz"])),
        (float(row["ixz"]), float(row["iyz"]), float(row["izz"])),
    )
    inverse_tensor = _inverse(tensor)
    velocity: Vector = (float(row["vx"]), float(row["vy"]), float(row["vz"]))
    angular: Vector = (float(row["wx"]), float(row["wy"]), float(row["wz"]))
    arm: Vector = (float(row["rx"]), float(row["ry"]), float(row["rz"]))
    normal: Vector = (float(row["nx"]), float(row["ny"]), float(row["nz"]))
    restitution = float(row["restitution"])
    friction = float(row["friction_coefficient"])

    cross_arm = _cross_matrix(arm)
    coupled = _matmul(_matmul(cross_arm, inverse_tensor), cross_arm)
    contact_mass: Matrix = tuple(
        tuple(
            (1.0 / mass if row_index == column_index else 0.0) - coupled[row_index][column_index]
            for column_index in range(3)
        )
        for row_index in range(3)
    )  # type: ignore[assignment]

    velocity_before = velocity
    angular_before = angular
    contact_velocity = _contact_velocity(velocity, angular, arm)
    normal_impulse = (
        -(1.0 + restitution)
        * _dot(contact_velocity, normal)
        / _dot(normal, _matvec(contact_mass, normal))
    )
    velocity, angular = _apply(
        velocity,
        angular,
        _scale(normal, normal_impulse),
        arm,
        mass,
        inverse_tensor,
    )

    contact_velocity = _contact_velocity(velocity, angular, arm)
    tangent_velocity = tuple(
        contact_velocity[index] - _dot(contact_velocity, normal) * normal[index]
        for index in range(3)
    )
    tangent_speed = _norm(tangent_velocity)
    tangent_impulse: Vector = (0.0, 0.0, 0.0)
    mode = "stick"
    if tangent_speed > 1e-15:
        first, second = _basis(normal)
        tangent_matrix = (
            (_dot(first, _matvec(contact_mass, first)), _dot(first, _matvec(contact_mass, second))),
            (_dot(second, _matvec(contact_mass, first)), _dot(second, _matvec(contact_mass, second))),
        )
        coefficient_1, coefficient_2 = _solve2(
            tangent_matrix,
            (-_dot(first, tangent_velocity), -_dot(second, tangent_velocity)),
        )
        candidate = _add(_scale(first, coefficient_1), _scale(second, coefficient_2))
        limit = friction * normal_impulse
        if _norm(candidate) <= limit + 1e-12:
            tangent_impulse = candidate
        else:
            tangent_impulse = _scale(tangent_velocity, -limit / tangent_speed)
            mode = "slide"

    velocity_after, angular_after = _apply(
        velocity,
        angular,
        tangent_impulse,
        arm,
        mass,
        inverse_tensor,
    )
    energy_before = 0.5 * mass * _dot(velocity_before, velocity_before) + 0.5 * _dot(
        angular_before, _matvec(tensor, angular_before)
    )
    energy_after = 0.5 * mass * _dot(velocity_after, velocity_after) + 0.5 * _dot(
        angular_after, _matvec(tensor, angular_after)
    )
    return {
        "event_id": str(row["event_id"]),
        "normal_impulse_ns": normal_impulse,
        "tangential_impulse_ns": {
            "x": tangent_impulse[0],
            "y": tangent_impulse[1],
            "z": tangent_impulse[2],
        },
        "contact_mode": mode,
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
        "diagnostics": {"tangent_velocity_before_friction": tangent_velocity},
    }


def _pair_row(
    event_id: str,
    mass: float = 3.0,
    inertia: float = 0.45,
    vx: float = -0.3,
    vy: float = -1.0,
    omega: float = 0.0,
    r1x: float = -0.2,
    r1y: float = -0.08,
    r2x: float = 0.2,
    r2y: float = -0.12,
    nx: float = 0.0,
    ny: float = 1.0,
    restitution: float = 0.2,
    friction: float = 0.8,
) -> dict[str, object]:
    """Build one complete two-contact landing row."""
    return {
        "event_id": event_id,
        "mass_kg": mass,
        "inertia_kg_m2": inertia,
        "vx_m_s": vx,
        "vy_m_s": vy,
        "omega_rad_s": omega,
        "r1x_m": r1x,
        "r1y_m": r1y,
        "r2x_m": r2x,
        "r2y_m": r2y,
        "nx": nx,
        "ny": ny,
        "restitution": restitution,
        "friction_coefficient": friction,
    }


def _dot2(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Return a planar dot product."""
    return a[0] * b[0] + a[1] * b[1]


def _cross2(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Return a scalar planar cross product."""
    return a[0] * b[1] - a[1] * b[0]


def _pair_velocity(
    velocity: tuple[float, float],
    omega: float,
    arm: tuple[float, float],
) -> tuple[float, float]:
    """Return two-dimensional contact velocity."""
    return (velocity[0] - omega * arm[1], velocity[1] + omega * arm[0])


def _pair_apply(
    mass: float,
    inertia: float,
    velocity: tuple[float, float],
    omega: float,
    arms: tuple[tuple[float, float], tuple[float, float]],
    impulses: tuple[float, float],
    direction: tuple[float, float],
) -> tuple[tuple[float, float], float]:
    """Apply two scalar impulses independently."""
    total = impulses[0] + impulses[1]
    velocity_after = (
        velocity[0] + total * direction[0] / mass,
        velocity[1] + total * direction[1] / mass,
    )
    torque = (
        _cross2(arms[0], (impulses[0] * direction[0], impulses[0] * direction[1]))
        + _cross2(arms[1], (impulses[1] * direction[0], impulses[1] * direction[1]))
    )
    return velocity_after, omega + torque / inertia


def _pair_normal_reference(
    row: dict[str, object],
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Enumerate admissible normal active sets independently."""
    mass = float(row["mass_kg"])
    inertia = float(row["inertia_kg_m2"])
    velocity = (float(row["vx_m_s"]), float(row["vy_m_s"]))
    omega = float(row["omega_rad_s"])
    normal = (float(row["nx"]), float(row["ny"]))
    arms = (
        (float(row["r1x_m"]), float(row["r1y_m"])),
        (float(row["r2x_m"]), float(row["r2y_m"])),
    )
    restitution = float(row["restitution"])
    pre_speeds = tuple(
        _dot2(_pair_velocity(velocity, omega, arm), normal)
        for arm in arms
    )
    approaching = [index for index, speed in enumerate(pre_speeds) if speed < 0.0]
    normal_matrix = tuple(
        tuple(
            1.0 / mass
            + _cross2(arms[i], normal) * _cross2(arms[j], normal) / inertia
            for j in range(2)
        )
        for i in range(2)
    )
    candidates: list[tuple[float, tuple[float, float], tuple[float, float], float]] = []
    for size in (1, 2):
        for subset in itertools.combinations(approaching, size):
            impulses = [0.0, 0.0]
            if len(subset) == 1:
                index = subset[0]
                impulses[index] = (
                    -(1.0 + restitution) * pre_speeds[index] / normal_matrix[index][index]
                )
            else:
                coefficients = _solve2(
                    normal_matrix,
                    (
                        -(1.0 + restitution) * pre_speeds[0],
                        -(1.0 + restitution) * pre_speeds[1],
                    ),
                )
                impulses[0], impulses[1] = coefficients
            if any(impulses[index] < -1e-10 for index in subset):
                continue
            moments = (max(0.0, impulses[0]), max(0.0, impulses[1]))
            velocity_after, omega_after = _pair_apply(
                mass, inertia, velocity, omega, arms, moments, normal
            )
            post_speeds = tuple(
                _dot2(_pair_velocity(velocity_after, omega_after, arm), normal)
                for arm in arms
            )
            inactive = {0, 1} - set(subset)
            if any(post_speeds[index] < -1e-9 for index in inactive):
                continue
            if all(
                abs(post_speeds[index] + restitution * pre_speeds[index]) <= 1e-8
                for index in subset
            ):
                candidates.append((sum(moments), moments, velocity_after, omega_after))
    return min(candidates, key=lambda item: item[0])[1:]


def _pair_qp_reference(
    matrix: tuple[tuple[float, float], tuple[float, float]],
    linear: tuple[float, float],
    limits: tuple[float, float],
    count: int,
) -> tuple[float, ...]:
    """Enumerate friction bounds for a small convex quadratic program."""
    options = tuple(
        (0,) if limits[index] <= 1e-15 else (-1, 0, 1)
        for index in range(count)
    )
    best: tuple[float, tuple[float, ...]] | None = None
    for statuses in itertools.product(*options):
        values = [0.0] * count
        free = [index for index, status in enumerate(statuses) if status == 0]
        for index, status in enumerate(statuses):
            if status == -1:
                values[index] = -limits[index]
            elif status == 1:
                values[index] = limits[index]
        if free:
            rhs = []
            for row in free:
                fixed = sum(
                    matrix[row][column] * values[column]
                    for column in range(count)
                    if column not in free
                )
                rhs.append(-(linear[row] + fixed))
            if len(free) == 1:
                values[free[0]] = rhs[0] / matrix[free[0]][free[0]]
            else:
                solved = _solve2(
                    (
                        (matrix[free[0]][free[0]], matrix[free[0]][free[1]]),
                        (matrix[free[1]][free[0]], matrix[free[1]][free[1]]),
                    ),
                    (rhs[0], rhs[1]),
                )
                values[free[0]], values[free[1]] = solved
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
        if any(
            (statuses[index] == -1 and gradient[index] < -1e-8)
            or (statuses[index] == 1 and gradient[index] > 1e-8)
            for index in range(count)
        ):
            continue
        objective = 0.5 * sum(
            values[row] * matrix[row][column] * values[column]
            for row in range(count)
            for column in range(count)
        ) + sum(values[index] * linear[index] for index in range(count))
        if best is None or objective < best[0] - 1e-12:
            best = (objective, tuple(values))
    return best[1]


def _pair_reference(row: dict[str, object]) -> dict[str, Any]:
    """Solve one two-contact event independently."""
    mass = float(row["mass_kg"])
    inertia = float(row["inertia_kg_m2"])
    velocity = (float(row["vx_m_s"]), float(row["vy_m_s"]))
    omega = float(row["omega_rad_s"])
    normal = (float(row["nx"]), float(row["ny"]))
    tangent = (-normal[1], normal[0])
    arms = (
        (float(row["r1x_m"]), float(row["r1y_m"])),
        (float(row["r2x_m"]), float(row["r2y_m"])),
    )
    friction = float(row["friction_coefficient"])
    normal_impulses, velocity_after_normal, omega_after_normal = _pair_normal_reference(row)
    active = [index for index, value in enumerate(normal_impulses) if value > 1e-10]
    tangent_matrix = tuple(
        tuple(
            1.0 / mass
            + _cross2(arms[i], tangent) * _cross2(arms[j], tangent) / inertia
            for j in range(2)
        )
        for i in range(2)
    )
    tangent_speeds = tuple(
        _dot2(
            _pair_velocity(velocity_after_normal, omega_after_normal, arms[index]),
            tangent,
        )
        for index in active
    )
    reduced = tuple(tuple(tangent_matrix[row][column] for column in active) for row in active)
    limits = tuple(friction * normal_impulses[index] for index in active)
    friction_values = _pair_qp_reference(reduced, tangent_speeds, limits, len(active))
    totals = [0.0, 0.0]
    tangent_world = [(0.0, 0.0), (0.0, 0.0)]
    for slot, index in enumerate(active):
        totals[index] = friction_values[slot]
        tangent_world[index] = (
            friction_values[slot] * tangent[0],
            friction_values[slot] * tangent[1],
        )
    velocity_after, omega_after = _pair_apply(
        mass, inertia, velocity_after_normal, omega_after_normal, arms, tuple(totals), tangent
    )
    modes = ["inactive", "inactive"]
    for slot, index in enumerate(active):
        value = abs(friction_values[slot])
        modes[index] = (
            "slide"
            if limits[slot] <= 1e-15 or value >= limits[slot] - 1e-8
            else "stick"
        )
    energy_before = 0.5 * mass * _dot2(velocity, velocity) + 0.5 * inertia * omega * omega
    energy_after = (
        0.5 * mass * _dot2(velocity_after, velocity_after)
        + 0.5 * inertia * omega_after * omega_after
    )
    return {
        "event_id": str(row["event_id"]),
        "contact_normal_impulses_ns": list(normal_impulses),
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
        "diagnostics": {"tangent_speeds_after_normal": tangent_speeds},
    }


def test_c1_centered_spherical_impulse():
    """A centered spherical impact uses only mass and restitution."""
    row = _row(
        "centered",
        ixx=0.6,
        iyy=0.6,
        izz=0.6,
        ixy=0.0,
        ixz=0.0,
        iyz=0.0,
        vx=-3.0,
        vy=0.0,
        vz=0.0,
        wx=0.0,
        wy=0.0,
        wz=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        restitution=0.5,
        friction=0.0,
    )
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c1-a", [row])
    event = report["events"][0]
    assert event["normal_impulse_ns"] == pytest.approx(9.0, abs=1e-10)
    assert event["velocity_after_m_s"]["x"] == pytest.approx(1.5, abs=1e-10)


def test_c1_offset_matches_scalar_limit():
    """The spatial contact matrix reproduces the scalar-inertia offset result."""
    row = _row(
        "offset",
        ixx=0.5,
        iyy=0.5,
        izz=0.5,
        ixy=0.0,
        ixz=0.0,
        iyz=0.0,
        vx=-3.0,
        vy=0.0,
        vz=0.0,
        wx=0.0,
        wy=0.0,
        wz=0.0,
        rx=0.0,
        ry=0.3,
        rz=0.0,
        restitution=0.5,
        friction=0.0,
    )
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c1-b", [row])
    event = report["events"][0]
    assert event["normal_impulse_ns"] == pytest.approx(4.5 / 0.68, rel=1e-10)


def test_c1_inertia_cross_terms_change_normal_impulse():
    """A non-diagonal inertia tensor changes the effective normal mass."""
    row = _row(
        "cross-inertia",
        ixx=0.8,
        iyy=0.65,
        izz=0.9,
        ixy=0.12,
        ixz=-0.07,
        iyz=0.04,
        vx=-1.6,
        vy=0.5,
        vz=-0.4,
        wx=0.6,
        wy=-0.4,
        wz=0.3,
        rx=0.12,
        ry=-0.08,
        rz=0.1,
        nx=0.48,
        ny=-0.6,
        nz=0.64,
        restitution=0.35,
        friction=0.0,
    )
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c1-c", [row])
    diagonal = {**row, "ixy": 0.0, "ixz": 0.0, "iyz": 0.0}
    expected = _reference(row)
    diagonal_expected = _reference(diagonal)
    assert report["events"][0]["normal_impulse_ns"] == pytest.approx(
        expected["normal_impulse_ns"], rel=1e-10
    )
    assert report["events"][0]["normal_impulse_ns"] != pytest.approx(
        diagonal_expected["normal_impulse_ns"], rel=1e-7
    )


def test_c1_oblique_contact_updates_full_spin():
    """An oblique contact produces the expected velocity and angular vector."""
    row = _row(
        "oblique",
        ixx=0.72,
        iyy=0.61,
        izz=0.84,
        ixy=0.08,
        ixz=-0.05,
        iyz=0.03,
        vx=-1.1,
        vy=-1.4,
        vz=0.8,
        wx=0.5,
        wy=-0.3,
        wz=0.2,
        rx=-0.09,
        ry=0.11,
        rz=0.07,
        nx=0.6,
        ny=0.8,
        nz=0.0,
        restitution=0.2,
        friction=0.0,
    )
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c1-d", [row])
    event = report["events"][0]
    expected = _reference(row)
    assert event["velocity_after_m_s"] == pytest.approx(
        expected["velocity_after_m_s"], rel=1e-10
    )
    assert event["angular_velocity_after_rad_s"] == pytest.approx(
        expected["angular_velocity_after_rad_s"], rel=1e-10
    )


def test_c2_normal_aligned_arm_has_no_tangent_impulse():
    """A normal impulse parallel to the arm creates no tangent demand."""
    row = _row(
        "pure-normal",
        vx=-1.2,
        vy=-1.6,
        vz=0.0,
        wx=0.0,
        wy=0.0,
        wz=0.0,
        rx=0.06,
        ry=0.08,
        rz=0.0,
        nx=0.6,
        ny=0.8,
        nz=0.0,
        friction=0.8,
    )
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c2-a", [row])
    event = report["events"][0]
    assert event["contact_mode"] == "stick"
    assert event["tangential_impulse_ns"] == pytest.approx(
        {"x": 0.0, "y": 0.0, "z": 0.0}, abs=1e-12
    )


def test_c2_stick_cancels_contact_tangent_velocity():
    """A tangential demand inside the friction cone removes contact slip."""
    row = _row("stick", restitution=0.25, friction=0.95)
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c2-b", [row])
    event = report["events"][0]
    velocity: Vector = (
        event["velocity_after_m_s"]["x"],
        event["velocity_after_m_s"]["y"],
        event["velocity_after_m_s"]["z"],
    )
    angular: Vector = (
        event["angular_velocity_after_rad_s"]["x"],
        event["angular_velocity_after_rad_s"]["y"],
        event["angular_velocity_after_rad_s"]["z"],
    )
    arm: Vector = (float(row["rx"]), float(row["ry"]), float(row["rz"]))
    normal: Vector = (float(row["nx"]), float(row["ny"]), float(row["nz"]))
    contact_velocity = _contact_velocity(velocity, angular, arm)
    tangent_velocity = tuple(
        contact_velocity[index] - _dot(contact_velocity, normal) * normal[index]
        for index in range(3)
    )
    assert event["contact_mode"] == "stick"
    assert _norm(tangent_velocity) == pytest.approx(0.0, abs=1e-9)


def test_c2_slide_obeys_vector_friction_cone():
    """A high tangent demand has the full signed Coulomb magnitude."""
    row = _row("slide", vx=-1.0, vy=2.6, vz=1.4, friction=0.02)
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c2-c", [row])
    event = report["events"][0]
    impulse: Vector = (
        event["tangential_impulse_ns"]["x"],
        event["tangential_impulse_ns"]["y"],
        event["tangential_impulse_ns"]["z"],
    )
    assert event["contact_mode"] == "slide"
    assert _norm(impulse) == pytest.approx(0.02 * event["normal_impulse_ns"], rel=1e-10)


def test_c2_friction_changes_all_spatial_angular_components():
    """Tangential impulse acts through the full inverse inertia tensor."""
    row = _row(
        "spatial-spin",
        ixx=0.8,
        iyy=0.7,
        izz=0.95,
        ixy=0.11,
        ixz=-0.06,
        iyz=0.05,
        vx=-1.2,
        vy=1.1,
        vz=-0.6,
        wx=0.7,
        wy=-0.4,
        wz=0.3,
        rx=0.1,
        ry=-0.07,
        rz=0.08,
        nx=0.48,
        ny=-0.6,
        nz=0.64,
        friction=0.16,
    )
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c2-d", [row])
    event = report["events"][0]
    expected = _reference(row)
    assert event["tangential_impulse_ns"] == pytest.approx(
        expected["tangential_impulse_ns"], rel=1e-10
    )
    assert event["angular_velocity_after_rad_s"] == pytest.approx(
        expected["angular_velocity_after_rad_s"], rel=1e-10
    )
    assert event["angular_velocity_after_rad_s"]["x"] != pytest.approx(0.7, abs=1e-5)
    assert event["angular_velocity_after_rad_s"]["y"] != pytest.approx(-0.4, abs=1e-5)
    assert event["angular_velocity_after_rad_s"]["z"] != pytest.approx(0.3, abs=1e-5)


def test_c2_tangent_matrix_retains_cross_coupling():
    """An anisotropic tangent system produces a vector not parallel to slip."""
    row = _row(
        "coupled-tangent",
        ixx=0.56,
        iyy=0.73,
        izz=0.91,
        ixy=0.14,
        ixz=-0.09,
        iyz=0.08,
        vx=-1.3,
        vy=0.45,
        vz=-0.35,
        wx=0.8,
        wy=-0.35,
        wz=0.55,
        rx=0.13,
        ry=-0.09,
        rz=0.11,
        nx=0.36,
        ny=-0.48,
        nz=0.8,
        friction=0.95,
    )
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c2-e", [row])
    event = report["events"][0]
    expected = _reference(row)
    impulse: Vector = (
        event["tangential_impulse_ns"]["x"],
        event["tangential_impulse_ns"]["y"],
        event["tangential_impulse_ns"]["z"],
    )
    tangent_velocity: Vector = expected["diagnostics"]["tangent_velocity_before_friction"]
    assert event["contact_mode"] == "stick"
    assert event["tangential_impulse_ns"] == pytest.approx(
        expected["tangential_impulse_ns"], rel=1e-10
    )
    assert _norm(_cross(impulse, tangent_velocity)) > 1e-5


def test_c3_energy_uses_full_inertia_tensor():
    """Kinetic energy includes the complete rotational quadratic form."""
    row = _row(
        "energy",
        ixx=0.75,
        iyy=0.62,
        izz=0.88,
        ixy=0.07,
        ixz=-0.04,
        iyz=0.03,
        friction=0.42,
    )
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c3-a", [row])
    event = report["events"][0]
    expected = _reference(row)
    assert event["kinetic_energy_before_j"] == pytest.approx(
        expected["kinetic_energy_before_j"], rel=1e-10
    )
    assert event["kinetic_energy_after_j"] == pytest.approx(
        expected["kinetic_energy_after_j"], rel=1e-10
    )
    assert event["energy_loss_j"] == pytest.approx(
        expected["energy_loss_j"], rel=1e-10
    )


def test_c3_summary_aggregates_modes_and_energy():
    """Summary counts contact modes and sums per-event energy loss."""
    stick = _row("stick-summary", restitution=0.25, friction=0.95)
    slide = _row("slide-summary", vx=-1.0, vy=2.6, vz=1.4, friction=0.02)
    report = _report_for(TEST_ROOT / "parcel-impact-3d-c3-b", [stick, slide])
    expected_loss = sum(
        float(_reference(row)["energy_loss_j"]) for row in [stick, slide]
    )
    assert report["summary"]["event_count"] == 2
    assert report["summary"]["stick_count"] == 1
    assert report["summary"]["slide_count"] == 1
    assert report["summary"]["total_energy_loss_j"] == pytest.approx(
        expected_loss, rel=1e-10
    )
    assert report["summary"]["maximum_energy_gain_j"] == pytest.approx(0.0, abs=1e-10)


def test_c4_nonunit_normal_rejected_without_output():
    """A non-unit contact normal rejects the complete batch."""
    row = _row("bad-normal", nx=1.2)
    input_path = TEST_ROOT / "parcel-impact-3d-c4-a.csv"
    output_path = TEST_ROOT / "parcel-impact-3d-c4-a.json"
    output_path.unlink(missing_ok=True)
    _write_csv(input_path, [row])
    completed = _run_cli(input_path, output_path)
    assert completed.returncode != 0
    assert not output_path.exists()


def test_c4_nonpositive_inertia_rejected():
    """A non-positive-definite inertia tensor fails before output."""
    row = _row("bad-inertia", ixx=0.5, iyy=0.5, ixy=0.8)
    input_path = TEST_ROOT / "parcel-impact-3d-c4-b.csv"
    output_path = TEST_ROOT / "parcel-impact-3d-c4-b.json"
    output_path.unlink(missing_ok=True)
    _write_csv(input_path, [row])
    completed = _run_cli(input_path, output_path)
    assert completed.returncode != 0
    assert not output_path.exists()


def test_c4_separating_contact_preserves_existing_output():
    """A separating contact does not replace an existing report."""
    row = _row("separating", vx=2.0)
    input_path = TEST_ROOT / "parcel-impact-3d-c4-c.csv"
    output_path = TEST_ROOT / "parcel-impact-3d-c4-c.json"
    _write_csv(input_path, [row])
    output_path.write_text("existing-report\n", encoding="utf-8")
    completed = _run_cli(input_path, output_path)
    assert completed.returncode != 0
    assert output_path.read_text(encoding="utf-8") == "existing-report\n"


def test_c4_missing_columns_and_nonfinite_values_rejected():
    """Incomplete schemas and non-finite values both fail cleanly."""
    missing_input = TEST_ROOT / "parcel-impact-3d-c4-d.csv"
    missing_output = TEST_ROOT / "parcel-impact-3d-c4-d.json"
    missing_input.write_text("event_id,mass_kg\nmissing,2\n", encoding="utf-8")
    missing_completed = _run_cli(missing_input, missing_output)

    row = _row("nan")
    nan_input = TEST_ROOT / "parcel-impact-3d-c4-e.csv"
    nan_output = TEST_ROOT / "parcel-impact-3d-c4-e.json"
    _write_csv(nan_input, [row])
    text = nan_input.read_text(encoding="utf-8").replace("-1.5", "nan", 1)
    nan_input.write_text(text, encoding="utf-8")
    nan_completed = _run_cli(nan_input, nan_output)

    assert missing_completed.returncode != 0
    assert nan_completed.returncode != 0
    assert not missing_output.exists()
    assert not nan_output.exists()


def test_c5_both_contact_normals_are_coupled():
    """Two approaching contacts use the full nonnegative normal mass matrix."""
    row = _pair_row("coupled-normal", restitution=0.2, friction=0.8)
    report = _pair_report_for(TEST_ROOT / "parcel-pair-c5-a", [row])
    event = report["events"][0]
    expected = _pair_reference(row)
    assert event["contact_normal_impulses_ns"] == pytest.approx(
        expected["contact_normal_impulses_ns"], rel=1e-10
    )
    assert min(event["contact_normal_impulses_ns"]) > 0.0
    assert "inactive" not in event["contact_modes"]


def test_c5_one_sided_contact_sets_other_impulse_to_zero():
    """A separating corner leaves the other contact to carry the impact."""
    row = _pair_row(
        "one-sided",
        vx=0.0,
        vy=-1.0,
        omega=10.0,
        friction=0.8,
    )
    report = _pair_report_for(TEST_ROOT / "parcel-pair-c5-b", [row])
    event = report["events"][0]
    expected = _pair_reference(row)
    assert event["contact_normal_impulses_ns"] == pytest.approx(
        expected["contact_normal_impulses_ns"], rel=1e-10
    )
    assert event["contact_modes"].count("inactive") == 1
    assert 0.0 in event["contact_normal_impulses_ns"]


def test_c5_two_point_stick_uses_joint_tangent_matrix():
    """Both sticking contacts are solved together rather than independently."""
    row = _pair_row(
        "two-stick",
        vx=0.0,
        vy=-1.0,
        omega=0.02,
        friction=0.95,
    )
    report = _pair_report_for(TEST_ROOT / "parcel-pair-c5-c", [row])
    event = report["events"][0]
    expected = _pair_reference(row)
    assert event["contact_modes"] == ["stick", "stick"]
    assert event["contact_tangent_impulses_ns"] == pytest.approx(
        expected["contact_tangent_impulses_ns"], rel=1e-10
    )


def test_c5_two_slide_impulses_obey_individual_box_limits():
    """A sliding contact pair respects each normal-impulse friction cap."""
    row = _pair_row(
        "two-slide",
        vx=-0.3,
        vy=-1.0,
        omega=0.0,
        friction=0.05,
    )
    report = _pair_report_for(TEST_ROOT / "parcel-pair-c5-d", [row])
    event = report["events"][0]
    limits = [
        0.05 * impulse for impulse in event["contact_normal_impulses_ns"]
    ]
    magnitudes = [
        math.hypot(impulse["x"], impulse["y"])
        for impulse in event["contact_tangent_impulses_ns"]
    ]
    assert event["contact_modes"] == ["slide", "slide"]
    assert magnitudes == pytest.approx(limits, rel=1e-10)


def test_c5_pair_energy_and_angular_state_match_reference():
    """Two-contact angular recoil and energy use the combined impulse state."""
    row = _pair_row(
        "pair-energy",
        mass=4.2,
        inertia=0.73,
        vx=-0.8,
        vy=-1.7,
        omega=0.6,
        r1x=-0.19,
        r1y=-0.03,
        r2x=0.24,
        r2y=-0.11,
        friction=0.34,
    )
    report = _pair_report_for(TEST_ROOT / "parcel-pair-c5-e", [row])
    event = report["events"][0]
    expected = _pair_reference(row)
    assert event["angular_velocity_after_rad_s"] == pytest.approx(
        expected["angular_velocity_after_rad_s"], rel=1e-10
    )
    assert event["kinetic_energy_before_j"] == pytest.approx(
        expected["kinetic_energy_before_j"], rel=1e-10
    )
    assert event["kinetic_energy_after_j"] == pytest.approx(
        expected["kinetic_energy_after_j"], rel=1e-10
    )
    assert event["energy_loss_j"] == pytest.approx(
        expected["energy_loss_j"], rel=1e-10
    )


def test_c5_pair_rejects_no_approach_and_coincident_points():
    """No approaching corner and duplicate contact points both fail cleanly."""
    no_approach = _pair_row("no-approach", vx=0.0, vy=1.0, omega=0.0)
    coincident = _pair_row(
        "coincident",
        r1x=0.1,
        r1y=-0.1,
        r2x=0.1,
        r2y=-0.1,
    )
    first_input = TEST_ROOT / "parcel-pair-c5-f1.csv"
    first_output = TEST_ROOT / "parcel-pair-c5-f1.json"
    second_input = TEST_ROOT / "parcel-pair-c5-f2.csv"
    second_output = TEST_ROOT / "parcel-pair-c5-f2.json"
    _write_pair_csv(first_input, [no_approach])
    _write_pair_csv(second_input, [coincident])
    second_output.write_text("existing-pair-report\n", encoding="utf-8")
    first_completed = _run_pair_cli(first_input, first_output)
    second_completed = _run_pair_cli(second_input, second_output)
    assert first_completed.returncode != 0
    assert second_completed.returncode != 0
    assert not first_output.exists()
    assert second_output.read_text(encoding="utf-8") == "existing-pair-report\n"


def test_e2e_pair_batch_report():
    """The bundled two-contact batch yields ordered events and summaries."""
    input_path = WORKSPACE / "data" / "pallet_landings.csv"
    output_path = TEST_ROOT / "parcel-pair-e2e.json"
    completed = _run_pair_cli(input_path, output_path)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    with input_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected_events = [_pair_reference(row) for row in rows]
    modes = [mode for event in expected_events for mode in event["contact_modes"]]
    expected_loss = sum(float(event["energy_loss_j"]) for event in expected_events)
    assert len(report["events"]) == 8
    assert [event["event_id"] for event in report["events"]] == [
        str(row["event_id"]) for row in rows
    ]
    assert report["summary"]["event_count"] == 8
    assert report["summary"]["stick_count"] == modes.count("stick")
    assert report["summary"]["slide_count"] == modes.count("slide")
    assert report["summary"]["inactive_count"] == modes.count("inactive")
    assert report["summary"]["total_energy_loss_j"] == pytest.approx(
        expected_loss, rel=1e-10
    )
    assert report["events"][0]["contact_normal_impulses_ns"] == pytest.approx(
        expected_events[0]["contact_normal_impulses_ns"], rel=1e-10
    )


def test_e2e_sample_batch_report():
    """The bundled simulated batch yields twelve ordered spatial results."""
    input_path = WORKSPACE / "data" / "impact_events.csv"
    output_path = TEST_ROOT / "parcel-impact-3d-e2e.json"
    completed = _run_cli(input_path, output_path)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))

    with input_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected_events = [_reference(row) for row in rows]
    expected_loss = sum(float(event["energy_loss_j"]) for event in expected_events)
    expected_sticks = sum(event["contact_mode"] == "stick" for event in expected_events)
    expected_slides = sum(event["contact_mode"] == "slide" for event in expected_events)

    assert len(report["events"]) == 12
    assert [event["event_id"] for event in report["events"]] == [
        str(row["event_id"]) for row in rows
    ]
    assert report["summary"]["event_count"] == 12
    assert report["summary"]["stick_count"] == expected_sticks
    assert report["summary"]["slide_count"] == expected_slides
    assert report["summary"]["total_energy_loss_j"] == pytest.approx(
        expected_loss, rel=1e-10
    )
    first_expected = expected_events[0]
    assert report["events"][0]["normal_impulse_ns"] == pytest.approx(
        first_expected["normal_impulse_ns"], rel=1e-10
    )
    assert report["events"][0]["tangential_impulse_ns"] == pytest.approx(
        first_expected["tangential_impulse_ns"], rel=1e-10
    )
