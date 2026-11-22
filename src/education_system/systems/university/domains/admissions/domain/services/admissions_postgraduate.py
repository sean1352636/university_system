"""Postgraduate admissions requirements: references, and for research
degrees the proposal, supervisor agreement and interview.

Every application whose ``application_type`` is postgraduate needs two
references before it can enrol. A research (PGR) application also needs a
research proposal on file, at least one proposed supervisor who has agreed
to supervise (and none still undecided), and an interview recorded with a
recommendation to offer. :func:`requirement_issues` lists what is missing;
``admissions_lifecycle.readiness_issues`` adds it to the enrolment gate, so
these hold conversion back exactly as an unmet condition does.

References arrive one of two ways. :func:`request_reference` e-mails the
referee a one-time link through the university outbox (only a hash of the
token is stored; the link stops working once used or after
:data:`TOKEN_DAYS`); :func:`submit_reference_by_token` is what the public
page behind that link calls. Or admissions staff record a reference that
came in by other means, with the file, via :func:`record_reference`.

On conversion :func:`pgr_handover` gives the research proposal and the
supervisors who accepted; ``convert_to_student`` hands that to the PGR
module through a ``research_pgr`` lifecycle action.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

from education_system.systems.university.domains.admissions.domain.services import (
    admissions_casework as casework,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

logger = logging.getLogger(__name__)

#: ``application_type`` values that are postgraduate. Plain "postgraduate"
#: (what the CRM has always offered) is treated as taught.
POSTGRADUATE_TYPES = frozenset({
    "postgraduate", "postgraduate_taught", "postgraduate_research", "pgt", "pgr",
})
RESEARCH_TYPES = frozenset({"postgraduate_research", "pgr"})

REQUIRED_REFEREES = 2
TOKEN_DAYS = 28
RELATIONSHIPS = ("academic", "professional", "employer", "other")
SUPERVISOR_ROLES = ("primary", "secondary", "advisor")
SUPERVISOR_STAFF_ROLES = ("instructor", "staff", "admin")
INTERVIEW_OUTCOMES = ("recommend_offer", "not_recommended", "reconvene")

_DDL = (
    """CREATE TABLE IF NOT EXISTS admission_referees (
        referee_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        relationship TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        token_hash TEXT UNIQUE,
        token_expires_at TEXT,
        request_count INTEGER NOT NULL DEFAULT 0,
        requested_at TEXT,
        requested_by TEXT,
        received_at TEXT,
        received_via TEXT,
        recorded_by TEXT,
        reference_text TEXT,
        document_id INTEGER,
        withdrawn_reason TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (application_id)
            REFERENCES admission_applications(application_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS admission_research_proposals (
        proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        document_id INTEGER,
        is_current INTEGER NOT NULL DEFAULT 1,
        uploaded_by TEXT NOT NULL,
        uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (application_id)
            REFERENCES admission_applications(application_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS admission_supervisor_nominations (
        nomination_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        supervisor_username TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'primary',
        status TEXT NOT NULL DEFAULT 'proposed',
        nominated_by TEXT NOT NULL,
        nominated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        decided_by TEXT,
        decided_at TEXT,
        comment TEXT,
        UNIQUE(application_id, supervisor_username),
        FOREIGN KEY (application_id)
            REFERENCES admission_applications(application_id) ON DELETE CASCADE
    )""",
)


def ensure(conn) -> None:
    for ddl in _DDL:
        conn.execute(ddl)
    # admissions_schemas declares this column, but CREATE TABLE IF NOT EXISTS
    # does not add it to a table made before it was declared.
    have = {r[1] for r in conn.execute("PRAGMA table_info(admission_interviews)")}
    if have and "status" not in have:
        conn.execute("ALTER TABLE admission_interviews "
                     "ADD COLUMN status TEXT NOT NULL DEFAULT 'scheduled'")
    casework.ensure_audit(conn)


def is_postgraduate(application_type: Any) -> bool:
    return str(application_type or "").strip().lower() in POSTGRADUATE_TYPES


def is_research(application_type: Any) -> bool:
    return str(application_type or "").strip().lower() in RESEARCH_TYPES


def _hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def reference_url(token: str) -> str:
    base = os.environ.get("UNIVERSITY_PUBLIC_URL", "http://localhost:5000").rstrip("/")
    return f"{base}/api/v1/university/admissions-references/{token}"


def _pg_application(conn, application_id: int):
    row = casework.application_row(conn, application_id)
    if not is_postgraduate(row["application_type"]):
        raise AdmissionsBoundaryError(
            f"Application {application_id} is not a postgraduate application")
    return row


def _research_application(conn, application_id: int):
    row = _pg_application(conn, application_id)
    if not is_research(row["application_type"]):
        raise AdmissionsBoundaryError(
            f"Application {application_id} is not a research (PGR) application")
    return row


# ── Referees ────────────────────────────────────────────────────────

def add_referee(viewer: Any, application_id: int, name: str, email: str,
                relationship: str) -> int:
    actor = casework.require_manager(viewer)
    name, email = (name or "").strip(), (email or "").strip().lower()
    relationship = (relationship or "").strip().lower()
    if not name or "@" not in email:
        raise AdmissionsBoundaryError("A referee needs a name and a valid e-mail address")
    if relationship not in RELATIONSHIPS:
        raise AdmissionsBoundaryError(
            "Relationship must be one of " + ", ".join(RELATIONSHIPS))
    with transaction() as conn:
        ensure(conn)
        _pg_application(conn, application_id)
        active = conn.execute(
            "SELECT COUNT(*) FROM admission_referees "
            "WHERE application_id = ? AND status != 'withdrawn'",
            (int(application_id),)).fetchone()[0]
        if active >= REQUIRED_REFEREES:
            raise AdmissionsBoundaryError(
                f"This application already has {REQUIRED_REFEREES} referees; "
                "withdraw one before adding another")
        cur = conn.execute(
            """INSERT INTO admission_referees
                 (application_id, name, email, relationship, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (int(application_id), name, email, relationship, actor))
        referee_id = int(cur.lastrowid)
        casework.audit(conn, application_id, "referee_added", actor,
                       target_type="referee", target_id=referee_id,
                       detail={"name": name, "relationship": relationship})
    return referee_id


def _referee(conn, referee_id: int):
    ensure(conn)
    row = conn.execute("SELECT * FROM admission_referees WHERE referee_id = ?",
                       (int(referee_id),)).fetchone()
    if row is None:
        raise AdmissionsBoundaryError(f"Referee {referee_id} does not exist")
    return row


def withdraw_referee(viewer: Any, referee_id: int, reason: str) -> None:
    actor = casework.require_manager(viewer)
    if not (reason or "").strip():
        raise AdmissionsBoundaryError("A reason is required to withdraw a referee")
    with transaction() as conn:
        referee = _referee(conn, referee_id)
        if referee["status"] == "received":
            raise AdmissionsBoundaryError("A received reference cannot be withdrawn")
        conn.execute(
            "UPDATE admission_referees SET status = 'withdrawn', token_hash = NULL, "
            "withdrawn_reason = ? WHERE referee_id = ?", (reason.strip(), int(referee_id)))
        casework.audit(conn, referee["application_id"], "referee_withdrawn", actor,
                       target_type="referee", target_id=referee_id,
                       detail={"reason": reason.strip()})


def _request_body(referee, applicant: str, programme: str, link: str,
                  expires: str) -> str:
    return (
        f"Dear {referee['name']},\n\n"
        f"{applicant} has applied for postgraduate study ({programme}) and has "
        f"named you as a referee ({referee['relationship']}).\n\n"
        "Please provide your reference using this personal link. It can be "
        f"used once and expires on {expires[:10]}:\n\n{link}\n\n"
        "If you would rather send a signed letter, reply to this e-mail and "
        "the admissions office will record it for you.\n\n"
        "With thanks,\nPostgraduate Admissions\n"
    )


def request_reference(viewer: Any, referee_id: int) -> dict:
    """Send (or re-send) the reference request with a fresh one-time link.

    Returns ``{"status", "message"}`` where status is the outbox's own:
    ``queued`` (will be delivered), ``stored`` (inbox-only mode — kept in
    the university inbox, *not* e-mailed out) or ``suppressed``.
    """
    from education_system.systems.university.infrastructure.email import outbox_delivery
    actor = casework.require_manager(viewer)
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(days=TOKEN_DAYS)).isoformat(timespec="seconds")
    with transaction() as conn:
        referee = _referee(conn, referee_id)
        if referee["status"] in ("received", "withdrawn"):
            raise AdmissionsBoundaryError(
                f"This referee is {referee['status']}; no request is needed")
        app = _pg_application(conn, referee["application_id"])
        conn.execute(
            """UPDATE admission_referees
                  SET status = 'requested', token_hash = ?, token_expires_at = ?,
                      request_count = request_count + 1, requested_at = ?,
                      requested_by = ?
                WHERE referee_id = ?""",
            (_hash(token), expires, casework.now(), actor, int(referee_id)))
        casework.audit(conn, app["application_id"], "reference_requested", actor,
                       target_type="referee", target_id=referee_id,
                       detail={"email": referee["email"], "expires": expires})
    applicant = f"{app['first_name'] or ''} {app['last_name'] or ''}".strip() or "An applicant"
    body = _request_body(referee, applicant, app["program_applied"] or "postgraduate study",
                         reference_url(token), expires)
    result = outbox_delivery.enqueue(
        referee["email"], f"Reference request for {applicant}", body,
        kind="transactional", category="admissions",
        to_ref=f"referee:{referee_id}", created_by=actor)
    status = str(result.get("status") or "")
    messages = {
        "queued": f"Request queued for delivery to {referee['email']}.",
        "stored": ("E-mail delivery is in inbox-only mode: the request was stored "
                   "in the university outbox but NOT sent to the referee. Record the "
                   "reference by hand when it arrives, or switch delivery mode."),
        "suppressed": f"{referee['email']} is suppressed in the outbox; nothing was sent.",
    }
    return {"status": status, "message": messages.get(status, f"Outbox status: {status}")}


def referee_for_token(token: str) -> dict | None:
    """What the public reference page shows, or ``None`` if the link is
    unknown, used, withdrawn or expired."""
    with get_connection() as conn:
        ensure(conn)
        row = conn.execute(
            """SELECT r.referee_id, r.name, r.relationship, r.status,
                      r.token_expires_at, a.program_applied,
                      p.first_name, p.last_name
                 FROM admission_referees r
                 JOIN admission_applications a ON a.application_id = r.application_id
                 LEFT JOIN admission_prospects p ON p.prospect_id = a.prospect_id
                WHERE r.token_hash = ?""",
            (_hash(token),)).fetchone()
    if row is None or row["status"] != "requested":
        return None
    if (row["token_expires_at"] or "") < casework.now():
        return None
    return {
        "referee_name": row["name"], "relationship": row["relationship"],
        "applicant": f"{row['first_name'] or ''} {row['last_name'] or ''}".strip(),
        "programme": row["program_applied"] or "",
    }


def submit_reference_by_token(token: str, text: str, *, file_bytes: bytes | None = None,
                              filename: str = "") -> dict:
    """Record the referee's own submission. The link works once."""
    text = (text or "").strip()
    if not text and not file_bytes:
        return {"ok": False, "message": "Please write a reference or attach a letter."}
    with transaction() as conn:
        ensure(conn)
        row = conn.execute("SELECT * FROM admission_referees WHERE token_hash = ?",
                           (_hash(token),)).fetchone()
        if row is None or row["status"] != "requested" \
                or (row["token_expires_at"] or "") < casework.now():
            return {"ok": False, "message": "This link is not valid or has already been used."}
        actor = f"referee:{row['email']}"
        document_id = None
        if file_bytes:
            document_id = casework.store_document(
                conn, row["application_id"], document_type="reference",
                uploaded_by=actor, data=file_bytes, filename=filename,
                document_name=f"Reference from {row['name']}")
        _mark_received(conn, row, text, document_id, via="link", recorded_by=actor)
    return {"ok": True, "message": "Thank you. Your reference has been received."}


def _mark_received(conn, referee, text: str, document_id, *, via: str,
                   recorded_by: str) -> None:
    conn.execute(
        """UPDATE admission_referees
              SET status = 'received', token_hash = NULL, received_at = ?,
                  received_via = ?, recorded_by = ?, reference_text = ?,
                  document_id = ?
            WHERE referee_id = ?""",
        (casework.now(), via, recorded_by, text or None, document_id,
         referee["referee_id"]))
    casework.audit(conn, referee["application_id"], "reference_received", recorded_by,
                   target_type="referee", target_id=referee["referee_id"],
                   detail={"via": via, "document_id": document_id})


def record_reference(viewer: Any, referee_id: int, *, text: str = "",
                     file_path: str | None = None) -> None:
    """Admissions staff record a reference received outside the link."""
    actor = casework.require_manager(viewer)
    if not (text or "").strip() and not file_path:
        raise AdmissionsBoundaryError("Attach the reference file or enter its text")
    with transaction() as conn:
        referee = _referee(conn, referee_id)
        if referee["status"] in ("received", "withdrawn"):
            raise AdmissionsBoundaryError(f"This referee is already {referee['status']}")
        document_id = None
        if file_path:
            document_id = casework.store_document(
                conn, referee["application_id"], document_type="reference",
                uploaded_by=actor, source_path=file_path, verified=True,
                document_name=f"Reference from {referee['name']}")
        _mark_received(conn, referee, (text or "").strip(), document_id,
                       via="staff", recorded_by=actor)


# ── Research proposal ──────────────────────────────────────────────

def add_proposal(viewer: Any, application_id: int, title: str, *, summary: str = "",
                 file_path: str | None = None) -> int:
    actor = casework.require_manager(viewer)
    if not (title or "").strip():
        raise AdmissionsBoundaryError("The proposal needs a title")
    if not file_path:
        raise AdmissionsBoundaryError("Attach the research proposal document")
    with transaction() as conn:
        ensure(conn)
        _research_application(conn, application_id)
        document_id = casework.store_document(
            conn, application_id, document_type="research_proposal",
            uploaded_by=actor, source_path=file_path,
            document_name=f"Research proposal: {title.strip()}")
        conn.execute("UPDATE admission_research_proposals SET is_current = 0 "
                     "WHERE application_id = ?", (int(application_id),))
        cur = conn.execute(
            """INSERT INTO admission_research_proposals
                 (application_id, title, summary, document_id, uploaded_by)
               VALUES (?, ?, ?, ?, ?)""",
            (int(application_id), title.strip(), (summary or "").strip(),
             document_id, actor))
        proposal_id = int(cur.lastrowid)
        casework.audit(conn, application_id, "research_proposal_uploaded", actor,
                       target_type="proposal", target_id=proposal_id,
                       detail={"title": title.strip(), "document_id": document_id})
    return proposal_id


# ── Supervisors ─────────────────────────────────────────────────────

def staff_directory() -> list[dict]:
    """Academic and professional staff who can be proposed as supervisors."""
    marks = ",".join("?" * len(SUPERVISOR_STAFF_ROLES))
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            # db-audit: ignore[DBW001] - placeholders only
            f"SELECT username, first_name, last_name, email, role FROM users "
            f"WHERE role IN ({marks}) AND COALESCE(service_account, 0) = 0 "
            f"ORDER BY last_name, first_name",
            SUPERVISOR_STAFF_ROLES).fetchall()]


def nominate_supervisor(viewer: Any, application_id: int, username: str,
                        role: str = "primary") -> int:
    actor = casework.require_manager(viewer)
    username = (username or "").strip()
    if role not in SUPERVISOR_ROLES:
        raise AdmissionsBoundaryError("Role must be one of " + ", ".join(SUPERVISOR_ROLES))
    if username not in {s["username"] for s in staff_directory()}:
        raise AdmissionsBoundaryError(f"{username!r} is not a member of staff")
    with transaction() as conn:
        ensure(conn)
        _research_application(conn, application_id)
        existing = conn.execute(
            "SELECT nomination_id, status FROM admission_supervisor_nominations "
            "WHERE application_id = ? AND supervisor_username = ?",
            (int(application_id), username)).fetchone()
        if existing is not None and existing["status"] != "withdrawn":
            raise AdmissionsBoundaryError(f"{username} is already proposed")
        if existing is not None:
            conn.execute(
                """UPDATE admission_supervisor_nominations
                      SET status = 'proposed', role = ?, nominated_by = ?,
                          nominated_at = ?, decided_by = NULL, decided_at = NULL,
                          comment = NULL
                    WHERE nomination_id = ?""",
                (role, actor, casework.now(), existing["nomination_id"]))
            nomination_id = int(existing["nomination_id"])
        else:
            nomination_id = int(conn.execute(
                """INSERT INTO admission_supervisor_nominations
                     (application_id, supervisor_username, role, nominated_by)
                   VALUES (?, ?, ?, ?)""",
                (int(application_id), username, role, actor)).lastrowid)
        casework.audit(conn, application_id, "supervisor_proposed", actor,
                       target_type="supervisor_nomination", target_id=nomination_id,
                       detail={"supervisor": username, "role": role})
    return nomination_id


def _nomination(conn, nomination_id: int):
    ensure(conn)
    row = conn.execute(
        "SELECT * FROM admission_supervisor_nominations WHERE nomination_id = ?",
        (int(nomination_id),)).fetchone()
    if row is None:
        raise AdmissionsBoundaryError(f"Nomination {nomination_id} does not exist")
    return row


def withdraw_nomination(viewer: Any, nomination_id: int, reason: str) -> None:
    actor = casework.require_manager(viewer)
    with transaction() as conn:
        row = _nomination(conn, nomination_id)
        conn.execute(
            "UPDATE admission_supervisor_nominations SET status = 'withdrawn', "
            "comment = ? WHERE nomination_id = ?", ((reason or "").strip(), int(nomination_id)))
        casework.audit(conn, row["application_id"], "supervisor_withdrawn", actor,
                       target_type="supervisor_nomination", target_id=nomination_id,
                       detail={"supervisor": row["supervisor_username"], "reason": reason})


def decide_supervision(viewer: Any, nomination_id: int, accept: bool,
                       comment: str = "") -> str:
    """The proposed supervisor accepts or declines, with a comment.

    Only the supervisor named on the nomination may decide; an admin may
    record a decision on their behalf, and the audit trail says so.
    """
    actor = casework.actor_name(viewer)
    comment = (comment or "").strip()
    if not accept and not comment:
        raise AdmissionsBoundaryError("Please give a reason when declining")
    with transaction() as conn:
        row = _nomination(conn, nomination_id)
        on_behalf = actor != row["supervisor_username"]
        if on_behalf and not casework.is_admin(viewer):
            raise AdmissionsBoundaryError(
                "Only the proposed supervisor can accept or decline this request")
        if row["status"] != "proposed":
            raise AdmissionsBoundaryError(f"This request is already {row['status']}")
        status = "accepted" if accept else "declined"
        conn.execute(
            """UPDATE admission_supervisor_nominations
                  SET status = ?, decided_by = ?, decided_at = ?, comment = ?
                WHERE nomination_id = ?""",
            (status, actor, casework.now(), comment, int(nomination_id)))
        casework.audit(conn, row["application_id"], f"supervision_{status}", actor,
                       target_type="supervisor_nomination", target_id=nomination_id,
                       detail={"supervisor": row["supervisor_username"],
                               "comment": comment, "on_behalf": on_behalf})
    return status


def supervision_requests(viewer: Any, *, include_decided: bool = True) -> list[dict]:
    """The requests addressed to the signed-in member of staff."""
    username = casework.actor_name(viewer)
    if not username:
        return []
    with get_connection() as conn:
        ensure(conn)
        rows = conn.execute(
            """SELECT n.*, a.program_applied, a.academic_year, a.status AS application_status,
                      p.first_name, p.last_name,
                      (SELECT title FROM admission_research_proposals rp
                        WHERE rp.application_id = n.application_id AND rp.is_current = 1
                        ORDER BY proposal_id DESC LIMIT 1) AS proposal_title,
                      (SELECT document_id FROM admission_research_proposals rp
                        WHERE rp.application_id = n.application_id AND rp.is_current = 1
                        ORDER BY proposal_id DESC LIMIT 1) AS proposal_document_id
                 FROM admission_supervisor_nominations n
                 JOIN admission_applications a ON a.application_id = n.application_id
                 LEFT JOIN admission_prospects p ON p.prospect_id = a.prospect_id
                WHERE n.supervisor_username = ? AND n.status != 'withdrawn'
                ORDER BY CASE n.status WHEN 'proposed' THEN 0 ELSE 1 END,
                         n.nominated_at DESC""",
            (username,)).fetchall()
    out = [dict(r) for r in rows]
    return out if include_decided else [r for r in out if r["status"] == "proposed"]


# ── Interview ───────────────────────────────────────────────────────

def schedule_interview(viewer: Any, application_id: int, scheduled_at: str, *,
                       panel: str, format: str = "", location: str = "") -> int:
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle as lifecycle,
    )
    actor = casework.require_manager(viewer)
    if not (scheduled_at or "").strip() or not (panel or "").strip():
        raise AdmissionsBoundaryError("An interview needs a date/time and a panel")
    with get_connection() as conn:
        _pg_application(conn, application_id)
    interview_id = lifecycle.schedule_activity(
        application_id, scheduled_at.strip(), activity_type="interview",
        format=format, location=location, panel=panel.strip())
    with transaction() as conn:
        casework.audit(conn, application_id, "interview_scheduled", actor,
                       target_type="interview", target_id=interview_id,
                       detail={"scheduled_at": scheduled_at, "panel": panel})
    return interview_id


