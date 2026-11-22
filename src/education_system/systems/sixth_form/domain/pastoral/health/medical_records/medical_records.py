"""Medical Records data layer.

Four tables:

* ``med_profiles``      — one row per student (UNIQUE), with GP
                          practice, NHS number, blood group, emergency
                          contact, last-reviewed date, free-text notes.
* ``med_conditions``    — many per student: condition, severity,
                          diagnosed date, care-plan reference,
                          active/inactive.
* ``med_medications``   — many per student: name, dose, frequency,
                          route, start/end date, prescribed-by,
                          emergency flag, notes.
* ``med_allergies``     — many per student: allergen, severity,
                          reaction, EpiPen flag, notes.

Data is sensitive — auth gating happens upstream in the GUI / CLI
layers. The data layer itself only enforces shape and integrity.

Added on top (MEDICAL capability required in the data layer itself,
and every read/write goes to the sensitive-access log):

* ``med_healthcare_plans`` — individual healthcare plans (condition,
  triggers, actions, emergency procedure, review date, parent and
  clinician sign-off). Linking a plan to a condition fills that
  condition's ``care_plan_ref`` (``IHP-<id>``).
* ``med_administrations`` — medication administration log (medicine,
  dose, date/time, given by, witnessed by, stock after).
* ``med_stock`` — stock held in college per medication; each
  administration decrements it.

Cascade: deleting a student wipes profile + conditions + medications
+ allergies. Deleting a profile wipes the related rows (FK CASCADE).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.pastoral import _records

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_MEDICAL_RECORDS_DB

CONDITION_SEVERITIES: tuple[str, ...] = (
    "Mild", "Moderate", "Severe",
)
DEFAULT_CONDITION_SEVERITY: str = "Moderate"

ALLERGY_SEVERITIES: tuple[str, ...] = (
    "Mild", "Moderate", "Severe", "Life-threatening",
)
DEFAULT_ALLERGY_SEVERITY: str = "Moderate"

MEDICATION_ROUTES: tuple[str, ...] = (
    "Oral", "Inhaled", "Topical", "Injection",
    "Nasal", "Eye drops", "Other",
)
DEFAULT_MEDICATION_ROUTE: str = "Oral"

BLOOD_GROUPS: tuple[str, ...] = (
    "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NHS_RE = re.compile(r"^\d{3}\s?\d{3}\s?\d{4}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS med_profiles (
    profile_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          TEXT NOT NULL UNIQUE,
    nhs_number          TEXT,
    blood_group         TEXT,
    gp_name             TEXT,
    gp_practice         TEXT,
    gp_phone            TEXT,
    emergency_contact_name   TEXT,
    emergency_contact_phone  TEXT,
    emergency_contact_rel    TEXT,
    last_reviewed       TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS med_conditions (
    condition_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    name            TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'Moderate',
    diagnosed_date  TEXT,
    care_plan_ref   TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS med_medications (
    medication_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    name            TEXT NOT NULL,
    dose            TEXT,
    frequency       TEXT,
    route           TEXT NOT NULL DEFAULT 'Oral',
    start_date      TEXT,
    end_date        TEXT,
    prescribed_by   TEXT,
    is_emergency    INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS med_allergies (
    allergy_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    allergen        TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'Moderate',
    reaction        TEXT,
    has_epipen      INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_med_cond_student   ON med_conditions(student_id);
CREATE INDEX IF NOT EXISTS idx_med_cond_active    ON med_conditions(active);
CREATE INDEX IF NOT EXISTS idx_med_med_student    ON med_medications(student_id);
CREATE INDEX IF NOT EXISTS idx_med_med_emergency  ON med_medications(is_emergency);
CREATE INDEX IF NOT EXISTS idx_med_alg_student    ON med_allergies(student_id);
CREATE INDEX IF NOT EXISTS idx_med_alg_severity   ON med_allergies(severity);
"""


