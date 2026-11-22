"""Sidecar JSON storage and pipeline helpers for the Sixth Form Admissions GUI.

Split out of ``admissions_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

from pathlib import Path

from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
)


# ── Sidecar JSON storage ──────────────────────────────────────────
# Small bits of GUI-only state (interview rooms, slot caps, saved views)
# live next to the admissions DB rather than in the schema.

def _sidecar_path(name: str) -> "Path":
    from pathlib import Path
    return Path(data.DB_PATH).parent / name


def _load_json(name: str, default):
    import json
    p = _sidecar_path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a corrupt sidecar shouldn't break the GUI
        return default


def _store_json(name: str, obj) -> None:
    import json
    _sidecar_path(name).write_text(json.dumps(obj, indent=2), encoding="utf-8")


ROOMS_FILE = "admissions_interview_rooms.json"
CONFIG_FILE = "admissions_config.json"
DEFAULT_SLOT_CAP = 8

# Required document types for a complete applicant file (item 42).
REQUIRED_DOCS = ("Personal Statement", "Reference Letter", "Transcript")

# Rough probability that an applicant in a given open stage eventually
# enrols — feeds the pipeline forecast (item 34). Heuristic, tunable.
_ENROL_PROB = {
    "Submitted": 0.15,
    "Under Review": 0.25,
    "Interview Scheduled": 0.40,
    "Interviewed": 0.55,
    "Offer Made": 0.70,
    "Waitlisted": 0.20,
    "Offer Accepted": 0.95,
}


def _forecast_enrolment(applicants: list[Applicant]) -> dict:
    """Projected enrolments = already enrolled + expected from the pipeline."""
    enrolled = sum(1 for a in applicants if a.status == "Enrolled")
    expected = 0.0
    contributing = 0
    for a in applicants:
        p = _ENROL_PROB.get(a.status)
        if p:
            expected += p
            contributing += 1
    return {
        "enrolled": enrolled,
        "expected_additional": round(expected, 1),
        "projected_total": round(enrolled + expected),
        "in_pipeline": contributing,
    }


def _merge_ics(applicant_ids: list[str]) -> tuple[str, int]:
    """Combine each applicant's single-event calendar into one VCALENDAR."""
    events: list[str] = []
    for aid in applicant_ids:
        try:
            cal = data.interview_to_ics(aid)
        except Exception:  # noqa: BLE001 — skip applicants without an interview
            continue
        start = cal.find("BEGIN:VEVENT")
        end = cal.find("END:VEVENT")
        if start != -1 and end != -1:
            events.append(cal[start:end + len("END:VEVENT")])
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//SixthForm//Admissions//EN", *events, "END:VCALENDAR"])
    return body + "\r\n", len(events)


def _scaled(values: list[float], size: int) -> list[int]:
    """Scale values to pixel lengths in [0, size] against their own max."""
    top = max(values, default=0)
    return [int(round(size * v / top)) if top else 0 for v in values]
