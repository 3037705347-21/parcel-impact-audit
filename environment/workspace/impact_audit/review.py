"""Cross-run review ledger for repeated batch decisions."""

from __future__ import annotations


def audit(history_path, batch_id: str, outcome: str, run_id: str | None = None):
    """Append one review decision; the workspace version is not implemented."""
    raise NotImplementedError("review ledger is not implemented")


def surface(history_path):
    """Return the latest decision counts; the workspace version is not implemented."""
    raise NotImplementedError("review ledger is not implemented")
