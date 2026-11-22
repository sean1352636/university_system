"""Volunteering records behind the Student Union volunteering screens.

The screens used to show five made-up opportunities, a made-up 45-hour
history and a certificate that was never written. This module is what
they read and write instead:

* ``volunteer_opportunities`` — the existing table; SU staff create and
  edit rows. A ``category`` column is added for the screen's filter.
* ``volunteer_signups`` — the existing table. It was declared with a
  foreign key to ``students``, which rejected the ``user:<username>``
  owner id staff/admin accounts use (see ``identity.py``). It is rebuilt
  once, keeping every row, with that one key dropped.
* ``volunteer_hours_log`` — new. A student logs hours (optionally against
  a sign-up); SU staff verify or reject them. Only verified hours count
  toward the totals and the certificate.

Everything takes an open connection; callers commit nothing themselves.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STAFF_ROLES = frozenset({"admin", "superadmin", "administrator", "staff"})

CATEGORIES = ("Community Service", "Education", "Environment", "Health",
              "Animals", "Other")

OPPORTUNITY_STATUSES = ("open", "closed", "cancelled")

_SIGNUPS_SQL = """
CREATE TABLE volunteer_signups (
    signup_id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER,
    student_id TEXT,
    signup_date TEXT,
    hours_completed REAL DEFAULT 0.0,
    completion_date TEXT,
    feedback TEXT,
    status TEXT DEFAULT 'signed_up',
    FOREIGN KEY (opportunity_id) REFERENCES volunteer_opportunities (opportunity_id)
)"""

_OPPORTUNITIES_SQL = """
CREATE TABLE IF NOT EXISTS volunteer_opportunities (
    opportunity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_name TEXT,
    contact_person TEXT,
    contact_email TEXT,
    description TEXT,
    location TEXT,
    start_date TEXT,
    end_date TEXT,
    hours_required REAL,
    skills_needed TEXT,
    max_volunteers INTEGER,
    current_volunteers INTEGER DEFAULT 0,
    status TEXT DEFAULT 'open'
)"""

_HOURS_SQL = """
CREATE TABLE IF NOT EXISTS volunteer_hours_log (
    hours_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    opportunity_id INTEGER,
    organization TEXT NOT NULL,
    activity TEXT,
    activity_date TEXT NOT NULL,
    hours REAL NOT NULL CHECK (hours > 0),
    supervisor_name TEXT,
    supervisor_email TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'verified', 'rejected')),
    submitted_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_note TEXT,
    FOREIGN KEY (opportunity_id) REFERENCES volunteer_opportunities (opportunity_id)
)"""

_ensured: set[str] = set()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _db_key(conn) -> str:
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        return str(row[2] if row else id(conn))
    except Exception:  # pragma: no cover - defensive
        return str(id(conn))


def _columns(conn, table: str) -> list[str]:
    # db-audit: ignore[DBW001] - fixed table names only
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _add_column(conn, table: str, column: str, decl: str) -> None:
    if column not in _columns(conn, table):
        # db-audit: ignore[DBW001] - fixed identifiers only
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _drop_students_fk_from_signups(conn) -> None:
    """Rebuild ``volunteer_signups`` without its ``students`` foreign key.

    Idempotent: does nothing once the key is gone. Keeps every row and
    every extra column the live table has grown.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='volunteer_signups'"
    ).fetchone()
    if row is None:
        conn.execute(_SIGNUPS_SQL.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1))
        return
    if "REFERENCES students" not in (row[0] or ""):
        return

    old_cols = _columns(conn, "volunteer_signups")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = off")
    try:
        conn.execute("DROP TABLE IF EXISTS volunteer_signups_new")
        conn.execute(_SIGNUPS_SQL.replace("volunteer_signups", "volunteer_signups_new", 1))
        new_cols = _columns(conn, "volunteer_signups_new")
        for col in old_cols:
            if col not in new_cols:
                # db-audit: ignore[DBW001] - column names read from PRAGMA
                conn.execute(f'ALTER TABLE volunteer_signups_new ADD COLUMN "{col}"')
        cols = ", ".join(f'"{c}"' for c in old_cols)
        # db-audit: ignore[DBW001] - column names read from PRAGMA
        conn.execute(f"INSERT INTO volunteer_signups_new ({cols}) SELECT {cols} FROM volunteer_signups")
        conn.execute("DROP TABLE volunteer_signups")
        conn.execute("ALTER TABLE volunteer_signups_new RENAME TO volunteer_signups")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = on")


