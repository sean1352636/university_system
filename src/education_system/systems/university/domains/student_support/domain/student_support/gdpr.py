"""UK GDPR for support tickets: retention, subject access and erasure.

Retention (storage limitation, Art. 5(1)(e))
--------------------------------------------
A resolved or closed ticket is **purged** once its closure date (closed, else
resolved, else last updated) is older than its tier's period:

* **standard** — 2 years (typical UK HE practice for routine enquiries: long
  enough for complaints to the OIA, which must reach it within 12 months of
  the university's final decision, and for repeat-contact history);
* **restricted** — 6 years (health, disability and hardship casework, kept as
  long as a contract / personal-injury claim could arise: Limitation Act 1980);
* **safeguarding** — and any ticket that ever carried crisis language — is
  **never purged automatically**; the safeguarding leads review it (the
  safeguarding register keeps the concern itself under its own retention).

The periods can be changed by an administrator (:func:`set_retention`, kept
in ``helpdesk_system_settings``). A ticket under a legal hold
(``university_legal_holds``, record type ``support_ticket``) is skipped.

Purging keeps an anonymous skeleton for statistics (category, team, tier,
priority, status, dates, rating) and removes everything personal: subject
and text, the requester, replies, attachments (rows, and the files on disk
after the commit), referrals and every other row tied to the ticket;
``data_purged_at`` records when. The daily support job runs :func:`purge`
and also removes upload folders left behind by tickets that no longer exist
(e.g. after a whole-student erasure).

Subject access (Art. 15)
------------------------
:func:`subject_access_export` (administrators) gives everything held about a
person in support tickets, sealed text revealed, following the health
portal's ``subject_access``: the person's tickets, their own words and the
replies sent to them are disclosed; staff **internal notes** and private
staff attachments are notes *about* the person and in scope, but go to
``for_review`` for the data protection officer to check before release
(third-party data, and the serious-harm test for health / social-work data
under DPA 2018 Sch. 3); safeguarding concern references go the same way.

Erasure (Art. 17)
-----------------
Dual control, as the student erasure: :func:`erase_student` records a
request (administrator A, with a case reference and reason), a different
administrator who has just re-entered their password decides
(:func:`decide_erasure`), then :func:`execute_erasure` purges the person's
tickets as above. Open tickets block the request (close them first);
safeguarding tickets and tickets under a legal hold are kept (Art. 17(3):
legal obligations and claims, vital interests) and listed in the result.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    confidentiality as _tiers,
    schema,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

logger = logging.getLogger(__name__)

RETENTION_YEARS = {_tiers.STANDARD: 2, _tiers.RESTRICTED: 6}     # safeguarding: never
SETTING_KEYS = {_tiers.STANDARD: 'support_retention_standard_years',
                _tiers.RESTRICTED: 'support_retention_restricted_years'}
PURGED_SUBJECT = "[Removed under the retention policy]"
ERASED_SUBJECT = "[Erased on request]"
#: Columns blanked when a ticket is purged (those that exist).
PERSONAL_COLUMNS = ('description', 'resolution', 'satisfaction_feedback', 'tags',
                    'requester_username', 'student_id', 'user_id', 'share_consent',
                    'share_consent_at', 'knowledge_base_articles')


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _has(conn, table) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,)).fetchone() is not None


def _cols(conn, table) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _require_admin(actor) -> dict:
    user = _auth.require_auth(actor)
    if not _auth.is_admin(user):
        raise PermissionError("Only an administrator can do this")
    return user


# ── retention policy ────────────────────────────────────────────────────


def retention_policy(conn=None) -> dict:
    """``{tier: years or None}`` — None: never purged automatically."""
    policy: dict = {**RETENTION_YEARS, _tiers.SAFEGUARDING: None}
    own = conn is None
    conn = conn or store.connect()
    try:
        if _has(conn, 'helpdesk_system_settings'):
            for tier, key in SETTING_KEYS.items():
                row = conn.execute("SELECT setting_value FROM helpdesk_system_settings "
                                   "WHERE setting_key = ?", (key,)).fetchone()
                if row and str(row[0]).isdigit() and int(row[0]) >= 1:
                    policy[tier] = int(row[0])
    finally:
        if own:
            conn.close()
    return policy


def set_retention(actor, *, standard_years: int, restricted_years: int) -> dict:
    """Change the retention periods (administrators; 1-25 years, restricted
    at least as long as standard)."""
    user = _require_admin(actor)
    standard, restricted = int(standard_years), int(restricted_years)
    if not (1 <= standard <= 25 and 1 <= restricted <= 25):
        raise ValueError("Keep tickets for 1 to 25 years")
    if restricted < standard:
        raise ValueError("Restricted tickets must be kept at least as long as standard ones")
    with store.writing() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS helpdesk_system_settings (setting_key TEXT "
                     "PRIMARY KEY, setting_value TEXT, updated_at TEXT)")
        for tier, years in ((_tiers.STANDARD, standard), (_tiers.RESTRICTED, restricted)):
            conn.execute("INSERT INTO helpdesk_system_settings (setting_key, setting_value, "
                         "updated_at) VALUES (?, ?, ?) ON CONFLICT (setting_key) DO UPDATE SET "
                         "setting_value = excluded.setting_value, updated_at = "
                         "excluded.updated_at", (SETTING_KEYS[tier], str(years), _now()))
        log_audit('retention_policy', resource_type='support_settings', actor=user, conn=conn,
                  new_values={'standard_years': standard, 'restricted_years': restricted})
        return retention_policy(conn)


# ── purging one ticket ──────────────────────────────────────────────────


def _children(conn) -> list:
    """``(table, column)`` of every foreign key to ``support_tickets`` (but
    its own parent link)."""
    out = []
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND "
                                 "name NOT LIKE 'sqlite_%' AND name <> 'support_tickets'"):
        for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
            if fk[2] == 'support_tickets':
                out.append((table, fk[3]))
    return out


def _on_hold(conn, ticket_id) -> bool:
    if not _has(conn, 'university_legal_holds'):
        return False
    return conn.execute("SELECT 1 FROM university_legal_holds WHERE record_type = "
                        "'support_ticket' AND record_id = ? AND released_at IS NULL",
                        (str(ticket_id),)).fetchone() is not None


def purge_ticket(conn, ticket_id, *, subject=PURGED_SUBJECT, children=None) -> list:
    """Remove the personal data of one ticket on ``conn`` (no commit);
    returns the attachment file paths to delete after the commit."""
    files = [r[0] for r in conn.execute("SELECT file_path FROM ticket_attachments WHERE "
                                        "ticket_id = ?", (ticket_id,)).fetchall() if r[0]]
    for table, column in (children if children is not None else _children(conn)):
        # Names come from the schema (PRAGMA), never from input.
        conn.execute(f'DELETE FROM "{table}" WHERE "{column}" = ?', (ticket_id,))  # nosec B608
    have = _cols(conn, 'support_tickets')
    blank = [c for c in PERSONAL_COLUMNS if c in have and c != 'description']
    sets = ", ".join(f'"{c}" = NULL' for c in blank)
    conn.execute(f"UPDATE support_tickets SET {sets}, subject = ?, description = '', "  # nosec B608
                 "data_purged_at = ? WHERE ticket_id = ?", (subject, _now(), ticket_id))
    return files


#: Why a ticket may be deleted outright (otherwise it is closed and kept for
#: the retention period, or removed by an approved erasure request).
DELETE_REASONS = ('created in error', 'duplicate', 'spam or abuse', 'test ticket', 'other')


def delete_ticket(actor, ticket_id, reason, *, confirm_ticket_id=None, detail="") -> dict:
    """Delete one ticket permanently: the ticket, its replies, attachments
    (and their files), assignments, links, time entries and referral
    cross-references. Administrators only, with a reason.

    Refused for safeguarding / crisis tickets (they are kept for the duty of
    care), for tickets under a legal hold, and unless ``confirm_ticket_id``
    repeats the ticket number. Tickets merged into it are unlinked, not
    deleted. The audit log keeps who deleted which ticket, when and why —
    never its text. Returns ``{'ticket_id', 'files_removed'}``.
    """
    user = _require_admin(actor)
    reason = str(reason or '').strip().lower()
    if reason not in DELETE_REASONS:
        raise ValueError("Choose a reason: " + ", ".join(DELETE_REASONS))
    detail = str(detail or '').strip()
    if reason == 'other' and len(detail) < 10:
        raise ValueError("Explain why the ticket is being deleted (a sentence)")
    try:
        tid = int(ticket_id)
    except (TypeError, ValueError):
        raise ValueError("Give a ticket number") from None
    if str(confirm_ticket_id or '').strip().lstrip('#') != str(tid):
        raise ValueError(f"Type the ticket number ({tid}) to confirm the deletion")
    with store.writing() as conn:
        row = conn.execute("SELECT ticket_id, confidentiality, crisis_flag, status, category, "
                           "team, created_at FROM support_tickets WHERE ticket_id = ?",
                           (tid,)).fetchone()
        if row is None:
            raise ValueError(f"Ticket #{tid} was not found")
        if row['crisis_flag'] or _tiers.tier_of(row) == _tiers.SAFEGUARDING:
            raise PermissionError(f"Ticket #{tid} is a safeguarding ticket and cannot be deleted; "
                                  "it is kept for the duty of care")
        if _on_hold(conn, tid):
            raise PermissionError(f"Ticket #{tid} is under a legal hold and cannot be deleted")
        files = purge_ticket(conn, tid)
        conn.execute("UPDATE support_tickets SET parent_ticket_id = NULL "
                     "WHERE parent_ticket_id = ?", (tid,))
        if _has(conn, 'support_ticket_referrals'):
            conn.execute("DELETE FROM support_ticket_referrals WHERE ticket_id = ?", (tid,))
        conn.execute("DELETE FROM support_tickets WHERE ticket_id = ?", (tid,))
        log_audit('delete_ticket', resource_id=tid, actor=user, conn=conn,
                  old_values={'status': row['status'], 'category': row['category'],
                              'team': row['team'], 'confidentiality': _tiers.tier_of(row),
                              'created_at': row['created_at']},
                  new_values={'reason': reason, 'detail': detail or None,
                              'attachments': len(files)})
    removed = delete_files(files)
    logger.info("Support ticket #%s deleted by %s (%s)", tid, user.get('username'), reason)
    return {'ticket_id': tid, 'files_removed': removed}


def delete_files(paths) -> int:
    """Delete attachment files (after the commit). Only files inside the
    support upload folder are touched; emptied ticket folders go too."""
    from education_system.systems.university.domains.student_support.domain.student_support.core import (
        attachment_manager,
    )
    root = attachment_manager.upload_root().resolve()
    removed = 0
    for value in paths:
        path = Path(value).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            logger.warning("Not deleting %s: outside the support upload folder", path)
            continue
        try:
            if path.is_file():
                path.unlink()
                removed += 1
            if path.parent != root and path.parent.is_dir() and not any(path.parent.iterdir()):
                path.parent.rmdir()
        except OSError:
            logger.warning("Could not delete %s", path, exc_info=True)
    return removed


def sweep_orphan_files() -> int:
    """Delete upload folders of tickets that no longer exist or were purged."""
    from education_system.systems.university.domains.student_support.domain.student_support.core import (
        attachment_manager,
    )
    root = attachment_manager.upload_root()
    if not root.is_dir():
        return 0
    with store.reading() as conn:
        live = {str(r[0]) for r in conn.execute(
            "SELECT ticket_id FROM support_tickets WHERE data_purged_at IS NULL")}
    stale = [p for p in root.iterdir() if p.is_dir() and p.name.isdigit() and p.name not in live]
    return delete_files([f for folder in stale for f in folder.iterdir() if f.is_file()])


# ── the retention job ───────────────────────────────────────────────────


def due_for_purge(conn, now: Optional[str] = None) -> list:
    """Ticket ids past their tier's retention period (see module doc)."""
    now = now or _now()
    policy = retention_policy(conn)
    closed = "COALESCE(closed_at, resolved_at, updated_at, created_at)"
    due = []
    for tier in (_tiers.STANDARD, _tiers.RESTRICTED):
        years = policy.get(tier)
        if not years:
            continue
        due += [r[0] for r in conn.execute(
            f"SELECT ticket_id FROM support_tickets WHERE data_purged_at IS NULL "  # nosec B608
            f"AND status IN ('resolved', 'closed') AND COALESCE(crisis_flag, 0) = 0 "
            f"AND COALESCE(confidentiality, 'standard') = ? "
            f"AND {closed} < datetime(?, ?)", (tier, now, f"-{int(years)} years")).fetchall()]
    return [tid for tid in sorted(due) if not _on_hold(conn, tid)]


