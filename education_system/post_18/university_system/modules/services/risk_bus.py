"""Cross-domain risk-register helpers.

The ``risks`` table (legal/risk_management/university_risk_management.py)
is the canonical risk register, but until now nothing wrote to it
except the GUI. This module turns the register into a live system fed
by:

* ``cases_bus.open_case`` for security/disciplinary incidents at
  severity ≥ High,
* attendance pattern flags (whole-class no-shows),
* SU large/alcohol-licensed events (date-bounded entries that auto-
  expire after the event),
* research projects with biosafety / human-subjects / chemical tags.

It also publishes review-date entries onto the academic calendar
through the same path SU events and H&S drills use, so risk reviews
surface on every subscriber's calendar.

Public surface:

* ``raise_risk(...)``        → risk_id, publishes ``risk.raised``
* ``close_risk(risk_id, ...)`` → bool,    publishes ``risk.closed``
* ``set_review_date(risk_id, date)`` → publishes a calendar event
  type ``risk_review`` and stores the date.
* ``list_risks_for(reference_id)`` → rows linked to a case / project
  / event id.
* ``raise_research_risk(project_id, activity_tags, pi_id, ...)``
  → bulk helper used by the research portal.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable

from education_system.post_18.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


# Mapping of tags the research portal might emit → risk register
# category. Anything unmatched falls under "Compliance".
_RESEARCH_TAG_CATEGORY = {
    "biosafety":     "Safety",
    "human_subjects": "Compliance",
    "animal":         "Compliance",
    "chemical":       "Safety",
    "radiation":      "Safety",
    "data_protection": "IT",
    "clinical":       "Compliance",
    "field_work":     "Safety",
}


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("risk_bus publish failed: %s", exc)


def _ensure_risk_extras(conn: sqlite3.Connection) -> None:
    """Add the cross-domain columns the registry GUI doesn't itself
    use yet: ``reference_id`` (links to a case / project / event),
    ``next_review_date``, ``expires_at``, ``closed_at``. Idempotent."""
    try:
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(risks)"
        ).fetchall()}
    except Exception:
        return
    if not cols:
        # Table doesn't exist yet — caller will create the canonical
        # schema via the legacy module first; we're additive only.
        return
    for col, ddl in (
        ("reference_id",     "TEXT"),
        ("next_review_date", "TEXT"),
        ("expires_at",       "TEXT"),
        ("closed_at",        "TEXT"),
    ):
        if col not in cols:
            try:
                conn.execute(
                    f"ALTER TABLE risks ADD COLUMN {col} {ddl}"
                )
            except Exception as exc:
                logger.debug("ALTER risks.%s failed: %s", col, exc)


# ---------------------------------------------------------------------------
# Open / close
# ---------------------------------------------------------------------------

def raise_risk(
    *,
    title: str,
    category: str,
    department: str = "Operations",
    description: str = "",
    likelihood: int = 3,
    impact: int = 3,
    owner: str | None = None,
    mitigation: str = "",
    reference_id: str | None = None,
    next_review_date: str | None = None,
    expires_at: str | None = None,
) -> int | None:
    """Insert a row into the risk register and publish ``risk.raised``.

    Likelihood and impact are 1–5 (rating = product). Caller may pass
    a ``reference_id`` (e.g. ``case:42``, ``project:RP-117``,
    ``event:SU-MOVIE-NIGHT``) so close-out can find this row again.

    Best-effort — returns ``None`` on any failure.
    """
    if not title or not category:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    risk_id: int | None = None
    try:
        with get_connection() as conn:
            _ensure_risk_extras(conn)
            cur = conn.execute(
                "INSERT INTO risks "
                "(title, category, department, description, "
                " likelihood, impact, status, owner, mitigation, "
                " created, updated, reference_id, "
                " next_review_date, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?, ?)",
                (title, category, department, description,
                 int(likelihood), int(impact),
                 owner, mitigation, now, now,
                 reference_id, next_review_date, expires_at),
            )
            risk_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("raise_risk(%s) failed: %s", title, exc)
        return None

    _publish("risk.raised",
             risk_id=risk_id, category=category,
             reference_id=reference_id,
             likelihood=int(likelihood), impact=int(impact))

    if next_review_date:
        set_review_date(risk_id, next_review_date)

    return risk_id


def close_risk(risk_id: int, *,
               outcome: str = "closed",
               closed_by: str | None = None) -> bool:
    """Mark a risk row as closed. Publishes ``risk.closed``."""
    if not risk_id:
        return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            _ensure_risk_extras(conn)
            conn.execute(
                "UPDATE risks SET status = ?, closed_at = ?, updated = ? "
                "WHERE id = ?",
                (outcome, now, now, int(risk_id)),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("close_risk(%s) failed: %s", risk_id, exc)
        return False
    _publish("risk.closed",
             risk_id=int(risk_id), outcome=outcome, closed_by=closed_by)
    return True


def close_risks_for_reference(reference_id: str,
                              *, outcome: str = "case_closed") -> int:
    """Close every active risks row linked by ``reference_id``.

    Used by ``cases_bus.close_case`` to fold risk-register entries
    back when the originating incident is resolved. Returns the
    number closed.
    """
    if not reference_id:
        return 0
    closed = 0
    try:
        with get_connection() as conn:
            _ensure_risk_extras(conn)
            rows = conn.execute(
                "SELECT id FROM risks "
                "WHERE reference_id = ? AND status = 'Open'",
                (reference_id,),
            ).fetchall()
        for r in rows:
            if close_risk(int(r[0]), outcome=outcome):
                closed += 1
    except Exception as exc:
        logger.warning("close_risks_for_reference(%s) failed: %s",
                       reference_id, exc)
    return closed


# ---------------------------------------------------------------------------
# Review dates → academic calendar
# ---------------------------------------------------------------------------

def set_review_date(risk_id: int, when: str) -> bool:
    """Persist ``next_review_date`` and publish a calendar entry of
    ``event_type='risk_review'`` so subscribers see it alongside SU
    events / H&S drills."""
    if not risk_id or not when:
        return False
    try:
        with get_connection() as conn:
            _ensure_risk_extras(conn)
            conn.execute(
                "UPDATE risks SET next_review_date = ?, updated = ? "
                "WHERE id = ?",
                (when[:10],
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 int(risk_id)),
            )
            row = conn.execute(
                "SELECT title FROM risks WHERE id = ?",
                (int(risk_id),),
            ).fetchone()
            title = row[0] if row else f"Risk #{risk_id}"
            conn.commit()
    except Exception as exc:
        logger.warning("set_review_date(%s) failed: %s", risk_id, exc)
        return False

    try:
        import uuid
        event_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO academic_calendar_events "
                "(id, name, date, description, event_type, "
                " date_added, last_modified, created_by) "
                "VALUES (?, ?, ?, ?, 'risk_review', ?, ?, ?)",
                (event_id, f"Risk review: {title}", when[:10],
                 f"Periodic review for risk #{risk_id}",
                 now, now, "risk_bus"),
            )
            conn.commit()
        try:
            from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import (
                publish, EVENT_CALENDAR_CHANGED,
            )
            publish(EVENT_CALENDAR_CHANGED, event_id=event_id,
                    event_type="risk_review", action="created",
                    date=when[:10], name=f"Risk review: {title}")
        except Exception:
            pass
    except Exception as exc:
        logger.debug("calendar publish for risk_review failed: %s", exc)
    return True


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def list_risks_for(reference_id: str) -> list[dict[str, Any]]:
    if not reference_id:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            _ensure_risk_extras(conn)
            for r in conn.execute(
                "SELECT id, title, category, status, likelihood, impact, "
                "       owner, next_review_date, expires_at, closed_at "
                "FROM risks WHERE reference_id = ? ORDER BY id DESC",
                (reference_id,),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_risks_for(%s) failed: %s", reference_id, exc)
    return out


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def raise_research_risk(project_id: str | int,
                        *, activity_tags: Iterable[str],
                        pi_id: str | None = None,
                        title: str | None = None,
                        next_review_date: str | None = None
                        ) -> list[int]:
    """Create one risks row per high-risk research activity tag.

    Maps tags via ``_RESEARCH_TAG_CATEGORY``. Unknown tags fall under
    Compliance. Returns the list of created risk_ids.
    """
    if not project_id or not activity_tags:
        return []
    ref = f"project:{project_id}"
    out: list[int] = []
    for tag in activity_tags:
        cat = _RESEARCH_TAG_CATEGORY.get(str(tag).lower(), "Compliance")
        rid = raise_risk(
            title=(title or f"Research project {project_id}")
                  + f" — {tag}",
            category=cat,
            department="Research",
            description=f"Auto-raised from project {project_id} "
                        f"with activity tag '{tag}'.",
            likelihood=3, impact=4,
            owner=pi_id,
            reference_id=ref,
            next_review_date=next_review_date,
        )
        if rid:
            out.append(rid)
    return out


def raise_event_clearance_risk(event_id: str,
                               *, name: str, when: str,
                               tags: Iterable[str],
                               organizer_id: str | None = None
                               ) -> int | None:
    """Date-bounded risk row for SU large/alcohol/external events.
    Auto-expires the day after the event."""
    cat = "Safety"
    if any(t.lower() == "alcohol" for t in tags):
        cat = "Compliance"
    return raise_risk(
        title=f"Event clearance: {name}",
        category=cat,
        department="Student Union",
        description=f"Auto-raised from SU event {event_id} "
                    f"with tags {sorted(set(tags))}.",
        likelihood=2, impact=3,
        owner=organizer_id,
        reference_id=f"event:{event_id}",
        next_review_date=when[:10],
        expires_at=when[:10],
    )


__all__ = [
    "raise_risk", "close_risk", "close_risks_for_reference",
    "set_review_date", "list_risks_for",
    "raise_research_risk", "raise_event_clearance_risk",
]
