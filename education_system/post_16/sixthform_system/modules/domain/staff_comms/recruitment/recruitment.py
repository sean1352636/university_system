"""Recruitment data layer for Sixth Form System.

Two tables:
- `vacancies`: posts being recruited for. Standalone (no FK).
- `recruitment_applicants`: per-vacancy applicants with FK cascade
  on vacancy delete. Full applicant lifecycle Applied → Shortlisted
  → Interviewed → Offer Made → Offer Accepted / Rejected → Started
  (or Withdrew).
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.post_16.sixthform_system.core import paths as _paths

logger = logging.getLogger(__name__)

ROLE_TYPES: tuple[str, ...] = (
    "Teacher",
    "Head of Department",
    "Senior Leader",
    "Headteacher",
    "Pastoral",
    "Teaching Assistant",
    "Cover Supervisor",
    "Technician",
    "Administrator",
    "Premises",
    "Catering",
    "Librarian",
    "Examinations Officer",
    "Other",
)
DEFAULT_ROLE_TYPE = "Teacher"

CONTRACT_TYPES: tuple[str, ...] = (
    "Permanent",
    "Fixed Term",
    "Maternity Cover",
    "Long-Term Supply",
    "Casual / Sessional",
    "Apprenticeship",
    "Internship",
    "Other",
)
DEFAULT_CONTRACT_TYPE = "Permanent"

VACANCY_STATUSES: tuple[str, ...] = (
    "Draft",
    "Advertised",
    "Shortlisting",
    "Interview",
    "Filled",
    "Closed",
    "Withdrawn",
    "On Hold",
)
DEFAULT_VACANCY_STATUS = "Draft"

APPLICANT_SOURCES: tuple[str, ...] = (
    "School Website",
    "TES",
    "Eteach",
    "Indeed",
    "LinkedIn",
    "Agency",
    "Word of Mouth",
    "Internal",
    "Speculative",
    "Other",
)
DEFAULT_APPLICANT_SOURCE = "School Website"

APPLICANT_STATUSES: tuple[str, ...] = (
    "Applied",
    "Under Review",
    "Shortlisted",
    "Rejected (Pre-Interview)",
    "Interview Scheduled",
    "Interviewed",
    "Offer Made",
    "Offer Accepted",
    "Offer Declined",
    "Withdrew",
    "Rejected (Post-Interview)",
    "Started",
)
DEFAULT_APPLICANT_STATUS = "Applied"


class ValidationError(Exception):
    pass


@dataclass
class Vacancy:
    vacancy_id: int
    reference: str | None
    title: str
    department: str | None
    role_type: str
    contract_type: str
    fte_percent: float
    salary_min: float | None
    salary_max: float | None
    salary_scale: str | None
    advertised_on: str | None
    closing_date: str | None
    shortlisting_date: str | None
    interview_date: str | None
    start_date: str | None
    hiring_manager: str | None
    description: str | None
    requirements: str | None
    benefits: str | None
    safeguarding_statement: bool
    advert_url: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Draft", "Advertised",
                                       "Shortlisting", "Interview",
                                       "On Hold")

    @property
    def closing_passed(self) -> bool:
        if not self.closing_date or not self.is_open:
            return False
        return self.closing_date < _dt.date.today().isoformat()


@dataclass
class Applicant:
    applicant_id: int
    vacancy_id: int
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    application_received_on: str
    source: str
    cv_received: bool
    application_form_received: bool
    references_received: bool
    dbs_clearance: bool
    shortlisted: bool
    interview_date: str | None
    interview_score: int | None
    interview_notes: str | None
    offer_made_on: str | None
    offer_response_on: str | None
    offer_salary: float | None
    rejection_reason: str | None
    started_on: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_active(self) -> bool:
        return self.status not in (
            "Rejected (Pre-Interview)",
            "Offer Declined",
            "Withdrew",
            "Rejected (Post-Interview)",
            "Started",
        )

    @property
    def has_offer(self) -> bool:
        return self.status in ("Offer Made",
                                       "Offer Accepted",
                                       "Started")


@dataclass
class RecruitmentSummary:
    total_vacancies: int = 0
    open_vacancies: int = 0
    advertised: int = 0
    closing_passed: int = 0
    total_applicants: int = 0
    active_applicants: int = 0
    shortlisted: int = 0
    interviewed: int = 0
    offers_made: int = 0
    offers_accepted: int = 0
    started: int = 0
    rejected: int = 0
    by_role_type: dict[str, int] = field(default_factory=dict)
    by_vacancy_status: dict[str, int] = field(default_factory=dict)
    by_applicant_status: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.RECRUITMENT_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vacancies (
                vacancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT,
                title TEXT NOT NULL,
                department TEXT,
                role_type TEXT NOT NULL,
                contract_type TEXT NOT NULL,
                fte_percent REAL NOT NULL DEFAULT 100,
                salary_min REAL,
                salary_max REAL,
                salary_scale TEXT,
                advertised_on TEXT,
                closing_date TEXT,
                shortlisting_date TEXT,
                interview_date TEXT,
                start_date TEXT,
                hiring_manager TEXT,
                description TEXT,
                requirements TEXT,
                benefits TEXT,
                safeguarding_statement INTEGER NOT NULL DEFAULT 1,
                advert_url TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recruitment_applicants (
                applicant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vacancy_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                application_received_on TEXT NOT NULL,
                source TEXT NOT NULL,
                cv_received INTEGER NOT NULL DEFAULT 0,
                application_form_received INTEGER NOT NULL DEFAULT 0,
                references_received INTEGER NOT NULL DEFAULT 0,
                dbs_clearance INTEGER NOT NULL DEFAULT 0,
                shortlisted INTEGER NOT NULL DEFAULT 0,
                interview_date TEXT,
                interview_score INTEGER,
                interview_notes TEXT,
                offer_made_on TEXT,
                offer_response_on TEXT,
                offer_salary REAL,
                rejection_reason TEXT,
                started_on TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(vacancy_id)
                  REFERENCES vacancies(vacancy_id)
                  ON DELETE CASCADE
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


# ── Vacancies ────────────────────────────────────────────

def _validate_vacancy(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")
    rt = (out.get("role_type") or DEFAULT_ROLE_TYPE).strip()
    if rt not in ROLE_TYPES:
        raise ValidationError(
            f"Role type must be one of: "
            f"{', '.join(ROLE_TYPES)}")
    out["role_type"] = rt
    ct = (out.get("contract_type")
            or DEFAULT_CONTRACT_TYPE).strip()
    if ct not in CONTRACT_TYPES:
        raise ValidationError(
            f"Contract type must be one of: "
            f"{', '.join(CONTRACT_TYPES)}")
    out["contract_type"] = ct
    status = (out.get("status")
              or DEFAULT_VACANCY_STATUS).strip()
    if status not in VACANCY_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(VACANCY_STATUSES)}")
    out["status"] = status

    try:
        fte = float(out.get("fte_percent") or 100)
    except (TypeError, ValueError):
        raise ValidationError(
            "FTE percent must be a number 0-100")
    if not (0 < fte <= 100):
        raise ValidationError(
            "FTE percent must be between 0 and 100")
    out["fte_percent"] = fte

    for key in ("salary_min", "salary_max"):
        v = out.get(key)
        if v in (None, ""):
            out[key] = None
        else:
            try:
                out[key] = float(v)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be a number")
            if out[key] < 0:
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be >= 0")
    if (out["salary_min"] is not None
            and out["salary_max"] is not None
            and out["salary_min"] > out["salary_max"]):
        raise ValidationError(
            "Salary min must be <= salary max")

    _check_date("Advertised on",     out.get("advertised_on"))
    _check_date("Closing date",      out.get("closing_date"))
    _check_date("Shortlisting date", out.get("shortlisting_date"))
    _check_date("Interview date",    out.get("interview_date"))
    _check_date("Start date",        out.get("start_date"))

    for k in ("reference", "department", "salary_scale",
               "hiring_manager", "description", "requirements",
               "benefits", "advert_url", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("advertised_on", "closing_date",
               "shortlisting_date", "interview_date",
               "start_date"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    out["safeguarding_statement"] = bool(
        out.get("safeguarding_statement", True))
    return out


def _row_vacancy(r: sqlite3.Row) -> Vacancy:
    return Vacancy(
        vacancy_id=r["vacancy_id"],
        reference=r["reference"],
        title=r["title"],
        department=r["department"],
        role_type=r["role_type"],
        contract_type=r["contract_type"],
        fte_percent=r["fte_percent"],
        salary_min=r["salary_min"],
        salary_max=r["salary_max"],
        salary_scale=r["salary_scale"],
        advertised_on=r["advertised_on"],
        closing_date=r["closing_date"],
        shortlisting_date=r["shortlisting_date"],
        interview_date=r["interview_date"],
        start_date=r["start_date"],
        hiring_manager=r["hiring_manager"],
        description=r["description"],
        requirements=r["requirements"],
        benefits=r["benefits"],
        safeguarding_statement=bool(r["safeguarding_statement"]),
        advert_url=r["advert_url"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_vacancy(payload: dict[str, Any]) -> Vacancy:
    init_db()
    p = _validate_vacancy(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO vacancies (
              reference, title, department, role_type,
              contract_type, fte_percent,
              salary_min, salary_max, salary_scale,
              advertised_on, closing_date, shortlisting_date,
              interview_date, start_date,
              hiring_manager, description, requirements,
              benefits, safeguarding_statement, advert_url,
              status, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["reference"], p["title"], p["department"],
            p["role_type"], p["contract_type"], p["fte_percent"],
            p["salary_min"], p["salary_max"], p["salary_scale"],
            p["advertised_on"], p["closing_date"],
            p["shortlisting_date"], p["interview_date"],
            p["start_date"], p["hiring_manager"],
            p["description"], p["requirements"], p["benefits"],
            1 if p["safeguarding_statement"] else 0,
            p["advert_url"], p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_vacancy(new_id)


def update_vacancy(vacancy_id: int,
                        payload: dict[str, Any]) -> Vacancy:
    init_db()
    if get_vacancy(vacancy_id) is None:
        raise ValidationError(f"No vacancy with id {vacancy_id}")
    p = _validate_vacancy(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE vacancies SET
              reference=?, title=?, department=?, role_type=?,
              contract_type=?, fte_percent=?,
              salary_min=?, salary_max=?, salary_scale=?,
              advertised_on=?, closing_date=?,
              shortlisting_date=?, interview_date=?, start_date=?,
              hiring_manager=?, description=?, requirements=?,
              benefits=?, safeguarding_statement=?, advert_url=?,
              status=?, notes=?, updated_on=?
            WHERE vacancy_id=?
        """, (
            p["reference"], p["title"], p["department"],
            p["role_type"], p["contract_type"], p["fte_percent"],
            p["salary_min"], p["salary_max"], p["salary_scale"],
            p["advertised_on"], p["closing_date"],
            p["shortlisting_date"], p["interview_date"],
            p["start_date"], p["hiring_manager"],
            p["description"], p["requirements"], p["benefits"],
            1 if p["safeguarding_statement"] else 0,
            p["advert_url"], p["status"], p["notes"],
            now, vacancy_id,
        ))
    return get_vacancy(vacancy_id)