def purge(actor=None, *, now: Optional[str] = None, dry_run: bool = False) -> dict:
    """Purge every ticket past its retention period. ``actor`` None is the
    scheduled job; a person must be an administrator. Returns
    ``{'due', 'purged', 'files_deleted', 'orphan_files_deleted'}``."""
    user = _require_admin(actor) if actor is not None else {'username': 'system'}
    with store.writing() as conn:
        due = due_for_purge(conn, now)
        if dry_run:
            return {'due': due, 'purged': 0, 'files_deleted': 0, 'orphan_files_deleted': 0}
        children = _children(conn)
        files: list = []
        for tid in due:
            files += purge_ticket(conn, tid, children=children)
            log_audit('retention_purge', resource_id=tid, actor=user, conn=conn,
                      details={'policy': retention_policy(conn)})
    deleted = delete_files(files)
    orphans = sweep_orphan_files()
    if due:
        logger.info("Support retention: purged %s ticket(s), %s file(s)", len(due), deleted)
    return {'due': due, 'purged': len(due), 'files_deleted': deleted,
            'orphan_files_deleted': orphans}


def run_retention_job() -> dict:
    """The daily support job (``services/bus/jobs/support_jobs``)."""
    return purge(None)


# ── whose tickets ───────────────────────────────────────────────────────


