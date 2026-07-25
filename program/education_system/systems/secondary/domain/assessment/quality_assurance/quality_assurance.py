"""Quality-assurance data layer for the Secondary School System.

Two tables:

* ``qa_reviews``   — one row per QA exercise (department review,
                      teaching-standards audit, curriculum check, etc.).
                      Captures the reviewer, focus, judgement, status
                      workflow (Planned → InProgress → Complete →
                      Closed), and free-text strengths /
                      areas_for_development.
* ``qa_actions``   — one row per action arising from a review, with
                      an owner, due date, status, and evidence.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

REVIEW_TYPES: tuple[str, ...] = (
    "Department", "Subject", "Year group", "Teaching standards",
    "Curriculum", "Marking", "SEND provision", "Safeguarding",
    "Other")
DEFAULT_REVIEW_TYPE: str = "Department"

REVIEW_STATUSES: tuple[str, ...] = (
    "Planned", "InProgress", "Complete", "Closed")
DEFAULT_REVIEW_STATUS: str = "Planned"

JUDGEMENTS: tuple[str, ...] = (
    "Outstanding", "Good", "Requires improvement",
    "Inadequate", "Not judged")
DEFAULT_JUDGEMENT: str = "Not judged"

ACTION_STATUSES: tuple[str, ...] = (
    "Open", "InProgress", "Done", "Cancelled")
DEFAULT_ACTION_STATUS: str = "Open"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS qa_reviews (
    review_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title              TEXT NOT NULL,
    review_type        TEXT NOT NULL DEFAULT 'Department',
    focus_area         TEXT,
    lead_reviewer      TEXT NOT NULL,
    additional_team    TEXT,
    review_date        TEXT NOT NULL DEFAULT (date('now')),
    status             TEXT NOT NULL DEFAULT 'Planned',
    judgement          TEXT NOT NULL DEFAULT 'Not judged',
    strengths          TEXT,
    areas_for_development TEXT,
    summary            TEXT,
    follow_up_date     TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qa_actions (
    action_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id     INTEGER NOT NULL,
    action        TEXT NOT NULL,
    owner         TEXT,
    due_date      TEXT,
    status        TEXT NOT NULL DEFAULT 'Open',
    evidence      TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (review_id) REFERENCES qa_reviews(review_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_qa_status ON qa_reviews(status);
CREATE INDEX IF NOT EXISTS idx_qa_actions_review
    ON qa_actions(review_id);
CREATE INDEX IF NOT EXISTS idx_qa_actions_status
    ON qa_actions(status);
"""


@dataclass
class QAReview:
    review_id: int
    title: str
    review_type: str
    focus_area: str | None
    lead_reviewer: str
    additional_team: str | None
    review_date: str
    status: str
    judgement: str
    strengths: str | None
    areas_for_development: str | None
    summary: str | None
    follow_up_date: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class QAAction:
    action_id: int
    review_id: int
    action: str
    owner: str | None
    due_date: str | None
    status: str
    evidence: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def overdue(self) -> bool:
        if self.status in ("Done", "Cancelled") or not self.due_date:
            return False
        try:
            return _dt.date.fromisoformat(self.due_date) < _dt.date.today()
        except ValueError:
            return False


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise quality_assurance tables")
        raise
    logger.info("Secondary quality_assurance tables ready")
    _DB_READY = True


