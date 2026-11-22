"""SEND: access arrangements (the old Accessibility window) and external
agencies. Part of the SEND screen; the rules are described in :mod:`send`."""

from __future__ import annotations

import datetime as _dt
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.send.domain.send_common import (
    PUPIL_COLS as _PUPIL_COLS,
)
from education_system.systems.secondary.modules.send.domain.send_common import (
    NotFound,
    ValidationError,
    _audit,
    _blank,
    _bool,
    _choice,
    _date,
    _make,
    _need_pupil,
    _pupil,
    _require_editor,
    _text,
)
from education_system.systems.secondary.modules.pupils.domain import sen_details as SD
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ACCESS_TYPES: tuple[str, ...] = (
    "Reasonable adjustment", "Exam access arrangement", "Physical access", "Sensory access",
    "Communication support", "Medical / health", "Other")
EXAM_ACCESS = "Exam access arrangement"
ACCESS_CATEGORIES: tuple[str, ...] = (
    "Extra time (25%)", "Extra time (50%)", "Rest breaks", "Word processor", "Modified papers",
    "Coloured overlays", "Reader", "Scribe", "Quiet room", "Prompter",
    "Wheelchair access / ramp", "Hearing loop / FM system", "Large print",
    "Assistive technology", "Sign-language support", "Toilet pass", "Medical break", "Other")
ACCESS_STATUSES: tuple[str, ...] = ("Proposed", "Active", "Expired", "Withdrawn",
                                    "Under review")
EVIDENCE_SOURCES: tuple[str, ...] = (
    "EHCP", "SEND assessment", "Medical letter", "Educational psychologist report",
    "JCQ Form 8", "Teacher recommendation", "Parent request", "Other")
FORM_8 = "JCQ Form 8"
AGENCIES: tuple[str, ...] = (
    "Educational psychologist", "Speech and language therapy", "CAMHS",
    "Occupational therapy", "Physiotherapy", "Specialist teacher (sensory)",
    "Autism outreach", "Social care", "School nurse", "Paediatrician", "Early help", "Other")