def ensure_schema(conn) -> None:
    """Create/upgrade the volunteering tables (idempotent, once per DB)."""
    key = _db_key(conn)
    if key in _ensured:
        return
    conn.execute(_OPPORTUNITIES_SQL)
    for col, decl in (("category", "TEXT"), ("created_by", "TEXT"),
                      ("created_at", "TEXT"), ("updated_at", "TEXT")):
        _add_column(conn, "volunteer_opportunities", col, decl)
    _drop_students_fk_from_signups(conn)
    conn.execute(_HOURS_SQL)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_volunteer_hours_owner "
                 "ON volunteer_hours_log (owner_id, status)")
    conn.commit()
    _ensured.add(key)


def is_staff(auth) -> bool:
    user = getattr(auth, "current_user", None) or {}
    try:
        return str(user.get("role") or "").lower() in STAFF_ROLES
    except AttributeError:
        return False


def _dicts(cur) -> list[dict[str, Any]]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


# ---------------------------------------------------------------- opportunities

def list_opportunities(conn, *, category: str | None = None,
                       include_closed: bool = False) -> list[dict[str, Any]]:
    ensure_schema(conn)
    sql = ("SELECT opportunity_id, organization_name, contact_person, contact_email, "
           "description, location, start_date, end_date, hours_required, "
           "skills_needed, max_volunteers, "
           "(SELECT COUNT(*) FROM volunteer_signups s "
           "  WHERE s.opportunity_id = o.opportunity_id "
           "  AND COALESCE(s.status, 'signed_up') != 'cancelled') AS signed_up, "
           "status, category FROM volunteer_opportunities o WHERE 1=1")
    params: list[Any] = []
    if not include_closed:
        sql += " AND LOWER(COALESCE(status, 'open')) = 'open'"
    if category and category != "All":
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY COALESCE(start_date, '9999'), organization_name"
    return _dicts(conn.execute(sql, params))


def get_opportunity(conn, opportunity_id: int) -> dict[str, Any] | None:
    ensure_schema(conn)
    rows = _dicts(conn.execute(
        "SELECT * FROM volunteer_opportunities WHERE opportunity_id = ?",
        (opportunity_id,)))
    return rows[0] if rows else None


def _validate_date(value: str | None, label: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD.") from exc
    return value


def save_opportunity(conn, data: dict[str, Any], *, actor: str | None,
                     opportunity_id: int | None = None) -> int:
    """Create (no id) or update an opportunity; returns its id."""
    ensure_schema(conn)
    org = (data.get("organization_name") or "").strip()
    desc = (data.get("description") or "").strip()
    if not org or not desc:
        raise ValueError("Organisation and description are required.")
    start = _validate_date(data.get("start_date"), "Start date")
    end = _validate_date(data.get("end_date"), "End date")
    if start and end and end < start:
        raise ValueError("End date is before the start date.")
    hours = data.get("hours_required")
    hours = float(hours) if str(hours or "").strip() else None
    if hours is not None and hours < 0:
        raise ValueError("Hours cannot be negative.")
    max_v = data.get("max_volunteers")
    max_v = int(max_v) if str(max_v or "").strip() else None
    if max_v is not None and max_v < 0:
        raise ValueError("Places cannot be negative.")
    status = (data.get("status") or "open").strip().lower()
    if status not in OPPORTUNITY_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(OPPORTUNITY_STATUSES)}.")

    values = (org, (data.get("contact_person") or "").strip() or None,
              (data.get("contact_email") or "").strip() or None, desc,
              (data.get("location") or "").strip() or None, start, end, hours,
              (data.get("skills_needed") or "").strip() or None, max_v, status,
              (data.get("category") or "").strip() or None)
    if opportunity_id is None:
        cur = conn.execute(
            "INSERT INTO volunteer_opportunities (organization_name, contact_person, "
            "contact_email, description, location, start_date, end_date, hours_required, "
            "skills_needed, max_volunteers, status, category, current_volunteers, "
            "created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)",
            values + (actor, _now()))
        conn.commit()
        return int(cur.lastrowid)
    if max_v is not None:
        taken = conn.execute(
            "SELECT COUNT(*) FROM volunteer_signups WHERE opportunity_id = ? "
            "AND COALESCE(status, 'signed_up') != 'cancelled'", (opportunity_id,)).fetchone()[0]
        if max_v < taken:
            raise ValueError(f"{taken} people are already signed up; places cannot be fewer.")
    conn.execute(
        "UPDATE volunteer_opportunities SET organization_name=?, contact_person=?, "
        "contact_email=?, description=?, location=?, start_date=?, end_date=?, "
        "hours_required=?, skills_needed=?, max_volunteers=?, status=?, category=?, "
        "updated_at=? WHERE opportunity_id=?",
        values + (_now(), opportunity_id))
    conn.commit()
    return int(opportunity_id)


