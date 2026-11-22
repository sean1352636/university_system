"""Enrolment & Leavers: who is on roll, who joined, who left and what's still
to do about each leaver.

The pupil record (``pupils.roll_status``) stays the single truth for on/off
roll. This module adds the leaving details a school must keep and act on:

* **Recording a leaver** (:func:`record_leaver`) marks the pupil left (which
  closes their login) and keeps where they went and why.
* **Follow-up actions** (:meth:`LeaverView.actions`) - what each leaving
  reason still needs, in line with the School Attendance (Pupil
  Registration) (England) Regulations and the children-missing-education
  duties:

  - moved to another (known) school → send the Common Transfer File (CTF),
    due within 15 school days (counted here as 21 calendar days);
  - moved away with no known school → refer to the local authority as a
    possible child missing education;
  - elective home education / permanent exclusion → notify the local
    authority;
  - end of Year 11 → record the post-16 destination;
  - a pupil marked left some other way (the pupil form) → record the details.

* **Reinstating** (:func:`reinstate`) puts a returning pupil back on roll and
  reopens their login.

Leaving details are kept per leaving (a pupil can leave, return and leave
again). Only roles allowed to open the "Enrolment & Leavers" menu entry may
use this - it holds exclusion and missing-education details.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass, fields
from typing import Any

from education_system.systems.secondary.modules.admissions.domain import admissions as A
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

MENU_LABEL = "Enrolment & Leavers"
CTF_DAYS = 21  # 15 school days, as calendar days

REASONS = P.LEAVING_REASONS
END_OF_Y11 = "End of Year 11"
MOVED_SCHOOL = "Moved to another school"
MOVED_AWAY = "Moved away"
EHE = "Elective home education"
EXCLUSION = "Permanent exclusion"
OTHER = "Other"

POST16_DESTINATIONS: tuple[str, ...] = (
    "School sixth form",
    "Sixth form college",
    "FE college",
    "Apprenticeship",
    "Employment with training",
    "Employment without training",
    "Not in education, employment or training (NEET)",
    "Moved abroad",
    "Unknown",
)

_SCHEMA = """
-- One row per leaving; no foreign key so the details outlive the record.
CREATE TABLE IF NOT EXISTS pupil_leaving (
    leaving_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id           INTEGER NOT NULL,
    leaving_date       TEXT NOT NULL,
    reason             TEXT NOT NULL,
    destination_school TEXT,
    destination_urn    TEXT,
    destination_la     TEXT,
    post16_destination TEXT,
    la_notified_date   TEXT,
    ctf_sent_date      TEXT,
    notes              TEXT,
    status             TEXT NOT NULL DEFAULT 'left' CHECK (status IN ('left', 'reinstated')),
    recorded_at        TEXT NOT NULL DEFAULT (datetime('now')),
    recorded_by        TEXT,
    reinstated_at      TEXT,
    reinstated_by      TEXT,
    reinstate_note     TEXT
);
CREATE INDEX IF NOT EXISTS ix_pupil_leaving_pupil ON pupil_leaving (pupil_id, status);
"""

database.register_schema("enrolment", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class Leaving:
    leaving_id: int
    pupil_id: int
    leaving_date: str
    reason: str
    destination_school: str | None
    destination_urn: str | None
    destination_la: str | None
    post16_destination: str | None
    la_notified_date: str | None
    ctf_sent_date: str | None
    notes: str | None
    status: str
    recorded_at: str
    recorded_by: str | None
    reinstated_at: str | None
    reinstated_by: str | None
    reinstate_note: str | None


_FIELDS = tuple(f.name for f in fields(Leaving))
DETAIL_FIELDS: tuple[str, ...] = (
    "destination_school", "destination_urn", "destination_la", "post16_destination",
    "la_notified_date", "ctf_sent_date", "notes",
)
FIELD_LABELS = {
    "destination_school": "Destination school", "destination_urn": "Destination URN",
    "destination_la": "Destination local authority", "post16_destination": "Post-16 destination",
    "la_notified_date": "Local authority notified", "ctf_sent_date": "CTF sent",
    "notes": "Notes",
}


def _row(r) -> Leaving:
    return Leaving(**{k: r[k] for k in _FIELDS})


@dataclass(frozen=True)
class LeaverView:
    pupil: P.Pupil
    leaving: Leaving | None

    def actions(self, today: _dt.date | None = None) -> list[str]:
        """What still needs doing for this leaver (empty when nothing)."""
        today = today or _dt.date.today()
        lv = self.leaving
        if lv is None:
            return ["Leaving details not recorded"]
        out = []
        if lv.reason == END_OF_Y11:
            if not lv.post16_destination:
                out.append("Record post-16 destination")
            return out
        if lv.destination_school and not lv.ctf_sent_date:
            due = _dt.date.fromisoformat(lv.leaving_date) + _dt.timedelta(days=CTF_DAYS)
            late = " (overdue)" if today > due else f" (by {due.isoformat()})"
            out.append("Send the Common Transfer File" + late)
        if not lv.la_notified_date:
            if lv.reason == MOVED_AWAY and not lv.destination_school:
                out.append("Destination unknown: refer to the local authority "
                           "(child missing education)")
            elif lv.reason == EHE:
                out.append("Notify the local authority (elective home education)")
            elif lv.reason == EXCLUSION:
                out.append("Notify the local authority (permanent exclusion)")
        return out


# ── Validation helpers ───────────────────────────────────────────────

_URN_RE = re.compile(r"^\d{6}$")


def _date(value: Any, label: str, problems: list[str], *, not_before: str | None = None,
          today: _dt.date) -> str | None:
    d = P._parse_date(value, label, problems)
    if d is None:
        return None
    if d > today.isoformat():
        problems.append(f"{label} can't be in the future")
    elif not_before and d < not_before:
        problems.append(f"{label} can't be before {not_before}")
    return d


def _clean_details(data: dict[str, Any], *, leaving_date: str | None, reason: str,
                   problems: list[str], today: _dt.date) -> dict[str, Any]:
    unknown = set(data) - set(DETAIL_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {
        "destination_school": P._clean_text(data.get("destination_school"), 120),
        "destination_la": P._clean_text(data.get("destination_la"), 80),
        "notes": P._clean_text(data.get("notes"), 2000),
    }
    urn = P._clean_text(data.get("destination_urn"), 10)
    if urn and not _URN_RE.match(urn):
        problems.append("A school URN is 6 digits")
    out["destination_urn"] = urn
    post16 = P._clean_text(data.get("post16_destination"), 60)
    if post16 and post16 not in POST16_DESTINATIONS:
        problems.append("Post-16 destination must be one of: " + ", ".join(POST16_DESTINATIONS))
    if post16 and reason != END_OF_Y11:
        problems.append("A post-16 destination is only for Year 11 leavers")
    out["post16_destination"] = post16
    for key, label in (("la_notified_date", "Local authority notified date"),
                       ("ctf_sent_date", "CTF sent date")):
        out[key] = _date(data.get(key), label, problems, not_before=leaving_date, today=today)
    if reason == MOVED_SCHOOL and not out["destination_school"]:
        problems.append("Give the school the pupil has moved to")
    if reason == OTHER and not out["notes"]:
        problems.append("Explain the reason in the notes")
    return out


def _require(actor: Principal, action: str, target: str | None) -> None:
    if not actor.can_open(MENU_LABEL):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account doesn't have access to Enrolment & Leavers.")


def _pupil(pupil_id: int, action: str, actor: Principal) -> P.Pupil:
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        activity_log.record(action, target=f"id:{pupil_id}", outcome="not_found",
                            principal=actor)
        raise NotFound(f"No pupil with id {pupil_id}")
    return pupil


# ── Read ─────────────────────────────────────────────────────────────

def current_leaving(pupil_id: int) -> Leaving | None:
    """The details of the pupil's latest (unreversed) leaving, if any."""
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pupil_leaving WHERE pupil_id = ? AND status = 'left' "
                         "ORDER BY leaving_id DESC LIMIT 1", (int(pupil_id),)).fetchone()
    return _row(r) if r else None


