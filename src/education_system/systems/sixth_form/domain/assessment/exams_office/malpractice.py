"""Malpractice and maladministration log.

Every suspected breach of the exam regulations, by a candidate or a
member of staff, and every administrative failure by the centre, is
logged here with the JCQ form used to report it, the date the board was
told, and the board's outcome and sanction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

SUBJECT_TYPES: tuple[str, ...] = ("Candidate", "Staff", "Centre")

CATEGORIES: tuple[str, ...] = (
    "Candidate malpractice", "Staff malpractice", "Maladministration")

# JCQ "Suspected Malpractice: Policies and Procedures" forms.
JCQ_FORMS: tuple[str, ...] = (
    "JCQ/M1 (candidate malpractice report)",
    "JCQ/M2 (staff malpractice / maladministration)",
    "JCQ/M3 (centre's response)",
    "Board's own form",
    "Not reported (internal only)",
)

INCIDENT_TYPES: tuple[str, ...] = (
    "Unauthorised item (phone / watch / notes)",
    "Communicating during the exam",
    "Copying / collusion",
    "Disruptive behaviour",
    "Plagiarism / AI misuse (NEA)",
    "Offensive material in script",
    "Impersonation",
    "Breach of security of papers",
    "Wrong paper / timing error",
    "Failure to apply access arrangement",
    "Improper assistance",
    "Other",
)

STATUSES: tuple[str, ...] = ("Open", "Reported to board", "Outcome received", "Closed")

# JCQ sanctions available to a board against a candidate, and against
# staff. Free text is accepted for anything else.
CANDIDATE_SANCTIONS: tuple[str, ...] = (
    "No action", "Warning", "Loss of marks for a section",
    "Loss of marks for the component", "Loss of all marks for the unit",
    "Disqualification from the component", "Disqualification from the qualification",
    "Disqualification from all qualifications in the series", "Barred from future entries")
STAFF_SANCTIONS: tuple[str, ...] = (
    "No action", "Written warning", "Training required", "Special conditions",
    "Suspension from exam duties", "Barred from involvement in exams")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_malpractice (
    case_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type     TEXT NOT NULL,
    category         TEXT NOT NULL,
    student_id       TEXT,
    staff_id         TEXT,
    staff_name       TEXT,
    incident_date    TEXT NOT NULL,
    incident_type    TEXT NOT NULL,
    incident         TEXT NOT NULL,
    sitting_id       INTEGER,
    exam_board       TEXT,
    component_code   TEXT,
    jcq_form         TEXT,
    form_reference   TEXT,
    reported_to_board_date TEXT,
    board_reference  TEXT,
    status           TEXT NOT NULL DEFAULT 'Open',
    outcome          TEXT,
    outcome_date     TEXT,
    sanction         TEXT,
    recorded_by      TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL,
    FOREIGN KEY (sitting_id) REFERENCES attendance_exam_sittings(sitting_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_exams_malp_student ON exams_malpractice(student_id);
CREATE INDEX IF NOT EXISTS idx_exams_malp_status ON exams_malpractice(status);
"""


def _attendance_init() -> None:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _exams,
    )
    _exams.init_db()


def init_db() -> None:
    store.ensure("malpractice", _SCHEMA, after=(_attendance_init,))


_FIELDS = ("case_id", "subject_type", "category", "student_id", "staff_id",
           "staff_name", "incident_date", "incident_type", "incident", "sitting_id",
           "exam_board", "component_code", "jcq_form", "form_reference",
           "reported_to_board_date", "board_reference", "status", "outcome",
           "outcome_date", "sanction", "recorded_by", "created_at", "updated_at")


@dataclass
class Case:
    case_id: int
    subject_type: str
    category: str
    student_id: str | None
    staff_id: str | None
    staff_name: str | None
    incident_date: str
    incident_type: str
    incident: str
    sitting_id: int | None
    exam_board: str | None
    component_code: str | None
    jcq_form: str | None
    form_reference: str | None
    reported_to_board_date: str | None
    board_reference: str | None
    status: str
    outcome: str | None
    outcome_date: str | None
    sanction: str | None
    recorded_by: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def who(self) -> str:
        if self.subject_type == "Candidate":
            return self.student_id or "(candidate)"
        if self.subject_type == "Staff":
            return self.staff_name or self.staff_id or "(staff)"
        return "Centre"


