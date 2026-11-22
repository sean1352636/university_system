"""Admissions reporting, exports and letter text.

Split out of :mod:`admissions` (file-size limit): the analytics behind
the Summary/Analytics pages, CSV import/export, the GDPR subject-access
export, the offer letter and status e-mail text, and the GCSE concern
check. Everything here reads applicants through :mod:`admissions`, so the
same ``admissions`` capability applies.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from typing import Any

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions.admissions import (
    OPEN_STATUSES,
    SOURCES,
    STATUSES,
    Applicant,
    Summary,
    ValidationError,
    _connect,
    create_applicant,
    get_applicant,
    get_interview_score,
    init_db,
    list_applicants,
    list_documents,
    list_events,
    list_notes,
    list_programme_choices,
)

logger = logging.getLogger(__name__)


# ── GCSE-vs-conditions heuristic (item 14) ────────────────────────

#: A grade in offer conditions: "grade 6", "at 5", "6+", "6 or above",
#: "5 in Maths". A bare count such as "5 GCSEs" is not a grade.
_REQUIRED_GRADE_RE = re.compile(
    r"\b(?:grade|grades|at|of)\s+([1-9])\b"
    r"|\b([1-9])\s*(?:\+|or\s+(?:above|higher|better)|in\b)",
    re.IGNORECASE)


def gcse_concern(predicted: str | None,
                  conditions: str | None) -> str | None:
    """Best-effort flag when predicted GCSEs look below offer conditions.

    Takes the highest grade the conditions ask for (only numbers written
    as grades — "grade 6", "6+", "5 in Maths" — not counts like "5
    GCSEs") and checks the predicted subject grades (read as "Subject
    grade" pairs, 9–1 only) clear it. Returns a warning, or None when
    nothing obvious is amiss or the text can't be read.
    """
    if not predicted or not conditions:
        return None
    from education_system.systems.sixth_form.domain.admissions import (
        entry_requirements as _er,
    )
    req = [int(a or b) for a, b in _REQUIRED_GRADE_RE.findall(conditions)]
    pred = [(subj, int(g)) for subj, g in _er.parse_gcse_text(predicted)
            if g.isdigit() and 1 <= int(g) <= 9]
    if not req or not pred:
        return None
    needed = max(req)
    below = sorted(f"{subj} {g}" for subj, g in pred if g < needed)
    if below:
        return (f"Predicted grades below the highest required grade "
                f"({needed}) in the offer conditions: {', '.join(below)}.")
    return None


# ── Analytics (items 41–45) ───────────────────────────────────────

_HAPPY_PATH: tuple[str, ...] = (
    "Submitted", "Under Review", "Interview Scheduled",
    "Interviewed", "Offer Made", "Offer Accepted", "Enrolled",
)


def funnel() -> list[tuple[str, int]]:
    """Count applicants who *reached* each happy-path stage, using the
    transition events plus current status (monotonic)."""
    init_db()
    idx = {s: i for i, s in enumerate(_HAPPY_PATH)}
    reached_counts = [0] * len(_HAPPY_PATH)
    with _connect() as conn:
        events_by = {}
        for e in conn.execute(
                "SELECT applicant_id, detail FROM admissions_events "
                "WHERE detail LIKE 'Status:%'"):
            events_by.setdefault(e["applicant_id"], []).append(e["detail"])
    for a in list_applicants():
        max_i = idx.get(a.status, -1)
        for detail in events_by.get(a.applicant_id, []):
            tgt = detail.split("→")[-1].strip()
            if tgt in idx:
                max_i = max(max_i, idx[tgt])
        # Everyone was at least Submitted.
        max_i = max(max_i, 0)
        for i in range(max_i + 1):
            reached_counts[i] += 1
    return list(zip(_HAPPY_PATH, reached_counts))


def source_effectiveness() -> list[dict[str, Any]]:
    rows = list_applicants()
    out = []
    for src in SOURCES:
        sub = [a for a in rows if a.application_source == src]
        if not sub:
            continue
        enrolled = sum(1 for a in sub if a.status == "Enrolled")
        offers = sum(1 for a in sub if a.status in (
            "Offer Made", "Offer Accepted", "Offer Declined", "Enrolled"))
        out.append({
            "source": src, "total": len(sub), "offers": offers,
            "enrolled": enrolled,
            "conversion": round(100 * enrolled / len(sub), 1),
        })
    return sorted(out, key=lambda d: -d["conversion"])


def time_to_decision_stats() -> dict[str, Any]:
    days = []
    for a in list_applicants():
        if a.decision_date and a.submitted_at:
            d0 = _try_date(a.submitted_at)
            d1 = _try_date(a.decision_date)
            if d0 and d1 and d1 >= d0:
                days.append((d1 - d0).days)
    if not days:
        return {"count": 0, "avg": None, "median": None,
                "min": None, "max": None}
    days.sort()
    n = len(days)
    median = (days[n // 2] if n % 2 else
              (days[n // 2 - 1] + days[n // 2]) / 2)
    return {"count": n, "avg": round(sum(days) / n, 1),
            "median": median, "min": days[0], "max": days[-1]}


def applications_by_week() -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for a in list_applicants():
        d = _try_date(a.submitted_at)
        if d is None:
            continue
        iso = d.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items())


def subject_demand() -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for a in list_applicants():
        for s in a.subjects:
            counts[s] = counts.get(s, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def _try_date(value: str | None) -> "_dt.date | None":
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


# ── CSV import / export (items 47, 48) ────────────────────────────

_CSV_FIELDS = (
    "applicant_id", "first_name", "last_name", "dob", "email", "phone",
    "address", "previous_school", "predicted_gcses",
    "subject_1", "subject_2", "subject_3", "reference_name",
    "reference_contact", "application_source", "submitted_at", "status",
    "offer_type", "offer_conditions", "interview_date", "interviewer",
    "decision_by", "decision_date", "decision_reason", "reference_status",
)


def export_csv(path: str, applicants: list[Applicant] | None = None) -> int:
    import csv
    _guard.require("exporting applicants")
    rows = applicants if applicants is not None else list_applicants()
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        w.writeheader()
        for a in rows:
            w.writerow({f: getattr(a, f, "") or "" for f in _CSV_FIELDS})
    logger.info("Exported %d applicants to %s", len(rows), path)
    return len(rows)


def import_csv(path: str) -> tuple[int, list[str]]:
    """Create applicants from a CSV. Returns (created_count, errors)."""
    import csv
    init_db()
    created, errors = 0, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            try:
                payload = {k: (row.get(k) or "").strip()
                           for k in _CSV_FIELDS if k != "applicant_id"}
                if not payload.get("submitted_at"):
                    payload["submitted_at"] = _dt.date.today().isoformat()
                create_applicant(payload)
                created += 1
            except Exception as e:  # noqa: BLE001 — report per row
                errors.append(f"Row {i}: {e}")
    logger.info("Imported %d applicants from %s (%d errors)",
                created, path, len(errors))
    return created, errors



# ── GDPR export / erasure (item 50) ───────────────────────────────

def gdpr_export(applicant_id: str) -> dict[str, Any]:
    _guard.require("exporting applicant data")
    _guard.log_sensitive("admissions", "gdpr export",
                         applicant_id=applicant_id)
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    from dataclasses import asdict
    score = get_interview_score(applicant_id)
    out = {
        "applicant": asdict(a),
        "notes": [asdict(n) for n in list_notes(applicant_id)],
        "events": [asdict(e) for e in list_events(applicant_id)],
        "documents": [asdict(d) for d in list_documents(applicant_id)],
        "interview_score": asdict(score) if score else None,
        "programme_choices": [asdict(c) for c in
                              list_programme_choices(applicant_id)],
    }
    # Records held by the sibling admissions modules (same database).
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            entry_requirements as _er, references as _refs,
            open_events as _events,
        )
        out["gcse_results"] = [asdict(g) for g in _er.list_gcses(applicant_id)]
        out["offer_conditions"] = [asdict(c) for c in
                                   _er.list_conditions(applicant_id)]
        out["references"] = [asdict(r) for r in
                             _refs.list_references(applicant_id=applicant_id)]
        out["event_bookings"] = [asdict(b) for b in
                                 _events.bookings_for_applicant(applicant_id)]
    except Exception:
        logger.exception("GDPR export: could not add related admissions "
                         "records for %s", applicant_id)
    return out



# ── Letters and e-mail text ────────────────────────────────────────

def render_offer_letter(applicant_id: str) -> str:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    today = _dt.date.today().isoformat()
    cond = a.offer_conditions or "(no specific conditions)"
    kind = a.offer_type or "Conditional"
    body = [
        f"Date: {today}",
        f"Our ref: {a.applicant_id}",
        "",
        f"Dear {a.first_name} {a.last_name},",
        "",
        f"Following the review of your application, we are pleased to make "
        f"you a {kind.lower()} offer of a place in our Sixth Form to study:",
        "  " + (", ".join(a.subjects) if a.subjects else "(subjects TBC)"),
        "",
        f"Conditions of offer: {cond}",
    ]
    if a.offer_expiry:
        body.append(f"This offer must be accepted by {a.offer_expiry}.")
    body += [
        "",
        "We look forward to welcoming you.",
        "",
        "Yours sincerely,",
        "Admissions Team",
    ]
    return "\n".join(body)


def render_status_email(applicant_id: str) -> tuple[str, str]:
    """Return (subject, body) acknowledgement/decision email text."""
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    name = a.first_name
    s = a.status
    if s == "Offer Made":
        sub = "Your Sixth Form offer"
        msg = (f"Dear {name},\n\nWe are delighted to offer you a place. "
               f"Conditions: {a.offer_conditions or 'none'}.")
        if a.offer_expiry:
            msg += f"\nPlease respond by {a.offer_expiry}."
    elif s == "Rejected":
        sub = "Your Sixth Form application"
        msg = (f"Dear {name},\n\nThank you for applying. On this occasion "
               f"we are unable to offer you a place.")
        if a.decision_reason:
            msg += f"\nReason: {a.decision_reason}."
    elif s == "Interview Scheduled":
        sub = "Your Sixth Form interview"
        msg = (f"Dear {name},\n\nYour interview is scheduled for "
               f"{a.interview_date} with {a.interviewer or 'our team'}.")
    elif s in ("Offer Accepted", "Enrolled"):
        sub = "Welcome to Sixth Form"
        msg = (f"Dear {name},\n\nThank you for accepting your place. "
               f"We look forward to seeing you.")
    else:
        sub = "Your Sixth Form application — update"
        msg = (f"Dear {name},\n\nYour application status is now: {s}.")
    return sub, msg + "\n\nKind regards,\nAdmissions Team"


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()

    rows = list_applicants()
    by_status = {s: 0 for s in STATUSES}
    by_source = {s: 0 for s in SOURCES}
    upcoming_interviews = 0
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_source[a.application_source] = by_source.get(
            a.application_source, 0) + 1
        if a.interview_date and today <= a.interview_date <= horizon:
            upcoming_interviews += 1

    open_count = sum(by_status.get(s, 0) for s in OPEN_STATUSES)
    awaiting = (by_status.get("Under Review", 0)
                 + by_status.get("Interviewed", 0))
    pending_offers = by_status.get("Offer Made", 0)
    converted = by_status.get("Enrolled", 0)
    rejected = by_status.get("Rejected", 0)

    return Summary(
        total=len(rows),
        by_status=by_status,
        by_source=by_source,
        open_count=open_count,
        awaiting_decision=awaiting,
        pending_offers=pending_offers,
        converted=converted,
        rejected=rejected,
        upcoming_interviews=upcoming_interviews,
    )
