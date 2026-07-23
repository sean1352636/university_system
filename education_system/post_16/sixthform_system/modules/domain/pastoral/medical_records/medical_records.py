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

from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.MEDICAL_RECORDS_DB

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
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
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
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
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
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
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
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
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