def record_interview_outcome(viewer: Any, interview_id: int, outcome: str,
                             notes: str = "") -> None:
    actor = casework.require_manager(viewer)
    if outcome not in INTERVIEW_OUTCOMES:
        raise AdmissionsBoundaryError(
            "Outcome must be one of " + ", ".join(INTERVIEW_OUTCOMES))
    with transaction() as conn:
        ensure(conn)
        row = conn.execute("SELECT * FROM admission_interviews WHERE interview_id = ?",
                           (int(interview_id),)).fetchone()
        if row is None:
            raise AdmissionsBoundaryError(f"Interview {interview_id} does not exist")
        status = "reconvene" if outcome == "reconvene" else "completed"
        conn.execute(
            "UPDATE admission_interviews SET status = ?, outcome = ?, notes = ? "
            "WHERE interview_id = ?", (status, outcome, (notes or "").strip(), int(interview_id)))
        casework.audit(conn, row["application_id"], "interview_outcome", actor,
                       target_type="interview", target_id=interview_id,
                       detail={"outcome": outcome, "notes": notes})


# ── Read model and the gate ────────────────────────────────────────

def summary(application_id: int) -> dict:
    """Everything the postgraduate panel shows for one application."""
    with get_connection() as conn:
        ensure(conn)
        app = casework.application_row(conn, application_id)
        aid = int(application_id)

        def rows(sql: str) -> list[dict]:
            return [dict(r) for r in conn.execute(sql, (aid,)).fetchall()]

        result = {
            "application_type": app["application_type"],
            "postgraduate": is_postgraduate(app["application_type"]),
            "research": is_research(app["application_type"]),
            "referees": rows("SELECT referee_id, name, email, relationship, status, "
                             "requested_at, request_count, token_expires_at, received_at, "
                             "received_via, recorded_by, document_id, reference_text "
                             "FROM admission_referees WHERE application_id = ? "
                             "ORDER BY referee_id"),
            "proposals": rows("SELECT * FROM admission_research_proposals "
                              "WHERE application_id = ? ORDER BY proposal_id DESC"),
            "nominations": rows("SELECT * FROM admission_supervisor_nominations "
                                "WHERE application_id = ? ORDER BY nomination_id"),
            "interviews": rows("SELECT * FROM admission_interviews WHERE application_id = ? "
                               "AND activity_type = 'interview' "
                               "ORDER BY scheduled_at, interview_id"),
        }
    result["issues"] = _issues_from(result) if result["postgraduate"] else []
    return result


