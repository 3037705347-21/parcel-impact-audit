"""Experiment variant that computes physics without admission gating."""

from __future__ import annotations

from . import physics_model


physics_model.validate_event = lambda event: None
ImpactEvent = physics_model.ImpactEvent
solve_event = physics_model.solve_event
