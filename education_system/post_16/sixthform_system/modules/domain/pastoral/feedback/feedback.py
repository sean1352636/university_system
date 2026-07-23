"""Feedback data layer for Sixth Form System.

General-purpose feedback log — lighter than the Complaints module.
Stores positive feedback, suggestions, questions and concerns from
students / parents / staff / visitors. Optional 1-5 star rating
and lightweight response workflow (Received → Reviewing →
Responded → Acted → Closed → Archived).
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

FEEDBACK_TYPES: tuple[str, ...] = (
    "Positive",
    "Suggestion",
    "Question",
    "Concern",
    "Negative",
    "Compliment",
    "Other",
)
DEFAULT_FEEDBACK_TYPE = "Suggestion"

SOURCES: tuple[str, ...] = (
    "Self-Submitted",
    "Suggestion Box",
    "Email",
    "Phone",
    "Web Form",
    "Verbal",
    "Survey Comment",
    "Parent Evening",
    "Open Day",
    "Other",
)
DEFAULT_SOURCE = "Web Form"

SUBMITTER_ROLES: tuple[str, ...] = (
    "Student",
    "Parent / Carer",
    "Staff",
    "Visitor",
    "Former Student",
    "Anonymous",
    "Other",
)
DEFAULT_SUBMITTER_ROLE = "Anonymous"

CATEGORIES: tuple[str, ...] = (
    "Teaching & Learning",
    "Curriculum",
    "Pastoral / Wellbeing",
    "Behaviour",
    "Facilities",
    "IT / Technology",
    "Catering",
    "Communication",
    "Events / Trips",
    "Admissions",
    "Sixth Form Experience",
    "Enrichment",
    "Other",
)
DEFAULT_CATEGORY = "Other"

STATUSES: tuple[str, ...] = (
    "Received",
    "Reviewing",
    "Responded",
    "Acted",
    "Closed",
    "Archived",
)
DEFAULT_STATUS = "Received"

RATINGS: tuple[int, ...] = (1, 2, 3, 4, 5)


class ValidationError(Exception):
    pass


@dataclass
class Feedback:
    feedback_id: int
    received_on: str
    source: str
    submitter_name: str | None
    submitter_role: str
    contact_email: str | None
    contact_phone: str | None
    anonymous: bool
    feedback_type: str
    category: str
    subject: str
    description: str | None
    rating: int | None
    assigned_to: str | None
    response: str | None
    response_on: str | None
    response_by: str | None
    public_shareable: bool
    linked_to: str | None
    status: str
    closed_on: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Closed", "Archived")

    @property
    def has_response(self) -> bool:
        return bool(self.response)


@dataclass
class FeedbackSummary:
    total: int = 0
    open_count: int = 0
    awaiting_response: int = 0
    positive_count: int = 0
    negative_count: int = 0
    suggestions_count: int = 0
    public_count: int = 0
    average_rating: float | None = None
    by_type: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_rating: dict[int, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.FEEDBACK_DB)
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
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_on TEXT NOT NULL,
                source TEXT NOT NULL,
                submitter_name TEXT,
                submitter_role TEXT NOT NULL,
                contact_email TEXT,
                contact_phone TEXT,
                anonymous INTEGER NOT NULL DEFAULT 0,
                feedback_type TEXT NOT NULL,
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT,
                rating INTEGER,
                assigned_to TEXT,
                response TEXT,
                response_on TEXT,
                response_by TEXT,
                public_shareable INTEGER NOT NULL DEFAULT 0,
                linked_to TEXT,
                status TEXT NOT NULL,
                closed_on TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["received_on"] = (out.get("received_on") or "").strip()
    if not out["received_on"]:
        out["received_on"] = _dt.date.today().isoformat()
    _check_date("Received on", out["received_on"])
    _check_date("Response on", out.get("response_on"))
    _check_date("Closed on",   out.get("closed_on"))

    src = (out.get("source") or DEFAULT_SOURCE).strip()
    if src not in SOURCES:
        raise ValidationError(
            f"Source must be one of: {', '.join(SOURCES)}")
    out["source"] = src

    role = (out.get("submitter_role")
              or DEFAULT_SUBMITTER_ROLE).strip()
    if role not in SUBMITTER_ROLES:
        raise ValidationError(
            f"Submitter role must be one of: "
            f"{', '.join(SUBMITTER_ROLES)}")
    out["submitter_role"] = role

    ft = (out.get("feedback_type") or "").strip()
    if ft not in FEEDBACK_TYPES:
        raise ValidationError(
            f"Feedback type must be one of: "
            f"{', '.join(FEEDBACK_TYPES)}")
    out["feedback_type"] = ft

    cat = (out.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    out["subject"] = (out.get("subject") or "").strip()
    if not out["subject"]:
        raise ValidationError("Subject is required")

    r = out.get("rating")
    if r in (None, ""):
        out["rating"] = None
    else:
        try:
            iv = int(r)
        except (TypeError, ValueError):
            raise ValidationError("Rating must be 1-5")
        if iv not in RATINGS:
            raise ValidationError("Rating must be 1-5")
        out["rating"] = iv

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("submitter_name", "contact_email", "contact_phone",
               "description", "assigned_to", "response",
               "response_by", "linked_to", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("response_on", "closed_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    out["anonymous"] = bool(out.get("anonymous"))
    out["public_shareable"] = bool(out.get("public_shareable"))
    return out


def _row(r: sqlite3.Row) -> Feedback:
    return Feedback(
        feedback_id=r["feedback_id"],
        received_on=r["received_on"],
        source=r["source"],
        submitter_name=r["submitter_name"],
        submitter_role=r["submitter_role"],
        contact_email=r["contact_email"],
        contact_phone=r["contact_phone"],
        anonymous=bool(r["anonymous"]),
        feedback_type=r["feedback_type"],
        category=r["category"],
        subject=r["subject"],
        description=r["description"],
        rating=r["rating"],
        assigned_to=r["assigned_to"],
        response=r["response"],
        response_on=r["response_on"],
        response_by=r["response_by"],
        public_shareable=bool(r["public_shareable"]),
        linked_to=r["linked_to"],
        status=r["status"],
        closed_on=r["closed_on"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_feedback(payload: dict[str, Any]) -> Feedback:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO feedback (
              received_on, source, submitter_name, submitter_role,
              contact_email, contact_phone, anonymous,
              feedback_type, category, subject, description,
              rating, assigned_to,
              response, response_on, response_by,
              public_shareable, linked_to, status, closed_on, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["received_on"], p["source"], p["submitter_name"],
            p["submitter_role"], p["contact_email"],
            p["contact_phone"], 1 if p["anonymous"] else 0,
            p["feedback_type"], p["category"],
            p["subject"], p["description"],
            p["rating"], p["assigned_to"],
            p["response"], p["response_on"], p["response_by"],
            1 if p["public_shareable"] else 0,
            p["linked_to"], p["status"], p["closed_on"],
            p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_feedback(new_id)


def update_feedback(feedback_id: int,
                       payload: dict[str, Any]) -> Feedback:
    init_db()
    if get_feedback(feedback_id) is None:
        raise ValidationError(f"No feedback with id {feedback_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE feedback SET
              received_on=?, source=?, submitter_name=?,
              submitter_role=?, contact_email=?, contact_phone=?,
              anonymous=?,
              feedback_type=?, category=?, subject=?, description=?,
              rating=?, assigned_to=?,
              response=?, response_on=?, response_by=?,
              public_shareable=?, linked_to=?, status=?,
              closed_on=?, notes=?, updated_on=?
            WHERE feedback_id=?
        """, (
            p["received_on"], p["source"], p["submitter_name"],
            p["submitter_role"], p["contact_email"],
            p["contact_phone"], 1 if p["anonymous"] else 0,
            p["feedback_type"], p["category"],
            p["subject"], p["description"],
            p["rating"], p["assigned_to"],
            p["response"], p["response_on"], p["response_by"],
            1 if p["public_shareable"] else 0,
            p["linked_to"], p["status"], p["closed_on"],
            p["notes"], now, feedback_id,
        ))
    return get_feedback(feedback_id)


