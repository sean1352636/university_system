"""The Student Support / Helpdesk ticket service.

Module-level functions over the one ticket model (see ``schema``). Each takes
the signed-in user first — an auth object with ``current_user`` or the
``current_user`` dict itself — checks permission itself and raises
``PermissionError`` / ``ValueError`` with a message fit to show the user. No
printing, no prompting: the CLI and GUI call these.

Visibility comes from ``auth.can_view_ticket`` / ``auth.ticket_scope_sql``
(team and confidentiality tier — see ``confidentiality``); internal notes and
private attachments reach only the staff working the ticket. A look at a
restricted or safeguarding ticket by anyone but its requester is recorded
(fail closed) before its text — sealed at rest — is revealed.

New tickets are routed to a team (``routing.route``), classified into a tier
and checked for crisis language (``safety``): a crisis makes the ticket a
safeguarding ticket, and :func:`submit_ticket` / :func:`post_response` return
the crisis contacts to show at once (``'crisis'``) while a safeguarding
concern is raised after the commit. ``sla.set_due`` / ``sla.on_first_response``
keep the service levels (``routing`` and ``sla`` are optional until installed).

Each change is one transaction carrying its audit entry and in-app notices;
attachment files are written and ``notify.after_commit`` runs only after the
commit.
"""

from __future__ import annotations

import datetime
import importlib
import json
import logging
from pathlib import Path
from typing import Iterable, Optional

from education_system.systems.university.infrastructure.sql_safety import escape_like

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    confidentiality as _tiers,
    notify,
    safety,
    schema,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.config import (
    SUPPORT_CATEGORIES,
    TICKET_PRIORITIES,
    SupportConfig,
)
from education_system.systems.university.domains.student_support.domain.student_support.core import (
    attachment_manager as _files,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

logger = logging.getLogger(__name__)

config = SupportConfig()

MAX_SUBJECT = 200
MAX_DESCRIPTION = 5000
MAX_RESPONSE = 10000

#: Shown in lists instead of a confidential ticket's description.
SEALED_PLACEHOLDER = "[Confidential — open the ticket to read it]"

_PACKAGE = __name__.rsplit('.', 1)[0]


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _optional(name):
    """A sibling module that may not be installed yet (``routing``, ``sla``)."""
    try:
        return importlib.import_module(f"{_PACKAGE}.{name}")
    except ImportError:
        return None


# ── reading helpers ──────────────────────────────────────────────────────


def _ticket_row(conn, ticket_id):
    try:
        ticket_id = int(ticket_id)
    except (TypeError, ValueError):
        raise ValueError(f"'{ticket_id}' is not a ticket number")
    row = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise ValueError(f"Ticket #{ticket_id} was not found")
    return row


def _visible_ticket(conn, actor, ticket_id):
    row = _ticket_row(conn, ticket_id)
    if not _auth.can_view_ticket(actor, row, conn):
        raise PermissionError(f"You do not have access to ticket #{row['ticket_id']}")
    return row


def _staff_ticket(conn, actor, ticket_id, what="change this ticket"):
    if not _auth.is_case_worker(actor):
        raise PermissionError(f"Only support staff can {what}")
    row = _ticket_row(conn, ticket_id)
    if not _auth.can_work_ticket(actor, row, conn):
        raise PermissionError(f"Only support staff working ticket #{row['ticket_id']} can {what}")
    return row


def _revealed(actor, row, purpose='view', conn=None) -> dict:
    """``row`` as a dict with its sealed text revealed, after recording the
    look (``conn``: the caller's write transaction; leave out on a read)."""
    _tiers.record_view(actor, row, purpose=purpose, conn=conn)
    return _tiers.reveal_row(row)


def _decorate(ticket: dict) -> dict:
    try:
        ticket['tags'] = json.loads(ticket.get('tags') or '[]')
    except (TypeError, ValueError):
        ticket['tags'] = []
    ticket['status_label'] = schema.status_label(ticket.get('status'))
    return ticket


def _requester_ref(ticket) -> Optional[str]:
    """Who to tell about a ticket: the requester's username, else their
    student number (both resolve to an account in ``messages``)."""
    return ticket['requester_username'] or ticket['student_id']


def _assignee_ref(ticket) -> Optional[str]:
    value = ticket['assigned_to']
    return str(value) if value not in (None, '') else None


def _add_auto_note(conn, ticket_id, text, *, internal=False, role='system', who=None):
    text = _tiers.seal('ticket_responses', 'response_text', text,
                       _tiers.tier_for_ticket(conn, ticket_id))
    conn.execute('''
    INSERT INTO ticket_responses (ticket_id, responder_id, responder_username, responder_role,
                                  response_text, response_datetime, is_internal, is_auto_generated)
    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    ''', (ticket_id, str(who.users_id or who.username) if who else 'system',
          who.username if who else None, role if who is None else who.role,
          text, _now(), 1 if internal else 0))


def _metric(conn, name, value, category, metadata):
    conn.execute('''
    INSERT INTO system_metrics (metric_name, metric_value, category, recorded_datetime, metadata)
    VALUES (?, ?, ?, ?, ?)''', (name, value, category, _now(), json.dumps(metadata, default=str)))


def _after_commit(notices, files=None, ticket_id=None) -> list:
    failed = _files.write_attachment_files(files) if files else []
    if failed and ticket_id is not None:
        names = ", ".join(f"'{f['original_filename']}'" for f in failed)
        with store.writing() as conn:
            _add_auto_note(conn, ticket_id, f"The attachment {names} could not be saved; "
                           "please add it again.")
    try:
        notify.after_commit(notices)
    except Exception:
        logger.warning("after-commit notification work failed", exc_info=True)
    return failed


def _sync_pause(conn, ticket_id) -> None:
    """Start or end the SLA pause for waiting on the student (``sla``)."""
    sla = _optional('sla')
    if sla is not None:
        sla.sync_pause(conn, ticket_id)


def _collab():
    from education_system.systems.university.domains.student_support.domain.student_support import (
        collaboration,
    )
    return collaboration


# ── validation ───────────────────────────────────────────────────────────


def _match(value, allowed: Iterable[str]) -> Optional[str]:
    text = str(value or '').strip().lower()
    for item in allowed:
        if item.lower() == text:
            return item
    return None


def _clean_text(value, label, limit) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > limit:
        raise ValueError(f"{label} must be {limit} characters or less")
    return text


def _resolve_requester(conn, ref):
    """``(username, student_id, users_id)`` for a username or student number."""
    text = str(ref or '').strip()
    if not text:
        raise ValueError("Say who the ticket is for")
    row = conn.execute("SELECT id, username, student_id FROM users WHERE username = ?",
                       (text,)).fetchone()
    if row is None:
        row = conn.execute("SELECT id, username, student_id FROM users WHERE student_id = ? "
                           "ORDER BY id LIMIT 1", (text,)).fetchone()
    if row is not None:
        return row['username'], row['student_id'], row['id']
    has_students = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                "AND name = 'students'").fetchone()
    if has_students and conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                                     (text,)).fetchone():
        return None, text, None
    raise ValueError(f"No student or user '{text}' was found")


