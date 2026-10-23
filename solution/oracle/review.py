"""Cross-run review ledger for repeated batch decisions."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


VALID_OUTCOMES = {"rejected", "released"}


def _load(history_path: Path) -> list[dict[str, str]]:
    """Load an append-only review history."""
    if not history_path.exists():
        return []
    data = json.loads(history_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("review history must be an array")
    return data


def _write(history_path: Path, entries: list[dict[str, str]]) -> None:
    """Write the ledger atomically."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{history_path.name}.",
        suffix=".tmp",
        dir=history_path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(entries, ensure_ascii=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, history_path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def audit(history_path, batch_id: str, outcome: str, run_id: str | None = None) -> dict[str, object]:
    """Append one review decision and return the current net surface."""
    path = Path(history_path)
    if outcome not in VALID_OUTCOMES:
        raise ValueError("outcome must be rejected or released")
    entries = _load(path)
    entries.append(
        {
            "batch_id": batch_id,
            "outcome": outcome,
            "run_id": run_id or f"run-{len(entries) + 1}",
        }
    )
    _write(path, entries)
    return surface(path)


def surface(history_path) -> dict[str, object]:
    """Return latest state per batch and net decision counts."""
    latest: dict[str, str] = {}
    for entry in _load(Path(history_path)):
        if not isinstance(entry, dict):
            raise ValueError("review history entries must be objects")
        batch_id = entry.get("batch_id")
        outcome = entry.get("outcome")
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("review history batch_id is invalid")
        if outcome not in VALID_OUTCOMES:
            raise ValueError("review history outcome is invalid")
        latest[batch_id] = outcome
    return {
        "latest_state": next(reversed(latest.values())) if latest else None,
        "released_count": sum(value == "released" for value in latest.values()),
        "rejected_count": sum(value == "rejected" for value in latest.values()),
        "batch_count": len(latest),
    }