def delete_feedback(feedback_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM feedback WHERE feedback_id=?",
            (feedback_id,))
        return cur.rowcount > 0


def get_feedback(feedback_id: int) -> Feedback | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM feedback WHERE feedback_id=?",
            (feedback_id,)).fetchone()
        return _row(r) if r else None


def list_feedback(*,
                      feedback_type: str | None = None,
                      category: str | None = None,
                      source: str | None = None,
                      submitter_role: str | None = None,
                      status: str | None = None,
                      rating: int | None = None,
                      rating_min: int | None = None,
                      assigned_to_like: str | None = None,
                      subject_like: str | None = None,
                      open_only: bool = False,
                      awaiting_response: bool = False,
                      public_only: bool = False,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      ) -> list[Feedback]:
    init_db()
    sql = "SELECT * FROM feedback WHERE 1=1"
    params: list[Any] = []
    if feedback_type:
        sql += " AND feedback_type=?"
        params.append(feedback_type)
    if category:
        sql += " AND category=?"
        params.append(category)
    if source:
        sql += " AND source=?"
        params.append(source)
    if submitter_role:
        sql += " AND submitter_role=?"
        params.append(submitter_role)
    if status:
        sql += " AND status=?"
        params.append(status)
    if rating is not None:
        sql += " AND rating=?"
        params.append(rating)
    if rating_min is not None:
        sql += " AND rating >= ?"
        params.append(rating_min)
    if assigned_to_like:
        sql += " AND assigned_to LIKE ?"
        params.append(f"%{assigned_to_like}%")
    if subject_like:
        sql += " AND subject LIKE ?"
        params.append(f"%{subject_like}%")
    if open_only:
        sql += " AND status NOT IN ('Closed','Archived')"
    if awaiting_response:
        sql += (" AND response IS NULL"
                  " AND status NOT IN ('Closed','Archived')")
    if public_only:
        sql += " AND public_shareable=1"
    if date_from:
        _check_date("From", date_from)
        sql += " AND received_on >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND received_on <= ?"
        params.append(date_to)
    sql += " ORDER BY received_on DESC, feedback_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


