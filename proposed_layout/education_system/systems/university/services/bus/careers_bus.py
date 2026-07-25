"""Cross-domain careers / engagement service.

Career Services, Alumni, Job Board, Internships, Placement Hours,
Employee Portal and Apprenticeships all model the same shape:
*a student is connected to an employer for a period of time*.
This module unifies that under a single ``engagements`` table and
declares Employee Portal as the canonical writer for ``employers``.

Public surface:

* Engagements (kind = job | internship | placement | apprenticeship | mentorship):
  - ``start_engagement(...)``     → ``engagement_id``  (publishes started)
  - ``end_engagement(...)``       (publishes ended)
  - ``log_hours(...)``            (publishes hours_logged; auto-fires
                                  EVENT_GRADE_CHANGED when hours hit
                                  the engagement's ``hours_required``).
  - ``list_engagements(student_id, kind=None)``
  - ``engagement_progress(engagement_id)``
* Employers (single-writer surface):
  - ``get_employer(employer_id)``
  - ``list_employers(filters)``
  - ``upsert_employer(...)``      — Employee Portal calls this; everyone
                                    else reads through ``get_employer``.
* Job board:
  - ``post_job(...)`` (publishes EVENT_JOB_POSTED)
  - ``recent_jobs(category=, since=)``
* Apprenticeship-specific:
  - ``apprenticeship_off_job_hours(engagement_id)`` — derived from
    ``attendance_records``, no parallel tracker.
* Alumni helpers:
  - ``snapshot_alumni_employer(student_id)`` — derives current_employer
    from the most recent job/internship engagement.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


_ENGAGEMENTS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS engagements (
    engagement_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL,
    student_id      TEXT NOT NULL,
    employer_id     INTEGER,
    role            TEXT,
    started_on      TEXT,
    ended_on        TEXT,
    hours_required  REAL,
    hours_logged    REAL NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active',
    source_table    TEXT,
    source_id       INTEGER,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
)
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_engagements_student "
    "ON engagements(student_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_engagements_kind "
    "ON engagements(kind, status)",
    "CREATE INDEX IF NOT EXISTS idx_engagements_employer "
    "ON engagements(employer_id)",
)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_ENGAGEMENTS_SCHEMA_SQL)
    for sql in _INDEX_SQL:
        conn.execute(sql)


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.systems.university.interfaces.gui.academics._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("careers bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Engagements
# ---------------------------------------------------------------------------

VALID_KINDS = ("job", "internship", "placement", "apprenticeship", "mentorship")


def start_engagement(
    *,
    kind: str,
    student_id: str | int,
    employer_id: int | None = None,
    role: str | None = None,
    started_on: str | None = None,
    hours_required: float | None = None,
    source_table: str | None = None,
    source_id: int | None = None,
    notes: str | None = None,
) -> int | None:
    """Open a new engagement row and broadcast.

    ``kind`` must be one of :data:`VALID_KINDS`. ``hours_required``
    only applies to placement/apprenticeship/internship; when set,
    ``log_hours`` will fire ``EVENT_GRADE_CHANGED`` once the cumulative
    total reaches it.
    """
    if kind not in VALID_KINDS or not student_id:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = (started_on or now)[:10]
    new_id: int | None = None
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            cur = conn.execute(
                "INSERT INTO engagements "
                "(kind, student_id, employer_id, role, started_on, "
                " hours_required, hours_logged, status, "
                " source_table, source_id, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, 'active', ?, ?, ?, ?, ?)",
                (kind, str(student_id), employer_id, role, today,
                 hours_required, source_table, source_id, notes,
                 now, now),
            )
            new_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("start_engagement(%s) failed: %s", kind, exc)
        return None

    _publish(
        "careers.engagement.started",
        engagement_id=new_id, kind=kind,
        student_id=str(student_id), employer_id=employer_id,
        role=role, hours_required=hours_required,
    )
    return new_id


def end_engagement(engagement_id: int, *,
                   ended_on: str | None = None,
                   status: str = "completed") -> bool:
    if not engagement_id:
        return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    end_date = (ended_on or now)[:10]
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT student_id, kind FROM engagements WHERE engagement_id = ?",
                (int(engagement_id),),
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE engagements SET ended_on = ?, status = ?, "
                "    updated_at = ? WHERE engagement_id = ?",
                (end_date, status, now, int(engagement_id)),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("end_engagement(%s) failed: %s", engagement_id, exc)
        return False

    _publish(
        "careers.engagement.ended",
        engagement_id=engagement_id, kind=row["kind"],
        student_id=row["student_id"], status=status, ended_on=end_date,
    )
    return True


def log_hours(engagement_id: int, hours: float,
              *, log_date: str | None = None,
              activity: str | None = None,
              supervisor_signoff: str | None = None) -> dict[str, Any]:
    """Append a placement-hours row and update the engagement total.

    When the running ``hours_logged`` reaches ``hours_required``,
    publishes ``EVENT_GRADE_CHANGED`` with ``action='hours_complete'``
    so Grade Tracking can mark the credit-bearing module passed.

    Returns ``{ok, hours_logged, hours_required, completed}``.
    """
    out: dict[str, Any] = {
        "ok": False, "hours_logged": 0.0,
        "hours_required": None, "completed": False,
    }
    if not engagement_id or hours is None:
        return out
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = (log_date or now)[:10]
    h = float(hours)
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT student_id, kind, hours_logged, hours_required "
                "FROM engagements WHERE engagement_id = ?",
                (int(engagement_id),),
            ).fetchone()
            if not row:
                return out
            new_total = float(row["hours_logged"] or 0) + h
            conn.execute(
                "UPDATE engagements SET hours_logged = ?, updated_at = ? "
                "WHERE engagement_id = ?",
                (new_total, now, int(engagement_id)),
            )
            # Append to legacy log table when present.
            try:
                conn.execute(
                    "INSERT INTO placement_hours_log "
                    "(student_id, log_date, hours, activity, "
                    " supervisor_signoff, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (row["student_id"], today, h, activity,
                     supervisor_signoff, f"engagement:{engagement_id}"),
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()

        out.update({
            "ok": True, "hours_logged": new_total,
            "hours_required": row["hours_required"],
        })
        if (row["hours_required"] is not None
                and new_total >= float(row["hours_required"] or 0)):
            out["completed"] = True
            try:
                from education_system.systems.university.interfaces.gui.academics._event_bus import (
                    publish, EVENT_GRADE_CHANGED,
                )
                publish(
                    EVENT_GRADE_CHANGED,
                    student_id=row["student_id"],
                    engagement_id=engagement_id,
                    action="hours_complete",
                    hours_logged=new_total,
                    hours_required=row["hours_required"],
                    source="careers_bus",
                )
            except Exception:
                pass

        _publish(
            "careers.hours.logged",
            engagement_id=engagement_id,
            student_id=row["student_id"],
            kind=row["kind"], hours=h,
            hours_logged=new_total,
            hours_required=row["hours_required"],
            completed=out["completed"],
        )
    except Exception as exc:
        logger.warning("log_hours(%s) failed: %s", engagement_id, exc)
    return out


def list_engagements(student_id: str | int | None = None,
                     kind: str | None = None,
                     *, only_active: bool = False
                     ) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            params: list[Any] = []
            sql = ("SELECT engagement_id, kind, student_id, employer_id, "
                   "       role, started_on, ended_on, hours_required, "
                   "       hours_logged, status "
                   "FROM engagements WHERE 1=1 ")
            if student_id is not None:
                sql += "AND student_id = ? "
                params.append(str(student_id))
            if kind:
                sql += "AND kind = ? "
                params.append(kind)
            if only_active:
                sql += "AND status = 'active' "
            sql += "ORDER BY COALESCE(started_on, '') DESC, engagement_id DESC"
            for r in conn.execute(sql, tuple(params)).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_engagements failed: %s", exc)
    return out


def engagement_progress(engagement_id: int) -> dict[str, Any]:
    """Return ``{kind, hours_logged, hours_required, percent}``.

    For ``kind='apprenticeship'`` includes ``off_job_hours`` derived
    from attendance, since the levy rule wants 20% off-the-job.
    """
    out: dict[str, Any] = {}
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT engagement_id, kind, student_id, "
                "       hours_logged, hours_required, status "
                "FROM engagements WHERE engagement_id = ?",
                (int(engagement_id),),
            ).fetchone()
            if not row:
                return out
            out = dict(row)
            req = float(out.get("hours_required") or 0)
            done = float(out.get("hours_logged") or 0)
            out["percent"] = round((done / req) * 100, 1) if req > 0 else None
            if out["kind"] == "apprenticeship":
                out["off_job_hours"] = apprenticeship_off_job_hours(
                    engagement_id,
                )
    except Exception as exc:
        logger.warning("engagement_progress(%s) failed: %s",
                       engagement_id, exc)
    return out


def apprenticeship_off_job_hours(engagement_id: int) -> float:
    """Sum the apprentice's classroom attendance to certify off-job hours.

    Treats each ``attendance_records`` row with status='present' as
    ~1h of off-job training. The university audit then reconciles
    against the levy 20% rule.
    """
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT student_id FROM engagements WHERE engagement_id = ?",
                (int(engagement_id),),
            ).fetchone()
            if not row:
                return 0.0
            cnt = conn.execute(
                "SELECT COUNT(*) FROM attendance_records "
                "WHERE student_id = ? AND LOWER(status) = 'present'",
                (row["student_id"],),
            ).fetchone()
            return float(cnt[0] or 0)
    except Exception as exc:
        logger.warning("apprenticeship_off_job_hours failed: %s", exc)
        return 0.0


# ---------------------------------------------------------------------------
# Employers — Employee Portal is the canonical writer
# ---------------------------------------------------------------------------

def get_employer(employer_id: int) -> dict[str, Any] | None:
    if employer_id is None:
        return None
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM employers WHERE employer_id = ?",
                (int(employer_id),),
            ).fetchone()
            return dict(row) if row else None
    except Exception as exc:
        logger.warning("get_employer(%s) failed: %s", employer_id, exc)
        return None


def list_employers(*, industry: str | None = None,
                   verified_only: bool = False) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            sql = "SELECT * FROM employers WHERE 1=1 "
            params: list[Any] = []
            if industry:
                sql += "AND LOWER(COALESCE(industry,'')) = LOWER(?) "
                params.append(industry)
            if verified_only:
                sql += "AND COALESCE(is_verified, 0) = 1 "
            sql += "ORDER BY company_name"
            for r in conn.execute(sql, tuple(params)).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_employers failed: %s", exc)
    return out


def upsert_employer(*, employer_id: int | None = None,
                    company_name: str,
                    industry: str | None = None,
                    contact_email: str | None = None,
                    contact_phone: str | None = None,
                    address: str | None = None,
                    description: str | None = None) -> int | None:
    """Single canonical writer for the employers table.

    Returns the (existing or new) employer_id. Other GUIs route
    through this rather than INSERTing employers themselves.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            if employer_id is not None:
                conn.execute(
                    "UPDATE employers SET company_name = ?, industry = ?, "
                    "  contact_email = ?, contact_phone = ?, "
                    "  address = ?, description = ? "
                    "WHERE employer_id = ?",
                    (company_name, industry, contact_email,
                     contact_phone, address, description,
                     int(employer_id)),
                )
                conn.commit()
                return int(employer_id)
            cur = conn.execute(
                "INSERT INTO employers "
                "(company_name, industry, contact_email, "
                " contact_phone, address, description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (company_name, industry, contact_email,
                 contact_phone, address, description, now),
            )
            conn.commit()
            return cur.lastrowid
    except Exception as exc:
        logger.warning("upsert_employer failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Job board
# ---------------------------------------------------------------------------

def post_job(*, employer_id: int | None = None,
             company_name: str = "",
             job_title: str,
             job_description: str = "",
             location: str | None = None,
             job_type: str | None = None,
             category: str | None = None,
             posted_by: str | None = None,
             expiry_date: str | None = None) -> int | None:
    if not job_title:
        return None
    now = datetime.now().strftime("%Y-%m-%d")
    new_id: int | None = None
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO job_postings "
                "(posted_by, company_name, job_title, job_description, "
                " location, job_type, category, employer_id, "
                " post_date, expiry_date, is_active, applications_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)",
                (posted_by, company_name, job_title, job_description,
                 location, job_type, category, employer_id, now,
                 expiry_date),
            )
            new_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("post_job failed: %s", exc)
        return None

    _publish(
        "careers.job.posted",
        job_id=new_id, employer_id=employer_id,
        company_name=company_name, job_title=job_title,
        category=category, job_type=job_type,
    )
    return new_id