def leaving_history(pupil_id: int) -> list[Leaving]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM pupil_leaving WHERE pupil_id = ? "
                            "ORDER BY leaving_id DESC", (int(pupil_id),)).fetchall()
    return [_row(r) for r in rows]


def get_leaving(leaving_id: int) -> Leaving | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pupil_leaving WHERE leaving_id = ?",
                         (int(leaving_id),)).fetchone()
    return _row(r) if r else None


def _year_bounds(academic_year: str) -> tuple[str, str]:
    start = A.year_start_date(academic_year)
    return start.isoformat(), _dt.date(start.year + 1, 8, 31).isoformat()


def list_leavers(*, academic_year: str | None = None, reason: str | None = None,
                 actions_only: bool = False, search: str | None = None) -> list[LeaverView]:
    """Pupils who are off roll (newest leaving first), with their details."""
    pupils = P.list_pupils(roll_status="left", search=search or None)
    if academic_year:
        lo, hi = _year_bounds(academic_year)
        pupils = [p for p in pupils if p.leaving_date and lo <= p.leaving_date <= hi]
    if reason:
        pupils = [p for p in pupils if p.leaving_reason == reason]
    with database.connect() as conn:
        latest = {r["pupil_id"]: _row(r) for r in conn.execute(
            "SELECT * FROM pupil_leaving WHERE status = 'left' ORDER BY leaving_id")}
    views = [LeaverView(p, latest.get(p.pupil_id)) for p in pupils]
    if actions_only:
        views = [v for v in views if v.actions()]
    return sorted(views, key=lambda v: (v.pupil.leaving_date or "", v.pupil.pupil_id),
                  reverse=True)