def _person(conn, ref) -> dict:
    """``{'usernames', 'student_id', 'ids'}`` for a username or student number."""
    text = str(ref or '').strip()
    if not text:
        raise ValueError("Say whose support records these are")
    rows = conn.execute("SELECT id, username, student_id FROM users WHERE username = ? OR "
                        "student_id = ?", (text, text)).fetchall()
    student = next((r['student_id'] for r in rows if r['student_id']), None)
    if student is None and _has(conn, 'students') and conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (text,)).fetchone():
        student = text
    if not rows and student is None:
        raise ValueError(f"No student or user '{text}' was found")
    return {'usernames': sorted({r['username'] for r in rows}), 'student_id': student,
            'ids': sorted({str(r['id']) for r in rows})}


def _ticket_rows(conn, who) -> list:
    clauses, params = [], []
    if who['usernames']:
        clauses.append(f"requester_username IN ({', '.join('?' * len(who['usernames']))})")
        params += who['usernames']
    if who['student_id']:
        clauses.append("student_id = ?")
        params.append(who['student_id'])
    legacy = [who['student_id']] if who['student_id'] else []
    legacy += who['usernames']
    if legacy:
        clauses.append(f"(requester_username IS NULL AND user_id IN "
                       f"({', '.join('?' * len(legacy))}))")
        params += legacy
    return conn.execute(f"SELECT * FROM support_tickets WHERE ({' OR '.join(clauses)}) "  # nosec B608
                        "ORDER BY ticket_id", params).fetchall()