# ── create ───────────────────────────────────────────────────────────────


def _routing_uk_category(category):
    try:
        from education_system.systems.university.domains.student_support.domain.student_support import routing
    except ImportError:
        return None
    return routing.uk_category(category)


def _routing_stored_categories(category):
    try:
        from education_system.systems.university.domains.student_support.domain.student_support import routing
    except ImportError:
        return [category]
    return routing.stored_categories(category) or [category]


def _validate_new(source, subject, description, category, priority):
    """``(subject, description, category, priority)`` checked and normalised."""
    from education_system.systems.university.domains.student_support.domain.student_support.automation.sentiment_analysis import (
        _suggest_category,
    )
    if source not in schema.SOURCES:
        raise ValueError(f"Unknown source '{source}'")
    subject = _clean_text(subject, "Title", MAX_SUBJECT)
    description = _clean_text(description, "Description", MAX_DESCRIPTION)
    category = str(category or '').strip()
    if source == 'support':
        # A legacy value (e.g. 'Technical', 'Mental Health') means its UK category.
        matched = _match(_routing_uk_category(category) or category, SUPPORT_CATEGORIES)
        if not matched:
            matched = _suggest_category(f"{subject} {description}")
        if not matched:
            raise ValueError(f"Invalid category. Choose from: {', '.join(SUPPORT_CATEGORIES)}")
        category = matched
        priority_value = _match(priority, TICKET_PRIORITIES)
        if not priority_value:
            raise ValueError(f"Invalid priority. Choose from: {', '.join(TICKET_PRIORITIES)}")
    else:
        if not category:
            raise ValueError("Category is required")
        if not _match(priority, TICKET_PRIORITIES):
            raise ValueError(f"Invalid priority. Choose from: {', '.join(TICKET_PRIORITIES)}")
        priority_value = str(priority).strip().lower()
    return subject, description, category, priority_value


def _assignable(conn, username, ticket: dict) -> bool:
    """May ``username`` be given ``ticket`` (works tickets and is in its tier)?"""
    row = conn.execute("SELECT username, role FROM users WHERE username = ?",
                       (str(username),)).fetchone()
    return row is not None and _tiers.can_work({'username': row['username'],
                                                'role': row['role']}, ticket, conn)


def _requester_fields(conn, me, requester, source):
    """``(username, student_id, users_id, legacy user_id)`` of whom a new
    ticket is for (support staff may raise one for someone else)."""
    if requester is not None and str(requester).strip() not in (me.username, me.student_id or ''):
        if not me.is_staff:
            raise PermissionError("You can only create support tickets for your own account")
        username, student, users_id = _resolve_requester(conn, requester)
    else:
        username, student, users_id = me.username, me.student_id, me.users_id
    # user_id is what each front-end's existing screens read: Student
    # Support a student number, the Helpdesk a users.id.
    if source == 'support':
        legacy = student or username
    else:
        legacy = str(users_id) if users_id is not None else username
    return username, student, users_id, legacy