# ── Workflow ─────────────────────────────────────────────────────

def _to_dict(f: Feedback) -> dict[str, Any]:
    return {
        "received_on": f.received_on,
        "source": f.source,
        "submitter_name": f.submitter_name,
        "submitter_role": f.submitter_role,
        "contact_email": f.contact_email,
        "contact_phone": f.contact_phone,
        "anonymous": f.anonymous,
        "feedback_type": f.feedback_type,
        "category": f.category,
        "subject": f.subject,
        "description": f.description,
        "rating": f.rating,
        "assigned_to": f.assigned_to,
        "response": f.response,
        "response_on": f.response_on,
        "response_by": f.response_by,
        "public_shareable": f.public_shareable,
        "linked_to": f.linked_to,
        "status": f.status,
        "closed_on": f.closed_on,
        "notes": f.notes,
    }


def assign(feedback_id: int, *, to: str) -> Feedback:
    if not to:
        raise ValidationError("Assignee is required")
    f = get_feedback(feedback_id)
    if f is None:
        raise ValidationError(f"No feedback with id {feedback_id}")
    data = _to_dict(f)
    data["assigned_to"] = to
    if f.status == "Received":
        data["status"] = "Reviewing"
    return update_feedback(feedback_id, data)


def respond(feedback_id: int, *,
                response: str, response_by: str,
                response_on: str | None = None) -> Feedback:
    if not response:
        raise ValidationError("Response is required")
    if not response_by:
        raise ValidationError("Response by is required")
    f = get_feedback(feedback_id)
    if f is None:
        raise ValidationError(f"No feedback with id {feedback_id}")
    data = _to_dict(f)
    data["response"] = response
    data["response_by"] = response_by
    data["response_on"] = (response_on
                                or _dt.date.today().isoformat())
    data["status"] = "Responded"
    return update_feedback(feedback_id, data)