# ── subject access ──────────────────────────────────────────────────────


def _sar_ticket(conn, row, for_review: list, withheld: dict) -> dict:
    tid = row['ticket_id']
    ticket = _tiers.reveal_row(row)
    replies = []
    for r in conn.execute("SELECT * FROM ticket_responses WHERE ticket_id = ? ORDER BY "
                          "response_datetime, response_id", (tid,)).fetchall():
        reply = _tiers.reveal_row(r)
        if r['is_internal']:
            for_review.append({'ticket_id': tid, 'what': 'internal staff note', 'row': reply})
            withheld['internal notes (for review)'] = withheld.get(
                'internal notes (for review)', 0) + 1
        else:
            replies.append(reply)
    attachments = []
    for a in conn.execute("SELECT attachment_id, original_filename, file_size, mime_type, "
                          "uploaded_by, is_public, created_at FROM ticket_attachments WHERE "
                          "ticket_id = ?", (tid,)).fetchall():
        item = dict(a)
        if a['is_public'] or str(a['uploaded_by'] or '') in (row['requester_username'] or '',):
            attachments.append(item)
        else:
            for_review.append({'ticket_id': tid, 'what': 'private staff attachment', 'row': item})
    referrals = []
    if _has(conn, 'support_ticket_referrals'):
        for r in conn.execute("SELECT kind, target_ref, status, consent_basis, created_at FROM "
                              "support_ticket_referrals WHERE ticket_id = ?", (tid,)).fetchall():
            if r['kind'] == 'safeguarding':
                for_review.append({'ticket_id': tid, 'what': 'safeguarding concern reference',
                                   'row': dict(r)})
            else:
                referrals.append(dict(r))
    ticket.update(responses=replies, attachments=attachments, referrals=referrals)
    return ticket


