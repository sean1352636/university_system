"""Confidentiality tiers of a support ticket: who may see it, the record of
every look, break-glass access, and sealing the text at rest.

Three tiers (``support_tickets.confidentiality``):

* **standard** — the requester, support staff of the ticket's team (any
  support staff for an unrouted or ``general`` ticket, and support staff who
  belong to no team yet) and administrators;
* **restricted** — mental health, disability / accessibility, health and
  hardship detail (:func:`classify`): the requester, members of the ticket's
  team, the health team (:func:`health_roles`) when the ticket is about health
  or wellbeing, and administrators;
* **safeguarding** — raised by crisis language (``safety``) or set by staff:
  the requester, the safeguarding leads (:func:`lead_roles`) and
  administrators.

Team membership comes from ``routing.team_members`` / ``routing.user_teams``.
Until routing is installed, every support role counts as a member of every
team (the visibility the module had before tiers).

For restricted and safeguarding tickets:

* the description, resolution and replies are sealed at rest (the health
  portal's ``sealed_fields``, registered there under ``TIERED``) and revealed
  only after the access check;
* every look by anyone but the requester is written to the immutable audit
  log before anything is shown — if it cannot be written the look is refused
  (:func:`record_view`, as the health portal's ``access.record_view``);
* someone who works tickets but is outside the tier may open one ticket for
  an hour with **break-glass** access, giving a reason; it is logged, noted
  on the ticket and e-mailed to the administrators (:func:`break_glass`).

Staff move a ticket between tiers with a reason (:func:`set_tier`); lowering
a safeguarding ticket is for the safeguarding leads and administrators.
"""

from __future__ import annotations

import datetime
import logging
from functools import lru_cache
from typing import Any, Iterable, Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    schema,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

logger = logging.getLogger(__name__)

STANDARD, RESTRICTED, SAFEGUARDING = schema.CONFIDENTIALITY
TIERS = schema.CONFIDENTIALITY
SEALED_TIERS = (RESTRICTED, SAFEGUARDING)
TIER_LABELS = {STANDARD: 'Standard', RESTRICTED: 'Restricted', SAFEGUARDING: 'Safeguarding'}

#: Words in a category / subcategory that make a ticket restricted.
RESTRICTED_TERMS = ('mental health', 'wellbeing', 'well-being', 'counselling', 'counseling',
                    'health', 'medical', 'disability', 'disabled', 'accessibility',
                    'reasonable adjustment', 'neurodiver', 'dyslexi', 'autis', 'adhd',
                    'hardship')
#: Teams whose tickets are restricted whatever their category.
RESTRICTED_TEAMS = ('wellbeing', 'disability')
#: A restricted ticket the health team also sees: in one of these teams, or
#: with one of these words in its category / subcategory.
HEALTH_TEAMS = ('wellbeing',)
HEALTH_TERMS = ('mental health', 'wellbeing', 'well-being', 'health', 'medical',
                'counselling', 'counseling')
BREAK_GLASS_MINUTES = 60
_GRANTS: dict = {}          # (username, ticket_id) -> expiry (this process)

#: Bases on which someone other than the requester sees a ticket.
WORKER_BASES = ('admin', 'team', 'support', 'health_team', 'safeguarding_lead', 'break_glass')


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _get(ticket, key):
    try:
        return ticket[key]
    except (KeyError, IndexError, TypeError):
        return None


def _has_term(text, terms: Iterable[str]) -> bool:
    folded = str(text or '').lower()
    return any(term in folded for term in terms)


# ── tiers ────────────────────────────────────────────────────────────────


def normalize_tier(value, default=STANDARD) -> str:
    text = str(value or '').strip().lower()
    if not text:
        return default
    if text not in TIERS:
        raise ValueError(f"Unknown confidentiality '{value}'. Choose from: {', '.join(TIERS)}")
    return text


def tier_of(ticket) -> str:
    """The stored tier of ``ticket`` (rows from before tiers are standard)."""
    return normalize_tier(_get(ticket, 'confidentiality'))


def is_sealed_tier(tier) -> bool:
    return str(tier or '').lower() in SEALED_TIERS


def rank(tier) -> int:
    return TIERS.index(normalize_tier(tier))