def recent_jobs(*, category: str | None = None,
                since: str | None = None,
                limit: int = 20) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            sql = (
                "SELECT job_id, company_name, job_title, location, "
                "       job_type, category, post_date, expiry_date "
                "FROM job_postings "
                "WHERE COALESCE(is_active, 1) = 1 "
            )
            params: list[Any] = []
            if category:
                sql += "AND LOWER(COALESCE(category,'')) = LOWER(?) "
                params.append(category)
            if since:
                sql += "AND COALESCE(post_date, posted_date) >= ? "
                params.append(since[:10])
            sql += "ORDER BY COALESCE(post_date, posted_date) DESC LIMIT ?"
            params.append(int(limit))
            for r in conn.execute(sql, tuple(params)).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("recent_jobs failed: %s", exc)
    return out


# ---------------------------------------------------------------------------
# Application gate (#5)
# ---------------------------------------------------------------------------

def can_apply(student_id: str | int) -> dict[str, Any]:
    """Return ``{ok, reason}`` — refuse with active finance hold."""
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            has_active_hold,
        )
        if has_active_hold(student_id):
            return {"ok": False,
                    "reason": "Active finance hold — resolve outstanding "
                              "charges before applying."}
    except Exception:
        pass
    return {"ok": True, "reason": ""}