def submit_ticket(actor, *, subject, description, category, priority='Medium',
                  requester=None, source='support', channel='web', team=None,
                  attachments=None, tags=None, template_id=None, subcategory=None,
                  impact=None, urgency=None, department=None, due_date=None,
                  assigned_to=None, confidentiality=None) -> dict:
    """Raise a ticket. Returns ``{'ticket_id', 'team', 'confidentiality',
    'crisis'}`` — ``crisis`` is None, or the support to show the person at
    once (``safety.crisis_support``) when the ticket used crisis language.

    ``requester`` (a username or student number) lets support staff raise a
    ticket for someone else; anyone else may only raise their own. ``source``
    is 'support' (Student Support) or 'helpdesk'. ``confidentiality`` may ask
    for a higher tier than the ticket's subject gives it (only staff can ask
    for safeguarding).
    """
    from education_system.systems.university.domains.student_support.domain.student_support.automation.sentiment_analysis import (
        _analyze_sentiment,
        _estimate_resolution_time,
        _get_auto_assignment,
    )
    from education_system.systems.university.domains.student_support.domain.student_support.features.templates import (
        _create_auto_response,
    )

    user = _auth.require_auth(actor)
    subject, description, category, priority_value = _validate_new(
        source, subject, description, category, priority)
    if confidentiality and _tiers.normalize_tier(confidentiality) == _tiers.SAFEGUARDING \
            and not _auth.is_case_worker(user):
        confidentiality = _tiers.RESTRICTED
    crisis = safety.detect(subject, description)
    routing = _optional('routing')
    if routing is not None:
        team = routing.route(category, subcategory, team)
    if crisis:
        team = safety.TEAM
        priority_value = safety.PRIORITY[source]
    tier = _tiers.classify(category, subcategory, team, crisis=crisis, requested=confidentiality)

    prepared = _files.prepare_attachments(attachments)
    sentiment = _analyze_sentiment(description)
    # Opens its own connection: done before the write transaction.
    if assigned_to is None and config.auto_assign_enabled and not crisis:
        assigned_to = _get_auto_assignment(category, priority_value)
    estimated_resolution = _estimate_resolution_time(category, priority_value)

    notices, support = [], None
    with store.writing() as conn:
        me = _auth.current_requester(user, conn)
        req_username, req_student, _uid, legacy_user_id = _requester_fields(
            conn, me, requester, source)
        draft = {'ticket_id': None, 'requester_username': req_username,
                 'student_id': req_student, 'team': team, 'category': category,
                 'subcategory': subcategory, 'confidentiality': tier}
        if assigned_to and not _assignable(conn, assigned_to, draft):
            assigned_to = None
        now = _now()
        cur = conn.execute('''
        INSERT INTO support_tickets (
            user_id, requester_username, student_id, subject, description, category, subcategory,
            priority, impact, urgency, status, source, channel, team, department, due_date,
            created_at, updated_at, last_activity_at, assigned_to, sentiment,
            estimated_resolution, tags, confidentiality, crisis_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (legacy_user_id, req_username, req_student, subject,
              _tiers.seal('support_tickets', 'description', description, tier), category,
              subcategory, priority_value, impact or 'low', urgency or 'low', source, channel,
              team, department, due_date, now, now, now, assigned_to, sentiment,
              estimated_resolution, json.dumps(list(tags or [])), tier, 1 if crisis else 0))
        ticket_id = cur.lastrowid
        sla = _optional('sla')
        if sla is not None:
            sla.set_due(conn, ticket_id)
        if prepared:
            _files.insert_attachment_rows(conn, ticket_id, prepared, me.username, public=True)
        if template_id:
            conn.execute("UPDATE ticket_templates SET usage_count = COALESCE(usage_count, 0) + 1 "
                         "WHERE template_id = ?", (template_id,))
        _create_auto_response(ticket_id, 'acknowledgment', conn.cursor(),
                              username=req_username or req_student)
        if crisis:
            support = safety.crisis_support(conn)
            _add_auto_note(conn, ticket_id, "Crisis language detected: this ticket is now a "
                           "safeguarding ticket and a safeguarding concern is being raised.",
                           internal=True)
        log_audit('create_ticket', resource_id=ticket_id, actor=user, conn=conn,
                  details={'source': source, 'category': category, 'priority': priority_value,
                           'requester': req_username or req_student, 'team': team,
                           'confidentiality': tier, 'crisis': crisis,
                           'attachments': len(prepared)})
        notices = notify.ticket_created(ticket_id, subject, req_username or req_student,
                                        assigned_to)
        notify.deliver_in_app(conn, notices, sender_username=None)
    _after_commit(notices, prepared, ticket_id)
    if crisis:
        support['safeguarding_reference'] = safety.raise_concern(
            ticket_id, f"{subject}\n\n{description}", where='new ticket',
            actor_username=user['username'])
    logger.info("Support ticket #%s created by %s (source %s)", ticket_id, user['username'], source)
    return {'ticket_id': ticket_id, 'team': team, 'confidentiality': tier, 'crisis': support}


def create_ticket(actor, **fields) -> int:
    """Raise a ticket; returns its number (:func:`submit_ticket` for the
    crisis support and tier too). Takes the same keyword arguments."""
    return submit_ticket(actor, **fields)['ticket_id']


# ── read ─────────────────────────────────────────────────────────────────


def _responses(conn, ticket_id, staff: bool) -> list:
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM ticket_responses WHERE ticket_id = ? ORDER BY response_datetime, response_id",
        (ticket_id,)).fetchall()]
    for r in rows:
        r['source'] = 'support'
    # Helpdesk replies live in ticket_replies; show them in the same thread.
    has_replies = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                               "AND name = 'ticket_replies'").fetchone()
    if has_replies:
        for r in conn.execute('''
            SELECT tr.reply_id, tr.ticket_id, tr.user_id, tr.message, tr.is_internal,
                   tr.created_at, u.username, u.role
            FROM ticket_replies tr LEFT JOIN users u ON u.id = tr.user_id
            WHERE tr.ticket_id = ?''', (ticket_id,)).fetchall():
            rows.append({
                'response_id': None, 'reply_id': r['reply_id'], 'ticket_id': r['ticket_id'],
                'responder_id': r['user_id'], 'responder_username': r['username'],
                'responder_role': r['role'] or 'staff', 'response_text': r['message'],
                'response_datetime': r['created_at'], 'is_internal': r['is_internal'],
                'is_auto_generated': 0, 'template_used': None, 'source': 'helpdesk',
            })
    if not staff:
        rows = [r for r in rows if not r.get('is_internal')]
    rows.sort(key=lambda r: (str(r.get('response_datetime') or ''), r.get('response_id') or 0))
    # Callers have checked (and recorded) access: reveal sealed replies.
    return [_tiers.reveal_row(r) for r in rows]


def _attachments(conn, ticket_id, actor, ticket=None) -> list:
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM ticket_attachments WHERE ticket_id = ? ORDER BY created_at, attachment_id",
        (ticket_id,)).fetchall()]
    if ticket is None:
        ticket = _ticket_row(conn, ticket_id)
    if _auth.can_see_internal(actor, ticket, conn):
        return rows
    me = _auth.current_requester(actor, conn)
    mine = {me.username, str(me.users_id) if me.users_id is not None else None}
    return [r for r in rows if r.get('is_public') or str(r.get('uploaded_by') or '') in mine]


def get_ticket(actor, ticket_id) -> dict:
    """A ticket with the replies and attachments ``actor`` may see.

    A crisis ticket opened by its requester carries ``'crisis_support'`` (the
    contacts to show again)."""
    with store.reading() as conn:
        row = _visible_ticket(conn, actor, ticket_id)
        staff = _auth.can_see_internal(actor, row, conn)
        ticket = _decorate(_revealed(actor, row))
        ticket['responses'] = _responses(conn, row['ticket_id'], staff)
        ticket['attachments'] = _attachments(conn, row['ticket_id'], actor, row)
        ticket['access'] = _tiers.access_basis(actor, row, conn)
        if row['crisis_flag'] and ticket['access'] == 'owner':
            ticket['crisis_support'] = safety.crisis_support(conn)
    return ticket


def _filter_sql(filters: Optional[dict]) -> tuple[str, list]:
    sql, params = "", []
    if not filters:
        return sql, params
    status = filters.get('status')
    if status:
        values = status if isinstance(status, (list, tuple, set)) else [status]
        statuses = sorted({schema.normalize_status(v) for v in values})
        sql += f" AND status IN ({', '.join('?' * len(statuses))})"
        params += statuses
    if filters.get('active_only'):
        sql += f" AND status IN ({', '.join('?' * len(schema.ACTIVE_STATUSES))})"
        params += list(schema.ACTIVE_STATUSES)
    if filters.get('category'):
        # A UK category also finds tickets stored under its legacy names.
        values = _routing_stored_categories(filters['category'])
        sql += f" AND category IN ({', '.join('?' * len(values))})"
        params += values
    for key in ('source', 'team', 'requester_username', 'student_id'):
        if filters.get(key):
            sql += f" AND {key} = ?"
            params.append(filters[key])
    if filters.get('priority'):
        sql += " AND lower(priority) = lower(?)"
        params.append(filters['priority'])
    # assigned_to=None (key present) or unassigned=True: nobody has it.
    if filters.get('unassigned') or ('assigned_to' in filters and filters['assigned_to'] is None):
        sql += " AND (assigned_to IS NULL OR assigned_to = '')"
    elif filters.get('assigned_to'):
        sql += " AND assigned_to = ?"
        params.append(str(filters['assigned_to']))
    if filters.get('date_from'):
        sql += " AND created_at >= ?"
        params.append(filters['date_from'])
    if filters.get('date_to'):
        sql += " AND created_at <= ?"
        params.append(filters['date_to'])
    if filters.get('search'):
        term = f"%{escape_like(str(filters['search']))}%"
        sql += " AND (subject LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')"
        params += [term, term]
    return sql, params


def _page(conn, actor, where, params, filters, page, per_page) -> dict:
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 20), 500))
    fsql, fparams = _filter_sql(filters)
    base = f"FROM support_tickets WHERE {where}{fsql}"  # nosec B608 - built from fixed fragments
    total = conn.execute(f"SELECT COUNT(*) {base}", params + fparams).fetchone()[0]  # nosec B608
    rows = conn.execute(f"SELECT * {base} ORDER BY created_at DESC, ticket_id DESC "  # nosec B608
                        "LIMIT ? OFFSET ?", params + fparams + [per_page, (page - 1) * per_page]
                        ).fetchall()
    cur = conn.cursor()
    tickets = []
    for row in rows:
        staff = _auth.can_see_internal(actor, row, conn)
        ticket = _decorate(_list_row(actor, row, conn))
        ticket['attachment_count'] = _files._get_attachment_count(row['ticket_id'], cur, staff)
        ticket['last_response_by'] = _files._get_last_response_info(row['ticket_id'], cur, staff)
        tickets.append(ticket)
    return {'tickets': tickets, 'total_count': total, 'page': page, 'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page}


def _list_row(actor, row, conn) -> dict:
    """A list entry: a confidential ticket's text is revealed to its
    requester only (anyone else opens the ticket, which records the look)."""
    ticket = dict(row)
    if not _tiers.is_sealed_tier(_tiers.tier_of(row)):
        return ticket
    if _tiers.access_basis(actor, row, conn) == 'owner':
        return _tiers.reveal_row(ticket)
    for column in ('description', 'resolution'):
        if ticket.get(column):
            ticket[column] = SEALED_PLACEHOLDER
    return ticket


def list_my_tickets(actor, filters=None, page=1, per_page=20) -> dict:
    """Tickets the signed-in person raised (whoever they are)."""
    with store.reading() as conn:
        me = _auth.current_requester(actor, conn)
        if me.student_id:
            where = ("(requester_username = ? OR (requester_username IS NULL AND "
                     "(student_id = ? OR user_id = ?)))")
            params = [me.username, me.student_id, me.student_id]
        else:
            where, params = "requester_username = ?", [me.username]
        return _page(conn, actor, where, params, filters, page, per_page)


def list_tickets(actor, filters=None, page=1, per_page=20) -> dict:
    """Every ticket the signed-in support staff member may work on."""
    if not _auth.is_case_worker(actor):
        raise PermissionError("Only support staff can list all tickets")
    with store.reading() as conn:
        where, params = _auth.ticket_scope_sql(actor, conn=conn)
        return _page(conn, actor, where, params, filters, page, per_page)


def list_tickets_for_requester(actor, requester, filters=None, page=1, per_page=20) -> dict:
    """Staff view of one person's tickets (``requester``: username or student number)."""
    if not _auth.is_case_worker(actor):
        raise PermissionError("Only support staff can view another person's tickets")
    with store.reading() as conn:
        username, student_id, _uid = _resolve_requester(conn, requester)
        clauses, params = [], []
        if username:
            clauses.append("requester_username = ?")
            params.append(username)
        if student_id:
            clauses.append("student_id = ?")
            clauses.append("(requester_username IS NULL AND user_id = ?)")
            params += [student_id, student_id]
        where = "(" + " OR ".join(clauses) + ")"
        scope, sparams = _auth.ticket_scope_sql(actor, conn=conn)
        return _page(conn, actor, f"{where} AND {scope}", params + sparams, filters, page, per_page)


def list_attachments(actor, ticket_id) -> list:
    with store.reading() as conn:
        row = _visible_ticket(conn, actor, ticket_id)
        _tiers.record_view(actor, row, purpose='attachments')
        return _attachments(conn, row['ticket_id'], actor, row)


def get_attachment(actor, attachment_id) -> dict:
    """``{'filename', 'data', 'mime_type'}`` of an attachment ``actor`` may see."""
    with store.reading() as conn:
        att = conn.execute("SELECT * FROM ticket_attachments WHERE attachment_id = ?",
                           (attachment_id,)).fetchone()
        if att is None:
            raise ValueError(f"Attachment {attachment_id} was not found")
        ticket = _visible_ticket(conn, actor, att['ticket_id'])
        visible = {a['attachment_id'] for a in _attachments(conn, att['ticket_id'], actor, ticket)}
        if att['attachment_id'] not in visible:
            raise PermissionError("You do not have access to this attachment")
        _tiers.record_view(actor, ticket, purpose='download_attachment')
    path = Path(att['file_path'])
    root = _files.upload_root().resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError:
        # Rows written before the upload folder moved keep their old path;
        # anything outside the ticket's own folder name is refused.
        if path.parent.name != str(att['ticket_id']) or path.parent.parent.name != 'tickets':
            raise PermissionError("This attachment is stored outside the support upload folder")
    if not path.is_file():
        raise FileNotFoundError(f"The file for attachment {attachment_id} is missing")
    log_audit('download_attachment', resource_id=att['ticket_id'], actor=actor,
              details={'attachment_id': att['attachment_id']})
    return {'filename': att['original_filename'], 'data': path.read_bytes(),
            'mime_type': att['mime_type']}


def ticket_history(actor, ticket_id) -> dict:
    """``{'ticket', 'timeline'}`` — creation, the replies and attachments
    ``actor`` may see and, for support staff, the audit entries."""
    with store.reading() as conn:
        row = _visible_ticket(conn, actor, ticket_id)
        staff = _auth.can_see_internal(actor, row, conn)
        tid = row['ticket_id']
        revealed = _revealed(actor, row, purpose='history')
        ticket = _decorate(dict(revealed))
        timeline = [{'type': 'creation', 'datetime': row['created_at'] or '', 'data': revealed}]
        timeline += [{'type': 'response', 'datetime': r['response_datetime'] or '', 'data': r}
                     for r in _responses(conn, tid, staff)]
        timeline += [{'type': 'attachment', 'datetime': a['created_at'] or '', 'data': a}
                     for a in _attachments(conn, tid, actor, row)]
        if staff and conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                  "AND name = 'audit_trail'").fetchone():
            timeline += [{'type': 'audit', 'datetime': a['timestamp'] or '', 'data': dict(a)}
                         for a in conn.execute(
                             "SELECT * FROM audit_trail WHERE resource_id = ? AND "
                             "resource_type LIKE '%ticket%' ORDER BY timestamp", (str(tid),)
                         ).fetchall()]
    timeline.sort(key=lambda e: str(e['datetime']))
    return {'ticket': ticket, 'timeline': timeline}


# ── change ───────────────────────────────────────────────────────────────


def _crisis_in_reply(conn, ticket, source) -> str:
    """Crisis language in the requester's reply: make the ticket a
    safeguarding ticket on ``conn``; returns its new tier."""
    tid = ticket['ticket_id']
    conn.execute("UPDATE support_tickets SET crisis_flag = 1, confidentiality = ?, team = ?, "
                 "priority = ? WHERE ticket_id = ?",
                 (_tiers.SAFEGUARDING, safety.TEAM,
                  safety.PRIORITY.get(source or 'support', 'Critical'), tid))
    _tiers.reseal(conn, tid, _tiers.SAFEGUARDING)
    _add_auto_note(conn, tid, "Crisis language in a reply from the requester: this ticket is now "
                   "a safeguarding ticket.", internal=True)
    log_audit('crisis_detected', resource_id=tid, conn=conn,
              old_values={'confidentiality': _tiers.tier_of(ticket)},
              new_values={'confidentiality': _tiers.SAFEGUARDING})
    return _tiers.SAFEGUARDING


def post_response(actor, ticket_id, text, *, internal=False, template_id=None,
                  attachments=None) -> dict:
    """Reply to a ticket (staff working it may make it an internal note).
    Returns ``{'response_id', 'crisis'}`` — ``crisis`` as in
    :func:`submit_ticket`, for crisis language in the requester's reply.

    A staff public reply moves an open ticket to in progress (taking it if
    nobody has) and records the first response; a reply from the requester
    brings a ticket waiting on them, or resolved, back into work.
    """
    user = _auth.require_auth(actor)
    text = _clean_text(text, "A reply", MAX_RESPONSE)
    prepared = _files.prepare_attachments(attachments)
    notices, support, crisis = [], None, False
    with store.writing() as conn:
        ticket = _visible_ticket(conn, user, ticket_id)
        tid = ticket['ticket_id']
        staff = _auth.can_work_ticket(user, ticket, conn)
        if internal and not staff:
            raise PermissionError("Only support staff can add internal notes")
        me = _auth.current_requester(user, conn)
        status = schema.normalize_status(ticket['status'], default='open')
        if not staff and status == 'closed':
            raise ValueError("This ticket is closed. Please open a new ticket if you still need help.")
        if staff:
            _tiers.record_view(user, ticket, purpose='reply', conn=conn)
        if template_id and staff:
            from education_system.systems.university.domains.student_support.domain.student_support.core.response_manager import (
                _apply_response_template,
            )
            text = _apply_response_template(template_id, tid, text, conn.cursor())
            conn.execute("UPDATE response_templates SET usage_count = COALESCE(usage_count, 0) + 1 "
                         "WHERE template_id = ?", (template_id,))
        tier = _tiers.tier_of(ticket)
        crisis = not staff and safety.detect(text)
        if crisis:
            tier = _crisis_in_reply(conn, ticket, ticket['source'])
            support = safety.crisis_support(conn)
        now = _now()
        cur = conn.execute('''
        INSERT INTO ticket_responses (ticket_id, responder_id, responder_username, responder_role,
                                      response_text, response_datetime, is_internal, template_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tid, str(me.users_id if me.users_id is not None else me.username), me.username,
              me.role, _tiers.seal('ticket_responses', 'response_text', text, tier), now,
              1 if internal else 0, template_id))
        response_id = cur.lastrowid
        if prepared:
            _files.insert_attachment_rows(conn, tid, prepared, me.username, public=not internal)

        new_status, assignee = status, ticket['assigned_to']
        first_response = ticket['first_response_at']
        resolved_at = ticket['resolved_at']
        if staff and not internal:
            if status == 'open':
                new_status = 'in_progress'
            if not assignee:
                assignee = me.username
            first_response = first_response or now
        elif not staff:
            if status == 'waiting_on_student' or status == 'resolved':
                new_status = 'in_progress' if assignee else 'open'
                resolved_at = None
        conn.execute('''
        UPDATE support_tickets SET status = ?, assigned_to = ?, first_response_at = ?,
               resolved_at = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?''', (new_status, assignee, first_response, resolved_at, now, now, tid))
        if staff and not internal and not ticket['first_response_at']:
            sla = _optional('sla')
            if sla is not None:
                sla.on_first_response(conn, tid)
        _sync_pause(conn, tid)
        log_audit('add_response', resource_id=tid, actor=user, conn=conn,
                  details={'response_id': response_id, 'internal': bool(internal),
                           'status': [status, new_status], 'crisis': crisis})
        told = [me.username]
        if not internal:
            if staff:
                notices = notify.reply_added(tid, ticket['subject'], _requester_ref(ticket), True)
                told.append(_requester_ref(ticket))
            else:
                notices = notify.reply_added(tid, ticket['subject'],
                                             assignee and str(assignee), False)
                told.append(assignee and str(assignee))
        kind = 'Internal note' if internal else 'New reply'
        notices += _collab().follower_notices(
            conn, ticket, f"{kind} on ticket #{tid}",
            f"{me.username} added {'an internal note' if internal else 'a reply'} to support "
            f"ticket #{tid} \"{ticket['subject']}\".", internal=internal, exclude=told)
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    _after_commit(notices, prepared, tid)
    if crisis:
        support['safeguarding_reference'] = safety.raise_concern(
            tid, text, where=f'reply #{response_id}', actor_username=user['username'])
    return {'response_id': response_id, 'crisis': support}