def save_case(data: dict[str, Any], *, case_id: int | None = None) -> Case:
    init_db()
    subject = store.choice(data.get("subject_type"), "Subject", SUBJECT_TYPES)
    category = store.choice(
        data.get("category"), "Category", CATEGORIES,
        default={"Candidate": "Candidate malpractice",
                 "Staff": "Staff malpractice"}.get(subject, "Maladministration"))
    sid = store.student(data.get("student_id")) if data.get("student_id") else None
    staff_id = store.text(data.get("staff_id"), "Staff ID", limit=40)
    staff_name = store.text(data.get("staff_name"), "Staff name", limit=120)
    if staff_id and not staff_name:
        from education_system.systems.sixth_form.domain.staff import staff as _staff
        s = _staff.get_staff(staff_id)
        if s is None:
            raise ValidationError(f"No staff member {staff_id}")
        staff_name = f"{s.first_name} {s.last_name}".strip()
    if subject == "Candidate" and not sid:
        raise ValidationError("Pick the candidate involved")
    if subject == "Staff" and not (staff_id or staff_name):
        raise ValidationError("Name the member of staff involved")
    reported = store.date(data.get("reported_to_board_date"), "Reported to board")
    outcome = store.text(data.get("outcome"), "Outcome", limit=1000)
    status = store.choice(data.get("status"), "Status", STATUSES, default="Open")
    if reported and status == "Open":
        status = "Reported to board"
    outcome_date = store.date(data.get("outcome_date"), "Outcome date")
    if outcome and status in ("Open", "Reported to board"):
        status = "Outcome received"
        outcome_date = outcome_date or store.today()
    sitting_id = store.integer(data.get("sitting_id"), "Sitting")
    vals = (subject, category, sid, staff_id, staff_name,
            store.date(data.get("incident_date"), "Incident date", required=True),
            store.choice(data.get("incident_type"), "Incident type", INCIDENT_TYPES,
                         default="Other"),
            store.text(data.get("incident"), "What happened", limit=4000, required=True),
            sitting_id, store.board(data.get("exam_board"), required=False),
            (store.text(data.get("component_code"), "Component code", limit=24) or "").upper()
            or None,
            store.choice(data.get("jcq_form"), "JCQ form", JCQ_FORMS, required=False),
            store.text(data.get("form_reference"), "Form reference", limit=60),
            reported, store.text(data.get("board_reference"), "Board reference", limit=60),
            status, outcome, outcome_date,
            store.text(data.get("sanction"), "Sanction", limit=200))
    with store.connect() as conn:
        if case_id is None:
            cur = conn.execute(
                """INSERT INTO exams_malpractice
                       (subject_type, category, student_id, staff_id, staff_name,
                        incident_date, incident_type, incident, sitting_id,
                        exam_board, component_code, jcq_form, form_reference,
                        reported_to_board_date, board_reference, status, outcome,
                        outcome_date, sanction, recorded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*vals, store.actor()))
            case_id = int(cur.lastrowid)
        else:
            conn.execute(
                """UPDATE exams_malpractice SET subject_type = ?, category = ?,
                       student_id = ?, staff_id = ?, staff_name = ?,
                       incident_date = ?, incident_type = ?, incident = ?,
                       sitting_id = ?, exam_board = ?, component_code = ?,
                       jcq_form = ?, form_reference = ?, reported_to_board_date = ?,
                       board_reference = ?, status = ?, outcome = ?,
                       outcome_date = ?, sanction = ?, updated_at = datetime('now')
                   WHERE case_id = ?""", (*vals, case_id))
        conn.commit()
    out = get_case(case_id)
    assert out is not None
    logger.info("Saved malpractice case #%d (%s)", case_id, category)
    return out


def get_case(case_id: int) -> Case | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT * FROM exams_malpractice WHERE case_id = ?",
                         (case_id,)).fetchone()
    return Case(**{k: r[k] for k in _FIELDS}) if r else None


def list_cases(*, status: str | None = None, category: str | None = None,
               student_id: str | None = None, date_from: str | None = None,
               date_to: str | None = None) -> list[Case]:
    init_db()
    clauses, args = [], []
    for col, val in (("status", status), ("category", category),
                     ("student_id", student_id)):
        if val:
            clauses.append(f"{col} = ?")
            args.append(val)
    if date_from:
        clauses.append("incident_date >= ?")
        args.append(store.date(date_from, "From"))
    if date_to:
        clauses.append("incident_date <= ?")
        args.append(store.date(date_to, "To"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM exams_malpractice {where} "
                            "ORDER BY incident_date DESC, case_id DESC", args).fetchall()
    return [Case(**{k: r[k] for k in _FIELDS}) for r in rows]


def delete_case(case_id: int) -> bool:
    init_db()
    case = get_case(case_id)
    if case and case.reported_to_board_date:
        raise ValidationError(
            "A case reported to the board is a retained record — close it instead")
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM exams_malpractice WHERE case_id = ?", (case_id,))
        conn.commit()
    return bool(cur.rowcount)
