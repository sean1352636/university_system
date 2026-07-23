"""Safeguarding-log data layer for the Sixth Form System.

UK schools must keep auditable records of safeguarding concerns. This
module models the two tables those records typically need:

* ``safeguarding_concerns`` — one row per concern, with category,
  risk level, status, DSL notification and referral fields.
* ``safeguarding_updates`` — chronological notes attached to a concern,
  so the file shows what happened next.

**Access control is NOT enforced here.** Safeguarding data is sensitive
and access must be restricted by the auth layer (DSL / senior staff
only). This module assumes the caller has been authorised.

Cascade: deleting a student wipes their concerns; deleting a concern
wipes its update chronology.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SAFEGUARDING_DB

CONCERN_TYPES: tuple[str, ...] = (
    "Disclosure", "Observation", "Allegation",
    "Third-party report", "Self-disclosure", "Other",
)

CATEGORIES: tuple[str, ...] = (
    "Physical", "Emotional", "Sexual", "Neglect",
    "Online/Cyber", "Bullying", "Mental Health", "Self-harm",
    "Substance Misuse", "Radicalisation / Prevent",
    "Domestic", "FGM", "Child Sexual Exploitation",
    "Child Criminal Exploitation", "Missing Education",
    "Other",
)

RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High", "Critical")

STATUSES: tuple[str, ...] = (
    "Open", "Under Investigation", "Resolved", "Closed", "Escalated",
)
DEFAULT_STATUS: str = "Open"

# These count as "active" when computing dashboards.
OPEN_STATUSES: tuple[str, ...] = (
    "Open", "Under Investigation", "Escalated",
)

AGENCIES: tuple[str, ...] = (
    "Children's Social Care", "MASH", "LADO", "Police",
    "CAMHS", "NSPCC", "Local Authority", "Health Visitor",
    "Early Help", "School Nurse", "Other",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS safeguarding_concerns (
    concern_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          TEXT NOT NULL,
    concern_date        TEXT NOT NULL,
    reported_date       TEXT NOT NULL,
    concern_type        TEXT NOT NULL,
    category            TEXT NOT NULL,
    risk_level          TEXT NOT NULL,
    reported_by         TEXT NOT NULL,
    description         TEXT NOT NULL,
    action_taken        TEXT,
    dsl_notified        INTEGER NOT NULL DEFAULT 0,
    dsl_name            TEXT,
    dsl_notified_at     TEXT,
    parents_informed    INTEGER NOT NULL DEFAULT 0,
    parents_informed_at TEXT,
    external_agencies   TEXT,
    referral_made       INTEGER NOT NULL DEFAULT 0,
    referral_date       TEXT,
    referral_ref        TEXT,
    status              TEXT NOT NULL DEFAULT 'Open',
    follow_up_date      TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS safeguarding_updates (
    update_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id    INTEGER NOT NULL,
    update_date   TEXT NOT NULL,
    update_text   TEXT NOT NULL,
    updated_by    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (concern_id)
        REFERENCES safeguarding_concerns(concern_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sgc_student  ON safeguarding_concerns(student_id);
CREATE INDEX IF NOT EXISTS idx_sgc_status   ON safeguarding_concerns(status);
CREATE INDEX IF NOT EXISTS idx_sgc_risk     ON safeguarding_concerns(risk_level);
CREATE INDEX IF NOT EXISTS idx_sgc_category ON safeguarding_concerns(category);
CREATE INDEX IF NOT EXISTS idx_sgu_concern  ON safeguarding_updates(concern_id);
"""


@dataclass
class Concern:
    concern_id: int
    student_id: str
    concern_date: str
    reported_date: str
    concern_type: str
    category: str
    risk_level: str
    reported_by: str
    description: str
    action_taken: str | None
    dsl_notified: bool
    dsl_name: str | None
    dsl_notified_at: str | None
    parents_informed: bool
    parents_informed_at: str | None
    external_agencies: str | None
    referral_made: bool
    referral_date: str | None
    referral_ref: str | None
    status: str
    follow_up_date: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Update:
    update_id: int
    concern_id: int
    update_date: str
    update_text: str
    updated_by: str | None
    created_at: str