def add_response(actor, ticket_id, text, *, internal=False, template_id=None,
                 attachments=None) -> int:
    """Reply to a ticket; returns the reply's id (:func:`post_response` for
    the crisis support too)."""
    return post_response(actor, ticket_id, text, internal=internal, template_id=template_id,
                         attachments=attachments)['response_id']


def _change_status(conn, user, me, ticket, new, note=None) -> tuple[dict, list]:
    """Move ``ticket`` to ``new`` on ``conn``; returns ``(result, notices)``."""
    tid = ticket['ticket_id']
    old = schema.normalize_status(ticket['status'], default='open')
    if old == new and not note:
        return {'old': old, 'new': new, 'changed': False}, []
    now = _now()
    fields = {'status': new, 'updated_at': now, 'last_activity_at': now}
    if note and new in schema.DONE_STATUSES:
        # The resolution is sealed with the ticket's text.
        note_stored = _tiers.seal('support_tickets', 'resolution', note, _tiers.tier_of(ticket))
    else:
        note_stored = note
    if new == 'resolved':
        fields['resolved_at'] = ticket['resolved_at'] or now
        if note:
            fields['resolution'] = note_stored
    elif new == 'closed':
        fields['closed_at'] = now
        fields['resolved_at'] = ticket['resolved_at'] or now
        if note:
            fields['resolution'] = note_stored
    elif new == 'escalated':
        fields['escalated_at'] = now
        fields['escalation_level'] = (ticket['escalation_level'] or 0) + 1
    else:
        fields['resolved_at'] = None
        fields['closed_at'] = None
    if new == 'in_progress' and not ticket['assigned_to']:
        fields['assigned_to'] = me.username
    # Column names come from the fixed dict above.
    conn.execute("UPDATE support_tickets SET " + ", ".join(f"{k} = ?" for k in fields)  # nosec B608
                 + " WHERE ticket_id = ?", list(fields.values()) + [tid])
    _sync_pause(conn, tid)
    text = (f"Status changed from {schema.STATUS_LABELS.get(old, old)} to "
            f"{schema.STATUS_LABELS[new]}")
    if note:
        text += f"\n\n{'Resolution' if new in schema.DONE_STATUSES else 'Note'}: {note}"
    _add_auto_note(conn, tid, text, who=me)
    _metric(conn, 'status_change', 1, 'tickets',
            {'ticket_id': tid, 'old_status': old, 'new_status': new, 'changed_by': me.username})
    log_audit('set_status', resource_id=tid, actor=user, conn=conn,
              old_values={'status': old}, new_values={'status': new})
    notices = []
    if old != new:
        notices = notify.status_changed(tid, ticket['subject'], _requester_ref(ticket),
                                        schema.STATUS_LABELS[new])
        if new == 'resolved' and config.satisfaction_survey_enabled:
            notices += notify.satisfaction_invite(tid, ticket['subject'], _requester_ref(ticket))
        notices += _collab().follower_notices(
            conn, ticket, f"Ticket #{tid}: {schema.STATUS_LABELS[new]}",
            f"Support ticket #{tid} \"{ticket['subject']}\" is now {schema.STATUS_LABELS[new]} "
            f"(changed by {me.username}).", exclude=[me.username, _requester_ref(ticket)])
    return {'old': old, 'new': new, 'changed': old != new}, notices


