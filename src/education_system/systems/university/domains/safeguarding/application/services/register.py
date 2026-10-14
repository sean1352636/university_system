"""Student register, category breakdown and dashboard counters.

Ported from the standalone UniGuard prototype. Three things the prototype
had that the portal did not:

* a **student register** — the people cases attach to, rather than only the
  cases themselves. Unlike the prototype this is read-only: students are
  owned by Student Records, so the register reads them and joins on the
  concern count instead of keeping a second roster.
* a **category breakdown** for the dashboard chart.
* **headline counters** (open / high / unassigned / mine / raised by me).

The student roster lives in the main university database while cases live
in the classified safeguarding database, so the join is done in Python
rather than SQL — the two connections are deliberately separate.
"""

import logging

from education_system.systems.university.domains.safeguarding.infrastructure.db import (
    _connect,
)

logger = logging.getLogger(__name__)

_HIGH_SEVERITIES = ("CRITICAL", "HIGH")


def _university_connection():
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )

    return get_connection()


def _concern_counts_by_username(include_whistleblowing=False):
    """Return ``{username: open_case_count}`` across the safeguarding DB."""
    q = (
        "SELECT LOWER(COALESCE(username,'')), COUNT(*) "
        "FROM safeguarding_submissions "
        "WHERE COALESCE(purged,0)=0 AND COALESCE(anonymous,0)=0 "
        "AND COALESCE(status,'') != 'Closed'"
    )
    if not include_whistleblowing:
        q += " AND COALESCE(whistleblowing,0)=0"
    q += " GROUP BY LOWER(COALESCE(username,''))"
    conn = _connect()
    try:
        rows = conn.cursor().execute(q).fetchall()
    finally:
        conn.close()
    return {name: n for name, n in rows if name}


def student_register(search="", limit=500, include_whistleblowing=False):
    """Rows of ``(student_id, name, course, year, email, username, concerns)``.

    ``search`` matches student id, name or email, case-insensitively.
    """
    counts = _concern_counts_by_username(include_whistleblowing)

    q = """
        SELECT s.student_id,
               TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')),
               COALESCE(s.course, s.program, ''),
               COALESCE(s.year_of_study, s.year, ''),
               COALESCE(s.email_address, ''),
               COALESCE(u.username, '')
          FROM students s
          LEFT JOIN users u ON u.student_id = s.student_id
         WHERE COALESCE(s.is_active, 1) = 1
    """
    params = []
    if search:
        needle = f"%{search.strip().lower()}%"
        q += (
            " AND (LOWER(COALESCE(s.student_id,'')) LIKE ?"
            " OR LOWER(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')) LIKE ?"
            " OR LOWER(COALESCE(s.email_address,'')) LIKE ?)"
        )
        params.extend([needle, needle, needle])
    q += " ORDER BY s.last_name, s.first_name LIMIT ?"
    params.append(int(limit))

    conn = _university_connection()
    try:
        rows = conn.cursor().execute(q, params).fetchall()
    except Exception:
        logger.warning("student register query failed", exc_info=True)
        return []

    out = []
    for sid, name, course, year, email, username in rows:
        out.append(
            (
                sid,
                name or "(no name recorded)",
                course,
                str(year or ""),
                email,
                username,
                counts.get((username or "").lower(), 0),
            )
        )
    return out


def category_breakdown(open_only=True, include_whistleblowing=False, limit=9):
    """``[(category, count)]`` sorted high-to-low, for the dashboard chart.

    ``categories`` is stored as a comma-separated string, so one case with
    two categories counts once against each.
    """
    q = (
        "SELECT categories FROM safeguarding_submissions "
        "WHERE COALESCE(purged,0)=0"
    )
    if open_only:
        q += " AND COALESCE(status,'') != 'Closed'"
    if not include_whistleblowing:
        q += " AND COALESCE(whistleblowing,0)=0"
    conn = _connect()
    try:
        rows = conn.cursor().execute(q).fetchall()
    finally:
        conn.close()

    tally = {}
    for (raw,) in rows:
        parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
        for part in parts or ["(uncategorised)"]:
            tally[part] = tally.get(part, 0) + 1
    ordered = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered[:limit] if limit else ordered


def dashboard_counters(user, include_whistleblowing=False):
    """Headline numbers for the stat cards.

    Keys: ``open``, ``high``, ``unassigned``, ``mine``, ``raised``.
    """
    username = (user or {}).get("username") or ""
    where = "COALESCE(purged,0)=0"
    if not include_whistleblowing:
        where += " AND COALESCE(whistleblowing,0)=0"
    open_clause = f"{where} AND COALESCE(status,'') != 'Closed'"

    sev_placeholders = ",".join("?" for _ in _HIGH_SEVERITIES)
    queries = {
        "open": (f"SELECT COUNT(*) FROM safeguarding_submissions WHERE {open_clause}", ()),
        "high": (
            f"SELECT COUNT(*) FROM safeguarding_submissions WHERE {open_clause} "
            f"AND severity IN ({sev_placeholders})",
            _HIGH_SEVERITIES,
        ),
        "unassigned": (
            f"SELECT COUNT(*) FROM safeguarding_submissions WHERE {open_clause} "
            "AND COALESCE(assigned_to,'') = ''",
            (),
        ),
        "mine": (
            f"SELECT COUNT(*) FROM safeguarding_submissions WHERE {open_clause} "
            "AND LOWER(COALESCE(assigned_to,'')) = ?",
            (username.lower(),),
        ),
        "raised": (
            "SELECT COUNT(*) FROM safeguarding_submissions "
            f"WHERE {where} AND ("
            "LOWER(COALESCE(reporter_username,'')) = ? "
            "OR (COALESCE(reporter_username,'') = '' "
            "    AND LOWER(COALESCE(username,'')) = ?))",
            (username.lower(), username.lower()),
        ),
    }

    conn = _connect()
    out = {}
    try:
        cur = conn.cursor()
        for key, (sql, params) in queries.items():
            # db-audit: ignore[DBW001] - clauses above are string literals
            try:
                out[key] = cur.execute(sql, params).fetchone()[0]
            except Exception:
                logger.debug("counter %s failed", key, exc_info=True)
                out[key] = 0
    finally:
        conn.close()
    return out


__all__ = ["student_register", "category_breakdown", "dashboard_counters"]
