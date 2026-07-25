"""
Integration service (features 34-38).

34. LMS deep-link generator
35. SIS sync — pull a roster from a callable / iterable into evaluation_rosters
36. HR integration — aggregate scores into an instructor packet
37. Calendar holds — block evaluation windows on instructor calendars
38. Webhook subscribers + event publishing (records to webhook_log; the
    runtime HTTP delivery is left to the caller / a worker so this module
    has no network deps).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Callable, Iterable

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)


# ---------- 34. LMS deep links ----------

_LMS_BUILDERS = {
    "canvas":     "{base}/courses/{course}/external_tools/retrieve?url={url}",
    "moodle":     "{base}/mod/lti/launch.php?cmid={course}&url={url}",
    "blackboard": "{base}/webapps/blackboard/execute/content/launchLink?course_id={course}&url={url}",
}


def lms_deep_link(evaluation_id: int, lms: str, *, base_url: str,
                  course_id: str, eval_url: str) -> str:
    builder = _LMS_BUILDERS.get(lms.lower())
    if not builder:
        raise ValueError(f"Unsupported LMS: {lms}")
    url = builder.format(base=base_url.rstrip("/"), course=course_id, url=eval_url)
    with transaction() as conn:
        conn.execute(
            "INSERT INTO evaluation_lms_links (evaluation_id, lms, deep_link_url) VALUES (?,?,?)",
            (evaluation_id, lms.lower(), url),
        )
        conn.commit()
    return url


def list_lms_links(evaluation_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_lms_links WHERE evaluation_id=? ORDER BY link_id",
            (evaluation_id,),
        ).fetchall()]


# ---------- 35. SIS sync ----------

def sis_sync(evaluation_id: int,
             current_ids: Iterable[str]) -> dict[str, int]:
    """Replace the roster snapshot from a freshly-pulled SIS list.

    Returns counts of {added, removed, total}.
    """
    current = {s for s in current_ids if s}
    with get_connection() as conn:
        prior = {r[0] for r in conn.execute(
            "SELECT student_id FROM evaluation_rosters WHERE evaluation_id=?",
            (evaluation_id,),
        ).fetchall()}
    added = current - prior
    removed = prior - current
    with transaction() as conn:
        if removed:
            conn.executemany(
                "DELETE FROM evaluation_rosters WHERE evaluation_id=? AND student_id=?",
                [(evaluation_id, s) for s in removed],
            )
        if added:
            conn.executemany(
                "INSERT OR IGNORE INTO evaluation_rosters (evaluation_id, student_id) VALUES (?,?)",
                [(evaluation_id, s) for s in added],
            )
        conn.execute(
            """INSERT INTO evaluation_sis_sync_log (evaluation_id, added, removed, total)
               VALUES (?,?,?,?)""",
            (evaluation_id, len(added), len(removed), len(current)),
        )
        conn.commit()
    return {"added": len(added), "removed": len(removed), "total": len(current)}


def sis_sync_log(evaluation_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_sis_sync_log WHERE evaluation_id=? "
            "ORDER BY synced_at DESC", (evaluation_id,),
        ).fetchall()]


# ---------- 36. HR export ----------

def hr_export_instructor(instructor_id: str, academic_year: str) -> dict:
    """Compute and persist an instructor packet of aggregate scores."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT e.evaluation_id, e.module_code, e.semester,
                      AVG(a.numeric_value) AS avg_score,
                      COUNT(DISTINCT r.response_id) AS responses
               FROM course_evaluations e
               LEFT JOIN evaluation_responses r ON r.evaluation_id = e.evaluation_id AND r.is_complete=1
               LEFT JOIN evaluation_answers a ON a.response_id = r.response_id AND a.numeric_value IS NOT NULL
               WHERE e.instructor_id=? AND e.academic_year=?
               GROUP BY e.evaluation_id""",
            (instructor_id, academic_year),
        ).fetchall()
    payload = {
        "instructor_id": instructor_id,
        "academic_year": academic_year,
        "courses": [dict(r) for r in rows],
        "average": (
            round(sum((r["avg_score"] or 0) for r in rows) / len(rows), 3)
            if rows else None
        ),
        "exported_at": datetime.now().isoformat(),
    }
    with transaction() as conn:
        conn.execute(
            """INSERT INTO evaluation_hr_exports
                 (instructor_id, academic_year, aggregate_json) VALUES (?,?,?)""",
            (instructor_id, academic_year, json.dumps(payload, default=str)),
        )
        conn.commit()
    return payload


def list_hr_exports(*, instructor_id: str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_hr_exports"
    args: list = []
    if instructor_id:
        sql += " WHERE instructor_id=?"
        args.append(instructor_id)
    sql += " ORDER BY exported_at DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ---------- 37. Calendar holds ----------

def add_calendar_hold(evaluation_id: int, instructor_id: str,
                      start_date: str, end_date: str) -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_calendar_holds
                 (evaluation_id, instructor_id, start_date, end_date)
               VALUES (?,?,?,?)""",
            (evaluation_id, instructor_id, start_date, end_date),
        )
        conn.commit()
        return cur.lastrowid