def support_section(conn, person) -> dict:
    """The support-ticket section of a SAR disclosure for ``person`` (a
    username or student number): ``{'records': [tickets], 'for_review':
    [...], 'withheld': {what: count}}``."""
    who = _person(conn, person)
    for_review: list = []
    withheld: dict = {}
    records = [_sar_ticket(conn, row, for_review, withheld) for row in _ticket_rows(conn, who)]
    return {'person': who, 'records': records, 'for_review': for_review, 'withheld': withheld,
            'generated_at': _now()}


def subject_access_export(actor, student) -> dict:
    """Everything support tickets hold about ``student`` (administrators;
    the disclosure is recorded in the immutable audit log first, fail closed)."""
    user = _require_admin(actor)
    with store.reading() as conn:
        section = support_section(conn, student)
    from education_system.systems.university.infrastructure.security.immutable_audit_log import (
        log_security_event,
    )
    try:
        log_security_event(user_id=str(user['username']), action="SAR_SUPPORT_DISCLOSURE",
                           resource_type="support_ticket", resource_id=str(student),
                           details={'tickets': [t['ticket_id'] for t in section['records']],
                                    'withheld': section['withheld']})
    except Exception as exc:
        raise PermissionError(f"The disclosure could not be recorded, so it was refused ({exc})") \
            from None
    log_audit('subject_access_export', resource_type='support_person', resource_id=student,
              actor=user, details={'tickets': len(section['records'])})
    return section


# ── erasure (dual control) ──────────────────────────────────────────────


def _erasure_plan(conn, who) -> dict:
    keep, erase, active = [], [], []
    for row in _ticket_rows(conn, who):
        tid = row['ticket_id']
        if row['data_purged_at']:
            continue
        if row['status'] not in schema.DONE_STATUSES:
            active.append(tid)
        elif _tiers.tier_of(row) == _tiers.SAFEGUARDING or row['crisis_flag'] \
                or _on_hold(conn, tid):
            keep.append(tid)
        else:
            erase.append(tid)
    return {'erase': erase, 'keep': keep, 'active': active}


def erase_student(actor, student, reason, *, case_reference=None) -> int:
    """Request erasure of ``student``'s support records (administrators);
    returns the request id. Another administrator decides it."""
    user = _require_admin(actor)
    reason = str(reason or '').strip()
    if len(reason) < 10:
        raise ValueError("Give the reason for the erasure (a sentence)")
    case_reference = str(case_reference or '').strip() or \
        f"SUPPORT-ERASURE-{datetime.date.today():%Y%m%d}"
    with store.writing() as conn:
        schema.ensure_care_tables(conn)
        who = _person(conn, student)
        plan = _erasure_plan(conn, who)
        if plan['active']:
            raise ValueError("Close these tickets first: "
                             + ", ".join(f"#{t}" for t in plan['active']))
        if conn.execute("SELECT 1 FROM support_erasure_requests WHERE status IN ('requested', "
                        "'approved') AND (student_id = ? OR requester_username = ?)",
                        (who['student_id'], (who['usernames'] or [None])[0])).fetchone():
            raise ValueError("An erasure request for this person is already open")
        rid = conn.execute(
            "INSERT INTO support_erasure_requests (requester_username, student_id, "
            "case_reference, reason, tickets_json, requested_by, requested_at) VALUES "
            "(?, ?, ?, ?, ?, ?, ?)", ((who['usernames'] or [None])[0], who['student_id'],
                                      case_reference, reason, json.dumps(plan),
                                      user['username'], _now())).lastrowid
        log_audit('erasure_requested', resource_type='support_erasure', resource_id=rid,
                  actor=user, conn=conn, details={'plan': plan, 'case': case_reference})
    return int(rid)