def delete_vacancy(vacancy_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM vacancies WHERE vacancy_id=?",
            (vacancy_id,))
        return cur.rowcount > 0


def get_vacancy(vacancy_id: int) -> Vacancy | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM vacancies WHERE vacancy_id=?",
            (vacancy_id,)).fetchone()
        return _row_vacancy(r) if r else None


def list_vacancies(*,
                        role_type: str | None = None,
                        contract_type: str | None = None,
                        status: str | None = None,
                        department_like: str | None = None,
                        title_like: str | None = None,
                        open_only: bool = False,
                        closing_passed: bool = False,
                        ) -> list[Vacancy]:
    init_db()
    sql = "SELECT * FROM vacancies WHERE 1=1"
    params: list[Any] = []
    if role_type:
        sql += " AND role_type=?"
        params.append(role_type)
    if contract_type:
        sql += " AND contract_type=?"
        params.append(contract_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if department_like:
        sql += " AND department LIKE ?"
        params.append(f"%{department_like}%")
    if title_like:
        sql += " AND title LIKE ?"
        params.append(f"%{title_like}%")
    if open_only:
        sql += (" AND status IN "
                  "('Draft','Advertised','Shortlisting',"
                  "'Interview','On Hold')")
    if closing_passed:
        today = _dt.date.today().isoformat()
        sql += (" AND closing_date IS NOT NULL"
                  " AND closing_date < ?"
                  " AND status IN "
                  "('Draft','Advertised','Shortlisting',"
                  "'Interview','On Hold')")
        params.append(today)
    sql += " ORDER BY closing_date ASC, vacancy_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_vacancy(r) for r in rows]


def _to_vacancy_dict(v: Vacancy) -> dict[str, Any]:
    return {
        "reference": v.reference,
        "title": v.title,
        "department": v.department,
        "role_type": v.role_type,
        "contract_type": v.contract_type,
        "fte_percent": v.fte_percent,
        "salary_min": v.salary_min,
        "salary_max": v.salary_max,
        "salary_scale": v.salary_scale,
        "advertised_on": v.advertised_on,
        "closing_date": v.closing_date,
        "shortlisting_date": v.shortlisting_date,
        "interview_date": v.interview_date,
        "start_date": v.start_date,
        "hiring_manager": v.hiring_manager,
        "description": v.description,
        "requirements": v.requirements,
        "benefits": v.benefits,
        "safeguarding_statement": v.safeguarding_statement,
        "advert_url": v.advert_url,
        "status": v.status,
        "notes": v.notes,
    }


def advertise(vacancy_id: int, *,
                  advertised_on: str | None = None) -> Vacancy:
    v = get_vacancy(vacancy_id)
    if v is None:
        raise ValidationError(f"No vacancy with id {vacancy_id}")
    data = _to_vacancy_dict(v)
    data["status"] = "Advertised"
    if not data["advertised_on"]:
        data["advertised_on"] = (advertised_on
                                       or _dt.date.today().isoformat())
    return update_vacancy(vacancy_id, data)


def set_vacancy_status(vacancy_id: int,
                            new_status: str) -> Vacancy:
    if new_status not in VACANCY_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(VACANCY_STATUSES)}")
    v = get_vacancy(vacancy_id)
    if v is None:
        raise ValidationError(f"No vacancy with id {vacancy_id}")
    return update_vacancy(vacancy_id,
                                {**_to_vacancy_dict(v),
                                  "status": new_status})


