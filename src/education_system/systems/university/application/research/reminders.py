"""What needs doing in the research office, and the daily reminder run.

:func:`attention` lists what one person needs to act on (the portal's
dashboard). :func:`run` is the once-a-day job: ethics approvals past their
expiry are marked expired, and reminders go out for approvals about to
expire, funder deadlines, grant reports, IP deadlines and overdue
declarations of interest. Each item is reminded at most once every
:data:`REMIND_EVERY_DAYS` days. The portal runs it when it opens.

PGR overdue reviews, milestones and corrections are escalated by the PGR
service itself (:func:`run_pgr_escalations`, its own transaction).

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.application.research import access as ra
from education_system.systems.university.application.research import ethics
from education_system.systems.university.application.research import grants
from education_system.systems.university.application.research import integrity
from education_system.systems.university.application.research import ip

REMIND_EVERY_DAYS = 7
ETHICS_WARNING_DAYS = 60
GRANT_WARNING_DAYS = 30
IP_WARNING_DAYS = 60


def _item(area, title, detail, ref=None) -> dict:
    return {"area": area, "title": title, "detail": detail, "ref": ref}


def _ethics_items(conn, who) -> list[dict]:
    out = [_item("Ethics", f"Review {r['reference']}", r["title"], ("ethics", r["review_id"]))
           for r in ethics.my_reviews(conn, who)]
    if who.chairs_ethics:
        queue = ethics.chair_queue(conn)
        out += [_item("Ethics", f"Allocate reviewers to {r['reference']}",
                      f"{r['allocated']} of {r['needed']} allocated", ("ethics", r["review_id"]))
                for r in queue["to_allocate"]]
        out += [_item("Ethics", f"Decide {r['reference']}", r["title"], ("ethics", r["review_id"]))
                for r in queue["to_decide"]]
    for row in ethics.listing(conn, who):
        mine = who.me in (row.get("applicant_id"), row.get("principal_investigator_id"))
        if row["status"] == "awaiting_supervisor" and row.get("supervisor_id") == who.username:
            out.append(_item("Ethics", f"Endorse {row['reference']}", "Your student's application",
                             ("ethics", row["review_id"])))
        elif mine and row["status"] == "revisions_required":
            out.append(_item("Ethics", f"Revise {row['reference']}", row.get("reviewer_comments")
                             or "", ("ethics", row["review_id"])))
    for row in ethics.expiring(conn, ETHICS_WARNING_DAYS):
        if who.me in (row["applicant_id"], row["principal_investigator_id"]) or who.is_office:
            out.append(_item("Ethics", f"Approval {row['reference']} expires "
                             f"{row['approval_expiry_date']}", "Renew it or close the study",
                             ("ethics", row["review_id"])))
    return out


def _grant_items(conn, who) -> list[dict]:
    out = [_item("Grants", f"Approve {g['grant_name']}", f"Deadline {g['application_deadline']}",
                 ("grant", g["application_id"])) for g in grants.approvals_for(conn, who)]
    due = grants.due(conn, GRANT_WARNING_DAYS)
    for g in due["deadlines"]:
        if g["principal_investigator_id"] == who.username or who.is_office:
            out.append(_item("Grants", f"Funder deadline {g['application_deadline']}",
                             f"{g['grant_name']} is still {g['status'].replace('_', ' ')}",
                             ("grant", g["application_id"])))
    for r in due["reports"]:
        if r["principal_investigator_id"] == who.username or who.is_office:
            out.append(_item("Grants", f"{r['kind'].capitalize()} report due {r['due_date']}",
                             r["grant_name"], ("grant", r["application_id"])))
    if who.is_office:
        out += [_item("Grants", f"Accept award: {g['grant_name']}",
                      "; ".join(grants.acceptance_blockers(conn, g)) or "Ready to accept",
                      ("grant", g["application_id"]))
                for g in grants.listing(conn, who, "awarded")]
    return out


def _ip_items(conn, who) -> list[dict]:
    if not who.is_tto:
        return []
    out = [_item("IP", f"Assess {d['reference']}", d["title"], ("ip", d["disclosure_id"]))
           for d in ip.listing(conn, who, "submitted")]
    out += [_item("IP", f"{d['kind']} – {d['due_date']}", f"{d['reference']} {d['title']}",
                  ("ip", d["disclosure_id"])) for d in ip.deadlines_due(conn, IP_WARNING_DAYS)]
    return out


def _integrity_items(conn, who) -> list[dict]:
    out = [_item("Integrity", f"Review declaration by {ra.person_name(conn, d['username'])}",
                 f"{d['kind']}: {d.get('counterpart') or ''}", ("declaration",
                                                                 d["declaration_id"]))
           for d in integrity.to_review(conn, who)]
    out += [_item("Integrity", f"Review data management plan v{p['version']}",
                  p["project_title"], ("project", p["project_id"]))
            for p in integrity.plans_to_review(conn, who)]
    if any(o["username"] == who.username for o in integrity.overdue(conn)):
        out.append(_item("Integrity", "Declaration of interests due",
                         "Declare your interests (or that you have none)", None))
    for p in integrity.projects_missing_plan(conn):
        if p["principal_investigator_id"] == who.username or who.is_office:
            out.append(_item("Integrity", f"Data management plan needed: {p['project_title']}",
                             "The project's grant requires an approved plan",
                             ("project", p["project_id"])))
    return out


def attention(conn, who) -> list[dict]:
    """Everything ``who`` should act on, grouped by area."""
    ra.ensure(conn)
    if who is None:
        return []
    out = _ethics_items(conn, who)
    if who.is_staff:
        out += _grant_items(conn, who) + _ip_items(conn, who) + _integrity_items(conn, who)
    return out


# ── the daily run ───────────────────────────────────────────────────────


def _recently(conn, key, day) -> bool:
    since = (day - timedelta(days=REMIND_EVERY_DAYS)).isoformat()
    return conn.execute("SELECT 1 FROM research_audit WHERE entity = 'reminder' AND entity_id = ? "
                        "AND json_extract(detail, '$.day') > ? AND json_extract(detail, '$.day') "
                        "<= ?", (key, since, day.isoformat())).fetchone() is not None


def _remind(conn, key, day, to, subject, body) -> list:
    if _recently(conn, key, day):
        return []
    ra.audit(conn, "system", "reminder", key, "sent", {"to": list(to), "day": day.isoformat()})
    return ra.notify(conn, to, subject, body)


def already_ran(conn, day=None) -> bool:
    ra.ensure(conn)
    day = day or ra.today()
    return conn.execute("SELECT 1 FROM research_audit WHERE entity = 'reminder_run' AND "
                        "entity_id = ?", (day,)).fetchone() is not None


def run(conn, as_of=None, force=False) -> dict:
    """Expire lapsed ethics approvals and send due reminders (once a day
    unless ``force``). Returns ``{"expired", "reminded", "emails"}``."""
    ra.ensure(conn)
    day = date.fromisoformat(ra.iso_date(as_of, "Date") or ra.today())
    if not force and already_ran(conn, day.isoformat()):
        return {"expired": 0, "reminded": 0, "emails": []}
    emails = []
    expired = ethics.expire_due(conn, day.isoformat())
    for row in expired:
        emails += ra.notify(conn, [row["applicant_id"], row["principal_investigator_id"]],
                            f"Ethics approval {row['reference']} has expired",
                            "Research under this approval must stop until it is renewed.")
    before = len(emails)
    for row in ethics.expiring(conn, ETHICS_WARNING_DAYS, day.isoformat()):
        emails += _remind(conn, f"ethics:{row['review_id']}", day,
                          [row["applicant_id"], row["principal_investigator_id"]],
                          f"Ethics approval {row['reference']} expires "
                          f"{row['approval_expiry_date']}", "Apply to renew it, or close the "
                          "study if it has finished.")
    due = grants.due(conn, GRANT_WARNING_DAYS, day.isoformat())
    for g in due["deadlines"]:
        emails += _remind(conn, f"grant-deadline:{g['application_id']}", day,
                          [g["principal_investigator_id"]],
                          f"Funder deadline {g['application_deadline']}: {g['grant_name']}",
                          f"The application is still {g['status'].replace('_', ' ')}.")
    for r in due["reports"]:
        emails += _remind(conn, f"grant-report:{r['report_id']}", day,
                          [r["principal_investigator_id"]],
                          f"{r['kind'].capitalize()} report due {r['due_date']}",
                          f"For {r['grant_name']}.")
    for d in ip.deadlines_due(conn, IP_WARNING_DAYS, day.isoformat()):
        emails += _remind(conn, f"ip:{d['deadline_id']}", day,
                          ra.holders(conn, "tto") or ra.holders(conn, "research_office"),
                          f"IP deadline {d['due_date']}: {d['kind']}",
                          f"{d['reference']} {d['title']}")
    for o in integrity.overdue(conn, day.isoformat()):
        emails += _remind(conn, f"declaration:{o['username']}", day, [o["username"]],
                          "Please declare your interests",
                          "Research staff declare their interests (or that they have none) "
                          "every year.")
    ra.audit(conn, "system", "reminder_run", day.isoformat(), "ran",
             {"expired": len(expired), "emails": len(emails)})
    return {"expired": len(expired), "reminded": len(emails) - before, "emails": emails}


def run_pgr_escalations(as_of=None) -> int:
    """The PGR service's own overdue escalation (it commits itself)."""
    from education_system.systems.university.domains.research.domain.research.pgr import service
    return service.escalate_overdue(as_of=as_of)