def sign_up(conn, opportunity_id: int, owner_id: str) -> None:
    """Sign ``owner_id`` up; raises ValueError with a user-facing reason."""
    ensure_schema(conn)
    if not owner_id:
        raise ValueError("You must be signed in to sign up.")
    opp = get_opportunity(conn, opportunity_id)
    if not opp or str(opp.get("status") or "open").lower() != "open":
        raise ValueError("That opportunity is no longer open.")
    existing = conn.execute(
        "SELECT signup_id, status FROM volunteer_signups WHERE opportunity_id = ? AND student_id = ?",
        (opportunity_id, owner_id)).fetchone()
    if existing and (existing[1] or "signed_up") != "cancelled":
        raise ValueError("You are already signed up for this opportunity.")
    taken = conn.execute(
        "SELECT COUNT(*) FROM volunteer_signups WHERE opportunity_id = ? "
        "AND COALESCE(status, 'signed_up') != 'cancelled'", (opportunity_id,)).fetchone()[0]
    if opp.get("max_volunteers") and taken >= int(opp["max_volunteers"]):
        raise ValueError("This opportunity is full.")
    if existing:
        conn.execute("UPDATE volunteer_signups SET status='signed_up', signup_date=? "
                     "WHERE signup_id=?", (_now(), existing[0]))
    else:
        conn.execute(
            "INSERT INTO volunteer_signups (opportunity_id, student_id, signup_date, status) "
            "VALUES (?, ?, ?, 'signed_up')", (opportunity_id, owner_id, _now()))
    conn.execute(
        "UPDATE volunteer_opportunities SET current_volunteers = ? WHERE opportunity_id = ?",
        (taken + 1, opportunity_id))
    conn.commit()


def my_signups(conn, owner_id: str) -> list[dict[str, Any]]:
    ensure_schema(conn)
    return _dicts(conn.execute(
        "SELECT s.signup_id, s.opportunity_id, o.organization_name, o.description, "
        "o.start_date, s.signup_date, s.hours_completed, s.status "
        "FROM volunteer_signups s JOIN volunteer_opportunities o "
        "ON o.opportunity_id = s.opportunity_id WHERE s.student_id = ? "
        "ORDER BY COALESCE(o.start_date, s.signup_date) DESC", (owner_id,)))


# ---------------------------------------------------------------- hours