def list_joiners(academic_year: str) -> list[P.Pupil]:
    """Pupils admitted during *academic_year* (on roll or since left)."""
    lo, hi = _year_bounds(academic_year)
    return sorted((p for p in P.list_pupils(roll_status=None)
                   if lo <= (p.admission_date or "") <= hi),
                  key=lambda p: (p.admission_date, p.pupil_id), reverse=True)


@dataclass(frozen=True)
class RollSummary:
    academic_year: str
    on_roll_by_year: dict[int, int]
    joiners: int
    leavers: int
    leavers_by_reason: dict[str, int]
    actions_due: int

    @property
    def on_roll(self) -> int:
        return sum(self.on_roll_by_year.values())


def roll_summary(academic_year: str | None = None) -> RollSummary:
    year = academic_year or A.current_academic_year()
    on_roll = {y: 0 for y in P.YEAR_GROUPS}
    for p in P.list_pupils():
        on_roll[p.year_group] = on_roll.get(p.year_group, 0) + 1
    leavers = list_leavers(academic_year=year)
    by_reason: dict[str, int] = {}
    for v in leavers:
        key = v.pupil.leaving_reason or "Not recorded"
        by_reason[key] = by_reason.get(key, 0) + 1
    due = sum(1 for v in list_leavers() if v.actions())
    return RollSummary(year, on_roll, len(list_joiners(year)), len(leavers), by_reason, due)


# ── Record / update / reinstate ───────────────────────────────────────

def record_leaver(pupil_id: int, *, leaving_date: str, reason: str,
                  details: dict[str, Any] | None = None, actor: Principal,
                  today: _dt.date | None = None) -> LeaverView:
    """Take a pupil off roll and keep the leaving details. Their login closes."""
    today = today or _dt.date.today()
    pupil = _pupil(pupil_id, "enrolment.leave", actor)
    _require(actor, "enrolment.leave", pupil.admission_no)
    problems: list[str] = []
    if pupil.roll_status != "on_roll":
        problems.append(f"{pupil.display_name} is already off roll")
    if reason not in REASONS:
        problems.append("Choose a leaving reason: " + ", ".join(REASONS))
    date = _date(leaving_date, "Leaving date", problems, not_before=pupil.admission_date,
                 today=today)
    if date is None and not any(p.startswith("Leaving date") for p in problems):
        problems.append("Give the leaving date (the last day on roll)")
    if reason == END_OF_Y11 and pupil.year_group != P.YEAR_GROUPS[-1]:
        problems.append(f"Only a Year {P.YEAR_GROUPS[-1]} pupil can leave at the end of "
                        f"Year {P.YEAR_GROUPS[-1]}")
    clean = _clean_details(details or {}, leaving_date=date, reason=reason,
                           problems=problems, today=today)
    if problems:
        activity_log.record("enrolment.leave", target=pupil.admission_no, outcome="invalid",
                            principal=actor, problems=len(problems))
        raise ValidationError(problems)
    P.update_pupil_detailed(pupil.pupil_id, {"roll_status": "left", "leaving_date": date,
                                             "leaving_reason": reason}, actor=actor)
    _insert_leaving(pupil.pupil_id, date, reason, clean, actor.username)  # type: ignore[arg-type]
    activity_log.record("enrolment.leave", target=pupil.admission_no, principal=actor,
                        reason=reason)
    return LeaverView(P.get_pupil(pupil.pupil_id), current_leaving(pupil.pupil_id))  # type: ignore[arg-type]


