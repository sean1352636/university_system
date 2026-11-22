"""First aid → Health & Safety.

A serious first-aid incident (severity High / Critical / Severe) becomes a
Health & Safety incident in ``hs_incidents`` — the H&S portal's own record —
so the H&S team investigates the *event*. It used to go through
``cases_bus.open_case(kind="hs_incident", subject_id=<reporter>)``, which
filed it under ``disciplinary_records`` against the person who reported it.

Public surface:

* ``record_first_aid_incident(incident_id, report)`` → the ``hs_incidents``
  id (idempotent: one H&S incident per first-aid incident, ref
  ``FA-<id>``), linked back on ``first_aid_incidents.hs_incident_id``;
  the H&S / first-aid coordinators are e-mailed through the outbox and a
  risk-register row is raised for Critical/Severe ones.
* ``record_trip_incident(trip_incident_id, report)`` → the ``hs_incidents``
  id for a serious / injury / RIDDOR trip incident (ref ``TRIP-<id>``,
  idempotent), with the same coordinator notice and risk row.
* ``coordinator_emails()`` → who hears about first-aid matters.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

SERIOUS = ("high", "critical", "severe")
COORDINATOR_ROLES = ("health_admin", "admin")


def _ensure_hs_table(conn) -> None:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'hs_incidents'").fetchone():
        return
    # The H&S portal owns the table; let it create it the one way it does.
    import importlib
    importlib.import_module(
        "education_system.systems.university.domains.governance.domain.health_safety."
        "health_safety_service").HSDatabase()


def coordinator_emails(conn=None) -> list[str]:
    own = conn is None
    conn = conn or get_connection(row_factory=False)
    try:
        marks = ",".join("?" * len(COORDINATOR_ROLES))
        return sorted({r[0] for r in conn.execute(
            f"SELECT email FROM users WHERE LOWER(role) IN ({marks}) "  # nosec B608
            "AND COALESCE(email, '') <> ''", COORDINATOR_ROLES)})
    finally:
        if own:
            conn.close()


def record_first_aid_incident(incident_id: int, report: dict[str, Any]) -> int | None:
    """Open (once) the H&S incident for a serious first-aid incident."""
    severity = str(report.get("severity") or "").lower()
    if severity not in SERIOUS:
        return None
    ref = f"FA-{int(incident_id)}"
    conn = get_connection(row_factory=False)
    try:
        _ensure_hs_table(conn)
        found = conn.execute("SELECT id FROM hs_incidents WHERE ref = ?", (ref,)).fetchone()
        if found:
            return found[0]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            "INSERT INTO hs_incidents (ref, incident_type, location, incident_date, severity, "
            "people_involved, description, actions_taken, reported_by, department, status, "
            "reported_at) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, 'Health & Safety', 'Open', ?)",
            (ref, report.get("incident_type") or "First-aid incident", report.get("location"),
             str(report.get("incident_date") or report.get("submitted_at") or now)[:10],
             str(report.get("severity") or "").title(),
             f"First-aid incident {ref}: {report.get('description') or ''}".strip(),
             "First aid given; escalated to Health & Safety for investigation.",
             report.get("reporter_user") or report.get("reporter_name") or "first aid portal",
             now))
        hs_id = cur.lastrowid
        if conn.execute("SELECT 1 FROM pragma_table_info('first_aid_incidents') "
                        "WHERE name = 'hs_incident_id'").fetchone():
            conn.execute("UPDATE first_aid_incidents SET hs_incident_id = ? WHERE id = ?",
                         (hs_id, incident_id))
        conn.commit()
        recipients = coordinator_emails(conn)
    finally:
        conn.close()
    _notify(recipients, ref, report)
    if severity in ("critical", "severe"):
        _raise_risk(hs_id, ref, report)
    return hs_id


def record_trip_incident(trip_incident_id: int, report: dict[str, Any]) -> int | None:
    """Open (once) the H&S incident for a trip incident Trip Management routes here.

    Trip Management decides what is routed (injuries, serious / critical
    incidents, RIDDOR-reportable ones), so there is no severity filter. The
    ref is ``TRIP-<id>``; ``report`` carries ``incident_type``, ``location``,
    ``incident_date``, ``severity``, ``people_involved``, ``description``,
    ``actions_taken``, ``reported_by`` and ``riddor_reportable``.
    """
    ref = f"TRIP-{int(trip_incident_id)}"
    conn = get_connection(row_factory=False)
    try:
        _ensure_hs_table(conn)
        found = conn.execute("SELECT id FROM hs_incidents WHERE ref = ?", (ref,)).fetchone()
        if found:
            return found[0]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        riddor = " Flagged as RIDDOR-reportable." if report.get("riddor_reportable") else ""
        cur = conn.execute(
            "INSERT INTO hs_incidents (ref, incident_type, location, incident_date, severity, "
            "people_involved, description, actions_taken, reported_by, department, status, "
            "reported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Trips & Mobility', 'Open', ?)",
            (ref, report.get("incident_type") or "Trip incident", report.get("location"),
             str(report.get("incident_date") or now)[:10],
             str(report.get("severity") or "").title(), report.get("people_involved"),
             f"Trip incident {ref}: {report.get('description') or ''}".strip() + riddor,
             report.get("actions_taken"), report.get("reported_by") or "trip management", now))
        hs_id = cur.lastrowid
        conn.commit()
        recipients = coordinator_emails(conn)
    finally:
        conn.close()
    _notify(recipients, ref, dict(report, source="trip"))
    if str(report.get("severity") or "").lower() == "critical":
        _raise_risk(hs_id, ref, report)
    return hs_id


def _notify(recipients, ref, report) -> None:
    if not recipients:
        return
    try:
        from education_system.systems.university.infrastructure.email.email_service.core import (
            send_email,
        )
    except Exception:
        logger.debug("E-mail unavailable for %s", ref, exc_info=True)
        return
    what = "trip incident" if report.get("source") == "trip" else "first-aid incident"
    body = (f"A {str(report.get('severity') or '').lower()} {what} ({ref}) was "
            f"recorded at {report.get('location') or 'an unrecorded location'} and has been "
            "opened as a Health & Safety incident for investigation.\n\n"
            f"Type: {report.get('incident_type') or '—'}\n"
            + ("Assess it for RIDDOR in the First Aid portal (Registers & RIDDOR)."
               if what == "first-aid incident" else
               "Assess it for RIDDOR in the Health & Safety portal."))
    for address in recipients:
        try:
            send_email(address, f"Serious {what} {ref}", body)
        except Exception:
            logger.debug("Notice for %s to %s failed", ref, address, exc_info=True)


def _raise_risk(hs_id, ref, report) -> None:
    try:
        from education_system.systems.university.services.bus import risk_bus
        reference = f"hs_incident:{hs_id}"
        if not risk_bus.list_risks_for(reference):
            risk_bus.raise_risk(
                title=f"H&S incident {ref}: {report.get('incident_type') or 'incident'}",
                category="Safety", department="Health & Safety",
                description=report.get("description") or "",
                likelihood=3, impact=5, reference_id=reference)
    except Exception:
        logger.debug("Risk row for %s not raised", ref, exc_info=True)