def classify(category, subcategory=None, team=None, *, crisis=False, requested=None) -> str:
    """The tier a new ticket starts in.

    Crisis language makes it safeguarding; a restricted subject (mental
    health, disability, health, hardship) or team makes it restricted. A
    ``requested`` tier can only raise the result, never lower it.
    """
    tier = STANDARD
    if crisis:
        tier = SAFEGUARDING
    elif (_has_term(category, RESTRICTED_TERMS) or _has_term(subcategory, RESTRICTED_TERMS)
          or str(team or '').lower() in RESTRICTED_TEAMS):
        tier = RESTRICTED
    if requested:
        wanted = normalize_tier(requested)
        if rank(wanted) > rank(tier):
            tier = wanted
    return tier


def is_health_ticket(ticket) -> bool:
    return (str(_get(ticket, 'team') or '').lower() in HEALTH_TEAMS
            or _has_term(_get(ticket, 'category'), HEALTH_TERMS)
            or _has_term(_get(ticket, 'subcategory'), HEALTH_TERMS))


# ── who belongs where ────────────────────────────────────────────────────


def _routing():
    try:
        from education_system.systems.university.domains.student_support.domain.student_support import (
            routing,
        )
    except ImportError:
        return None
    return routing


def user_teams(username) -> Optional[set]:
    """The teams ``username`` works in, or None while routing is not installed."""
    routing = _routing()
    fn = getattr(routing, 'user_teams', None) if routing else None
    if fn is None:
        return None
    return {str(t) for t in (fn(username) or ())}


def team_members(team) -> Optional[set]:
    """The usernames working in ``team``, or None while routing is not installed."""
    routing = _routing()
    fn = getattr(routing, 'team_members', None) if routing else None
    if fn is None:
        return None
    return {str(u) for u in (fn(team) or ())}


@lru_cache(maxsize=1)
def lead_roles() -> frozenset:
    """The safeguarding leads' roles (from the safeguarding permissions)."""
    from education_system.systems.university.services.bus import support_referrals_bus
    return frozenset(r.lower() for r in support_referrals_bus.safeguarding_lead_roles())


@lru_cache(maxsize=1)
def health_roles() -> frozenset:
    """The health team: clinicians and the wellbeing practitioners."""
    from education_system.systems.university.domains.health.application.health import access
    return frozenset(access.CLINICAL_ROLES) | frozenset(access.AREA_ROLES['wellbeing'])


def _role(user) -> str:
    return str((user or {}).get('role') or '').lower()


def is_case_worker(actor: Any = None) -> bool:
    """Does ``actor`` work tickets at all (support staff, admins, the health
    team, safeguarding leads, or anyone routing puts in a team)?"""
    user = _auth.user_of(actor)
    if not user or not user.get('username'):
        return False
    role = _role(user)
    if (role in _auth.SUPPORT_ROLES or role in _auth.ADMIN_ROLES or role in health_roles()
            or role in lead_roles()):
        return True
    return bool(user_teams(user['username']))


# ── access ───────────────────────────────────────────────────────────────


def _granted(username, ticket_id) -> bool:
    expiry = _GRANTS.get((str(username), int(ticket_id or 0)))
    return bool(expiry and expiry > datetime.datetime.now())


def _granted_ids(username) -> list:
    now = datetime.datetime.now()
    return sorted(tid for (who, tid), expiry in _GRANTS.items()
                  if who == str(username) and expiry > now)


def _team_basis(user, ticket, tier) -> Optional[str]:
    role = _role(user)
    team = str(_get(ticket, 'team') or '')
    teams = user_teams(user['username'])
    if teams is None:
        # Routing not installed: every support role is in every team.
        return 'support' if role in _auth.SUPPORT_ROLES else None
    if team and team in teams:
        return 'team'
    if tier == STANDARD and role in _auth.SUPPORT_ROLES and (
            not teams or team in ('', 'general')):
        return 'support'
    return None


def access_basis(actor, ticket, conn=None) -> Optional[str]:
    """Why ``actor`` may see ``ticket`` — 'owner', 'admin', 'team', 'support',
    'health_team', 'safeguarding_lead', 'break_glass' — or None."""
    user = _auth.user_of(actor)
    if not user or not user.get('username') or ticket is None:
        return None
    if _auth.owns_ticket(_auth.current_requester(user, conn), ticket):
        return 'owner'
    role = _role(user)
    if role in _auth.ADMIN_ROLES:
        return 'admin'
    tier = tier_of(ticket)
    basis = None
    if tier == SAFEGUARDING:
        basis = 'safeguarding_lead' if role in lead_roles() else None
    else:
        basis = _team_basis(user, ticket, tier)
        if basis is None and tier == RESTRICTED and role in health_roles() \
                and is_health_ticket(ticket):
            basis = 'health_team'
    if basis is None and _granted(user['username'], _get(ticket, 'ticket_id')):
        basis = 'break_glass'
    return basis