def _insert_leaving(pupil_id: int, date: str, reason: str, clean: dict[str, Any],
                    by: str | None, conn=None) -> None:
    cols = ["pupil_id", "leaving_date", "reason", *clean, "recorded_by"]
    values = [pupil_id, date, reason, *clean.values(), by]
    sql = (f"INSERT INTO pupil_leaving ({', '.join(cols)}) "
           f"VALUES ({', '.join('?' for _ in cols)})")
    if conn is not None:
        conn.execute(sql, values)
        return
    with database.connect() as c:
        c.execute(sql, values)


def record_details(pupil_id: int, details: dict[str, Any], *, actor: Principal,
                   today: _dt.date | None = None) -> LeaverView:
    """Add or change a leaver's details (destination, CTF sent, LA notified,
    post-16 destination, notes). Creates the details for a pupil who was
    marked left without them."""
    today = today or _dt.date.today()
    pupil = _pupil(pupil_id, "enrolment.details", actor)
    _require(actor, "enrolment.details", pupil.admission_no)
    if pupil.roll_status != "left":
        raise ValidationError([f"{pupil.display_name} is on roll"])
    current = current_leaving(pupil_id)
    reason = current.reason if current else (pupil.leaving_reason or OTHER)
    date = current.leaving_date if current else (pupil.leaving_date or today.isoformat())
    merged = {k: getattr(current, k) for k in DETAIL_FIELDS} if current else {}
    merged.update(details)
    problems: list[str] = []
    clean = _clean_details(merged, leaving_date=date, reason=reason, problems=problems,
                           today=today)
    if problems:
        activity_log.record("enrolment.details", target=pupil.admission_no,
                            outcome="invalid", principal=actor, problems=len(problems))
        raise ValidationError(problems)
    if current is None:
        _insert_leaving(pupil.pupil_id, date, reason, clean, actor.username)
        changed = sorted(k for k, v in clean.items() if v)
    else:
        changed = sorted(k for k, v in clean.items() if getattr(current, k) != v)
        if changed:
            with database.connect() as conn:
                conn.execute(
                    f"UPDATE pupil_leaving SET {', '.join(f'{k} = ?' for k in changed)} "
                    "WHERE leaving_id = ?", [clean[k] for k in changed] + [current.leaving_id])
    activity_log.record("enrolment.details", target=pupil.admission_no, principal=actor,
                        outcome="ok" if changed else "no_change", fields=changed or None)
    return LeaverView(pupil, current_leaving(pupil_id))


def reinstate(pupil_id: int, *, actor: Principal, note: str,
              year_group: int | None = None) -> P.Pupil:
    """Put a returning pupil back on roll (and reopen their login). A note is
    required; *year_group* moves them if they return to a different year."""
    pupil = _pupil(pupil_id, "enrolment.reinstate", actor)
    _require(actor, "enrolment.reinstate", pupil.admission_no)
    problems = []
    if pupil.roll_status != "left":
        problems.append(f"{pupil.display_name} is already on roll")
    note = P._clean_text(note, 500) or ""
    if not note:
        problems.append("Say why the pupil is coming back on roll")
    if problems:
        activity_log.record("enrolment.reinstate", target=pupil.admission_no,
                            outcome="invalid", principal=actor, problems=len(problems))
        raise ValidationError(problems)
    changes: dict[str, Any] = {"roll_status": "on_roll"}
    if year_group is not None:
        changes["year_group"] = year_group
    current = current_leaving(pupil_id)
    updated, _changed = P.update_pupil_detailed(pupil.pupil_id, changes, actor=actor)
    if current is not None:
        with database.connect() as conn:
            conn.execute("UPDATE pupil_leaving SET status = 'reinstated', reinstated_at = "
                         "datetime('now'), reinstated_by = ?, reinstate_note = ? "
                         "WHERE leaving_id = ?", (actor.username, note, current.leaving_id))
    activity_log.record("enrolment.reinstate", target=pupil.admission_no, principal=actor)
    return updated