def set_status(actor, ticket_id, status, *, note=None) -> dict:
    """Move a ticket to ``status`` (any spelling either front-end used).

    Returns ``{'old', 'new', 'changed'}``. Resolving records ``resolved_at``
    (and ``resolution`` from ``note``); closing records ``closed_at``;
    reopening clears both. The assignee is kept (an unassigned ticket moved
    to in progress is taken by whoever moved it).
    """
    user = _auth.require_auth(actor)
    new = schema.normalize_status(status)
    with store.writing() as conn:
        ticket = _staff_ticket(conn, user, ticket_id, "change a ticket's status")
        me = _auth.current_requester(user, conn)
        result, notices = _change_status(conn, user, me, ticket, new, note)
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    _after_commit(notices)
    return result


def assign(actor, ticket_id, assignee) -> dict:
    """Give a ticket to a support staff member (``assignee`` a username), or
    ``None`` to unassign. Returns ``{'old', 'new'}``."""
    user = _auth.require_auth(actor)
    notices = []
    with store.writing() as conn:
        ticket = _staff_ticket(conn, user, ticket_id, "assign tickets")
        tid = ticket['ticket_id']
        me = _auth.current_requester(user, conn)
        new = None
        if assignee not in (None, ''):
            row = conn.execute("SELECT username, role FROM users WHERE username = ?",
                               (str(assignee).strip(),)).fetchone()
            if row is None:
                raise ValueError(f"No user '{assignee}' was found")
            if not _auth.is_case_worker({'username': row['username'], 'role': row['role']}):
                raise ValueError(f"{row['username']} is not support staff")
            if not _assignable(conn, row['username'], ticket):
                raise ValueError(f"{row['username']} is not in this ticket's team or "
                                 "confidentiality tier")
            new = row['username']
        old = ticket['assigned_to']
        if (old or None) == new:
            return {'old': old, 'new': new}
        now = _now()
        conn.execute("UPDATE support_tickets SET assigned_to = ?, updated_at = ?, "
                     "last_activity_at = ? WHERE ticket_id = ?", (new, now, now, tid))
        _add_auto_note(conn, tid, f"Assigned to {new}" if new else "Unassigned",
                       internal=True, who=me)
        log_audit('assign', resource_id=tid, actor=user, conn=conn,
                  old_values={'assigned_to': old}, new_values={'assigned_to': new})
        if new and new != me.username:
            notices = notify.assigned(tid, ticket['subject'], new)
            notify.deliver_in_app(conn, notices, sender_username=me.username)
    _after_commit(notices)
    return {'old': old, 'new': new}


