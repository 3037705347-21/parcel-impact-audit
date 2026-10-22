"""Two-contact calculations used by the pallet landing command."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PairEvent:
    """One planar body contacting a surface at two points."""

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


def solve_pair_event(event: PairEvent) -> dict[str, object]:
    """Resolve each candidate contact independently into the report shape."""
    normal_speed_1 = event.vx_m_s * event.nx + event.vy_m_s * event.ny
    normal_speed_2 = normal_speed_1
    impulse_1 = -(1.0 + event.restitution) * event.mass_kg * min(0.0, normal_speed_1) / 2.0
    impulse_2 = -(1.0 + event.restitution) * event.mass_kg * min(0.0, normal_speed_2) / 2.0
    return {
        "event_id": event.event_id,
        "contact_normal_impulses_ns": [impulse_1, impulse_2],
        "contact_tangent_impulses_ns": [
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
        ],
        "contact_modes": ["stick", "stick"],
        "velocity_after_m_s": {
            "x": event.vx_m_s + (impulse_1 + impulse_2) * event.nx / event.mass_kg,
            "y": event.vy_m_s + (impulse_1 + impulse_2) * event.ny / event.mass_kg,
        },
        "angular_velocity_after_rad_s": event.omega_rad_s,
    }