def can_view(actor, ticket, conn=None) -> bool:
    """May ``actor`` see ``ticket``? (The one gate: ``auth.can_view_ticket``.)"""
    return access_basis(actor, ticket, conn) is not None


def can_work(actor, ticket, conn=None) -> bool:
    """May ``actor`` work ``ticket`` as staff (not merely as its requester)?"""
    return access_basis(actor, ticket, conn) in WORKER_BASES


def _tier_sql(p: str) -> str:
    return f"COALESCE({p}confidentiality, 'standard')"


def _health_sql(p: str) -> tuple[str, list]:
    likes, params = [], []
    for term in HEALTH_TERMS:
        likes.append(f"lower(COALESCE({p}category, '')) LIKE ? "
                     f"OR lower(COALESCE({p}subcategory, '')) LIKE ?")
        params += [f"%{term}%", f"%{term}%"]
    teams = ", ".join('?' * len(HEALTH_TEAMS))
    return f"({p}team IN ({teams}) OR " + " OR ".join(likes) + ")", list(HEALTH_TEAMS) + params


def _team_scope(user, p) -> tuple[list, list]:
    role, tier = _role(user), _tier_sql(p)
    teams = user_teams(user['username'])
    clauses, params = [], []
    if teams is None:
        if role in _auth.SUPPORT_ROLES:
            clauses.append(f"{tier} IN ('standard', 'restricted')")
        return clauses, params
    if teams:
        marks = ", ".join('?' * len(teams))
        clauses.append(f"({tier} IN ('standard', 'restricted') AND {p}team IN ({marks}))")
        params += sorted(teams)
    if role in _auth.SUPPORT_ROLES:
        clauses.append(f"{tier} = 'standard'" if not teams else
                       f"({tier} = 'standard' AND COALESCE({p}team, '') IN ('', 'general'))")
    return clauses, params


def scope_sql(actor: Any = None, alias: str = '', conn=None) -> tuple[str, list]:
    """``(where_sql, params)``: the tickets ``actor`` may see (any tier)."""
    user = _auth.require_auth(actor)
    p = f"{alias}." if alias else ''
    role = _role(user)
    if role in _auth.ADMIN_ROLES:
        return "1=1", []
    who = _auth.current_requester(user, conn)
    if who.student_id:
        clauses = [f"({p}requester_username = ? OR ({p}requester_username IS NULL AND "
                   f"({p}student_id = ? OR {p}user_id = ?)))"]
        params: list = [who.username, who.student_id, who.student_id]
    else:
        clauses, params = [f"{p}requester_username = ?"], [who.username]
    more, extra = _team_scope(user, p)
    clauses += more
    params += extra
    if role in health_roles():
        health, hparams = _health_sql(p)
        clauses.append(f"({_tier_sql(p)} = 'restricted' AND {health})")
        params += hparams
    if role in lead_roles():
        clauses.append(f"{_tier_sql(p)} = 'safeguarding'")
    granted = _granted_ids(user['username'])
    if granted:
        clauses.append(f"{p}ticket_id IN ({', '.join('?' * len(granted))})")
        params += granted
    return "(" + " OR ".join(clauses) + ")", params


# ── the record of every look ─────────────────────────────────────────────


def record_view(actor, ticket, *, purpose='view', reason=None, conn=None,
                basis=None) -> None:
    """Write a look at a restricted / safeguarding ticket by anyone but its
    requester to the immutable audit log, or raise ``PermissionError`` (fail
    closed). Standard tickets and the requester's own looks are not logged.

    ``conn`` joins the caller's write transaction; leave it out on a read.
    """
    tier = tier_of(ticket)
    if not is_sealed_tier(tier):
        return
    user = _auth.user_of(actor) or {}
    basis = basis or access_basis(user, ticket, conn)
    if basis == 'owner':
        return
    from education_system.systems.university.infrastructure.security.immutable_audit_log import (
        AuditAction,
        log_security_event,
    )
    try:
        log_security_event(
            user_id=str(user.get('username') or 'unknown'), action=AuditAction.DATA_VIEW,
            resource_type=f"support_ticket_{tier}", resource_id=str(_get(ticket, 'ticket_id')),
            details={'student_id': _get(ticket, 'student_id'), 'role': _role(user),
                     'basis': basis, 'purpose': purpose, 'reason': reason}, conn=conn)
    except Exception as exc:
        raise PermissionError(f"The access could not be recorded, so it was refused ({exc})") \
            from None


