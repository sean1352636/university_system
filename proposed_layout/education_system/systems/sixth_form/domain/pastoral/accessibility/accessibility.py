"""Accessibility — SEND profiles and accommodations for sixth-form students.

Two related tables:

* ``accessibility_profiles`` — one row per student (1:1, ``student_id``
  is UNIQUE). Holds the SEND status (EHCP / SEN Support / None), the
  primary area of need, diagnoses, mobility aids, and the most recent
  review metadata.

* ``accessibility_accommodations`` — one row per individual arrangement
  the student is entitled to (e.g. "25% extra time", "reader",
  "wheelchair-accessible classrooms"). Categorised so exam-access
  arrangements can be filtered out separately for the JCQ-style
  printout.

Cascade: deleting a student wipes both rows.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.pastoral.accessibility import (
    accessibility as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ACCESSIBILITY_DB

SEND_STATUSES: tuple[str, ...] = (
    "None", "SEN Support", "EHCP", "Monitoring", "Exited",
)
DEFAULT_SEND_STATUS: str = "None"

PRIMARY_NEEDS: tuple[str, ...] = (
    "Cognition & Learning",
    "Communication & Interaction",
    "Social, Emotional & Mental Health",
    "Sensory or Physical",
    "Multiple Needs",
    "Other",
)

ACCOMMODATION_CATEGORIES: tuple[str, ...] = (
    "Exam Access",
    "Classroom",
    "Physical / Building",
    "Assistive Technology",
    "Communication",
    "Pastoral",
    "Other",
)
DEFAULT_ACCOMMODATION_CATEGORY: str = "Exam Access"

ACCOMMODATION_STATUSES: tuple[str, ...] = (
    "Active", "Pending", "Expired", "Withdrawn",
)
DEFAULT_ACCOMMODATION_STATUS: str = "Active"

# A non-exhaustive catalogue of common arrangements. Surface these as
# autocomplete in the GUI / a picker in the CLI; users may type free
# text for anything not listed.
COMMON_ACCOMMODATIONS: tuple[str, ...] = (
    "25% extra time",
    "50% extra time",
    "Reader",
    "Scribe",
    "Word processor",
    "Rest breaks",
    "Prompter",
    "Practical assistant",
    "Modified papers (large print)",
    "Modified papers (coloured overlay)",
    "Separate room",
    "Small group setting",
    "Preferential seating",
    "Lift / step-free access",
    "Wheelchair-accessible classrooms",
    "Sign language interpreter",
    "Hearing loop",
    "Screen reader",
    "Speech-to-text software",
    "Coloured paper",
    "Frequent toilet breaks",
    "Medication reminder",
    "Pastoral check-in",
    "Quiet exit / safe space",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accessibility_profiles (
    profile_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL UNIQUE,
    send_status       TEXT NOT NULL DEFAULT 'None',
    has_ehcp          INTEGER NOT NULL DEFAULT 0,
    ehcp_reference    TEXT,
    primary_need      TEXT,
    secondary_needs   TEXT,
    diagnoses         TEXT,
    mobility_aids     TEXT,
    requires_pep      INTEGER NOT NULL DEFAULT 0,
    fire_evac_notes   TEXT,
    last_reviewed     TEXT,
    next_review_due   TEXT,
    reviewer          TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS accessibility_accommodations (
    accommodation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    category          TEXT NOT NULL DEFAULT 'Exam Access',
    name              TEXT NOT NULL,
    description       TEXT,
    status            TEXT NOT NULL DEFAULT 'Active',
    start_date        TEXT,
    end_date          TEXT,
    approved_by       TEXT,
    approved_date     TEXT,
    evidence          TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_acc_prof_student
    ON accessibility_profiles(student_id);
CREATE INDEX IF NOT EXISTS idx_acc_prof_status
    ON accessibility_profiles(send_status);
CREATE INDEX IF NOT EXISTS idx_acc_arr_student
    ON accessibility_accommodations(student_id);
CREATE INDEX IF NOT EXISTS idx_acc_arr_category
    ON accessibility_accommodations(category);
CREATE INDEX IF NOT EXISTS idx_acc_arr_status
    ON accessibility_accommodations(status);
"""