_TIER_RANK = {_tiers.STANDARD: 0, _tiers.RESTRICTED: 1, _tiers.SAFEGUARDING: 2}


def edit_ticket(actor, ticket_id, *, subject=None, description=None, reason="") -> dict:
    """Change a ticket's subject and/or description.

    Support staff working the ticket may edit it with a reason; the requester
    may correct their own ticket while it is still open. The description keeps
    the ticket's tier sealing, the change is audited (lengths, not text) and
    noted on the ticket, and crisis language in the requester's edit takes the
    same path as in a reply. Returns ``{'changed', 'crisis'}``.
    """
    user = _auth.require_auth(actor)
    reason = str(reason or '').strip()
    new_subject = None if subject is None else _clean_text(subject, "Title", MAX_SUBJECT)
    new_description = (None if description is None
                       else _clean_text(description, "Description", MAX_DESCRIPTION))
    support, crisis = None, False
    with store.writing() as conn:
        row = _ticket_row(conn, ticket_id)
        tid = row['ticket_id']
        me = _auth.current_requester(user, conn)
        staff = _auth.is_case_worker(user) and _auth.can_work_ticket(user, row, conn)
        if not staff:
            if not _auth.owns_ticket(me, row):
                raise PermissionError(f"Only support staff working ticket #{tid} can edit it")
            if row['status'] != 'open':
                raise PermissionError("You can only edit your ticket while it is still open — "
                                      "add a reply instead")
        elif len(reason) < 5:
            raise ValueError("Give a reason for editing the ticket")
        current = _revealed(user, row, purpose='edit', conn=conn)
        changed = []
        if new_subject is not None and new_subject != current.get('subject'):
            changed.append('subject')
        if new_description is not None and new_description != current.get('description'):
            changed.append('description')
        if not changed:
            return {'changed': [], 'crisis': None}
        tier = _tiers.tier_of(row)
        if not staff and new_description is not None and safety.detect(new_description):
            crisis = True
            tier = _crisis_in_reply(conn, row, row['source'])
            support = safety.crisis_support(conn)
        now = _now()
        sets, params = ["updated_at = ?", "last_activity_at = ?"], [now, now]
        if 'subject' in changed:
            sets.append("subject = ?")
            params.append(new_subject)
        if 'description' in changed:
            sets.append("description = ?")
            params.append(_tiers.seal('support_tickets', 'description', new_description, tier))
        conn.execute(f"UPDATE support_tickets SET {', '.join(sets)} WHERE ticket_id = ?",  # nosec B608 - fixed column names
                     params + [tid])
        what = " and ".join(changed)
        _add_auto_note(conn, tid, f"Ticket {what} edited by {me.username}"
                       + (f": {reason}" if reason else "."), internal=True, who=me)
        log_audit('edit_ticket', resource_id=tid, actor=user, conn=conn,
                  old_values={'subject': current.get('subject'),
                              'description_length': len(current.get('description') or '')},
                  new_values={'subject': new_subject if 'subject' in changed else current.get('subject'),
                              'description_length': len(new_description or current.get('description') or ''),
                              'reason': reason or None, 'crisis': crisis})
    if crisis:
        support['safeguarding_reference'] = safety.raise_concern(
            tid, f"{new_subject or current.get('subject')}\n\n{new_description}",
            where='edited ticket', actor_username=user['username'])
    return {'changed': changed, 'crisis': support}