def _row_review(r: sqlite3.Row) -> QAReview:
    return QAReview(
        review_id=r["review_id"], title=r["title"],
        review_type=r["review_type"], focus_area=r["focus_area"],
        lead_reviewer=r["lead_reviewer"],
        additional_team=r["additional_team"],
        review_date=r["review_date"], status=r["status"],
        judgement=r["judgement"],
        strengths=r["strengths"],
        areas_for_development=r["areas_for_development"],
        summary=r["summary"], follow_up_date=r["follow_up_date"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_action(r: sqlite3.Row) -> QAAction:
    return QAAction(
        action_id=r["action_id"], review_id=r["review_id"],
        action=r["action"], owner=r["owner"],
        due_date=r["due_date"], status=r["status"],
        evidence=r["evidence"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_review(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 120:
        raise ValidationError("Title must be 120 characters or fewer")
    out["title"] = title

    rtype = (data.get("review_type") or DEFAULT_REVIEW_TYPE).strip()
    if rtype not in REVIEW_TYPES:
        raise ValidationError(
            f"Review type must be one of {', '.join(REVIEW_TYPES)}")
    out["review_type"] = rtype

    out["focus_area"] = (data.get("focus_area") or "").strip() or None

    lead = (data.get("lead_reviewer") or "").strip()
    if not lead:
        raise ValidationError("Lead reviewer is required")
    out["lead_reviewer"] = lead
    out["additional_team"] = (data.get("additional_team") or "").strip() or None

    out["review_date"] = _validate_date(data.get("review_date"),
                                          "Review date")

    status = (data.get("status") or DEFAULT_REVIEW_STATUS).strip()
    if status not in REVIEW_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(REVIEW_STATUSES)}")
    out["status"] = status

    judgement = (data.get("judgement") or DEFAULT_JUDGEMENT).strip()
    if judgement not in JUDGEMENTS:
        raise ValidationError(
            f"Judgement must be one of {', '.join(JUDGEMENTS)}")
    out["judgement"] = judgement

    out["strengths"]              = (data.get("strengths") or "").strip() or None
    out["areas_for_development"]  = (data.get("areas_for_development") or "").strip() or None
    out["summary"]                = (data.get("summary") or "").strip() or None
    out["follow_up_date"]         = _validate_date(
        data.get("follow_up_date"), "Follow-up date", required=False)
    out["notes"]                  = (data.get("notes") or "").strip() or None

    if (out["status"] in ("Complete", "Closed")
            and out["judgement"] == "Not judged"):
        raise ValidationError(
            f"Judgement is required when status is {out['status']}")
    if (out["follow_up_date"]
            and out["follow_up_date"] < out["review_date"]):
        raise ValidationError(
            "Follow-up date cannot be before review date")
    return out


def _validate_action(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rid_raw = data.get("review_id")
    if rid_raw in (None, ""):
        raise ValidationError("Review ID is required")
    try:
        out["review_id"] = int(rid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Review ID must be a number") from None

    action = (data.get("action") or "").strip()
    if not action:
        raise ValidationError("Action description is required")
    out["action"] = action

    out["owner"]    = (data.get("owner") or "").strip() or None
    out["due_date"] = _validate_date(data.get("due_date"), "Due date",
                                       required=False)

    status = (data.get("status") or DEFAULT_ACTION_STATUS).strip()
    if status not in ACTION_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ACTION_STATUSES)}")
    out["status"] = status

    out["evidence"] = (data.get("evidence") or "").strip() or None
    out["notes"]    = (data.get("notes") or "").strip() or None
    if status == "Done" and not out["evidence"]:
        raise ValidationError(
            "Evidence is required when an action is marked Done")
    return out


# ── Reviews ──────────────────────────────────────────────────────

def create_review(data: dict[str, Any]) -> QAReview:
    init_db()
    payload = _validate_review(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO qa_reviews
                       (title, review_type, focus_area, lead_reviewer,
                        additional_team, review_date, status,
                        judgement, strengths, areas_for_development,
                        summary, follow_up_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["title"], payload["review_type"],
                 payload["focus_area"], payload["lead_reviewer"],
                 payload["additional_team"], payload["review_date"],
                 payload["status"], payload["judgement"],
                 payload["strengths"], payload["areas_for_development"],
                 payload["summary"], payload["follow_up_date"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create QA review")
        raise
    rec = get_review(new_id)
    assert rec is not None
    logger.info("Created QA review #%d %r (%s, %s, status=%s)",
                rec.review_id, rec.title, rec.review_type,
                rec.judgement, rec.status)
    return rec


def get_review(review_id: int) -> QAReview | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM qa_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_review(%s) failed", review_id)
        raise
    return _row_review(r) if r else None


def list_reviews(*, review_type: str | None = None,
                 status: str | None = None,
                 judgement: str | None = None,
                 lead_reviewer: str | None = None,
                 date_from: str | None = None,
                 date_to: str | None = None) -> list[QAReview]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if review_type:
        if review_type not in REVIEW_TYPES:
            raise ValidationError(
                f"Type filter must be one of {', '.join(REVIEW_TYPES)}")
        where.append("review_type = ?")
        params.append(review_type)
    if status:
        if status not in REVIEW_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(REVIEW_STATUSES)}")
        where.append("status = ?")
        params.append(status)
    if judgement:
        if judgement not in JUDGEMENTS:
            raise ValidationError(
                f"Judgement filter must be one of "
                f"{', '.join(JUDGEMENTS)}")
        where.append("judgement = ?")
        params.append(judgement)
    if lead_reviewer:
        where.append("lead_reviewer = ?")
        params.append(lead_reviewer.strip())
    if date_from:
        where.append("review_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("review_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = "SELECT * FROM qa_reviews"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY review_date DESC, review_id DESC"
    try:
        with _connect() as conn:
            return [_row_review(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_reviews failed")
        raise


def update_review(review_id: int,
                  data: dict[str, Any]) -> QAReview:
    init_db()
    existing = get_review(review_id)
    if existing is None:
        raise ValidationError(f"No QA review #{review_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("title", "review_type", "focus_area",
                         "lead_reviewer", "additional_team",
                         "review_date", "status", "judgement",
                         "strengths", "areas_for_development",
                         "summary", "follow_up_date", "notes")}
    payload = _validate_review(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE qa_reviews SET
                       title = ?, review_type = ?, focus_area = ?,
                       lead_reviewer = ?, additional_team = ?,
                       review_date = ?, status = ?, judgement = ?,
                       strengths = ?, areas_for_development = ?,
                       summary = ?, follow_up_date = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE review_id = ?""",
                (payload["title"], payload["review_type"],
                 payload["focus_area"], payload["lead_reviewer"],
                 payload["additional_team"], payload["review_date"],
                 payload["status"], payload["judgement"],
                 payload["strengths"], payload["areas_for_development"],
                 payload["summary"], payload["follow_up_date"],
                 payload["notes"], review_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update QA review #%d", review_id)
        raise
    rec = get_review(review_id)
    assert rec is not None
    logger.info("Updated QA review #%d (status %s, judgement %s)",
                rec.review_id, rec.status, rec.judgement)
    return rec


def set_review_status(review_id: int, status: str) -> QAReview:
    return update_review(review_id, {"status": status})


def delete_review(review_id: int) -> bool:
    init_db()
    existing = get_review(review_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM qa_reviews WHERE review_id = ?",
                (review_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete QA review #%d", review_id)
        raise
    if deleted:
        logger.info("Deleted QA review #%d %r (cascade: actions)",
                    review_id, existing.title)
    return deleted


# ── Actions ──────────────────────────────────────────────────────

def add_action(data: dict[str, Any]) -> QAAction:
    init_db()
    payload = _validate_action(data)
    if get_review(payload["review_id"]) is None:
        raise ValidationError(
            f"No QA review #{payload['review_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO qa_actions
                       (review_id, action, owner, due_date, status,
                        evidence, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["review_id"], payload["action"],
                 payload["owner"], payload["due_date"],
                 payload["status"], payload["evidence"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to add action to QA review %d",
            payload["review_id"])
        raise
    logger.info("Added QA action #%d to review #%d (owner=%s, due=%s)",
                new_id, payload["review_id"], payload["owner"],
                payload["due_date"])
    rec = get_action(new_id)
    assert rec is not None
    return rec


def get_action(action_id: int) -> QAAction | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM qa_actions WHERE action_id = ?",
                (action_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_action(%s) failed", action_id)
        raise
    return _row_action(r) if r else None


def list_actions(*, review_id: int | None = None,
                 status: str | None = None,
                 owner: str | None = None,
                 overdue_only: bool = False) -> list[QAAction]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if review_id is not None:
        where.append("review_id = ?")
        params.append(int(review_id))
    if status:
        if status not in ACTION_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(ACTION_STATUSES)}")
        where.append("status = ?")
        params.append(status)
    if owner:
        where.append("owner = ?")
        params.append(owner.strip())
    if overdue_only:
        today = _dt.date.today().isoformat()
        where.append(
            "status NOT IN ('Done', 'Cancelled') "
            "AND due_date IS NOT NULL AND due_date < ?")
        params.append(today)
    sql = "SELECT * FROM qa_actions"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY due_date IS NULL, due_date, action_id"
    try:
        with _connect() as conn:
            return [_row_action(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_actions failed")
        raise


def update_action(action_id: int,
                   data: dict[str, Any]) -> QAAction:
    init_db()
    existing = get_action(action_id)
    if existing is None:
        raise ValidationError(f"No QA action #{action_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("review_id", "action", "owner", "due_date",
                         "status", "evidence", "notes")}
    payload = _validate_action(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE qa_actions SET
                       action = ?, owner = ?, due_date = ?,
                       status = ?, evidence = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE action_id = ?""",
                (payload["action"], payload["owner"],
                 payload["due_date"], payload["status"],
                 payload["evidence"], payload["notes"], action_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update QA action #%d", action_id)
        raise
    rec = get_action(action_id)
    assert rec is not None
    logger.info("Updated QA action #%d (status %s)",
                action_id, rec.status)
    return rec


def delete_action(action_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM qa_actions WHERE action_id = ?",
                (action_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete QA action #%d", action_id)
        raise
    if deleted:
        logger.info("Deleted QA action #%d", action_id)
    return deleted


def review_summary(review_id: int) -> dict[str, Any]:
    init_db()
    rec = get_review(review_id)
    if rec is None:
        raise ValidationError(f"No QA review #{review_id}")
    actions = list_actions(review_id=review_id)
    return {
        "review":   rec,
        "actions":  actions,
        "open_actions":  sum(1 for a in actions
                             if a.status not in ("Done", "Cancelled")),
        "done_actions":  sum(1 for a in actions if a.status == "Done"),
        "overdue":       sum(1 for a in actions if a.overdue),
    }


def cohort_summary() -> dict[str, Any]:
    reviews = list_reviews()
    actions = list_actions()
    return {
        "reviews":         len(reviews),
        "by_status":       dict(Counter(r.status for r in reviews)),
        "by_judgement":    dict(Counter(r.judgement for r in reviews)),
        "by_type":         dict(Counter(r.review_type for r in reviews)),
        "actions":         len(actions),
        "open_actions":    sum(1 for a in actions
                                if a.status not in ("Done",
                                                       "Cancelled")),
        "overdue_actions": sum(1 for a in actions if a.overdue),
    }