AGENCY_STATUSES: tuple[str, ...] = ("Referred", "Waiting", "Active", "Discharged", "Declined")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS send_access (
    arrangement_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    arrangement_type    TEXT NOT NULL DEFAULT 'Reasonable adjustment',
    category            TEXT NOT NULL,
    description         TEXT,
    exam_only           INTEGER NOT NULL DEFAULT 0 CHECK (exam_only IN (0, 1)),
    start_date          TEXT NOT NULL,
    end_date            TEXT,
    status              TEXT NOT NULL DEFAULT 'Proposed',
    evidence_source     TEXT,
    evidence_reference  TEXT,
    assessor            TEXT,
    assessed_on         TEXT,
    approved_by         TEXT,
    approval_date       TEXT,
    review_date         TEXT,
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_send_access_pupil ON send_access (pupil_id, status);
CREATE TABLE IF NOT EXISTS send_agencies (
    agency_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    agency              TEXT NOT NULL,
    contact_name        TEXT,
    contact_details     TEXT,
    referred_on         TEXT,
    referred_by         TEXT,
    status              TEXT NOT NULL DEFAULT 'Referred',
    first_seen_on       TEXT,
    next_appointment    TEXT,
    report_received_on  TEXT,
    outcome             TEXT,
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_send_agencies_pupil ON send_agencies (pupil_id);
"""
database.register_schema("send_access", _SCHEMA)


@dataclass(frozen=True)
class Arrangement:
    arrangement_id: int
    pupil_id: int
    arrangement_type: str
    category: str
    description: str | None
    exam_only: bool
    start_date: str
    end_date: str | None
    status: str
    evidence_source: str | None
    evidence_reference: str | None
    assessor: str | None
    assessed_on: str | None
    approved_by: str | None
    approval_date: str | None
    review_date: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0

    @property
    def expired(self) -> bool:
        return self.status == "Active" and bool(self.end_date) and \
            self.end_date < _today().isoformat()  # type: ignore[operator]


@dataclass(frozen=True)
class Agency:
    agency_id: int
    pupil_id: int
    agency: str
    contact_name: str | None
    contact_details: str | None
    referred_on: str | None
    referred_by: str | None
    status: str
    first_seen_on: str | None
    next_appointment: str | None
    report_received_on: str | None
    outcome: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0


# ── Access arrangements (the old Accessibility) ──────────────────────

_ACC_FIELDS = ("arrangement_type", "category", "description", "exam_only", "start_date",
               "end_date", "status", "evidence_source", "evidence_reference", "assessor",
               "assessed_on", "approved_by", "approval_date", "review_date", "notes")


def _acc_select() -> str:
    return f"SELECT x.*, {_PUPIL_COLS} FROM send_access x JOIN pupils p USING (pupil_id)"


def get_arrangement(arrangement_id: int) -> Arrangement:
    with database.connect() as conn:
        r = conn.execute(_acc_select() + " WHERE x.arrangement_id = ?",
                         (int(arrangement_id),)).fetchone()
    if r is None:
        raise NotFound(f"No arrangement #{arrangement_id}")
    return _make(Arrangement, r)


def list_arrangements(*, pupil_id: int | None = None, year_group: int | str | None = None,
                      arrangement_type: str | None = None, status: str | None = None,
                      exam_only: bool | None = None) -> list[Arrangement]:
    where, params = [], []
    for col, val in (("x.pupil_id", pupil_id), ("x.arrangement_type", arrangement_type),
                     ("x.status", status)):
        if not _blank(val):
            where.append(f"{col} = ?")
            params.append(val)
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    if exam_only is not None:
        where.append("x.exam_only = ?")
        params.append(int(exam_only))
    sql = _acc_select() + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY p.year_group, p.legal_last_name COLLATE NOCASE, x.start_date DESC"
    with database.connect() as conn:
        return [_make(Arrangement, r) for r in conn.execute(sql, params)]


def year9_start(p: P.Pupil, today: _dt.date | None = None) -> _dt.date:
    """1 September of the pupil's Year 9 (JCQ: assessments from then on)."""
    start = P.academic_year_start(today or _today())
    return _dt.date(start.year - (p.year_group - 9), 9, 1)


def _clean_access(data: dict[str, Any], cur: Arrangement | None, p: P.Pupil,
                  problems: list[str]) -> dict[str, Any]:
    merged = {k: getattr(cur, k) for k in _ACC_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _ACC_FIELDS})
    out: dict[str, Any] = {
        "arrangement_type": _choice(merged.get("arrangement_type"), ACCESS_TYPES, "Type",
                                    problems, ACCESS_TYPES[0]),
        "status": _choice(merged.get("status"), ACCESS_STATUSES, "Status", problems,
                          "Proposed"),
        "evidence_source": _choice(merged.get("evidence_source"), EVIDENCE_SOURCES,
                                   "Evidence source", problems, None)}
    cat = _text(merged.get("category"), 80)
    if not cat:
        problems.append("Category is required")
    out["category"] = cat
    for k in ("description", "notes"):
        out[k] = _text(merged.get(k), 2000)
    for k in ("evidence_reference", "assessor", "approved_by"):
        out[k] = _text(merged.get(k), 120)
    out["exam_only"] = int(_bool(merged.get("exam_only")))
    for k, label in (("start_date", "Start date"), ("end_date", "End date"),
                     ("assessed_on", "Assessed on"), ("approval_date", "Approval date"),
                     ("review_date", "Review date")):
        out[k] = _date(merged.get(k), label, problems)
    out["start_date"] = out["start_date"] or _today().isoformat()
    if out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("End date cannot be before start date")
    if out["status"] == "Active" and not out["approved_by"]:
        problems.append("An active arrangement needs who approved it")
    if out["status"] == "Active" and not out["approval_date"]:
        out["approval_date"] = _today().isoformat()
    if out["arrangement_type"] == EXAM_ACCESS and out["status"] == "Active" and \
            not out["evidence_source"]:
        problems.append("Record the evidence for an exam access arrangement (JCQ)")
    if out["evidence_source"] == FORM_8:
        if not out["assessed_on"]:
            problems.append("Give the date of the Form 8 assessment")
        elif p.year_group < 9 or out["assessed_on"] < year9_start(p).isoformat():
            problems.append("A JCQ Form 8 assessment must be done no earlier than the start "
                            f"of Year 9 ({year9_start(p)})")
        if not out["assessor"]:
            problems.append("Name the assessor for the Form 8")
    return out


def add_arrangement(data: dict[str, Any], *, actor: Principal) -> Arrangement:
    """The old New arrangement (*data* carries ``pupil_id``)."""
    _require_editor(actor, "access")
    problems: list[str] = []
    p = _pupil(data.get("pupil_id") or data.get("pupil"))
    if p is None:
        raise ValidationError(["Pupil ID is required"])
    c = _clean_access(data, None, p, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        aid = conn.execute(
            f"INSERT INTO send_access (pupil_id, {', '.join(_ACC_FIELDS)}, created_by, "
            f"updated_by) VALUES (?, {', '.join('?' * len(_ACC_FIELDS))}, ?, ?)",
            (p.pupil_id, *(c[k] for k in _ACC_FIELDS), actor.username,
             actor.username)).lastrowid
        _audit(conn, actor, "access", "add", pupil_id=p.pupil_id, item_id=aid)
    activity_log.record("send.access", target=p.admission_no, principal=actor, item=aid)
    return get_arrangement(aid)


def update_arrangement(arrangement_id: int, changes: dict[str, Any], *, actor: Principal
                       ) -> Arrangement:
    cur = get_arrangement(arrangement_id)
    _require_editor(actor, "access_update", cur.admission_no)
    problems: list[str] = []
    c = _clean_access(changes, cur, P.get_pupil(cur.pupil_id), problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _ACC_FIELDS if c[k] != (int(getattr(cur, k)) if k == "exam_only"
                                                  else getattr(cur, k))]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE send_access SET " + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') "
                           "WHERE arrangement_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.arrangement_id))
            _audit(conn, actor, "access", "update", pupil_id=cur.pupil_id,
                   item_id=cur.arrangement_id, fields=changed)
        activity_log.record("send.access_update", target=cur.admission_no, principal=actor,
                            item=cur.arrangement_id)
    return get_arrangement(cur.arrangement_id)


def set_arrangement_status(arrangement_id: int, status: str, *, actor: Principal,
                           approved_by: str | None = None) -> Arrangement:
    changes: dict[str, Any] = {"status": status}
    if approved_by:
        changes["approved_by"] = approved_by
    return update_arrangement(arrangement_id, changes, actor=actor)


def delete_arrangement(arrangement_id: int, *, actor: Principal) -> bool:
    cur = get_arrangement(arrangement_id)
    _require_editor(actor, "access_delete", cur.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM send_access WHERE arrangement_id = ?", (cur.arrangement_id,))
        _audit(conn, actor, "access", "delete", pupil_id=cur.pupil_id,
               item_id=cur.arrangement_id)
    activity_log.record("send.access_delete", target=cur.admission_no, principal=actor)
    return True


def expired_arrangements() -> list[Arrangement]:
    """The old Expired list: Active but past their end date."""
    return [a for a in list_arrangements(status="Active") if a.expired]


def expire_overdue(*, actor: Principal) -> int:
    """Mark Active arrangements past their end date as Expired."""
    _require_editor(actor, "access_expire")
    rows = expired_arrangements()
    with database.connect() as conn:
        for a in rows:
            conn.execute("UPDATE send_access SET status = 'Expired', updated_by = ?, "
                         "updated_at = datetime('now') WHERE arrangement_id = ?",
                         (actor.username, a.arrangement_id))
            _audit(conn, actor, "access", "expire", pupil_id=a.pupil_id,
                   item_id=a.arrangement_id)
    activity_log.record("send.access_expire", principal=actor, rows=len(rows))
    return len(rows)


def access_summary(*, year_group: int | str | None = None) -> dict[str, Any]:
    """The old Accessibility cohort summary."""
    rows = list_arrangements(year_group=year_group)
    return {"total": len(rows), "by_type": dict(Counter(a.arrangement_type for a in rows)),
            "by_category": dict(Counter(a.category for a in rows)),
            "by_status": dict(Counter(a.status for a in rows)),
            "exam_only": sum(1 for a in rows if a.exam_only),
            "expired": sum(1 for a in rows if a.expired),
            "pupils": len({a.pupil_id for a in rows if a.status == "Active"})}


def exam_access_text(pupil_id: int) -> str:
    """The pupil's active exam access arrangements, as one line."""
    return "; ".join(a.category for a in list_arrangements(pupil_id=pupil_id, status="Active")
                     if a.arrangement_type == EXAM_ACCESS)[:500]


def copy_exam_access(pupil_id: int, *, actor: Principal) -> SD.SenDetails:
    """Write the active exam access arrangements into the SEN details' exam
    access line (what exams entries and the sixth form read)."""
    _require_editor(actor, "access_copy")
    p = _need_pupil(pupil_id)
    if p.sen_status not in ("K", "E"):
        raise ValidationError([f"{p.display_name} has no SEN status - SEN details are kept for "
                               "SEN support or an EHC plan"])
    text = exam_access_text(p.pupil_id)
    cur = SD.get(p.pupil_id)
    if cur is None or not cur.primary_need:
        raise ValidationError(["Record the primary need first (Edit record)"])
    return SD.save(p.pupil_id, {"exam_access": text}, actor=actor)


# ── External agencies ────────────────────────────────────────────────

_AG_FIELDS = ("agency", "contact_name", "contact_details", "referred_on", "referred_by",
              "status", "first_seen_on", "next_appointment", "report_received_on", "outcome",
              "notes")


def _ag_select() -> str:
    return f"SELECT x.*, {_PUPIL_COLS} FROM send_agencies x JOIN pupils p USING (pupil_id)"


def get_agency(agency_id: int) -> Agency:
    with database.connect() as conn:
        r = conn.execute(_ag_select() + " WHERE x.agency_id = ?", (int(agency_id),)).fetchone()
    if r is None:
        raise NotFound(f"No agency record #{agency_id}")
    return _make(Agency, r)


def list_agencies(*, pupil_id: int | None = None, agency: str | None = None,
                  status: str | None = None, year_group: int | str | None = None
                  ) -> list[Agency]:
    where, params = [], []
    for col, val in (("x.pupil_id", pupil_id), ("x.agency", agency), ("x.status", status)):
        if not _blank(val):
            where.append(f"{col} = ?")
            params.append(val)
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    sql = _ag_select() + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY COALESCE(x.referred_on, x.created_at) DESC"
    with database.connect() as conn:
        return [_make(Agency, r) for r in conn.execute(sql, params)]


def _clean_agency(data: dict[str, Any], cur: Agency | None, problems: list[str]
                  ) -> dict[str, Any]:
    merged = {k: getattr(cur, k) for k in _AG_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _AG_FIELDS})
    out: dict[str, Any] = {"agency": _text(merged.get("agency"), 80),
                           "status": _choice(merged.get("status"), AGENCY_STATUSES, "Status",
                                             problems, "Referred")}
    if not out["agency"]:
        problems.append("Agency is required")
    for k, n in (("contact_name", 120), ("contact_details", 300), ("referred_by", 80),
                 ("outcome", 2000), ("notes", 2000)):
        out[k] = _text(merged.get(k), n)
    for k, label in (("referred_on", "Referred on"), ("first_seen_on", "First seen"),
                     ("next_appointment", "Next appointment"),
                     ("report_received_on", "Report received")):
        out[k] = _date(merged.get(k), label, problems)
    if out["referred_on"] and out["referred_on"] > _today().isoformat():
        problems.append("The referral date can't be in the future")
    for k in ("first_seen_on", "report_received_on"):
        if out[k] and out["referred_on"] and out[k] < out["referred_on"]:
            problems.append("Dates can't be before the referral")
    return out


def add_agency(data: dict[str, Any], *, actor: Principal) -> Agency:
    _require_editor(actor, "agency")
    problems: list[str] = []
    p = _pupil(data.get("pupil_id") or data.get("pupil"))
    if p is None:
        problems.append("Pupil ID is required")
    c = _clean_agency(data, None, problems)
    c["referred_on"] = c["referred_on"] or _today().isoformat()
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        aid = conn.execute(
            f"INSERT INTO send_agencies (pupil_id, {', '.join(_AG_FIELDS)}, created_by, "
            f"updated_by) VALUES (?, {', '.join('?' * len(_AG_FIELDS))}, ?, ?)",
            (p.pupil_id, *(c[k] for k in _AG_FIELDS), actor.username,
             actor.username)).lastrowid
        _audit(conn, actor, "agency", "add", pupil_id=p.pupil_id, item_id=aid)
    activity_log.record("send.agency", target=p.admission_no, principal=actor, item=aid)
    return get_agency(aid)


def update_agency(agency_id: int, changes: dict[str, Any], *, actor: Principal) -> Agency:
    cur = get_agency(agency_id)
    _require_editor(actor, "agency_update", cur.admission_no)
    problems: list[str] = []
    c = _clean_agency(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _AG_FIELDS if c[k] != getattr(cur, k)]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE send_agencies SET " + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE agency_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.agency_id))
            _audit(conn, actor, "agency", "update", pupil_id=cur.pupil_id,
                   item_id=cur.agency_id, fields=changed)
        activity_log.record("send.agency_update", target=cur.admission_no, principal=actor)
    return get_agency(cur.agency_id)


def delete_agency(agency_id: int, *, actor: Principal) -> bool:
    cur = get_agency(agency_id)
    _require_editor(actor, "agency_delete", cur.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM send_agencies WHERE agency_id = ?", (cur.agency_id,))
        _audit(conn, actor, "agency", "delete", pupil_id=cur.pupil_id, item_id=cur.agency_id)
    activity_log.record("send.agency_delete", target=cur.admission_no, principal=actor)
    return True