# ── sealing ──────────────────────────────────────────────────────────────


def _sealed_fields():
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields


def seal(table: str, column: str, value, tier):
    """``value`` as stored in ``table.column`` of a ticket in ``tier``."""
    return _sealed_fields().seal_value(table, column, value,
                                       confidential=is_sealed_tier(tier))


def reveal(value):
    """Readable text of a stored value (plain text passes through)."""
    return _sealed_fields().reveal(value)


def reveal_row(row) -> dict:
    """A dict copy of ``row`` with every sealed value revealed — call only
    after the access check (and :func:`record_view`)."""
    return _sealed_fields().unseal_row(row)


def tier_for_ticket(conn, ticket_id) -> str:
    row = conn.execute("SELECT confidentiality FROM support_tickets WHERE ticket_id = ?",
                       (ticket_id,)).fetchone()
    return normalize_tier(row[0] if row else None)


_TEXT_COLUMNS = (
    ('support_tickets', 'ticket_id', ('description', 'resolution')),
    ('ticket_responses', 'ticket_id', ('response_text',)),
    ('ticket_replies', 'ticket_id', ('message',)),
)


def reseal(conn, ticket_id, tier) -> int:
    """Seal (sealed tier) or unseal (standard) every stored text of a ticket
    on ``conn``; returns how many values changed."""
    sealed = is_sealed_tier(tier)
    changed = 0
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for table, key, columns in _TEXT_COLUMNS:
        if table not in tables:
            continue
        have = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        for column in (c for c in columns if c in have):
            # Table and column names come from _TEXT_COLUMNS above.
            for rowid, value in conn.execute(
                    f'SELECT rowid, "{column}" FROM "{table}" WHERE "{key}" = ? '  # nosec B608
                    f'AND "{column}" IS NOT NULL AND "{column}" <> \'\'', (ticket_id,)).fetchall():
                new = seal(table, column, value, tier) if sealed else reveal(value)
                if new != value:
                    conn.execute(f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?',  # nosec B608
                                 (new, rowid))
                    changed += 1
    return changed


# ── changing a ticket's tier ─────────────────────────────────────────────


def set_tier(actor, ticket_id, tier, reason) -> dict:
    """Move a ticket to ``tier`` with a reason; returns ``{'old', 'new'}``.

    Anyone who works the ticket may raise its tier or lower it from
    restricted; lowering a safeguarding ticket is for the safeguarding leads
    and administrators. The change is audited, noted on the ticket, and the
    ticket's text is sealed or unsealed to match.
    """
    user = _auth.require_auth(actor)
    new = normalize_tier(tier)
    reason = str(reason or '').strip()
    if len(reason) < 10:
        raise ValueError("Give a reason for changing the confidentiality (a sentence)")
    with store.writing() as conn:
        row = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                           (int(ticket_id),)).fetchone()
        if row is None:
            raise ValueError(f"Ticket #{ticket_id} was not found")
        basis = access_basis(user, row, conn)
        if basis not in WORKER_BASES:
            raise PermissionError("Only staff working this ticket can change its confidentiality")
        old = tier_of(row)
        if old == new:
            return {'old': old, 'new': new}
        if old == SAFEGUARDING and _role(user) not in _auth.ADMIN_ROLES \
                and _role(user) not in lead_roles():
            raise PermissionError("Only a safeguarding lead or an administrator can lower a "
                                  "safeguarding ticket")
        record_view(user, row, purpose='change_tier', reason=reason, conn=conn, basis=basis)
        conn.execute("UPDATE support_tickets SET confidentiality = ?, updated_at = ? "
                     "WHERE ticket_id = ?", (new, _now(), row['ticket_id']))
        reseal(conn, row['ticket_id'], new)
        me = _auth.current_requester(user, conn)
        note = (f"Confidentiality changed from {TIER_LABELS[old]} to {TIER_LABELS[new]}: "
                f"{reason}")
        conn.execute('''
        INSERT INTO ticket_responses (ticket_id, responder_id, responder_username, responder_role,
                                      response_text, response_datetime, is_internal,
                                      is_auto_generated)
        VALUES (?, ?, ?, ?, ?, ?, 1, 1)''', (row['ticket_id'], str(me.users_id or me.username),
                                            me.username, me.role, seal(
                                                'ticket_responses', 'response_text', note, new),
                                            _now()))
        log_audit('set_confidentiality', resource_id=row['ticket_id'], actor=user, conn=conn,
                  old_values={'confidentiality': old}, new_values={'confidentiality': new},
                  details={'reason': reason})
    return {'old': old, 'new': new}