def submit_hours(conn, owner_id: str, *, organization: str, activity: str,
                 activity_date: str, hours: str | float, supervisor_name: str,
                 supervisor_email: str = "", opportunity_id: int | None = None) -> int:
    ensure_schema(conn)
    if not owner_id:
        raise ValueError("You must be signed in to log hours.")
    organization = (organization or "").strip()
    supervisor_name = (supervisor_name or "").strip()
    if not organization or not supervisor_name:
        raise ValueError("Organisation and supervisor name are required.")
    try:
        hours_f = float(str(hours).strip())
    except ValueError as exc:
        raise ValueError("Hours must be a number.") from exc
    if hours_f <= 0 or hours_f > 24:
        raise ValueError("Hours must be more than 0 and no more than 24 for one day.")
    day = _validate_date(activity_date, "Date")
    if not day:
        raise ValueError("Date is required.")
    if day > datetime.now().strftime("%Y-%m-%d"):
        raise ValueError("You cannot log hours for a future date.")
    email = (supervisor_email or "").strip()
    if email and "@" not in email:
        raise ValueError("Supervisor email does not look like an email address.")
    cur = conn.execute(
        "INSERT INTO volunteer_hours_log (owner_id, opportunity_id, organization, activity, "
        "activity_date, hours, supervisor_name, supervisor_email, status, submitted_at) "
        "VALUES (?,?,?,?,?,?,?,?, 'pending', ?)",
        (owner_id, opportunity_id, organization, (activity or "").strip() or None, day,
         hours_f, supervisor_name, email or None, _now()))
    conn.commit()
    return int(cur.lastrowid)


def list_hours(conn, *, owner_id: str | None = None,
               status: str | None = None) -> list[dict[str, Any]]:
    ensure_schema(conn)
    sql = "SELECT * FROM volunteer_hours_log WHERE 1=1"
    params: list[Any] = []
    if owner_id:
        sql += " AND owner_id = ?"
        params.append(owner_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY activity_date DESC, hours_id DESC"
    return _dicts(conn.execute(sql, params))


def review_hours(conn, hours_id: int, *, approve: bool, reviewer: str,
                 note: str = "") -> None:
    """Verify or reject a pending submission (SU staff)."""
    ensure_schema(conn)
    row = conn.execute(
        "SELECT owner_id, opportunity_id, hours, activity_date, status "
        "FROM volunteer_hours_log WHERE hours_id = ?", (hours_id,)).fetchone()
    if not row:
        raise ValueError("That submission no longer exists.")
    if row[4] != "pending":
        raise ValueError(f"That submission has already been {row[4]}.")
    if row[0] and reviewer and str(row[0]) == str(reviewer):
        raise ValueError("You cannot verify your own hours.")
    new_status = "verified" if approve else "rejected"
    conn.execute(
        "UPDATE volunteer_hours_log SET status=?, reviewed_by=?, reviewed_at=?, review_note=? "
        "WHERE hours_id=?", (new_status, reviewer, _now(), (note or "").strip() or None, hours_id))
    if approve and row[1] is not None:
        conn.execute(
            "UPDATE volunteer_signups SET hours_completed = COALESCE(hours_completed, 0) + ?, "
            "completion_date = ?, status = 'completed' "
            "WHERE opportunity_id = ? AND student_id = ?",
            (row[2], row[3], row[1], row[0]))
    conn.commit()


def summary(conn, owner_id: str) -> dict[str, Any]:
    ensure_schema(conn)
    verified, orgs, activities = conn.execute(
        "SELECT COALESCE(SUM(hours), 0), COUNT(DISTINCT LOWER(organization)), COUNT(*) "
        "FROM volunteer_hours_log WHERE owner_id = ? AND status = 'verified'",
        (owner_id,)).fetchone()
    pending = conn.execute(
        "SELECT COALESCE(SUM(hours), 0) FROM volunteer_hours_log "
        "WHERE owner_id = ? AND status = 'pending'", (owner_id,)).fetchone()[0]
    signups = conn.execute(
        "SELECT COUNT(*) FROM volunteer_signups WHERE student_id = ? "
        "AND COALESCE(status, 'signed_up') != 'cancelled'", (owner_id,)).fetchone()[0]
    points = 0
    try:
        points = conn.execute(
            "SELECT COALESCE(SUM(points_earned), 0) FROM student_points "
            "WHERE student_id = ? AND activity_type = 'Community Service'",
            (owner_id,)).fetchone()[0]
    except Exception:  # student_points may not exist in a bare DB
        points = 0
    return {"verified_hours": float(verified or 0), "pending_hours": float(pending or 0),
            "organisations": int(orgs or 0), "verified_entries": int(activities or 0),
            "signups": int(signups or 0), "points": int(points or 0),
            "level": volunteer_level(float(verified or 0))}


def volunteer_level(hours: float) -> str:
    """Same thresholds the CLI uses for its volunteer level."""
    if hours >= 100:
        return "Volunteer Champion (100+ hours)"
    if hours >= 50:
        return "Dedicated Volunteer (50+ hours)"
    if hours >= 20:
        return "Active Volunteer (20+ hours)"
    if hours >= 5:
        return "Community Helper (5+ hours)"
    return "Getting Started"


def display_name(conn, owner_id: str) -> str:
    """Best name for an owner id: student record, then the user account."""
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
        FALLBACK_PREFIX, is_fallback,
    )
    try:
        if is_fallback(owner_id):
            row = conn.execute("SELECT first_name, last_name, username FROM users "
                               "WHERE username = ?", (owner_id[len(FALLBACK_PREFIX):],)).fetchone()
        else:
            row = conn.execute("SELECT first_name, last_name, student_id FROM students "
                               "WHERE student_id = ?", (owner_id,)).fetchone()
        if row:
            name = " ".join(p for p in (row[0], row[1]) if p)
            return name or str(row[2])
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("display_name lookup failed: %s", exc)
    return str(owner_id)