def set_team(actor, ticket_id, team, reason) -> dict:
    """Move a ticket to another team with a reason.

    The confidentiality tier never drops (moving into a restricted team raises
    it); the assignee stays only if they may work the ticket in its new team;
    the SLA due time is recalculated for the new team. Returns
    ``{'old', 'new', 'tier', 'unassigned'}``.
    """
    user = _auth.require_auth(actor)
    reason = str(reason or '').strip()
    if len(reason) < 5:
        raise ValueError("Give a reason for moving the ticket")
    routing = _optional('routing')
    new = routing.team_key(team) if routing is not None else (str(team or '').strip() or None)
    if not new:
        raise ValueError(f"Unknown team '{team}'")
    with store.writing() as conn:
        ticket = _staff_ticket(conn, user, ticket_id, "move tickets between teams")
        tid = ticket['ticket_id']
        me = _auth.current_requester(user, conn)
        old = ticket['team']
        if (old or None) == new:
            return {'old': old, 'new': new, 'tier': _tiers.tier_of(ticket), 'unassigned': False}
        old_tier = _tiers.tier_of(ticket)
        team_tier = _tiers.classify(ticket['category'], ticket['subcategory'], new)
        tier = max(old_tier, team_tier, key=lambda t: _TIER_RANK.get(t, 0))
        draft = dict(ticket)
        draft.update({'team': new, 'confidentiality': tier})
        assignee = _assignee_ref(ticket)
        unassigned = bool(assignee) and not _assignable(conn, assignee, draft)
        now = _now()
        conn.execute("UPDATE support_tickets SET team = ?, confidentiality = ?, updated_at = ?, "
                     "last_activity_at = ?" + (", assigned_to = NULL" if unassigned else "")
                     + " WHERE ticket_id = ?", (new, tier, now, now, tid))
        if tier != old_tier:
            _tiers.reseal(conn, tid, tier)
        sla = _optional('sla')
        if sla is not None:
            sla.set_due(conn, tid)
        label = routing.team_label if routing is not None else str
        note = f"Moved from {label(old) if old else 'no team'} to {label(new)}: {reason}"
        if unassigned:
            note += f" ({assignee} is not in the new team, so the ticket is unassigned)"
        _add_auto_note(conn, tid, note, internal=True, who=me)
        log_audit('set_team', resource_id=tid, actor=user, conn=conn,
                  old_values={'team': old, 'confidentiality': old_tier, 'assigned_to': assignee},
                  new_values={'team': new, 'confidentiality': tier,
                              'assigned_to': None if unassigned else assignee, 'reason': reason})
    return {'old': old, 'new': new, 'tier': tier, 'unassigned': unassigned}


def escalate(actor, ticket_id, reason) -> dict:
    """Escalate a ticket (status escalated, level + 1) with a reason; the
    assignee is told."""
    user = _auth.require_auth(actor)
    reason = _clean_text(reason, "A reason", 1000)
    with store.writing() as conn:
        ticket = _staff_ticket(conn, user, ticket_id, "escalate tickets")
        me = _auth.current_requester(user, conn)
        result, notices = _change_status(conn, user, me, ticket, 'escalated')
        if not result['changed']:
            # Already escalated: raise the level again.
            conn.execute("UPDATE support_tickets SET escalation_level = "
                         "COALESCE(escalation_level, 0) + 1, escalated_at = ? WHERE ticket_id = ?",
                         (_now(), ticket['ticket_id']))
        _add_auto_note(conn, ticket['ticket_id'], f"Escalated: {reason}", internal=True, who=me)
        log_audit('escalate', resource_id=ticket['ticket_id'], actor=user, conn=conn,
                  details={'reason': reason})
        if ticket['assigned_to'] and str(ticket['assigned_to']) != me.username:
            notices += notify.escalation_alert(ticket['ticket_id'], ticket['subject'],
                                               str(ticket['assigned_to']), reason)
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    _after_commit(notices)
    return result


def _same_requester(a, b) -> bool:
    if a['requester_username'] and b['requester_username']:
        return a['requester_username'] == b['requester_username']
    return bool(a['student_id']) and a['student_id'] == b['student_id']