def list_holds(instructor_id: str) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_calendar_holds WHERE instructor_id=? "
            "ORDER BY start_date", (instructor_id,),
        ).fetchall()]


def clear_hold(hold_id: int) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM evaluation_calendar_holds WHERE hold_id=?", (hold_id,))
        conn.commit()


# ---------- 38. Webhooks / event bus ----------

_KNOWN_EVENTS = (
    "evaluation.opened", "evaluation.closed", "response.submitted",
    "redflag.raised", "results.released",
)


def subscribe(event: str, url: str, *, secret: str = "") -> int:
    if event not in _KNOWN_EVENTS:
        raise ValueError(f"Unknown event: {event}")
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO evaluation_webhooks (event, url, secret) VALUES (?,?,?)",
            (event, url, secret),
        )
        conn.commit()
        return cur.lastrowid


def unsubscribe(hook_id: int) -> None:
    with transaction() as conn:
        conn.execute("UPDATE evaluation_webhooks SET active=0 WHERE hook_id=?", (hook_id,))
        conn.commit()


def list_subscribers(event: str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_webhooks WHERE active=1"
    args: list = []
    if event:
        sql += " AND event=?"
        args.append(event)
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def emit(event: str, payload: dict, *,
         deliver: Callable[[str, dict, dict], None] | None = None) -> int:
    """Record an event and (optionally) hand off delivery to a callable.

    `deliver(url, payload, headers)` is called for each active subscriber
    when provided. We never reach the network from inside this service.
    """
    if event not in _KNOWN_EVENTS:
        raise ValueError(f"Unknown event: {event}")
    body = json.dumps(payload, default=str)
    delivered = 0
    with transaction() as conn:
        for r in conn.execute(
            "SELECT * FROM evaluation_webhooks WHERE event=? AND active=1", (event,),
        ).fetchall():
            conn.execute(
                "INSERT INTO evaluation_webhook_log (hook_id, event, payload_json) VALUES (?,?,?)",
                (r["hook_id"], event, body),
            )
            if deliver:
                headers = {"X-Eval-Event": event, "X-Eval-Secret": r["secret"] or ""}
                try:
                    deliver(r["url"], payload, headers)
                except Exception:
                    pass
            delivered += 1
        conn.commit()
    return delivered


def webhook_log(*, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_webhook_log ORDER BY log_id DESC LIMIT ?", (limit,),
        ).fetchall()]


__all__ = [
    "lms_deep_link", "list_lms_links",
    "sis_sync", "sis_sync_log",
    "hr_export_instructor", "list_hr_exports",
    "add_calendar_hold", "list_holds", "clear_hold",
    "subscribe", "unsubscribe", "list_subscribers", "emit", "webhook_log",
]