@dataclass
class MedicalProfile:
    profile_id: int
    student_id: str
    nhs_number: str | None
    blood_group: str | None
    gp_name: str | None
    gp_practice: str | None
    gp_phone: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_contact_rel: str | None
    last_reviewed: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Condition:
    condition_id: int
    student_id: str
    name: str
    severity: str
    diagnosed_date: str | None
    care_plan_ref: str | None
    active: bool
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Medication:
    medication_id: int
    student_id: str
    name: str
    dose: str | None
    frequency: str | None
    route: str
    start_date: str | None
    end_date: str | None
    prescribed_by: str | None
    is_emergency: bool
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Allergy:
    allergy_id: int
    student_id: str
    allergen: str
    severity: str
    reaction: str | None
    has_epipen: bool
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class StudentMedicalSummary:
    student_id: str
    student_name: str
    profile: MedicalProfile | None
    active_conditions: int
    severe_conditions: int
    current_medications: int
    emergency_medications: int
    allergies: int
    severe_allergies: int


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
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
        conn.executescript(_CARE_SCHEMA)
        conn.commit()
    logger.debug("Medical-records schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_profile(r: sqlite3.Row) -> MedicalProfile:
    return MedicalProfile(
        profile_id=r["profile_id"], student_id=r["student_id"],
        nhs_number=r["nhs_number"], blood_group=r["blood_group"],
        gp_name=r["gp_name"], gp_practice=r["gp_practice"],
        gp_phone=r["gp_phone"],
        emergency_contact_name=r["emergency_contact_name"],
        emergency_contact_phone=r["emergency_contact_phone"],
        emergency_contact_rel=r["emergency_contact_rel"],
        last_reviewed=r["last_reviewed"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_condition(r: sqlite3.Row) -> Condition:
    return Condition(
        condition_id=r["condition_id"], student_id=r["student_id"],
        name=r["name"], severity=r["severity"],
        diagnosed_date=r["diagnosed_date"],
        care_plan_ref=r["care_plan_ref"],
        active=bool(r["active"]), notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_medication(r: sqlite3.Row) -> Medication:
    return Medication(
        medication_id=r["medication_id"], student_id=r["student_id"],
        name=r["name"], dose=r["dose"], frequency=r["frequency"],
        route=r["route"], start_date=r["start_date"],
        end_date=r["end_date"], prescribed_by=r["prescribed_by"],
        is_emergency=bool(r["is_emergency"]), notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_allergy(r: sqlite3.Row) -> Allergy:
    return Allergy(
        allergy_id=r["allergy_id"], student_id=r["student_id"],
        allergen=r["allergen"], severity=r["severity"],
        reaction=r["reaction"], has_epipen=bool(r["has_epipen"]),
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid medical-records input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real calendar date") from None
    return s


def _coerce_bool(v: Any) -> int:
    if isinstance(v, bool):
        return 1 if v else 0
    if v in (None, ""):
        return 0
    s = str(v).strip().lower()
    if s in ("1", "y", "yes", "true", "t"):
        return 1
    if s in ("0", "n", "no", "false", "f"):
        return 0
    raise ValidationError(f"Expected yes/no, got {v!r}")


def _validate_student(sid: str) -> str:
    sid = sid.strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_profile_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(
        _require(data.get("student_id"), "Student ID"))

    nhs = (data.get("nhs_number") or "").strip()
    if nhs:
        compact = re.sub(r"\s+", "", nhs)
        if not _NHS_RE.match(nhs) and not re.match(r"^\d{10}$", compact):
            raise ValidationError(
                "NHS number must be 10 digits (e.g. 943 476 5919)")
        out["nhs_number"] = nhs
    else:
        out["nhs_number"] = None

    bg = (data.get("blood_group") or "").strip() or None
    if bg is not None and bg not in BLOOD_GROUPS:
        raise ValidationError(
            f"Blood group must be one of: {', '.join(BLOOD_GROUPS)}")
    out["blood_group"] = bg

    out["last_reviewed"] = _validate_date(
        data.get("last_reviewed"), "Last reviewed")

    for field in ("gp_name", "gp_practice", "gp_phone",
                   "emergency_contact_name", "emergency_contact_phone",
                   "emergency_contact_rel", "notes"):
        out[field] = (data.get(field) or "").strip() or None
    return out


def _validate_condition_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(
        _require(data.get("student_id"), "Student ID"))
    out["name"] = _require(data.get("name"), "Condition name").strip()
    sev = (data.get("severity") or DEFAULT_CONDITION_SEVERITY).strip()
    if sev not in CONDITION_SEVERITIES:
        raise ValidationError(
            f"Severity must be one of: {', '.join(CONDITION_SEVERITIES)}")
    out["severity"] = sev
    out["diagnosed_date"] = _validate_date(
        data.get("diagnosed_date"), "Diagnosed date")
    out["care_plan_ref"] = (data.get("care_plan_ref") or "").strip() or None
    out["active"] = _coerce_bool(data.get("active", True))
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _validate_medication_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(
        _require(data.get("student_id"), "Student ID"))
    out["name"] = _require(data.get("name"), "Medication name").strip()
    route = (data.get("route") or DEFAULT_MEDICATION_ROUTE).strip()
    if route not in MEDICATION_ROUTES:
        raise ValidationError(
            f"Route must be one of: {', '.join(MEDICATION_ROUTES)}")
    out["route"] = route
    start = _validate_date(data.get("start_date"), "Start date")
    end   = _validate_date(data.get("end_date"), "End date")
    if start and end and start > end:
        raise ValidationError("End date must be on or after start date")
    out["start_date"] = start
    out["end_date"]   = end
    out["is_emergency"] = _coerce_bool(data.get("is_emergency"))
    for field in ("dose", "frequency", "prescribed_by", "notes"):
        out[field] = (data.get(field) or "").strip() or None
    return out


def _validate_allergy_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(
        _require(data.get("student_id"), "Student ID"))
    out["allergen"] = _require(data.get("allergen"), "Allergen").strip()
    sev = (data.get("severity") or DEFAULT_ALLERGY_SEVERITY).strip()
    if sev not in ALLERGY_SEVERITIES:
        raise ValidationError(
            f"Severity must be one of: {', '.join(ALLERGY_SEVERITIES)}")
    out["severity"] = sev
    out["has_epipen"] = _coerce_bool(data.get("has_epipen"))
    out["reaction"] = (data.get("reaction") or "").strip() or None
    out["notes"]    = (data.get("notes") or "").strip() or None
    return out


# ── Profile CRUD (upsert per student) ────────────────────────────

def save_profile(data: dict[str, Any]) -> MedicalProfile:
    init_db()
    p = _validate_profile_payload(data)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO med_profiles
                   (student_id, nhs_number, blood_group,
                    gp_name, gp_practice, gp_phone,
                    emergency_contact_name, emergency_contact_phone,
                    emergency_contact_rel, last_reviewed, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT(student_id) DO UPDATE SET
                   nhs_number              = excluded.nhs_number,
                   blood_group             = excluded.blood_group,
                   gp_name                 = excluded.gp_name,
                   gp_practice             = excluded.gp_practice,
                   gp_phone                = excluded.gp_phone,
                   emergency_contact_name  = excluded.emergency_contact_name,
                   emergency_contact_phone = excluded.emergency_contact_phone,
                   emergency_contact_rel   = excluded.emergency_contact_rel,
                   last_reviewed           = excluded.last_reviewed,
                   notes                   = excluded.notes,
                   updated_at              = datetime('now')""",
            (p["student_id"], p["nhs_number"], p["blood_group"],
             p["gp_name"], p["gp_practice"], p["gp_phone"],
             p["emergency_contact_name"], p["emergency_contact_phone"],
             p["emergency_contact_rel"], p["last_reviewed"],
             p["notes"]),
        )
        conn.commit()
        r = conn.execute(
            "SELECT * FROM med_profiles WHERE student_id = ?",
            (p["student_id"],),
        ).fetchone()
    assert r is not None
    out = _row_profile(r)
    logger.info("Saved medical profile for %s", out.student_id)
    return out


def get_profile(student_id: str) -> MedicalProfile | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM med_profiles WHERE student_id = ?",
            (student_id.strip(),),
        ).fetchone()
        return _row_profile(r) if r else None


def delete_profile(student_id: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM med_profiles WHERE student_id = ?",
            (student_id.strip(),),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted medical profile for %s", student_id)
            return True
        return False


# ── Conditions CRUD ──────────────────────────────────────────────

def create_condition(data: dict[str, Any]) -> Condition:
    init_db()
    p = _validate_condition_payload(data)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO med_conditions
                   (student_id, name, severity, diagnosed_date,
                    care_plan_ref, active, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["name"], p["severity"],
             p["diagnosed_date"], p["care_plan_ref"], p["active"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_condition(new_id)
    assert out is not None
    logger.info(
        "Added condition #%d for %s: %s (%s)",
        new_id, p["student_id"], p["name"], p["severity"],
    )
    return out


def get_condition(condition_id: int) -> Condition | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM med_conditions WHERE condition_id = ?",
            (condition_id,),
        ).fetchone()
        return _row_condition(r) if r else None


def list_conditions(
    *,
    student_id: str | None = None,
    active_only: bool = False,
    severity: str | None = None,
) -> list[Condition]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if active_only:
        clauses.append("active = 1")
    if severity:
        if severity not in CONDITION_SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(CONDITION_SEVERITIES)}")
        clauses.append("severity = ?")
        args.append(severity)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM med_conditions {where} "
           "ORDER BY active DESC, severity DESC, name COLLATE NOCASE")
    with _connect() as conn:
        return [_row_condition(r)
                for r in conn.execute(sql, args).fetchall()]


def update_condition(condition_id: int,
                      data: dict[str, Any]) -> Condition:
    init_db()
    existing = get_condition(condition_id)
    if existing is None:
        raise ValidationError(f"No condition with id {condition_id}")
    p = _validate_condition_payload({
        "student_id":     existing.student_id,
        "name":           data.get("name", existing.name),
        "severity":       data.get("severity", existing.severity),
        "diagnosed_date": data.get("diagnosed_date",
                                     existing.diagnosed_date),
        "care_plan_ref":  data.get("care_plan_ref",
                                     existing.care_plan_ref),
        "active":         data.get("active", existing.active),
        "notes":          data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE med_conditions SET
                   name = ?, severity = ?, diagnosed_date = ?,
                   care_plan_ref = ?, active = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE condition_id = ?""",
            (p["name"], p["severity"], p["diagnosed_date"],
             p["care_plan_ref"], p["active"], p["notes"],
             condition_id),
        )
        conn.commit()
    out = get_condition(condition_id)
    assert out is not None
    logger.info("Updated condition #%d (active=%s)",
                condition_id, out.active)
    return out


def delete_condition(condition_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM med_conditions WHERE condition_id = ?",
            (condition_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted condition #%d", condition_id)
            return True
        return False


# ── Medications CRUD ─────────────────────────────────────────────

def create_medication(data: dict[str, Any]) -> Medication:
    init_db()
    p = _validate_medication_payload(data)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO med_medications
                   (student_id, name, dose, frequency, route,
                    start_date, end_date, prescribed_by,
                    is_emergency, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["name"], p["dose"], p["frequency"],
             p["route"], p["start_date"], p["end_date"],
             p["prescribed_by"], p["is_emergency"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_medication(new_id)
    assert out is not None
    logger.info(
        "Added medication #%d for %s: %s (route=%s, emergency=%s)",
        new_id, p["student_id"], p["name"], p["route"],
        bool(p["is_emergency"]),
    )
    return out


def get_medication(medication_id: int) -> Medication | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM med_medications WHERE medication_id = ?",
            (medication_id,),
        ).fetchone()
        return _row_medication(r) if r else None


def list_medications(
    *,
    student_id: str | None = None,
    emergency_only: bool = False,
    active_on: str | None = None,
) -> list[Medication]:
    """List medications. ``active_on`` filters to meds where the
    period (start..end) brackets that date — both bounds inclusive,
    and missing bounds mean "open-ended".
    """
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if emergency_only:
        clauses.append("is_emergency = 1")
    if active_on:
        d = _validate_date(active_on, "active_on")
        clauses.append("(start_date IS NULL OR start_date <= ?)")
        args.append(d)
        clauses.append("(end_date   IS NULL OR end_date   >= ?)")
        args.append(d)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM med_medications {where} "
           "ORDER BY is_emergency DESC, name COLLATE NOCASE")
    with _connect() as conn:
        return [_row_medication(r)
                for r in conn.execute(sql, args).fetchall()]


def update_medication(medication_id: int,
                       data: dict[str, Any]) -> Medication:
    init_db()
    existing = get_medication(medication_id)
    if existing is None:
        raise ValidationError(f"No medication with id {medication_id}")
    p = _validate_medication_payload({
        "student_id":     existing.student_id,
        "name":           data.get("name", existing.name),
        "dose":           data.get("dose", existing.dose),
        "frequency":      data.get("frequency", existing.frequency),
        "route":          data.get("route", existing.route),
        "start_date":     data.get("start_date", existing.start_date),
        "end_date":       data.get("end_date", existing.end_date),
        "prescribed_by":  data.get("prescribed_by",
                                     existing.prescribed_by),
        "is_emergency":   data.get("is_emergency",
                                     existing.is_emergency),
        "notes":          data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE med_medications SET
                   name = ?, dose = ?, frequency = ?, route = ?,
                   start_date = ?, end_date = ?, prescribed_by = ?,
                   is_emergency = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE medication_id = ?""",
            (p["name"], p["dose"], p["frequency"], p["route"],
             p["start_date"], p["end_date"], p["prescribed_by"],
             p["is_emergency"], p["notes"], medication_id),
        )
        conn.commit()
    out = get_medication(medication_id)
    assert out is not None
    logger.info("Updated medication #%d (%s)", medication_id, out.name)
    return out


def delete_medication(medication_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM med_medications WHERE medication_id = ?",
            (medication_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted medication #%d", medication_id)
            return True
        return False


# ── Allergies CRUD ───────────────────────────────────────────────

def create_allergy(data: dict[str, Any]) -> Allergy:
    init_db()
    p = _validate_allergy_payload(data)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO med_allergies
                   (student_id, allergen, severity, reaction,
                    has_epipen, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["allergen"], p["severity"],
             p["reaction"], p["has_epipen"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_allergy(new_id)
    assert out is not None
    logger.info(
        "Added allergy #%d for %s: %s (%s, epipen=%s)",
        new_id, p["student_id"], p["allergen"], p["severity"],
        bool(p["has_epipen"]),
    )
    return out


def get_allergy(allergy_id: int) -> Allergy | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM med_allergies WHERE allergy_id = ?",
            (allergy_id,),
        ).fetchone()
        return _row_allergy(r) if r else None


def list_allergies(
    *,
    student_id: str | None = None,
    severity: str | None = None,
    epipen_only: bool = False,
) -> list[Allergy]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if severity:
        if severity not in ALLERGY_SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(ALLERGY_SEVERITIES)}")
        clauses.append("severity = ?")
        args.append(severity)
    if epipen_only:
        clauses.append("has_epipen = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    # Severe / life-threatening first.
    sev_order = " ".join(
        f"WHEN '{s}' THEN {i}"
        for i, s in enumerate(reversed(ALLERGY_SEVERITIES)))
    sql = (f"SELECT * FROM med_allergies {where} "
           f"ORDER BY CASE severity {sev_order} END, "
           "allergen COLLATE NOCASE")
    with _connect() as conn:
        return [_row_allergy(r)
                for r in conn.execute(sql, args).fetchall()]


def update_allergy(allergy_id: int, data: dict[str, Any]) -> Allergy:
    init_db()
    existing = get_allergy(allergy_id)
    if existing is None:
        raise ValidationError(f"No allergy with id {allergy_id}")
    p = _validate_allergy_payload({
        "student_id": existing.student_id,
        "allergen":   data.get("allergen", existing.allergen),
        "severity":   data.get("severity", existing.severity),
        "reaction":   data.get("reaction", existing.reaction),
        "has_epipen": data.get("has_epipen", existing.has_epipen),
        "notes":      data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE med_allergies SET
                   allergen = ?, severity = ?, reaction = ?,
                   has_epipen = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE allergy_id = ?""",
            (p["allergen"], p["severity"], p["reaction"],
             p["has_epipen"], p["notes"], allergy_id),
        )
        conn.commit()
    out = get_allergy(allergy_id)
    assert out is not None
    logger.info("Updated allergy #%d (%s, %s)",
                allergy_id, out.allergen, out.severity)
    return out


def delete_allergy(allergy_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM med_allergies WHERE allergy_id = ?",
            (allergy_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted allergy #%d", allergy_id)
            return True
        return False


# ── Aggregates ──────────────────────────────────────────────────

def summary_for_student(student_id: str) -> StudentMedicalSummary:
    init_db()
    sid = _validate_student(student_id)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = _students.get_student(sid)
    name = getattr(s, "full_name", None) or sid
    today = _dt.date.today().isoformat()
    conditions = list_conditions(student_id=sid)
    meds = list_medications(student_id=sid, active_on=today)
    allergies = list_allergies(student_id=sid)
    return StudentMedicalSummary(
        student_id=sid,
        student_name=name,
        profile=get_profile(sid),
        active_conditions=sum(1 for c in conditions if c.active),
        severe_conditions=sum(1 for c in conditions
                                if c.active and c.severity == "Severe"),
        current_medications=len(meds),
        emergency_medications=sum(1 for m in meds if m.is_emergency),
        allergies=len(allergies),
        severe_allergies=sum(1 for a in allergies
                               if a.severity in ("Severe",
                                                  "Life-threatening")),
    )


def all_student_summaries() -> list[StudentMedicalSummary]:
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return [summary_for_student(s.student_id)
            for s in _students.list_students()]


@dataclass
class MedicalSummary:
    total_profiles: int
    total_conditions: int
    severe_conditions: int
    total_medications: int
    emergency_medications: int
    total_allergies: int
    severe_allergies: int
    epipen_holders: int
    students_with_flag: int    # students with anything severe/life-threat


def summary() -> MedicalSummary:
    init_db()
    with _connect() as conn:
        profiles = int(conn.execute(
            "SELECT COUNT(*) AS n FROM med_profiles"
        ).fetchone()["n"])
        total_cond = int(conn.execute(
            "SELECT COUNT(*) AS n FROM med_conditions"
        ).fetchone()["n"])
        severe_cond = int(conn.execute(
            "SELECT COUNT(*) AS n FROM med_conditions "
            "WHERE active = 1 AND severity = 'Severe'"
        ).fetchone()["n"])
        total_meds = int(conn.execute(
            "SELECT COUNT(*) AS n FROM med_medications"
        ).fetchone()["n"])
        emergency_meds = int(conn.execute(
            "SELECT COUNT(*) AS n FROM med_medications "
            "WHERE is_emergency = 1"
        ).fetchone()["n"])
        total_alg = int(conn.execute(
            "SELECT COUNT(*) AS n FROM med_allergies"
        ).fetchone()["n"])
        severe_alg = int(conn.execute(
            "SELECT COUNT(*) AS n FROM med_allergies "
            "WHERE severity IN ('Severe', 'Life-threatening')"
        ).fetchone()["n"])
        epipens = int(conn.execute(
            "SELECT COUNT(DISTINCT student_id) AS n "
            "FROM med_allergies WHERE has_epipen = 1"
        ).fetchone()["n"])
        flagged = int(conn.execute(
            """SELECT COUNT(DISTINCT student_id) AS n FROM (
                   SELECT student_id FROM med_conditions
                       WHERE active = 1 AND severity = 'Severe'
                   UNION
                   SELECT student_id FROM med_allergies
                       WHERE severity IN ('Severe', 'Life-threatening')
                   UNION
                   SELECT student_id FROM med_medications
                       WHERE is_emergency = 1
               )"""
        ).fetchone()["n"])
    return MedicalSummary(
        total_profiles=profiles,
        total_conditions=total_cond,
        severe_conditions=severe_cond,
        total_medications=total_meds,
        emergency_medications=emergency_meds,
        total_allergies=total_alg,
        severe_allergies=severe_alg,
        epipen_holders=epipens,
        students_with_flag=flagged,
    )


# ══ Individual healthcare plans, administration log, stock ════════

PLAN_STATUSES: tuple[str, ...] = (
    "Draft", "Active", "Under Review", "Archived",
)
ADMIN_OUTCOMES: tuple[str, ...] = (
    "Given", "Refused", "Not available", "Self-administered (supervised)",
    "Vomited / spat out",
)

_CARE_SCHEMA = """
CREATE TABLE IF NOT EXISTS med_healthcare_plans (
    plan_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id           TEXT NOT NULL,
    condition_id         INTEGER,
    condition_name       TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'Draft',
    triggers             TEXT,
    symptoms             TEXT,
    daily_care           TEXT,
    actions              TEXT,
    emergency_procedure  TEXT NOT NULL,
    medication_notes     TEXT,
    staff_training       TEXT,
    plan_start           TEXT,
    review_date          TEXT,
    last_reviewed        TEXT,
    parent_signed_name   TEXT,
    parent_signed_on     TEXT,
    clinician_name       TEXT,
    clinician_role       TEXT,
    clinician_signed_on  TEXT,
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (condition_id) REFERENCES med_conditions(condition_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS med_stock (
    stock_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    medication_id  INTEGER NOT NULL UNIQUE,
    student_id     TEXT NOT NULL,
    quantity       INTEGER NOT NULL DEFAULT 0,
    unit           TEXT,
    location       TEXT,
    expiry_date    TEXT,
    reorder_level  INTEGER,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (medication_id) REFERENCES med_medications(medication_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS med_administrations (
    admin_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    medication_id     INTEGER,
    medicine          TEXT NOT NULL,
    dose              TEXT NOT NULL,
    administered_on   TEXT NOT NULL,
    administered_time TEXT NOT NULL,
    outcome           TEXT NOT NULL DEFAULT 'Given',
    quantity_used     INTEGER NOT NULL DEFAULT 1,
    given_by          TEXT NOT NULL,
    witnessed_by      TEXT,
    reason            TEXT,
    stock_after       INTEGER,
    parent_informed   INTEGER NOT NULL DEFAULT 0,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (medication_id) REFERENCES med_medications(medication_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_med_ihp_student  ON med_healthcare_plans(student_id);
CREATE INDEX IF NOT EXISTS idx_med_ihp_review   ON med_healthcare_plans(review_date);
CREATE INDEX IF NOT EXISTS idx_med_adm_student  ON med_administrations(student_id);
CREATE INDEX IF NOT EXISTS idx_med_adm_on       ON med_administrations(administered_on);
"""


@dataclass
class HealthcarePlan:
    plan_id: int
    student_id: str
    condition_id: int | None
    condition_name: str
    status: str
    triggers: str | None
    symptoms: str | None
    daily_care: str | None
    actions: str | None
    emergency_procedure: str
    medication_notes: str | None
    staff_training: str | None
    plan_start: str | None
    review_date: str | None
    last_reviewed: str | None
    parent_signed_name: str | None
    parent_signed_on: str | None
    clinician_name: str | None
    clinician_role: str | None
    clinician_signed_on: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def review_overdue(self) -> bool:
        return bool(self.status != "Archived" and self.review_date
                    and self.review_date < _records.today())

    @property
    def signed_off(self) -> bool:
        return bool(self.parent_signed_on and self.clinician_signed_on)


@dataclass
class StockItem:
    stock_id: int
    medication_id: int
    student_id: str
    quantity: int
    unit: str | None
    location: str | None
    expiry_date: str | None
    reorder_level: int | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def low(self) -> bool:
        return self.reorder_level is not None \
            and self.quantity <= self.reorder_level

    @property
    def expired(self) -> bool:
        return bool(self.expiry_date
                    and self.expiry_date < _records.today())


@dataclass
class Administration:
    admin_id: int
    student_id: str
    medication_id: int | None
    medicine: str
    dose: str
    administered_on: str
    administered_time: str
    outcome: str
    quantity_used: int
    given_by: str
    witnessed_by: str | None
    reason: str | None
    stock_after: int | None
    parent_informed: bool
    notes: str | None
    created_at: str | None
    updated_at: str | None


def _now_hhmm() -> str:
    return _dt.datetime.now().strftime("%H:%M")


_C = _records.Col

PLAN_SPEC = _records.TableSpec(
    table="med_healthcare_plans", id_col="plan_id", row_type=HealthcarePlan,
    label="Healthcare plan",
    order_by="status = 'Archived', review_date IS NULL, review_date",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("condition_id", "Linked condition #", "int", listed=False),
        _C("condition_name", "Condition", required=True),
        _C("status", "Status", "choice", choices=PLAN_STATUSES,
           default="Draft"),
        _C("triggers", "Triggers", "multiline", listed=False),
        _C("symptoms", "Signs / symptoms", "multiline", listed=False),
        _C("daily_care", "Daily care requirements", "multiline",
           listed=False),
        _C("actions", "Actions to take", "multiline", listed=False),
        _C("emergency_procedure", "Emergency procedure", "multiline",
           required=True, listed=False),
        _C("medication_notes", "Medication", "multiline", listed=False),
        _C("staff_training", "Staff training needed", "multiline",
           listed=False),
        _C("plan_start", "Plan start", "date", listed=False),
        _C("review_date", "Review date", "date"),
        _C("last_reviewed", "Last reviewed", "date"),
        _C("parent_signed_name", "Parent / carer signed (name)"),
        _C("parent_signed_on", "Parent signed on", "date"),
        _C("clinician_name", "Clinician", listed=False),
        _C("clinician_role", "Clinician role", listed=False),
        _C("clinician_signed_on", "Clinician signed on", "date"),
        _C("notes", "Notes", "multiline", listed=False),
    ))

STOCK_SPEC = _records.TableSpec(
    table="med_stock", id_col="stock_id", row_type=StockItem,
    label="Medication stock", order_by="student_id, medication_id",
    cols=(
        _C("medication_id", "Medication #", "int", required=True,
           fixed=True),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("quantity", "Quantity in stock", "int", required=True,
           min_value=0),
        _C("unit", "Unit (tablets, doses …)"),
        _C("location", "Stored at"),
        _C("expiry_date", "Expiry", "date"),
        _C("reorder_level", "Re-order at", "int", min_value=0),
        _C("notes", "Notes", "multiline", listed=False),
    ))

ADMIN_SPEC = _records.TableSpec(
    table="med_administrations", id_col="admin_id", row_type=Administration,
    label="Medication administration",
    order_by="administered_on DESC, administered_time DESC, admin_id DESC",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("medication_id", "Medication # (blank = not on record)", "int",
           listed=False),
        _C("medicine", "Medicine"),
        _C("dose", "Dose", required=True),
        _C("administered_on", "Date", "date", required=True,
           default=_records.today),
        _C("administered_time", "Time", "time", required=True,
           default=_now_hhmm),
        _C("outcome", "Outcome", "choice", choices=ADMIN_OUTCOMES,
           default="Given"),
        _C("quantity_used", "Quantity used", "int", default=1,
           min_value=0, listed=False),
        _C("given_by", "Given by"),
        _C("witnessed_by", "Witnessed by"),
        _C("reason", "Reason", listed=False),
        _C("stock_after", "Stock after", "int", fixed=True, hidden=True),
        _C("parent_informed", "Parent informed", "bool"),
        _C("notes", "Notes", "multiline", listed=False),
    ))


def _student_ok(sid: str) -> bool:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return _students.get_student(sid) is not None


def _med_guard(action: str, student_id: str | None = None,
               ref: str | None = None) -> Any:
    return _records.guard("MEDICAL", "medical", action,
                          student_id=student_id, record_ref=ref)


# ── Healthcare plans ──────────────────────────────────────────────

def _plan_rules(conn: sqlite3.Connection, p: dict[str, Any]) -> None:
    if p["condition_id"] is not None:
        c = conn.execute(
            "SELECT student_id, name FROM med_conditions "
            "WHERE condition_id = ?", (p["condition_id"],)).fetchone()
        if c is None:
            raise ValidationError(f"No condition #{p['condition_id']}")
        if c["student_id"] != p["student_id"]:
            raise ValidationError(
                f"Condition #{p['condition_id']} belongs to another student")
    if p["status"] == "Active" and not p["review_date"]:
        raise ValidationError("An active plan needs a review date")
    if p["plan_start"] and p["review_date"] \
            and p["review_date"] < p["plan_start"]:
        raise ValidationError("Review date cannot be before the plan start")
    if p["parent_signed_on"] and not p["parent_signed_name"]:
        raise ValidationError("Give the name of the parent/carer who signed")


def _link_care_plan_ref(conn: sqlite3.Connection, plan_id: int,
                        condition_id: int | None) -> None:
    if condition_id is None:
        return
    conn.execute(
        "UPDATE med_conditions SET care_plan_ref = ?, "
        "updated_at = datetime('now') WHERE condition_id = ? "
        "AND (care_plan_ref IS NULL OR care_plan_ref = '' "
        "     OR care_plan_ref LIKE 'IHP-%')",
        (f"IHP-{plan_id}", condition_id))


def create_healthcare_plan(data: dict[str, Any]) -> HealthcarePlan:
    init_db()
    p = _records.validate(PLAN_SPEC, data, error=ValidationError,
                          student_exists=_student_ok)
    _med_guard("create healthcare plan", p["student_id"])
    with _connect() as conn:
        _plan_rules(conn, p)
        new_id = _records.insert(conn, PLAN_SPEC, p)
        _link_care_plan_ref(conn, new_id, p["condition_id"])
        conn.commit()
        out = _records.fetch(conn, PLAN_SPEC, new_id)
    logger.info("Created healthcare plan #%d for %s (%s)", new_id,
                p["student_id"], p["condition_name"])
    return out


def get_healthcare_plan(plan_id: int) -> HealthcarePlan | None:
    init_db()
    with _connect() as conn:
        out = _records.fetch(conn, PLAN_SPEC, plan_id)
    if out is not None:
        _med_guard("view healthcare plan", out.student_id, f"ihp:{plan_id}")
    return out


def list_healthcare_plans(*, student_id: str | None = None,
                          status: str | None = None,
                          include_archived: bool = True
                          ) -> list[HealthcarePlan]:
    init_db()
    _med_guard("list healthcare plans", student_id)
    where = [] if include_archived else ["status <> 'Archived'"]
    with _connect() as conn:
        rows = _records.select(conn, PLAN_SPEC, equals={
            "student_id": student_id, "status": status}, where=where)
    return _records.visible_filter("MEDICAL", rows)


def update_healthcare_plan(plan_id: int,
                           data: dict[str, Any]) -> HealthcarePlan:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, PLAN_SPEC, plan_id)
    if existing is None:
        raise ValidationError(f"No healthcare plan #{plan_id}")
    p = _records.validate(PLAN_SPEC, data, error=ValidationError,
                          existing=existing, student_exists=_student_ok)
    _med_guard("update healthcare plan", existing.student_id,
               f"ihp:{plan_id}")
    with _connect() as conn:
        _plan_rules(conn, p)
        _records.update(conn, PLAN_SPEC, plan_id, p)
        _link_care_plan_ref(conn, plan_id, p["condition_id"])
        conn.commit()
        return _records.fetch(conn, PLAN_SPEC, plan_id)


def review_healthcare_plan(plan_id: int, *,
                           reviewed_on: str | None = None,
                           next_review: str,
                           notes: str | None = None) -> HealthcarePlan:
    """Record a plan review: stamps last_reviewed, sets the next review
    date and returns the plan to Active."""
    on = _records.check_date(reviewed_on, "Reviewed on",
                             ValidationError) or _records.today()
    nxt = _records.check_date(next_review, "Next review", ValidationError)
    if not nxt or nxt <= on:
        raise ValidationError("Next review must be a date after the review")
    plan = get_healthcare_plan(plan_id)
    if plan is None:
        raise ValidationError(f"No healthcare plan #{plan_id}")
    payload: dict[str, Any] = {"last_reviewed": on, "review_date": nxt,
                               "status": "Active"}
    if notes and notes.strip():
        line = f"[{on} review] {notes.strip()}"
        payload["notes"] = f"{plan.notes}\n{line}" if plan.notes else line
    return update_healthcare_plan(plan_id, payload)


def sign_off_healthcare_plan(plan_id: int, *, who: str,
                             name: str, role: str | None = None,
                             signed_on: str | None = None
                             ) -> HealthcarePlan:
    """Record parent (``who='parent'``) or clinician sign-off."""
    on = _records.check_date(signed_on, "Signed on",
                             ValidationError) or _records.today()
    if not (name or "").strip():
        raise ValidationError("Name is required")
    if who == "parent":
        payload = {"parent_signed_name": name.strip(),
                   "parent_signed_on": on}
    elif who == "clinician":
        payload = {"clinician_name": name.strip(),
                   "clinician_role": (role or "").strip() or None,
                   "clinician_signed_on": on}
    else:
        raise ValidationError("Sign-off must be by 'parent' or 'clinician'")
    return update_healthcare_plan(plan_id, payload)


def delete_healthcare_plan(plan_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, PLAN_SPEC, plan_id)
        if existing is None:
            return False
        _med_guard("delete healthcare plan", existing.student_id,
                   f"ihp:{plan_id}")
        if existing.condition_id is not None:
            conn.execute(
                "UPDATE med_conditions SET care_plan_ref = NULL "
                "WHERE condition_id = ? AND care_plan_ref = ?",
                (existing.condition_id, f"IHP-{plan_id}"))
        ok = _records.delete(conn, PLAN_SPEC, plan_id)
        conn.commit()
        return ok


@dataclass
class PlanAttention:
    plan: HealthcarePlan
    student_name: str
    problems: list[str]


def plans_needing_attention(*, within_days: int = 0) -> list[PlanAttention]:
    """Non-archived plans whose review is overdue (or due within
    *within_days*), or that lack parent / clinician sign-off; plus
    severe active conditions with no plan at all (reported with a
    placeholder plan id 0)."""
    init_db()
    _med_guard("list plans needing attention")
    horizon = (_dt.date.today()
               + _dt.timedelta(days=within_days)).isoformat()
    today = _records.today()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    out: list[PlanAttention] = []
    with _connect() as conn:
        plans = _records.select(conn, PLAN_SPEC,
                                where=["status <> 'Archived'"])
        uncovered = conn.execute(
            """SELECT c.* FROM med_conditions c
                WHERE c.active = 1 AND c.severity = 'Severe'
                  AND NOT EXISTS (
                      SELECT 1 FROM med_healthcare_plans h
                       WHERE h.status <> 'Archived'
                         AND (h.condition_id = c.condition_id
                              OR (h.student_id = c.student_id
                                  AND lower(h.condition_name)
                                      = lower(c.name))))
                ORDER BY c.student_id""").fetchall()
    for pl in plans:
        problems = []
        if not pl.review_date:
            problems.append("no review date")
        elif pl.review_date < today:
            problems.append(f"review overdue since {pl.review_date}")
        elif pl.review_date <= horizon:
            problems.append(f"review due {pl.review_date}")
        if not pl.parent_signed_on:
            problems.append("no parent/carer sign-off")
        if not pl.clinician_signed_on:
            problems.append("no clinician sign-off")
        if problems:
            out.append(PlanAttention(pl, names.get(pl.student_id, "?"),
                                     problems))
    for c in uncovered:
        placeholder = HealthcarePlan(
            plan_id=0, student_id=c["student_id"],
            condition_id=c["condition_id"], condition_name=c["name"],
            status="(none)", triggers=None, symptoms=None, daily_care=None,
            actions=None, emergency_procedure="", medication_notes=None,
            staff_training=None, plan_start=None, review_date=None,
            last_reviewed=None, parent_signed_name=None,
            parent_signed_on=None, clinician_name=None, clinician_role=None,
            clinician_signed_on=None, notes=None, created_at=None,
            updated_at=None)
        out.append(PlanAttention(placeholder,
                                 names.get(c["student_id"], "?"),
                                 ["severe condition has no healthcare plan"]))
    visible = {x.student_id for x in _records.visible_filter(
        "MEDICAL", [a.plan for a in out])}
    return [a for a in out if a.plan.student_id in visible]


# ── Stock ─────────────────────────────────────────────────────────

def _medication_owner(conn: sqlite3.Connection, medication_id: int) -> str:
    r = conn.execute("SELECT student_id FROM med_medications "
                     "WHERE medication_id = ?", (medication_id,)).fetchone()
    if r is None:
        raise ValidationError(f"No medication #{medication_id}")
    return r["student_id"]


def save_stock(data: dict[str, Any]) -> StockItem:
    """Create or replace the stock line for a medication."""
    init_db()
    p = _records.validate(STOCK_SPEC, data, error=ValidationError)
    with _connect() as conn:
        p["student_id"] = _medication_owner(conn, p["medication_id"])
        _med_guard("save medication stock", p["student_id"],
                   f"med:{p['medication_id']}")
        existing = conn.execute(
            "SELECT stock_id FROM med_stock WHERE medication_id = ?",
            (p["medication_id"],)).fetchone()
        if existing:
            sid = existing["stock_id"]
            _records.update(conn, STOCK_SPEC, sid, p)
        else:
            sid = _records.insert(conn, STOCK_SPEC, p)
        conn.commit()
        return _records.fetch(conn, STOCK_SPEC, sid)


def receive_stock(medication_id: int, quantity: int, *,
                  expiry_date: str | None = None) -> StockItem:
    """Add a new supply to stock (creating the line if needed)."""
    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        raise ValidationError("Quantity must be a whole number") from None
    if qty <= 0:
        raise ValidationError("Quantity received must be positive")
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM med_stock WHERE medication_id = ?",
                         (medication_id,)).fetchone()
    current = _records.to_row(STOCK_SPEC, r) if r else None
    payload: dict[str, Any] = {
        "medication_id": medication_id,
        "quantity": (current.quantity if current else 0) + qty,
    }
    for k in ("unit", "location", "reorder_level", "notes"):
        payload[k] = getattr(current, k) if current else None
    payload["expiry_date"] = expiry_date or (current.expiry_date
                                             if current else None)
    return save_stock(payload)


def list_stock(*, student_id: str | None = None,
               low_only: bool = False,
               expiring_within_days: int | None = None) -> list[StockItem]:
    init_db()
    _med_guard("list medication stock", student_id)
    where, args = [], []
    if low_only:
        where.append("reorder_level IS NOT NULL AND quantity <= reorder_level")
    if expiring_within_days is not None:
        where.append("expiry_date IS NOT NULL AND expiry_date <= ?")
        args.append((_dt.date.today() + _dt.timedelta(
            days=int(expiring_within_days))).isoformat())
    with _connect() as conn:
        rows = _records.select(conn, STOCK_SPEC,
                               equals={"student_id": student_id},
                               where=where, args=args)
    return _records.visible_filter("MEDICAL", rows)


def update_stock(stock_id: int, data: dict[str, Any]) -> StockItem:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, STOCK_SPEC, stock_id)
        if existing is None:
            raise ValidationError(f"No stock line #{stock_id}")
        p = _records.validate(STOCK_SPEC, data, error=ValidationError,
                              existing=existing)
        _med_guard("update medication stock", existing.student_id,
                   f"stock:{stock_id}")
        _records.update(conn, STOCK_SPEC, stock_id, p)
        conn.commit()
        return _records.fetch(conn, STOCK_SPEC, stock_id)


def delete_stock(stock_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, STOCK_SPEC, stock_id)
        if existing is None:
            return False
        _med_guard("delete medication stock", existing.student_id,
                   f"stock:{stock_id}")
        ok = _records.delete(conn, STOCK_SPEC, stock_id)
        conn.commit()
        return ok


# ── Administration log ────────────────────────────────────────────

def record_administration(data: dict[str, Any]) -> Administration:
    """Log one administration. When it is linked to a medication on the
    student's record, the medicine name defaults from it and the stock
    line (if any) is decremented by ``quantity_used`` for outcomes
    where the medicine was used."""
    init_db()
    p = _records.validate(ADMIN_SPEC, data, error=ValidationError,
                          student_exists=_student_ok)
    actor = _med_guard("record medication administration", p["student_id"])
    p["given_by"] = p["given_by"] or actor.staff_name or actor.username
    if not p["given_by"]:
        raise ValidationError("Given by is required")
    if p["witnessed_by"] and p["witnessed_by"].strip().lower() \
            == p["given_by"].strip().lower():
        raise ValidationError("The witness must be a different person")
    with _connect() as conn:
        if p["medication_id"] is not None:
            m = conn.execute(
                "SELECT student_id, name, dose FROM med_medications "
                "WHERE medication_id = ?", (p["medication_id"],)).fetchone()
            if m is None:
                raise ValidationError(f"No medication #{p['medication_id']}")
            if m["student_id"] != p["student_id"]:
                raise ValidationError(
                    "That medication is on another student's record")
            p["medicine"] = p["medicine"] or m["name"]
        if not p["medicine"]:
            raise ValidationError("Medicine is required")
        uses_stock = p["outcome"] in ("Given",
                                      "Self-administered (supervised)",
                                      "Vomited / spat out")
        if p["medication_id"] is not None and uses_stock:
            s = conn.execute(
                "SELECT stock_id, quantity FROM med_stock "
                "WHERE medication_id = ?", (p["medication_id"],)).fetchone()
            if s is not None:
                left = s["quantity"] - (p["quantity_used"] or 0)
                if left < 0:
                    raise ValidationError(
                        f"Only {s['quantity']} in stock — record the "
                        "new supply first")
                conn.execute(
                    "UPDATE med_stock SET quantity = ?, "
                    "updated_at = datetime('now') WHERE stock_id = ?",
                    (left, s["stock_id"]))
                p["stock_after"] = left
        new_id = _records.insert(conn, ADMIN_SPEC, p)
        conn.commit()
        out = _records.fetch(conn, ADMIN_SPEC, new_id)
    logger.info("Logged administration #%d of %s to %s (%s)", new_id,
                p["medicine"], p["student_id"], p["outcome"])
    return out


def list_administrations(*, student_id: str | None = None,
                         date_from: str | None = None,
                         date_to: str | None = None,
                         medication_id: int | None = None
                         ) -> list[Administration]:
    init_db()
    _med_guard("list medication administrations", student_id)
    where, args = [], []
    if date_from:
        where.append("administered_on >= ?")
        args.append(_records.check_date(date_from, "From", ValidationError))
    if date_to:
        where.append("administered_on <= ?")
        args.append(_records.check_date(date_to, "To", ValidationError))
    with _connect() as conn:
        rows = _records.select(conn, ADMIN_SPEC, equals={
            "student_id": student_id, "medication_id": medication_id},
            where=where, args=args)
    return _records.visible_filter("MEDICAL", rows)


def update_administration(admin_id: int,
                          data: dict[str, Any]) -> Administration:
    """Correct a log entry's details. Stock is not re-calculated; record
    a stock adjustment separately if the quantity was wrong."""
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, ADMIN_SPEC, admin_id)
    if existing is None:
        raise ValidationError(f"No administration #{admin_id}")
    data = {k: v for k, v in data.items()
            if k not in ("medication_id", "quantity_used")}
    p = _records.validate(ADMIN_SPEC, data, error=ValidationError,
                          existing=existing, student_exists=_student_ok)
    _med_guard("update medication administration", existing.student_id,
               f"admin:{admin_id}")
    with _connect() as conn:
        _records.update(conn, ADMIN_SPEC, admin_id, p)
        conn.commit()
        return _records.fetch(conn, ADMIN_SPEC, admin_id)


def delete_administration(admin_id: int) -> bool:
    """Delete a mistaken entry, returning its quantity to stock."""
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, ADMIN_SPEC, admin_id)
        if existing is None:
            return False
        _med_guard("delete medication administration", existing.student_id,
                   f"admin:{admin_id}")
        if existing.medication_id is not None \
                and existing.stock_after is not None:
            conn.execute(
                "UPDATE med_stock SET quantity = quantity + ?, "
                "updated_at = datetime('now') WHERE medication_id = ?",
                (existing.quantity_used or 0, existing.medication_id))
        ok = _records.delete(conn, ADMIN_SPEC, admin_id)
        conn.commit()
        return ok