# ── break-glass ──────────────────────────────────────────────────────────


def _admin_addresses(conn, tier) -> list:
    roles = set(_auth.ADMIN_ROLES) | ({*lead_roles()} if tier == SAFEGUARDING else set())
    marks = ", ".join('?' * len(roles))
    return [r[0] for r in conn.execute(
        f"SELECT DISTINCT email FROM users WHERE lower(role) IN ({marks}) "  # nosec B608
        "AND COALESCE(email, '') <> ''", sorted(roles)).fetchall()]


def break_glass(actor, ticket_id, reason) -> dict:
    """Open one restricted / safeguarding ticket for :data:`BREAK_GLASS_MINUTES`
    without being in its tier. For people who work tickets; needs a real
    reason; logged (fail closed), noted on the ticket and e-mailed to the
    administrators (and, for a safeguarding ticket, the safeguarding leads)
    after the commit. Returns ``{'ticket_id', 'expires_at', 'notified'}``."""
    user = _auth.require_auth(actor)
    if not is_case_worker(user):
        raise PermissionError("Break-glass access is for staff who work support tickets")
    reason = str(reason or '').strip()
    if len(reason) < 15:
        raise ValueError("Explain the emergency (at least a sentence)")
    with store.writing() as conn:
        row = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                           (int(ticket_id),)).fetchone()
        if row is None:
            raise ValueError(f"Ticket #{ticket_id} was not found")
        tier = tier_of(row)
        if access_basis(user, row, conn) is not None:
            raise ValueError("You can already open this ticket")
        if not is_sealed_tier(tier):
            raise PermissionError("This ticket belongs to another team")
        record_view(user, row, purpose='break_glass', reason=reason, conn=conn,
                    basis='break_glass')
        me = _auth.current_requester(user, conn)
        note = f"Opened with break-glass access by {me.username} ({me.role}): {reason}"
        conn.execute('''
        INSERT INTO ticket_responses (ticket_id, responder_id, responder_username, responder_role,
                                      response_text, response_datetime, is_internal,
                                      is_auto_generated)
        VALUES (?, ?, ?, ?, ?, ?, 1, 1)''', (row['ticket_id'], str(me.users_id or me.username),
                                            me.username, me.role,
                                            seal('ticket_responses', 'response_text', note, tier),
                                            _now()))
        log_audit('break_glass', resource_id=row['ticket_id'], actor=user, conn=conn,
                  details={'reason': reason, 'tier': tier})
        addresses = _admin_addresses(conn, tier)
    expires = datetime.datetime.now() + datetime.timedelta(minutes=BREAK_GLASS_MINUTES)
    _GRANTS[(str(user['username']), int(row['ticket_id']))] = expires
    notified = _send_break_glass_notices(addresses, row['ticket_id'], user, tier, reason)
    return {'ticket_id': row['ticket_id'], 'expires_at': expires.strftime('%Y-%m-%d %H:%M:%S'),
            'notified': notified}


def _send_break_glass_notices(addresses, ticket_id, user, tier, reason) -> int:
    from education_system.systems.university.infrastructure.email import email_service
    sent = 0
    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    for address in addresses:
        try:
            if email_service.send_email(
                    address, f"Support ticket #{ticket_id} opened with break-glass access",
                    f"{user['username']} ({user.get('role')}) opened {TIER_LABELS[tier].lower()} "
                    f"support ticket #{ticket_id} without being in its team. Reason given: "
                    f"{reason}", kind='transactional', category='security',
                    to_ref=f"support-break-glass:{ticket_id}:{user['username']}:{stamp}"):
                sent += 1
        except Exception:
            logger.warning("Break-glass notice to %s not sent", address, exc_info=True)
    return sent


__all__ = [
    'STANDARD', 'RESTRICTED', 'SAFEGUARDING', 'TIERS', 'SEALED_TIERS', 'TIER_LABELS',
    'normalize_tier', 'tier_of', 'is_sealed_tier', 'classify', 'is_health_ticket',
    'user_teams', 'team_members', 'lead_roles', 'health_roles', 'is_case_worker',
    'access_basis', 'can_view', 'can_work', 'scope_sql', 'record_view', 'seal', 'reveal',
    'reveal_row', 'tier_for_ticket', 'reseal', 'set_tier', 'break_glass',
]