@dataclass
class Profile:
    profile_id: int
    student_id: str
    send_status: str
    has_ehcp: bool
    ehcp_reference: str | None
    primary_need: str | None
    secondary_needs: str | None
    diagnoses: str | None
    mobility_aids: str | None
    requires_pep: bool
    fire_evac_notes: str | None
    last_reviewed: str | None
    next_review_due: str | None
    reviewer: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Accommodation:
    accommodation_id: int
    student_id: str
    category: str
    name: str
    description: str | None
    status: str
    start_date: str | None
    end_date: str | None
    approved_by: str | None
    approved_date: str | None
    evidence: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_current(self) -> bool:
        if self.status != "Active":
            return False
        today = _dt.date.today().isoformat()
        if self.start_date and self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True


@dataclass
class ProfileRow:
    profile: Profile
    student_name: str
    accommodation_count: int = 0
    active_accommodation_count: int = 0


@dataclass
class AccommodationRow:
    accommodation: Accommodation
    student_name: str


@dataclass
class Summary:
    student_count: int                       # students with a profile
    by_send_status: dict[str, int]
    by_primary_need: dict[str, int]
    ehcp_count: int
    pep_count: int
    review_overdue: int                      # next_review_due < today
    review_upcoming: int                     # next_review_due in next 30d
    accommodation_count: int
    active_accommodation_count: int
    by_category: dict[str, int]


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Accessibility schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_profile(r: sqlite3.Row) -> Profile:
    return Profile(
        profile_id=r["profile_id"], student_id=r["student_id"],
        send_status=r["send_status"], has_ehcp=bool(r["has_ehcp"]),
        ehcp_reference=r["ehcp_reference"],
        primary_need=r["primary_need"],
        secondary_needs=r["secondary_needs"],
        diagnoses=r["diagnoses"], mobility_aids=r["mobility_aids"],
        requires_pep=bool(r["requires_pep"]),
        fire_evac_notes=r["fire_evac_notes"],
        last_reviewed=r["last_reviewed"],
        next_review_due=r["next_review_due"],
        reviewer=r["reviewer"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_accomm(r: sqlite3.Row) -> Accommodation:
    return Accommodation(
        accommodation_id=r["accommodation_id"],
        student_id=r["student_id"], category=r["category"],
        name=r["name"], description=r["description"],
        status=r["status"], start_date=r["start_date"],
        end_date=r["end_date"], approved_by=r["approved_by"],
        approved_date=r["approved_date"], evidence=r["evidence"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student ID").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_profile_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    status = (payload.get("send_status") or DEFAULT_SEND_STATUS).strip()
    if status not in SEND_STATUSES:
        raise ValidationError(
            f"SEND status must be one of: {', '.join(SEND_STATUSES)}")
    out["send_status"] = status
    out["has_ehcp"] = bool(payload.get("has_ehcp"))
    if status == "EHCP":
        out["has_ehcp"] = True
    primary = (payload.get("primary_need") or "").strip()
    if primary and primary not in PRIMARY_NEEDS:
        raise ValidationError(
            f"Primary need must be one of: {', '.join(PRIMARY_NEEDS)}")
    out["primary_need"] = primary or None
    out["requires_pep"] = bool(payload.get("requires_pep"))
    out["ehcp_reference"]  = (payload.get("ehcp_reference") or "").strip() or None
    out["secondary_needs"] = (payload.get("secondary_needs") or "").strip() or None
    out["diagnoses"]       = (payload.get("diagnoses") or "").strip() or None
    out["mobility_aids"]   = (payload.get("mobility_aids") or "").strip() or None
    out["fire_evac_notes"] = (payload.get("fire_evac_notes") or "").strip() or None
    out["last_reviewed"]   = _validate_date(
        payload.get("last_reviewed"), "Last reviewed")
    out["next_review_due"] = _validate_date(
        payload.get("next_review_due"), "Next review due")
    out["reviewer"]        = (payload.get("reviewer") or "").strip() or None
    out["notes"]           = (payload.get("notes") or "").strip() or None
    return out


def _validate_accomm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    cat = (payload.get("category") or DEFAULT_ACCOMMODATION_CATEGORY).strip()
    if cat not in ACCOMMODATION_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: "
            f"{', '.join(ACCOMMODATION_CATEGORIES)}")
    out["category"] = cat
    out["name"] = _require(payload.get("name"), "Name").strip()
    status = (payload.get("status") or DEFAULT_ACCOMMODATION_STATUS).strip()
    if status not in ACCOMMODATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ACCOMMODATION_STATUSES)}")
    out["status"] = status
    out["start_date"] = _validate_date(
        payload.get("start_date"), "Start date")
    out["end_date"]   = _validate_date(
        payload.get("end_date"), "End date")
    if (out["start_date"] and out["end_date"]
            and out["end_date"] < out["start_date"]):
        raise ValidationError("End date cannot be before start date")
    out["approved_date"] = _validate_date(
        payload.get("approved_date"), "Approved date")
    out["description"] = (payload.get("description") or "").strip() or None
    out["approved_by"] = (payload.get("approved_by") or "").strip() or None
    out["evidence"]    = (payload.get("evidence") or "").strip() or None
    out["notes"]       = (payload.get("notes") or "").strip() or None
    return out


# ── Profile CRUD ──────────────────────────────────────────────────

def create_profile(payload: dict[str, Any]) -> Profile:
    init_db()
    p = _validate_profile_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM accessibility_profiles WHERE student_id = ?",
                (p["student_id"],)).fetchone():
            raise ValidationError(
                f"Student {p['student_id']} already has a profile — "
                "edit the existing one")
        cur = conn.execute(
            """INSERT INTO accessibility_profiles
                   (student_id, send_status, has_ehcp, ehcp_reference,
                    primary_need, secondary_needs, diagnoses,
                    mobility_aids, requires_pep, fire_evac_notes,
                    last_reviewed, next_review_due, reviewer, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["send_status"],
             1 if p["has_ehcp"] else 0, p["ehcp_reference"],
             p["primary_need"], p["secondary_needs"],
             p["diagnoses"], p["mobility_aids"],
             1 if p["requires_pep"] else 0, p["fire_evac_notes"],
             p["last_reviewed"], p["next_review_due"],
             p["reviewer"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_profile(new_id)
    assert out is not None
    logger.info("Created accessibility profile #%d for %s (status=%s)",
                new_id, p["student_id"], p["send_status"])
    return out


def get_profile(profile_id: int) -> Profile | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM accessibility_profiles WHERE profile_id = ?",
            (profile_id,)).fetchone()
        return _row_profile(r) if r else None


def get_profile_for_student(student_id: str) -> Profile | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM accessibility_profiles WHERE student_id = ?",
            (student_id.strip(),)).fetchone()
        return _row_profile(r) if r else None


def list_profiles(
    *,
    send_status: str | None = None,
    primary_need: str | None = None,
    ehcp_only: bool = False,
    review_overdue: bool = False,
) -> list[Profile]:
    init_db()
    clauses, args = [], []
    if send_status:
        if send_status not in SEND_STATUSES:
            raise ValidationError(
                f"SEND status must be one of: "
                f"{', '.join(SEND_STATUSES)}")
        clauses.append("send_status = ?")
        args.append(send_status)
    if primary_need:
        if primary_need not in PRIMARY_NEEDS:
            raise ValidationError(
                f"Primary need must be one of: "
                f"{', '.join(PRIMARY_NEEDS)}")
        clauses.append("primary_need = ?")
        args.append(primary_need)
    if ehcp_only:
        clauses.append("has_ehcp = 1")
    if review_overdue:
        clauses.append(
            "next_review_due IS NOT NULL AND next_review_due < ?")
        args.append(_dt.date.today().isoformat())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM accessibility_profiles {where} "
           "ORDER BY CASE send_status "
           "  WHEN 'EHCP'        THEN 0 "
           "  WHEN 'SEN Support' THEN 1 "
           "  WHEN 'Monitoring'  THEN 2 "
           "  WHEN 'Exited'      THEN 3 "
           "  ELSE 4 END, "
           "student_id ASC")
    with _connect() as conn:
        return [_row_profile(r) for r in conn.execute(sql, args).fetchall()]


def list_profiles_with_detail(**kwargs) -> list[ProfileRow]:
    rows = list_profiles(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    counts: dict[str, tuple[int, int]] = {}
    with _connect() as conn:
        for r in conn.execute(
                "SELECT student_id, "
                "  SUM(1) AS total, "
                "  SUM(CASE WHEN status='Active' THEN 1 ELSE 0 END) "
                "    AS active "
                "FROM accessibility_accommodations "
                "GROUP BY student_id").fetchall():
            counts[r["student_id"]] = (r["total"] or 0, r["active"] or 0)
    out: list[ProfileRow] = []
    for p in rows:
        tot, act = counts.get(p.student_id, (0, 0))
        out.append(ProfileRow(profile=p,
                                student_name=names.get(p.student_id, "(unknown)"),
                                accommodation_count=tot,
                                active_accommodation_count=act))
    return out


def update_profile(profile_id: int,
                   payload: dict[str, Any]) -> Profile:
    init_db()
    existing = get_profile(profile_id)
    if existing is None:
        raise ValidationError(f"No accessibility profile #{profile_id}")
    merged = {
        "student_id":      existing.student_id,
        "send_status":     payload.get("send_status", existing.send_status),
        "has_ehcp":        payload.get("has_ehcp", existing.has_ehcp),
        "ehcp_reference":  payload.get("ehcp_reference",
                                       existing.ehcp_reference),
        "primary_need":    payload.get("primary_need",
                                       existing.primary_need),
        "secondary_needs": payload.get("secondary_needs",
                                       existing.secondary_needs),
        "diagnoses":       payload.get("diagnoses", existing.diagnoses),
        "mobility_aids":   payload.get("mobility_aids",
                                       existing.mobility_aids),
        "requires_pep":    payload.get("requires_pep",
                                       existing.requires_pep),
        "fire_evac_notes": payload.get("fire_evac_notes",
                                       existing.fire_evac_notes),
        "last_reviewed":   payload.get("last_reviewed",
                                       existing.last_reviewed),
        "next_review_due": payload.get("next_review_due",
                                       existing.next_review_due),
        "reviewer":        payload.get("reviewer", existing.reviewer),
        "notes":           payload.get("notes", existing.notes),
    }
    p = _validate_profile_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE accessibility_profiles SET
                   send_status = ?, has_ehcp = ?, ehcp_reference = ?,
                   primary_need = ?, secondary_needs = ?, diagnoses = ?,
                   mobility_aids = ?, requires_pep = ?,
                   fire_evac_notes = ?, last_reviewed = ?,
                   next_review_due = ?, reviewer = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE profile_id = ?""",
            (p["send_status"], 1 if p["has_ehcp"] else 0,
             p["ehcp_reference"], p["primary_need"],
             p["secondary_needs"], p["diagnoses"], p["mobility_aids"],
             1 if p["requires_pep"] else 0, p["fire_evac_notes"],
             p["last_reviewed"], p["next_review_due"], p["reviewer"],
             p["notes"], profile_id),
        )
        conn.commit()
    out = get_profile(profile_id)
    assert out is not None
    logger.info("Updated accessibility profile #%d (status=%s)",
                profile_id, out.send_status)
    return out