def mark_acted(feedback_id: int, *,
                   notes: str | None = None) -> Feedback:
    f = get_feedback(feedback_id)
    if f is None:
        raise ValidationError(f"No feedback with id {feedback_id}")
    data = _to_dict(f)
    data["status"] = "Acted"
    if notes:
        existing = data["notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["notes"] = (
            prefix
            + f"{_dt.date.today().isoformat()} acted: {notes}")
    return update_feedback(feedback_id, data)


def close_feedback(feedback_id: int) -> Feedback:
    f = get_feedback(feedback_id)
    if f is None:
        raise ValidationError(f"No feedback with id {feedback_id}")
    data = _to_dict(f)
    data["status"] = "Closed"
    data["closed_on"] = (data["closed_on"]
                              or _dt.date.today().isoformat())
    return update_feedback(feedback_id, data)


def archive(feedback_id: int) -> Feedback:
    f = get_feedback(feedback_id)
    if f is None:
        raise ValidationError(f"No feedback with id {feedback_id}")
    return update_feedback(feedback_id,
                                {**_to_dict(f),
                                  "status": "Archived"})


def set_status(feedback_id: int, new_status: str) -> Feedback:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    f = get_feedback(feedback_id)
    if f is None:
        raise ValidationError(f"No feedback with id {feedback_id}")
    return update_feedback(feedback_id,
                                {**_to_dict(f),
                                  "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> FeedbackSummary:
    rows = list_feedback()
    out = FeedbackSummary(total=len(rows))
    if not rows:
        return out
    ratings: list[int] = []
    for f in rows:
        if f.is_open:
            out.open_count += 1
            if not f.has_response:
                out.awaiting_response += 1
        if f.feedback_type in ("Positive", "Compliment"):
            out.positive_count += 1
        if f.feedback_type in ("Negative", "Concern"):
            out.negative_count += 1
        if f.feedback_type == "Suggestion":
            out.suggestions_count += 1
        if f.public_shareable:
            out.public_count += 1
        if f.rating is not None:
            ratings.append(f.rating)
            out.by_rating[f.rating] = (
                out.by_rating.get(f.rating, 0) + 1)
        out.by_type[f.feedback_type] = (
            out.by_type.get(f.feedback_type, 0) + 1)
        out.by_category[f.category] = (
            out.by_category.get(f.category, 0) + 1)
        out.by_source[f.source] = (
            out.by_source.get(f.source, 0) + 1)
        out.by_status[f.status] = (
            out.by_status.get(f.status, 0) + 1)
    if ratings:
        out.average_rating = round(
            sum(ratings) / len(ratings), 2)
    return out


__all__ = [
    "FEEDBACK_TYPES", "DEFAULT_FEEDBACK_TYPE",
    "SOURCES", "DEFAULT_SOURCE",
    "SUBMITTER_ROLES", "DEFAULT_SUBMITTER_ROLE",
    "CATEGORIES", "DEFAULT_CATEGORY",
    "STATUSES", "DEFAULT_STATUS",
    "RATINGS",
    "ValidationError",
    "Feedback", "FeedbackSummary",
    "init_db",
    "create_feedback", "update_feedback", "delete_feedback",
    "get_feedback", "list_feedback",
    "assign", "respond", "mark_acted",
    "close_feedback", "archive", "set_status",
    "summary",
]