def mark_filled(vacancy_id: int) -> Vacancy:
    v = get_vacancy(vacancy_id)
    if v is None:
        raise ValidationError(f"No vacancy with id {vacancy_id}")
    return update_vacancy(vacancy_id,
                                {**_to_vacancy_dict(v),
                                  "status": "Filled"})


def applicant_count(vacancy_id: int) -> int:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM recruitment_applicants "
            "WHERE vacancy_id=?", (vacancy_id,)).fetchone()
    return int(row["c"]) if row else 0


# ── Applicants ───────────────────────────────────────────

def _validate_applicant(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["first_name"] = (out.get("first_name") or "").strip()
    out["last_name"] = (out.get("last_name") or "").strip()
    if not out["first_name"]:
        raise ValidationError("First name is required")
    if not out["last_name"]:
        raise ValidationError("Last name is required")
    out["application_received_on"] = (
        out.get("application_received_on") or "").strip()
    if not out["application_received_on"]:
        out["application_received_on"] = (
            _dt.date.today().isoformat())
    _check_date("Application received",
                  out["application_received_on"])
    _check_date("Interview date",      out.get("interview_date"))
    _check_date("Offer made on",       out.get("offer_made_on"))
    _check_date("Offer response on",   out.get("offer_response_on"))
    _check_date("Started on",          out.get("started_on"))

    src = (out.get("source") or DEFAULT_APPLICANT_SOURCE).strip()
    if src not in APPLICANT_SOURCES:
        raise ValidationError(
            f"Source must be one of: "
            f"{', '.join(APPLICANT_SOURCES)}")
    out["source"] = src

    status = (out.get("status")
              or DEFAULT_APPLICANT_STATUS).strip()
    if status not in APPLICANT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(APPLICANT_STATUSES)}")
    out["status"] = status

    score = out.get("interview_score")
    if score in (None, ""):
        out["interview_score"] = None
    else:
        try:
            iv = int(score)
        except (TypeError, ValueError):
            raise ValidationError(
                "Interview score must be 0-100")
        if not (0 <= iv <= 100):
            raise ValidationError(
                "Interview score must be 0-100")
        out["interview_score"] = iv

    sal = out.get("offer_salary")
    if sal in (None, ""):
        out["offer_salary"] = None
    else:
        try:
            out["offer_salary"] = float(sal)
        except (TypeError, ValueError):
            raise ValidationError(
                "Offer salary must be a number")
        if out["offer_salary"] < 0:
            raise ValidationError(
                "Offer salary must be >= 0")

    for k in ("email", "phone", "interview_notes",
               "rejection_reason", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("interview_date", "offer_made_on",
               "offer_response_on", "started_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    for k in ("cv_received", "application_form_received",
               "references_received", "dbs_clearance",
               "shortlisted"):
        out[k] = bool(out.get(k))
    return out


def _row_applicant(r: sqlite3.Row) -> Applicant:
    return Applicant(
        applicant_id=r["applicant_id"],
        vacancy_id=r["vacancy_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        email=r["email"],
        phone=r["phone"],
        application_received_on=r["application_received_on"],
        source=r["source"],
        cv_received=bool(r["cv_received"]),
        application_form_received=bool(
            r["application_form_received"]),
        references_received=bool(r["references_received"]),
        dbs_clearance=bool(r["dbs_clearance"]),
        shortlisted=bool(r["shortlisted"]),
        interview_date=r["interview_date"],
        interview_score=r["interview_score"],
        interview_notes=r["interview_notes"],
        offer_made_on=r["offer_made_on"],
        offer_response_on=r["offer_response_on"],
        offer_salary=r["offer_salary"],
        rejection_reason=r["rejection_reason"],
        started_on=r["started_on"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def add_applicant(vacancy_id: int,
                       payload: dict[str, Any]) -> Applicant:
    init_db()
    if get_vacancy(vacancy_id) is None:
        raise ValidationError(f"No vacancy with id {vacancy_id}")
    p = _validate_applicant(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO recruitment_applicants (
              vacancy_id, first_name, last_name, email, phone,
              application_received_on, source,
              cv_received, application_form_received,
              references_received, dbs_clearance, shortlisted,
              interview_date, interview_score, interview_notes,
              offer_made_on, offer_response_on, offer_salary,
              rejection_reason, started_on, status, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vacancy_id, p["first_name"], p["last_name"],
            p["email"], p["phone"],
            p["application_received_on"], p["source"],
            1 if p["cv_received"] else 0,
            1 if p["application_form_received"] else 0,
            1 if p["references_received"] else 0,
            1 if p["dbs_clearance"] else 0,
            1 if p["shortlisted"] else 0,
            p["interview_date"], p["interview_score"],
            p["interview_notes"], p["offer_made_on"],
            p["offer_response_on"], p["offer_salary"],
            p["rejection_reason"], p["started_on"],
            p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_applicant(new_id)


def update_applicant(applicant_id: int,
                          payload: dict[str, Any]) -> Applicant:
    init_db()
    existing = get_applicant(applicant_id)
    if existing is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    p = _validate_applicant(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE recruitment_applicants SET
              first_name=?, last_name=?, email=?, phone=?,
              application_received_on=?, source=?,
              cv_received=?, application_form_received=?,
              references_received=?, dbs_clearance=?, shortlisted=?,
              interview_date=?, interview_score=?,
              interview_notes=?,
              offer_made_on=?, offer_response_on=?, offer_salary=?,
              rejection_reason=?, started_on=?, status=?, notes=?,
              updated_on=?
            WHERE applicant_id=?
        """, (
            p["first_name"], p["last_name"], p["email"],
            p["phone"], p["application_received_on"],
            p["source"],
            1 if p["cv_received"] else 0,
            1 if p["application_form_received"] else 0,
            1 if p["references_received"] else 0,
            1 if p["dbs_clearance"] else 0,
            1 if p["shortlisted"] else 0,
            p["interview_date"], p["interview_score"],
            p["interview_notes"], p["offer_made_on"],
            p["offer_response_on"], p["offer_salary"],
            p["rejection_reason"], p["started_on"],
            p["status"], p["notes"], now, applicant_id,
        ))
    return get_applicant(applicant_id)


def delete_applicant(applicant_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM recruitment_applicants "
            "WHERE applicant_id=?", (applicant_id,))
        return cur.rowcount > 0


def get_applicant(applicant_id: int) -> Applicant | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM recruitment_applicants "
            "WHERE applicant_id=?",
            (applicant_id,)).fetchone()
        return _row_applicant(r) if r else None


def list_applicants(*,
                          vacancy_id: int | None = None,
                          status: str | None = None,
                          shortlisted_only: bool = False,
                          interview_scheduled: bool = False,
                          offer_made: bool = False,
                          ) -> list[Applicant]:
    init_db()
    sql = "SELECT * FROM recruitment_applicants WHERE 1=1"
    params: list[Any] = []
    if vacancy_id is not None:
        sql += " AND vacancy_id=?"
        params.append(vacancy_id)
    if status:
        sql += " AND status=?"
        params.append(status)
    if shortlisted_only:
        sql += " AND shortlisted=1"
    if interview_scheduled:
        sql += " AND status='Interview Scheduled'"
    if offer_made:
        sql += (" AND status IN ('Offer Made',"
                  "'Offer Accepted','Offer Declined')")
    sql += " ORDER BY application_received_on DESC, applicant_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_applicant(r) for r in rows]


def _to_applicant_dict(a: Applicant) -> dict[str, Any]:
    return {
        "first_name": a.first_name,
        "last_name": a.last_name,
        "email": a.email,
        "phone": a.phone,
        "application_received_on": a.application_received_on,
        "source": a.source,
        "cv_received": a.cv_received,
        "application_form_received": a.application_form_received,
        "references_received": a.references_received,
        "dbs_clearance": a.dbs_clearance,
        "shortlisted": a.shortlisted,
        "interview_date": a.interview_date,
        "interview_score": a.interview_score,
        "interview_notes": a.interview_notes,
        "offer_made_on": a.offer_made_on,
        "offer_response_on": a.offer_response_on,
        "offer_salary": a.offer_salary,
        "rejection_reason": a.rejection_reason,
        "started_on": a.started_on,
        "status": a.status,
        "notes": a.notes,
    }


def shortlist(applicant_id: int, *,
                  shortlisted: bool = True) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    data = _to_applicant_dict(a)
    data["shortlisted"] = shortlisted
    if shortlisted and a.status == "Applied":
        data["status"] = "Shortlisted"
    return update_applicant(applicant_id, data)


def schedule_interview(applicant_id: int, *,
                            interview_date: str) -> Applicant:
    _check_date("Interview date", interview_date)
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    data = _to_applicant_dict(a)
    data["interview_date"] = interview_date
    data["shortlisted"] = True
    data["status"] = "Interview Scheduled"
    return update_applicant(applicant_id, data)


def record_interview(applicant_id: int, *,
                          score: int | None = None,
                          notes: str | None = None
                          ) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    data = _to_applicant_dict(a)
    if score is not None:
        data["interview_score"] = score
    if notes is not None:
        data["interview_notes"] = notes
    data["status"] = "Interviewed"
    return update_applicant(applicant_id, data)


def make_offer(applicant_id: int, *,
                   salary: float | None = None,
                   offer_made_on: str | None = None
                   ) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    data = _to_applicant_dict(a)
    data["offer_made_on"] = (offer_made_on
                                  or _dt.date.today().isoformat())
    if salary is not None:
        data["offer_salary"] = salary
    data["status"] = "Offer Made"
    return update_applicant(applicant_id, data)


def offer_response(applicant_id: int, *,
                        accepted: bool,
                        response_on: str | None = None
                        ) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    data = _to_applicant_dict(a)
    data["offer_response_on"] = (response_on
                                       or _dt.date.today().isoformat())
    data["status"] = ("Offer Accepted" if accepted
                          else "Offer Declined")
    return update_applicant(applicant_id, data)


def mark_started(applicant_id: int, *,
                      started_on: str | None = None
                      ) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    data = _to_applicant_dict(a)
    data["started_on"] = (started_on
                              or _dt.date.today().isoformat())
    data["status"] = "Started"
    return update_applicant(applicant_id, data)


def reject_applicant(applicant_id: int, *,
                          reason: str,
                          post_interview: bool = False
                          ) -> Applicant:
    if not reason:
        raise ValidationError("Rejection reason is required")
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    data = _to_applicant_dict(a)
    data["rejection_reason"] = reason
    data["status"] = ("Rejected (Post-Interview)"
                          if post_interview
                          else "Rejected (Pre-Interview)")
    return update_applicant(applicant_id, data)


def withdraw_applicant(applicant_id: int, *,
                            reason: str | None = None
                            ) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    data = _to_applicant_dict(a)
    data["status"] = "Withdrew"
    if reason:
        existing = data["notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["notes"] = (
            prefix + f"Withdrew ({_dt.date.today().isoformat()}): "
            f"{reason}")
    return update_applicant(applicant_id, data)


def set_applicant_status(applicant_id: int,
                              new_status: str) -> Applicant:
    if new_status not in APPLICANT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(APPLICANT_STATUSES)}")
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(
            f"No applicant with id {applicant_id}")
    return update_applicant(applicant_id,
                                  {**_to_applicant_dict(a),
                                    "status": new_status})


# ── Summary ──────────────────────────────────────────────

def summary() -> RecruitmentSummary:
    vacancies = list_vacancies()
    applicants = list_applicants()
    out = RecruitmentSummary(
        total_vacancies=len(vacancies),
        total_applicants=len(applicants),
    )
    today = _dt.date.today().isoformat()
    for v in vacancies:
        if v.is_open:
            out.open_vacancies += 1
        if v.status == "Advertised":
            out.advertised += 1
        if (v.closing_date and v.closing_date < today
                and v.is_open):
            out.closing_passed += 1
        out.by_role_type[v.role_type] = (
            out.by_role_type.get(v.role_type, 0) + 1)
        out.by_vacancy_status[v.status] = (
            out.by_vacancy_status.get(v.status, 0) + 1)
    for a in applicants:
        if a.is_active:
            out.active_applicants += 1
        if a.shortlisted:
            out.shortlisted += 1
        if a.status in ("Interviewed", "Offer Made",
                                "Offer Accepted", "Offer Declined",
                                "Started",
                                "Rejected (Post-Interview)"):
            out.interviewed += 1
        if a.status == "Offer Made":
            out.offers_made += 1
        if a.status in ("Offer Accepted", "Started"):
            out.offers_accepted += 1
        if a.status == "Started":
            out.started += 1
        if "Rejected" in a.status:
            out.rejected += 1
        out.by_applicant_status[a.status] = (
            out.by_applicant_status.get(a.status, 0) + 1)
        out.by_source[a.source] = (
            out.by_source.get(a.source, 0) + 1)
    return out


__all__ = [
    "ROLE_TYPES", "DEFAULT_ROLE_TYPE",
    "CONTRACT_TYPES", "DEFAULT_CONTRACT_TYPE",
    "VACANCY_STATUSES", "DEFAULT_VACANCY_STATUS",
    "APPLICANT_SOURCES", "DEFAULT_APPLICANT_SOURCE",
    "APPLICANT_STATUSES", "DEFAULT_APPLICANT_STATUS",
    "ValidationError",
    "Vacancy", "Applicant", "RecruitmentSummary",
    "init_db",
    "create_vacancy", "update_vacancy", "delete_vacancy",
    "get_vacancy", "list_vacancies",
    "advertise", "set_vacancy_status", "mark_filled",
    "applicant_count",
    "add_applicant", "update_applicant", "delete_applicant",
    "get_applicant", "list_applicants",
    "shortlist", "schedule_interview", "record_interview",
    "make_offer", "offer_response", "mark_started",
    "reject_applicant", "withdraw_applicant",
    "set_applicant_status",
    "summary",
]