# ---------------------------------------------------------------------------
# Levy spend (#11)
# ---------------------------------------------------------------------------

def post_apprenticeship_levy_charge(engagement_id: int, amount: float,
                                    *, description: str | None = None,
                                    posted_by: str | None = None
                                    ) -> int | None:
    """Post a levy-funded training charge to the restricted ledger.

    Subject of the charge is the engagement's student_id (legible
    audit trail) but the ``reference_id`` ties to the engagement, not
    the student personally — Finance subscribers route to the levy
    fund.
    """
    if not engagement_id or not amount:
        return None
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT student_id FROM engagements WHERE engagement_id = ?",
                (int(engagement_id),),
            ).fetchone()
            if not row:
                return None
            sid = row["student_id"]
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
        return raise_charge(
            sid, float(amount),
            source="apprenticeship_levy",
            description=description or
                f"Apprenticeship levy spend — engagement #{engagement_id}",
            reference_id=f"engagement:{engagement_id}",
            processed_by=posted_by,
        )
    except Exception as exc:
        logger.warning("post_apprenticeship_levy_charge failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Alumni snapshot (#10)
# ---------------------------------------------------------------------------

def snapshot_alumni_employer(student_id: str | int) -> bool:
    """Update the alumni record's current_employer from the most recent
    job/internship engagement. No-ops when no row exists yet."""
    if not student_id:
        return False
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT e.role, e.employer_id, emp.company_name "
                "FROM engagements e "
                "LEFT JOIN employers emp ON e.employer_id = emp.employer_id "
                "WHERE e.student_id = ? "
                "  AND e.kind IN ('job', 'internship') "
                "ORDER BY COALESCE(e.ended_on, e.started_on, '') DESC "
                "LIMIT 1",
                (str(student_id),),
            ).fetchone()
            if not row or not row["company_name"]:
                return False
            conn.execute(
                "UPDATE alumni SET current_employer = ?, "
                "       job_title = COALESCE(?, job_title) "
                "WHERE student_id = ?",
                (row["company_name"], row["role"], str(student_id)),
            )
            conn.commit()
            return True
    except Exception as exc:
        logger.warning("snapshot_alumni_employer(%s) failed: %s",
                       student_id, exc)
        return False


__all__ = [
    "VALID_KINDS",
    "start_engagement", "end_engagement", "log_hours",
    "list_engagements", "engagement_progress",
    "apprenticeship_off_job_hours",
    "get_employer", "list_employers", "upsert_employer",
    "post_job", "recent_jobs",
    "can_apply",
    "post_apprenticeship_levy_charge",
    "snapshot_alumni_employer",
]
