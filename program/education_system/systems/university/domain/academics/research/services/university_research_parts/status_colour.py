"""Extracted function implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def status_colour(status):
    s = (status or "").lower()
    if any(k in s for k in ["approved", "completed", "passed", "granted", "licensed"]):
        return PALETTE["success"]
    if any(k in s for k in ["submitted", "active", "filed", "under review",
                            "scheduled", "pending", "evaluating",
                            "minor corrections"]):
        return PALETTE["warn"]
    if any(k in s for k in ["rejected", "failed", "overdue", "missed",
                            "expired", "abandoned", "withdrawn",
                            "major corrections", "revisions required"]):
        return PALETTE["danger"]
    return PALETTE["muted"]