def _issues_from(data: dict) -> list[str]:
    issues: list[str] = []
    received = sum(1 for r in data["referees"] if r["status"] == "received")
    if received < REQUIRED_REFEREES:
        issues.append(f"references incomplete ({received} of {REQUIRED_REFEREES} received)")
    if not data["research"]:
        return issues
    if not any(p["is_current"] for p in data["proposals"]):
        issues.append("research proposal has not been uploaded")
    live = [n for n in data["nominations"] if n["status"] != "withdrawn"]
    if not any(n["status"] == "accepted" for n in live):
        issues.append("no proposed supervisor has agreed to supervise")
    if any(n["status"] == "proposed" for n in live):
        issues.append("a proposed supervisor has not yet responded")
    if not any(i.get("outcome") == "recommend_offer" for i in data["interviews"]):
        issues.append("research interview not recorded with a recommendation to offer")
    return issues


def requirement_issues(application_id: int) -> list[str]:
    """What still holds a postgraduate application back from enrolment."""
    return summary(application_id)["issues"]


def pgr_handover(conn, application_id: int) -> dict | None:
    """The proposal and agreed supervisors to carry into the PGR record,
    or ``None`` for a non-research application."""
    app = casework.application_row(conn, application_id)
    if not is_research(app["application_type"]):
        return None
    ensure(conn)
    proposal = conn.execute(
        "SELECT title, summary FROM admission_research_proposals "
        "WHERE application_id = ? AND is_current = 1 ORDER BY proposal_id DESC LIMIT 1",
        (int(application_id),)).fetchone()
    supervisors = conn.execute(
        "SELECT supervisor_username, role FROM admission_supervisor_nominations "
        "WHERE application_id = ? AND status = 'accepted' "
        "ORDER BY CASE role WHEN 'primary' THEN 0 WHEN 'secondary' THEN 1 ELSE 2 END, "
        "nomination_id", (int(application_id),)).fetchall()
    return {
        "proposal_title": proposal["title"] if proposal else "",
        "proposal_summary": (proposal["summary"] if proposal else "") or "",
        "supervisors": [{"username": s["supervisor_username"], "role": s["role"]}
                        for s in supervisors],
    }


__all__ = [
    "INTERVIEW_OUTCOMES", "POSTGRADUATE_TYPES", "RELATIONSHIPS", "REQUIRED_REFEREES",
    "RESEARCH_TYPES", "SUPERVISOR_ROLES", "add_proposal", "add_referee",
    "decide_supervision", "is_postgraduate", "is_research", "nominate_supervisor",
    "pgr_handover", "record_interview_outcome", "record_reference", "referee_for_token",
    "request_reference", "requirement_issues", "schedule_interview", "staff_directory",
    "submit_reference_by_token", "summary", "supervision_requests",
    "withdraw_nomination", "withdraw_referee",
]