def _request(conn, request_id) -> dict:
    schema.ensure_care_tables(conn)
    row = conn.execute("SELECT * FROM support_erasure_requests WHERE request_id = ?",
                       (request_id,)).fetchone()
    if row is None:
        raise ValueError("No such erasure request")
    return dict(row)


def decide_erasure(actor, request_id, approve: bool, *, reauthenticated: bool,
                   note: str = '') -> str:
    """Approve or reject (a different administrator, who has just re-entered
    their password). Returns the new status."""
    user = _require_admin(actor)
    if not reauthenticated:
        raise ValueError("Re-enter your password to decide an erasure request")
    with store.writing() as conn:
        r = _request(conn, request_id)
        if r['status'] != 'requested':
            raise ValueError(f"This request is already {r['status']}")
        if r['requested_by'] == user['username']:
            raise ValueError("Someone other than the requester must decide")
        status = 'approved' if approve else 'rejected'
        conn.execute("UPDATE support_erasure_requests SET status = ?, decided_by = ?, "
                     "decided_at = ?, decision_note = ? WHERE request_id = ?",
                     (status, user['username'], _now(), note or None, request_id))
        log_audit('erasure_decided', resource_type='support_erasure', resource_id=request_id,
                  actor=user, conn=conn, details={'status': status, 'note': note})
    return status


def execute_erasure(actor, request_id) -> dict:
    """Carry out an approved request. Returns ``{'erased', 'kept',
    'files_deleted'}`` (kept: safeguarding / legal-hold tickets)."""
    user = _require_admin(actor)
    with store.writing() as conn:
        r = _request(conn, request_id)
        if r['status'] != 'approved':
            raise ValueError("Only an approved request can be carried out")
        who = _person(conn, r['student_id'] or r['requester_username'])
        plan = _erasure_plan(conn, who)
        if plan['active']:
            raise ValueError("Tickets have been reopened since approval: "
                             + ", ".join(f"#{t}" for t in plan['active']))
        children = _children(conn)
        files: list = []
        for tid in plan['erase']:
            files += purge_ticket(conn, tid, subject=ERASED_SUBJECT, children=children)
        result = {'erased': plan['erase'], 'kept': plan['keep']}
        conn.execute("UPDATE support_erasure_requests SET status = 'completed', completed_by = ?, "
                     "completed_at = ?, result_json = ? WHERE request_id = ?",
                     (user['username'], _now(), json.dumps(result), request_id))
        log_audit('erasure_completed', resource_type='support_erasure', resource_id=request_id,
                  actor=user, conn=conn, details=result)
    result['files_deleted'] = delete_files(files)
    return result


def erasure_requests(actor, status=None) -> list:
    _require_admin(actor)
    with store.writing() as conn:
        schema.ensure_care_tables(conn)
        sql, args = "SELECT * FROM support_erasure_requests", ()
        if status:
            sql, args = sql + " WHERE status = ?", (status,)
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY request_id DESC", args)]
    for r in rows:
        r['tickets'] = json.loads(r.pop('tickets_json') or '{}')
        r['result'] = json.loads(r.pop('result_json') or 'null')
    return rows


__all__ = [
    'RETENTION_YEARS', 'retention_policy', 'set_retention', 'due_for_purge', 'purge',
    'purge_ticket', 'delete_files', 'sweep_orphan_files', 'run_retention_job',
    'support_section', 'subject_access_export', 'erase_student', 'decide_erasure',
    'execute_erasure', 'erasure_requests',
]