# ---------------------------------------------------------------- certificate

class CertificateUnavailable(RuntimeError):
    """reportlab is not installed, so no PDF can be written."""


def write_certificate(conn, owner_id: str, out_dir: str | Path) -> Path:
    """Write a PDF certificate of ``owner_id``'s verified hours; return its path."""
    rows = [r for r in list_hours(conn, owner_id=owner_id, status="verified")]
    if not rows:
        raise ValueError("You have no verified volunteering hours yet.")
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise CertificateUnavailable(
            "PDF certificates need the 'reportlab' package, which is not installed.") from exc

    total = sum(float(r["hours"]) for r in rows)
    name = display_name(conn, owner_id)
    today = datetime.now()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(owner_id)).strip("_") or "volunteer"
    path = out / f"volunteer_certificate_{safe}_{today:%Y%m%d_%H%M%S}.pdf"

    styles = getSampleStyleSheet()
    story = [
        Paragraph("Student Union", styles["Title"]),
        Paragraph("Certificate of Volunteering", styles["Heading1"]),
        Spacer(1, 0.6 * cm),
        Paragraph(f"This certifies that <b>{_esc(name)}</b> ({_esc(owner_id)}) has completed "
                  f"<b>{total:.1f}</b> verified hours of volunteering.", styles["Normal"]),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Level: {_esc(volunteer_level(total))}", styles["Normal"]),
        Spacer(1, 0.6 * cm),
    ]
    data = [["Date", "Organisation", "Activity", "Hours", "Verified"]]
    for r in sorted(rows, key=lambda r: r["activity_date"]):
        data.append([r["activity_date"], _clip(r["organization"]), _clip(r.get("activity") or ""),
                     f"{float(r['hours']):.1f}", (r.get("reviewed_at") or "")[:10]])
    data.append(["", "", "Total", f"{total:.1f}", ""])
    table = Table(data, repeatRows=1, colWidths=[2.6 * cm, 5 * cm, 5 * cm, 1.6 * cm, 2.6 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story += [table, Spacer(1, 0.8 * cm),
              Paragraph(f"Issued {today:%d %B %Y}. Only hours verified by Student Union "
                        f"staff are included.", styles["Italic"])]
    SimpleDocTemplate(str(path), pagesize=A4, title="Volunteering certificate").build(story)
    return path


def _esc(text: Any) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _clip(text: Any, n: int = 40) -> str:
    text = str(text or "")
    return text if len(text) <= n else text[: n - 1] + "…"


__all__ = [
    "CATEGORIES", "OPPORTUNITY_STATUSES", "CertificateUnavailable", "display_name",
    "ensure_schema", "get_opportunity", "is_staff", "list_hours", "list_opportunities",
    "my_signups", "review_hours", "save_opportunity", "sign_up", "submit_hours",
    "summary", "volunteer_level", "write_certificate",
]