@dataclass
class ConcernRow:
    concern: Concern
    student_name: str
    update_count: int


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
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Safeguarding schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_concern(r: sqlite3.Row) -> Concern:
    return Concern(
        concern_id=r["concern_id"], student_id=r["student_id"],
        concern_date=r["concern_date"], reported_date=r["reported_date"],
        concern_type=r["concern_type"], category=r["category"],
        risk_level=r["risk_level"], reported_by=r["reported_by"],
        description=r["description"], action_taken=r["action_taken"],
        dsl_notified=bool(r["dsl_notified"]), dsl_name=r["dsl_name"],
        dsl_notified_at=r["dsl_notified_at"],
        parents_informed=bool(r["parents_informed"]),
        parents_informed_at=r["parents_informed_at"],
        external_agencies=r["external_agencies"],
        referral_made=bool(r["referral_made"]),
        referral_date=r["referral_date"], referral_ref=r["referral_ref"],
        status=r["status"], follow_up_date=r["follow_up_date"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_update(r: sqlite3.Row) -> Update:
    return Update(
        update_id=r["update_id"], concern_id=r["concern_id"],
        update_date=r["update_date"], update_text=r["update_text"],
        updated_by=r["updated_by"], created_at=r["created_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid safeguarding input."""


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
    return s


def _coerce_bool(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "true", "yes", "y", "on") else 0
    return 1 if bool(value) else 0


def _validate_concern_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    out["concern_date"] = _validate_date(
        _require(data.get("concern_date"), "Concern date"), "Concern date")
    out["reported_date"] = _validate_date(
        _require(data.get("reported_date"), "Reported date"),
        "Reported date")
    if out["reported_date"] < out["concern_date"]:
        raise ValidationError(
            "Reported date cannot be before the concern date")

    ctype = _require(data.get("concern_type"), "Concern type").strip()
    if ctype not in CONCERN_TYPES:
        raise ValidationError(
            f"Concern type must be one of: {', '.join(CONCERN_TYPES)}")
    out["concern_type"] = ctype

    category = _require(data.get("category"), "Category").strip()
    if category not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = category

    risk = _require(data.get("risk_level"), "Risk level").strip()
    if risk not in RISK_LEVELS:
        raise ValidationError(
            f"Risk level must be one of: {', '.join(RISK_LEVELS)}")
    out["risk_level"] = risk

    out["reported_by"] = _require(
        data.get("reported_by"), "Reported by").strip()
    out["description"] = _require(
        data.get("description"), "Description").strip()

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["dsl_notified"] = _coerce_bool(data.get("dsl_notified"))
    out["dsl_name"] = (data.get("dsl_name") or "").strip() or None
    out["dsl_notified_at"] = _validate_date(
        data.get("dsl_notified_at"), "DSL notified at")
    out["parents_informed"] = _coerce_bool(data.get("parents_informed"))
    out["parents_informed_at"] = _validate_date(
        data.get("parents_informed_at"), "Parents informed at")
    out["referral_made"] = _coerce_bool(data.get("referral_made"))
    out["referral_date"] = _validate_date(
        data.get("referral_date"), "Referral date")
    out["follow_up_date"] = _validate_date(
        data.get("follow_up_date"), "Follow-up date")

    # Sanity: if dsl_notified is False but dsl_notified_at is set, clear it.
    if not out["dsl_notified"]:
        out["dsl_notified_at"] = None
    if not out["parents_informed"]:
        out["parents_informed_at"] = None
    if not out["referral_made"]:
        out["referral_date"] = None

    # External agencies: free-text comma-separated. Optionally normalise
    # against AGENCIES — but staff may write site-specific names, so
    # we don't reject unknowns.
    out["external_agencies"] = (
        data.get("external_agencies") or "").strip() or None
    out["referral_ref"] = (data.get("referral_ref") or "").strip() or None
    out["action_taken"] = (data.get("action_taken") or "").strip() or None
    out["notes"]        = (data.get("notes") or "").strip() or None
    return out


def _validate_update_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["update_date"] = _validate_date(
        _require(data.get("update_date"), "Update date"), "Update date")
    out["update_text"] = _require(
        data.get("update_text"), "Update text").strip()
    out["updated_by"] = (data.get("updated_by") or "").strip() or None
    return out


# ── Concern CRUD ──────────────────────────────────────────────────

def create_concern(data: dict[str, Any]) -> Concern:
    init_db()
    try:
        p = _validate_concern_payload(data)
    except ValidationError as e:
        logger.warning("create_concern validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_concerns
                   (student_id, concern_date, reported_date, concern_type,
                    category, risk_level, reported_by, description,
                    action_taken, dsl_notified, dsl_name, dsl_notified_at,
                    parents_informed, parents_informed_at,
                    external_agencies, referral_made, referral_date,
                    referral_ref, status, follow_up_date, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (p["student_id"], p["concern_date"], p["reported_date"],
             p["concern_type"], p["category"], p["risk_level"],
             p["reported_by"], p["description"], p["action_taken"],
             p["dsl_notified"], p["dsl_name"], p["dsl_notified_at"],
             p["parents_informed"], p["parents_informed_at"],
             p["external_agencies"], p["referral_made"],
             p["referral_date"], p["referral_ref"], p["status"],
             p["follow_up_date"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_concern(new_id)
    assert out is not None
    logger.info(
        "Created safeguarding concern #%d for %s "
        "(%s, risk=%s, status=%s, dsl=%s, referral=%s)",
        new_id, p["student_id"], p["category"], p["risk_level"],
        p["status"], p["dsl_notified"], p["referral_made"],
    )
    # Mirror onto the cross-system safeguarding register so a flag raised
    # in sixth form is visible at university intake (best-effort).
    try:
        from education_system.shared.safeguarding import alert_service
        alert_service.raise_flag_for_local_concern(
            "college", out.student_id, category=out.category,
            severity=out.risk_level, summary=out.category,
            source_ref=str(out.concern_id), raised_by=out.reported_by)
    except Exception:
        logger.debug("Cross-system safeguarding publish skipped for #%s",
                     out.concern_id, exc_info=True)
    return out


def get_concern(concern_id: int) -> Concern | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM safeguarding_concerns WHERE concern_id = ?",
            (concern_id,),
        ).fetchone()
        return _row_concern(r) if r else None


def list_concerns(
    *,
    student_id: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    category: str | None = None,
    reported_by_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    open_only: bool = False,
) -> list[Concern]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if risk_level:
        if risk_level not in RISK_LEVELS:
            raise ValidationError(
                f"Risk level must be one of: {', '.join(RISK_LEVELS)}")
        clauses.append("risk_level = ?")
        args.append(risk_level)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if reported_by_like:
        clauses.append("reported_by LIKE ?")
        args.append(f"%{reported_by_like.strip()}%")
    if date_from:
        clauses.append("concern_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("concern_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if open_only:
        placeholders = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({placeholders})")
        args.extend(OPEN_STATUSES)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    # Sort: open & high-risk first, then by recency.
    sql = (
        f"SELECT * FROM safeguarding_concerns {where} "
        "ORDER BY "
        "  CASE risk_level WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 "
        "                  WHEN 'Medium' THEN 2 ELSE 3 END, "
        "  CASE WHEN status IN ('Open','Under Investigation','Escalated') "
        "       THEN 0 ELSE 1 END, "
        "  concern_date DESC, concern_id DESC"
    )
    with _connect() as conn:
        return [_row_concern(r) for r in conn.execute(sql, args).fetchall()]


def concerns_for_student(student_id: str) -> list[Concern]:
    return list_concerns(student_id=student_id)


def list_concerns_with_detail(**kwargs) -> list[ConcernRow]:
    rows = list_concerns(**kwargs)
    if not rows:
        return []
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    out: list[ConcernRow] = []
    for c in rows:
        out.append(ConcernRow(
            concern=c,
            student_name=names.get(c.student_id, "(unknown)"),
            update_count=count_updates(c.concern_id),
        ))
    return out


def update_concern(concern_id: int, data: dict[str, Any]) -> Concern:
    init_db()
    existing = get_concern(concern_id)
    if existing is None:
        logger.warning("update_concern: unknown id %d", concern_id)
        raise ValidationError(f"No concern with id {concern_id}")
    p = _validate_concern_payload({
        "student_id":          existing.student_id,
        "concern_date":        data.get("concern_date", existing.concern_date),
        "reported_date":       data.get("reported_date", existing.reported_date),
        "concern_type":        data.get("concern_type", existing.concern_type),
        "category":            data.get("category", existing.category),
        "risk_level":          data.get("risk_level", existing.risk_level),
        "reported_by":         data.get("reported_by", existing.reported_by),
        "description":         data.get("description", existing.description),
        "action_taken":        data.get("action_taken", existing.action_taken),
        "dsl_notified":        data.get("dsl_notified", existing.dsl_notified),
        "dsl_name":            data.get("dsl_name", existing.dsl_name),
        "dsl_notified_at":     data.get("dsl_notified_at",
                                        existing.dsl_notified_at),
        "parents_informed":    data.get("parents_informed",
                                        existing.parents_informed),
        "parents_informed_at": data.get("parents_informed_at",
                                        existing.parents_informed_at),
        "external_agencies":   data.get("external_agencies",
                                        existing.external_agencies),
        "referral_made":       data.get("referral_made", existing.referral_made),
        "referral_date":       data.get("referral_date", existing.referral_date),
        "referral_ref":        data.get("referral_ref", existing.referral_ref),
        "status":              data.get("status", existing.status),
        "follow_up_date":      data.get("follow_up_date",
                                        existing.follow_up_date),
        "notes":               data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE safeguarding_concerns SET
                   concern_date = ?, reported_date = ?, concern_type = ?,
                   category = ?, risk_level = ?, reported_by = ?,
                   description = ?, action_taken = ?,
                   dsl_notified = ?, dsl_name = ?, dsl_notified_at = ?,
                   parents_informed = ?, parents_informed_at = ?,
                   external_agencies = ?, referral_made = ?,
                   referral_date = ?, referral_ref = ?, status = ?,
                   follow_up_date = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE concern_id = ?""",
            (p["concern_date"], p["reported_date"], p["concern_type"],
             p["category"], p["risk_level"], p["reported_by"],
             p["description"], p["action_taken"],
             p["dsl_notified"], p["dsl_name"], p["dsl_notified_at"],
             p["parents_informed"], p["parents_informed_at"],
             p["external_agencies"], p["referral_made"],
             p["referral_date"], p["referral_ref"], p["status"],
             p["follow_up_date"], p["notes"], concern_id),
        )
        conn.commit()
    out = get_concern(concern_id)
    assert out is not None
    logger.info(
        "Updated safeguarding concern #%d (status=%s, risk=%s)",
        concern_id, out.status, out.risk_level,
    )
    return out


def delete_concern(concern_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM safeguarding_concerns WHERE concern_id = ?",
            (concern_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted safeguarding concern #%d", concern_id)
            return True
        logger.warning("delete_concern: unknown id %d", concern_id)
        return False


# ── Chronology / update CRUD ──────────────────────────────────────

def add_update(concern_id: int, data: dict[str, Any]) -> Update:
    init_db()
    if get_concern(concern_id) is None:
        raise ValidationError(f"No concern with id {concern_id}")
    try:
        p = _validate_update_payload(data)
    except ValidationError as e:
        logger.warning("add_update validation failed for #%d: %s",
                       concern_id, e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_updates
                   (concern_id, update_date, update_text, updated_by,
                    created_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (concern_id, p["update_date"], p["update_text"], p["updated_by"]),
        )
        conn.commit()
        new_id = cur.lastrowid
        # Touch the parent's updated_at so the directory shows freshness.
        conn.execute(
            "UPDATE safeguarding_concerns SET updated_at = datetime('now') "
            "WHERE concern_id = ?", (concern_id,),
        )
        conn.commit()
    out = get_update(new_id)
    assert out is not None
    logger.info(
        "Added safeguarding update #%d to concern #%d (%s, by %s)",
        new_id, concern_id, p["update_date"], p["updated_by"] or "—",
    )
    return out


def get_update(update_id: int) -> Update | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM safeguarding_updates WHERE update_id = ?",
            (update_id,),
        ).fetchone()
        return _row_update(r) if r else None


def list_updates(concern_id: int) -> list[Update]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM safeguarding_updates WHERE concern_id = ? "
            "ORDER BY update_date, update_id",
            (concern_id,),
        ).fetchall()
        return [_row_update(r) for r in rows]


def count_updates(concern_id: int) -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM safeguarding_updates "
            "WHERE concern_id = ?", (concern_id,),
        ).fetchone()
        return int(r["n"])


def edit_update(update_id: int, data: dict[str, Any]) -> Update:
    init_db()
    existing = get_update(update_id)
    if existing is None:
        raise ValidationError(f"No update with id {update_id}")
    p = _validate_update_payload({
        "update_date": data.get("update_date", existing.update_date),
        "update_text": data.get("update_text", existing.update_text),
        "updated_by":  data.get("updated_by", existing.updated_by),
    })
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_updates SET update_date = ?, "
            "update_text = ?, updated_by = ? WHERE update_id = ?",
            (p["update_date"], p["update_text"], p["updated_by"], update_id),
        )
        conn.commit()
    logger.info("Edited safeguarding update #%d", update_id)
    out = get_update(update_id)
    assert out is not None
    return out


def delete_update(update_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM safeguarding_updates WHERE update_id = ?",
            (update_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted safeguarding update #%d", update_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    open_count: int
    by_status: dict[str, int]
    by_risk: dict[str, int]
    by_category: dict[str, int]
    dsl_notified: int
    parents_informed: int
    referrals: int
    upcoming_follow_ups: int     # follow_up_date within window
    overdue_follow_ups: int      # follow_up_date < today, status still open
    high_risk_open: int          # High or Critical & still open


def summary(*, upcoming_window_days: int = 14) -> Summary:
    import datetime as _dt
    init_db()
    rows = list_concerns()
    today = _dt.date.today().isoformat()
    cutoff = (_dt.date.today() + _dt.timedelta(days=upcoming_window_days)
              ).isoformat()

    by_status = {s: 0 for s in STATUSES}
    by_risk = {r: 0 for r in RISK_LEVELS}
    by_category: dict[str, int] = {}
    open_count = 0
    dsl = 0
    parents = 0
    refs = 0
    upcoming = 0
    overdue = 0
    high_open = 0
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_risk[r.risk_level] = by_risk.get(r.risk_level, 0) + 1
        by_category[r.category] = by_category.get(r.category, 0) + 1
        is_open = r.status in OPEN_STATUSES
        if is_open:
            open_count += 1
        if r.dsl_notified:
            dsl += 1
        if r.parents_informed:
            parents += 1
        if r.referral_made:
            refs += 1
        if r.risk_level in ("High", "Critical") and is_open:
            high_open += 1
        if r.follow_up_date and is_open:
            if r.follow_up_date < today:
                overdue += 1
            elif r.follow_up_date <= cutoff:
                upcoming += 1
    return Summary(
        total=len(rows), open_count=open_count,
        by_status=by_status, by_risk=by_risk, by_category=by_category,
        dsl_notified=dsl, parents_informed=parents, referrals=refs,
        upcoming_follow_ups=upcoming, overdue_follow_ups=overdue,
        high_risk_open=high_open,
    )