def mark_reviewed(profile_id: int, *,
                  reviewer: str | None = None,
                  review_date: str | None = None,
                  next_review_due: str | None = None) -> Profile:
    payload: dict[str, Any] = {
        "last_reviewed": review_date or _dt.date.today().isoformat(),
    }
    if reviewer is not None:
        payload["reviewer"] = reviewer
    if next_review_due is not None:
        payload["next_review_due"] = next_review_due
    return update_profile(profile_id, payload)


def delete_profile(profile_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM accessibility_profiles WHERE profile_id = ?",
            (profile_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted accessibility profile #%d", profile_id)
            return True
        return False


# ── Accommodation CRUD ────────────────────────────────────────────

def create_accommodation(payload: dict[str, Any]) -> Accommodation:
    init_db()
    p = _validate_accomm_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO accessibility_accommodations
                   (student_id, category, name, description, status,
                    start_date, end_date, approved_by, approved_date,
                    evidence, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["category"], p["name"],
             p["description"], p["status"], p["start_date"],
             p["end_date"], p["approved_by"], p["approved_date"],
             p["evidence"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_accommodation(new_id)
    assert out is not None
    logger.info("Created accommodation #%d %r (%s) for %s",
                new_id, p["name"], p["category"], p["student_id"])
    return out


def get_accommodation(accommodation_id: int) -> Accommodation | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM accessibility_accommodations "
            "WHERE accommodation_id = ?",
            (accommodation_id,)).fetchone()
        return _row_accomm(r) if r else None


def list_accommodations(
    *,
    student_id: str | None = None,
    category: str | None = None,
    status: str | None = None,
    active_only: bool = False,
    name_like: str | None = None,
) -> list[Accommodation]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if category:
        if category not in ACCOMMODATION_CATEGORIES:
            raise ValidationError(
                f"Category must be one of: "
                f"{', '.join(ACCOMMODATION_CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if status:
        if status not in ACCOMMODATION_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(ACCOMMODATION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if active_only:
        clauses.append("status = 'Active'")
    if name_like:
        clauses.append("name LIKE ?")
        args.append(f"%{name_like.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM accessibility_accommodations {where} "
           "ORDER BY CASE category "
           "  WHEN 'Exam Access'           THEN 0 "
           "  WHEN 'Classroom'             THEN 1 "
           "  WHEN 'Physical / Building'   THEN 2 "
           "  WHEN 'Assistive Technology'  THEN 3 "
           "  WHEN 'Communication'         THEN 4 "
           "  WHEN 'Pastoral'              THEN 5 "
           "  ELSE 6 END, "
           "student_id ASC, name ASC")
    with _connect() as conn:
        return [_row_accomm(r) for r in conn.execute(sql, args).fetchall()]


def list_accommodations_with_detail(**kwargs) -> list[AccommodationRow]:
    rows = list_accommodations(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [AccommodationRow(accommodation=a,
                              student_name=names.get(a.student_id,
                                                      "(unknown)"))
            for a in rows]


def accommodations_for_student(student_id: str) -> list[Accommodation]:
    return list_accommodations(student_id=student_id)


def update_accommodation(accommodation_id: int,
                         payload: dict[str, Any]) -> Accommodation:
    init_db()
    existing = get_accommodation(accommodation_id)
    if existing is None:
        raise ValidationError(
            f"No accommodation #{accommodation_id}")
    merged = {
        "student_id":    existing.student_id,
        "category":      payload.get("category", existing.category),
        "name":          payload.get("name", existing.name),
        "description":   payload.get("description", existing.description),
        "status":        payload.get("status", existing.status),
        "start_date":    payload.get("start_date", existing.start_date),
        "end_date":      payload.get("end_date", existing.end_date),
        "approved_by":   payload.get("approved_by", existing.approved_by),
        "approved_date": payload.get("approved_date",
                                      existing.approved_date),
        "evidence":      payload.get("evidence", existing.evidence),
        "notes":         payload.get("notes", existing.notes),
    }
    p = _validate_accomm_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE accessibility_accommodations SET
                   category = ?, name = ?, description = ?, status = ?,
                   start_date = ?, end_date = ?, approved_by = ?,
                   approved_date = ?, evidence = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE accommodation_id = ?""",
            (p["category"], p["name"], p["description"], p["status"],
             p["start_date"], p["end_date"], p["approved_by"],
             p["approved_date"], p["evidence"], p["notes"],
             accommodation_id),
        )
        conn.commit()
    out = get_accommodation(accommodation_id)
    assert out is not None
    logger.info("Updated accommodation #%d (status=%s)",
                accommodation_id, out.status)
    return out


def set_accommodation_status(accommodation_id: int,
                             status: str) -> Accommodation:
    if status not in ACCOMMODATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ACCOMMODATION_STATUSES)}")
    return update_accommodation(accommodation_id, {"status": status})


def delete_accommodation(accommodation_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM accessibility_accommodations "
            "WHERE accommodation_id = ?",
            (accommodation_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted accommodation #%d", accommodation_id)
            return True
        return False


# ── Reports ───────────────────────────────────────────────────────

def exam_access_arrangements(*,
                              active_only: bool = True
                              ) -> list[AccommodationRow]:
    """JCQ-style listing: every exam-access arrangement with student
    name attached, ready to print for an exams officer."""
    return list_accommodations_with_detail(
        category="Exam Access",
        active_only=active_only,
    )


def summary(*, upcoming_window_days: int = 30) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()

    profiles = list_profiles()
    by_send = {s: 0 for s in SEND_STATUSES}
    by_need = {n: 0 for n in PRIMARY_NEEDS}
    ehcp = 0
    pep = 0
    overdue = 0
    upcoming = 0
    for p in profiles:
        by_send[p.send_status] = by_send.get(p.send_status, 0) + 1
        if p.primary_need:
            by_need[p.primary_need] = by_need.get(p.primary_need, 0) + 1
        if p.has_ehcp:
            ehcp += 1
        if p.requires_pep:
            pep += 1
        if p.next_review_due:
            if p.next_review_due < today:
                overdue += 1
            elif p.next_review_due <= horizon:
                upcoming += 1

    accs = list_accommodations()
    active = sum(1 for a in accs if a.is_current)
    by_cat = {c: 0 for c in ACCOMMODATION_CATEGORIES}
    for a in accs:
        by_cat[a.category] = by_cat.get(a.category, 0) + 1

    return Summary(
        student_count=len(profiles),
        by_send_status=by_send,
        by_primary_need=by_need,
        ehcp_count=ehcp,
        pep_count=pep,
        review_overdue=overdue,
        review_upcoming=upcoming,
        accommodation_count=len(accs),
        active_accommodation_count=active,
        by_category=by_cat,
    )