def _copy_replies(conn, from_id, to_id, tier) -> None:
    """Copy ``from_id``'s replies to ``to_id`` (marked as merged, sealed for
    ``tier``; each keeps its own internal / public flag)."""
    for r in conn.execute("SELECT * FROM ticket_responses WHERE ticket_id = ? "
                          "ORDER BY response_id", (from_id,)).fetchall():
        text = f"[Merged from ticket #{from_id}] {_tiers.reveal(r['response_text'])}"
        conn.execute('''
        INSERT INTO ticket_responses (ticket_id, responder_id, responder_username,
            responder_role, response_text, response_datetime, is_internal,
            is_auto_generated, template_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            to_id, r['responder_id'], r['responder_username'], r['responder_role'],
            _tiers.seal('ticket_responses', 'response_text', text, tier), r['response_datetime'],
            r['is_internal'] or 0, r['is_auto_generated'] or 0, r['template_used']))


def merge(actor, primary_id, secondary_ids, reason) -> int:
    """Merge duplicates into ``primary_id``; returns how many were merged.

    Only tickets raised by the same person can be merged (a merge copies the
    replies across, and another person's thread must not become visible).
    Copied replies keep their own internal / public flag.
    """
    user = _auth.require_auth(actor)
    reason = _clean_text(reason, "A reason for the merge", 1000)
    ids = []
    for value in secondary_ids or []:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            raise ValueError(f"'{value}' is not a ticket number")
    notices = []
    with store.writing() as conn:
        primary = _staff_ticket(conn, user, primary_id, "merge tickets")
        pid = primary['ticket_id']
        ids = [i for i in dict.fromkeys(ids) if i != pid]
        if not ids:
            raise ValueError("Choose at least one other ticket to merge")
        me = _auth.current_requester(user, conn)
        seconds = [_ticket_row(conn, i) for i in ids]
        for s in seconds:
            if not _same_requester(primary, s):
                raise ValueError(f"Ticket #{s['ticket_id']} was raised by someone else and "
                                 f"cannot be merged into #{pid}")
            if not _auth.can_work_ticket(user, s, conn):
                raise PermissionError(f"You are not working ticket #{s['ticket_id']}")
        # The merged ticket keeps the most confidential tier of them all.
        tier = max([_tiers.tier_of(primary)] + [_tiers.tier_of(s) for s in seconds],
                   key=_tiers.rank)
        if tier != _tiers.tier_of(primary):
            conn.execute("UPDATE support_tickets SET confidentiality = ? WHERE ticket_id = ?",
                         (tier, pid))
            _tiers.reseal(conn, pid, tier)
        now = _now()
        for s in seconds:
            sid = s['ticket_id']
            _copy_replies(conn, sid, pid, tier)
            conn.execute("UPDATE ticket_attachments SET ticket_id = ? WHERE ticket_id = ?", (pid, sid))
            conn.execute("UPDATE support_tickets SET parent_ticket_id = ?, status = 'closed', "
                         "closed_at = ?, updated_at = ? WHERE ticket_id = ?", (pid, now, now, sid))
            _add_auto_note(conn, sid, f"Merged into ticket #{pid}.", who=me)
        merged = ", ".join(f"#{s['ticket_id']}" for s in seconds)
        _add_auto_note(conn, pid, f"Tickets {merged} were merged into this ticket.", who=me)
        _add_auto_note(conn, pid, f"Merge reason: {reason}", internal=True, who=me)
        conn.execute("UPDATE support_tickets SET updated_at = ?, last_activity_at = ? "
                     "WHERE ticket_id = ?", (now, now, pid))
        log_audit('merge', resource_id=pid, actor=user, conn=conn,
                  details={'merged': [s['ticket_id'] for s in seconds], 'reason': reason})
        notices = [notify.Notice(_requester_ref(primary),
                                 f"Support tickets merged into #{pid}",
                                 f"Your tickets {merged} have been merged into ticket #{pid}; "
                                 "please follow up there.", 'merge', pid)]
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    _after_commit(notices)
    return len(seconds)


def add_attachment(actor, ticket_id, filename, data, *, public=True, mime_type=None) -> int:
    """Attach a file; returns its id. Only support staff may make it private."""
    user = _auth.require_auth(actor)
    if not public and not _auth.is_support_staff(user):
        raise PermissionError("Only support staff can add private attachments")
    prepared = _files.prepare_attachments([{'filename': filename, 'data': data,
                                            'mime_type': mime_type}])
    with store.writing() as conn:
        ticket = _visible_ticket(conn, user, ticket_id)
        me = _auth.current_requester(user, conn)
        _files.insert_attachment_rows(conn, ticket['ticket_id'], prepared, me.username,
                                      public=public)
        conn.execute("UPDATE support_tickets SET updated_at = ?, last_activity_at = ? "
                     "WHERE ticket_id = ?", (_now(), _now(), ticket['ticket_id']))
        log_audit('add_attachment', resource_id=ticket['ticket_id'], actor=user, conn=conn,
                  details={'file': prepared[0]['original_filename'], 'public': bool(public)})
    failed = _files.write_attachment_files(prepared)
    if failed:
        raise OSError(f"'{prepared[0]['original_filename']}' could not be saved; please try again")
    return prepared[0]['attachment_id']


def rate_ticket(actor, ticket_id, rating, feedback=None) -> bool:
    """The requester rates a resolved or closed ticket (1-5)."""
    user = _auth.require_auth(actor)
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise ValueError("Rating must be a number from 1 to 5")
    if not 1 <= rating <= 5:
        raise ValueError("Rating must be between 1 and 5")
    with store.writing() as conn:
        ticket = _visible_ticket(conn, user, ticket_id)
        me = _auth.current_requester(user, conn)
        if not _auth.owns_ticket(me, ticket) and not _auth.is_admin(user):
            raise PermissionError("Only the person who raised the ticket can rate it")
        if schema.normalize_status(ticket['status'], default='open') not in schema.DONE_STATUSES:
            raise ValueError("A ticket can be rated once it has been resolved")
        conn.execute("UPDATE support_tickets SET satisfaction_rating = ?, satisfaction_feedback = ? "
                     "WHERE ticket_id = ?", (rating, feedback, ticket['ticket_id']))
        _metric(conn, 'satisfaction_rating', rating, 'satisfaction',
                {'ticket_id': ticket['ticket_id'], 'username': me.username, 'feedback': feedback})
        log_audit('rate_ticket', resource_id=ticket['ticket_id'], actor=user, conn=conn,
                  details={'rating': rating})
    return True


def bulk_update(actor, ticket_ids, updates: dict) -> int:
    """Apply ``updates`` (status / priority / assigned_to / category) to many
    tickets; status and assignment go through :func:`set_status` / :func:`assign`."""
    if not _auth.is_support_staff(actor):
        raise PermissionError("Only support staff can perform bulk updates")
    updates = dict(updates or {})
    simple = {k: updates[k] for k in ('priority', 'category') if k in updates}
    count = 0
    for tid in ticket_ids or []:
        try:
            if 'status' in updates:
                set_status(actor, tid, updates['status'])
            if 'assigned_to' in updates:
                assign(actor, tid, updates['assigned_to'])
            if simple:
                with store.writing() as conn:
                    ticket = _staff_ticket(conn, actor, tid)
                    # Keys come from the fixed tuple above.
                    conn.execute("UPDATE support_tickets SET "  # nosec B608
                                 + ", ".join(f"{k} = ?" for k in simple)
                                 + ", updated_at = ? WHERE ticket_id = ?",
                                 list(simple.values()) + [_now(), ticket['ticket_id']])
                    _add_auto_note(conn, ticket['ticket_id'], "Bulk update: " + ", ".join(
                        f"{k}={v}" for k, v in simple.items()), internal=True,
                        who=_auth.current_requester(actor, conn))
                    log_audit('bulk_update', resource_id=ticket['ticket_id'], actor=actor,
                              conn=conn, new_values=simple)
            count += 1
        except ValueError as exc:
            logger.warning("Bulk update skipped ticket %s: %s", tid, exc)
    return count


__all__ = [
    'submit_ticket', 'post_response', 'SEALED_PLACEHOLDER',
    'create_ticket', 'get_ticket', 'list_my_tickets', 'list_tickets',
    'list_tickets_for_requester', 'list_attachments', 'get_attachment', 'ticket_history',
    'add_response', 'set_status', 'assign', 'escalate', 'merge', 'add_attachment',
    'rate_ticket', 'bulk_update',
]
