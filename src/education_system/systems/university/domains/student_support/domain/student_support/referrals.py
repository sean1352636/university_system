"""Referring a ticket on ("Refer to…").

Staff working a ticket can hand it to the service that acts on it, pre-filled
from the ticket:

* ``early_warning`` — an Early Warning intervention
  (``early_warning/case_links.raise_intervention``; noted on the student's
  support case there);
* ``mitigating_circumstances`` — a mitigating circumstances claim
  (Assessment);
* ``hardship`` — a hardship / emergency fund application (Finance bursaries);
* ``accessibility`` — a reasonable-adjustments request to accessibility
  services (which also queues it for the health portal's approval);
* ``safeguarding`` — a CRITICAL safeguarding concern (as crisis language
  raises automatically, see ``safety``).

The other domains are reached through ``services/bus/support_referrals_bus``.

Each referral is recorded in ``support_ticket_referrals`` *before* the other
service is called (status ``pending``) and completed with that service's
reference after (``created``, or ``failed`` with the error), with an internal
note on the ticket either way — so nothing is handed on without a trace, and
no write transaction is held while another service writes.

Consent (``share_consent`` on the ticket, given by the requester — see
``consent``):

* a **safeguarding** referral never needs it, and nor does an **Early
  Warning** referral of a crisis / safeguarding-tier ticket: duty of care
  (vital interests, UK GDPR Art. 9(2)(c); Keeping Children Safe / DSL
  guidance for adults at risk);
* otherwise a **restricted** or **safeguarding** ticket can only be referred
  once its requester has granted consent;
* a **standard** ticket can be referred unless the requester declined.

Only the ticket's subject (or the staff member's own summary) goes with a
referral; the ticket's description is copied only when the referrer asks
(``include_description``).
"""

from __future__ import annotations

import datetime
import logging
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

KINDS = {
    'early_warning': 'Early Warning intervention',
    'mitigating_circumstances': 'Mitigating circumstances claim',
    'hardship': 'Hardship fund application',
    'accessibility': 'Reasonable adjustments request',
    'safeguarding': 'Safeguarding concern',
}
DUTY_OF_CARE = 'duty_of_care'

_PRIORITY = {'critical': 'critical', 'urgent': 'critical', 'high': 'high', 'medium': 'medium',
             'low': 'low'}


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── the referral record ─────────────────────────────────────────────────


def note(conn, ticket_id, text) -> None:
    """An internal system note on the ticket (sealed with the ticket's tier)."""
    tier = _tiers.tier_for_ticket(conn, ticket_id)
    conn.execute('''
    INSERT INTO ticket_responses (ticket_id, responder_id, responder_username, responder_role,
                                  response_text, response_datetime, is_internal, is_auto_generated)
    VALUES (?, 'system', NULL, 'system', ?, ?, 1, 1)''',
                 (ticket_id, _tiers.seal('ticket_responses', 'response_text', text, tier), _now()))


def start(conn, ticket_id, kind, username, basis) -> int:
    """Record a referral as pending on ``conn``; returns its id."""
    schema.ensure_care_tables(conn)
    return int(conn.execute(
        "INSERT INTO support_ticket_referrals (ticket_id, kind, status, consent_basis, "
        "created_by, created_at) VALUES (?, ?, 'pending', ?, ?, ?)",
        (ticket_id, kind, basis, username, _now())).lastrowid)


def finish(referral_id, *, target_ref=None, error=None) -> None:
    """Complete a pending referral with the other service's reference (or
    its error), noted on the ticket. Never raises."""
    try:
        with store.writing() as conn:
            row = conn.execute("SELECT * FROM support_ticket_referrals WHERE referral_id = ?",
                               (referral_id,)).fetchone()
            label = KINDS.get(row['kind'], row['kind'])
            if error is None:
                conn.execute("UPDATE support_ticket_referrals SET status = 'created', "
                             "target_ref = ?, completed_at = ? WHERE referral_id = ?",
                             (str(target_ref), _now(), referral_id))
                note(conn, row['ticket_id'], f"Referred: {label} {target_ref} created "
                     f"(by {row['created_by']}; basis: {row['consent_basis']}).")
            else:
                conn.execute("UPDATE support_ticket_referrals SET status = 'failed', error = ?, "
                             "completed_at = ? WHERE referral_id = ?",
                             (str(error)[:500], _now(), referral_id))
                note(conn, row['ticket_id'], f"Referral failed: the {label.lower()} could not "
                     f"be created ({error}). Please make it by hand.")
            log_audit('referral', resource_id=row['ticket_id'], actor={'username': row['created_by']},
                      conn=conn, details={'kind': row['kind'], 'reference': target_ref,
                                          'error': error, 'basis': row['consent_basis']})
    except Exception:
        logger.exception("Could not complete support referral %s", referral_id)


def safeguarding_reference(conn, ticket_id) -> Optional[str]:
    """The ticket's safeguarding concern reference, if one was raised."""
    if not _has_table(conn):
        return None
    row = conn.execute("SELECT target_ref FROM support_ticket_referrals WHERE ticket_id = ? "
                       "AND kind = 'safeguarding' AND status = 'created' ORDER BY referral_id "
                       "LIMIT 1", (ticket_id,)).fetchone()
    return row[0] if row else None


def _has_table(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND "
                        "name = 'support_ticket_referrals'").fetchone() is not None


# ── consent ─────────────────────────────────────────────────────────────


def consent_basis(ticket, kind) -> str:
    """The basis a referral of ``ticket`` to ``kind`` rests on, or
    ``PermissionError`` when consent is needed and not given (see module doc)."""
    crisis = bool(ticket['crisis_flag']) or _tiers.tier_of(ticket) == _tiers.SAFEGUARDING
    if kind == 'safeguarding' or (crisis and kind == 'early_warning'):
        return DUTY_OF_CARE
    consent = ticket['share_consent']
    if consent == 'declined':
        raise PermissionError("The student has declined to share this ticket, so it cannot be "
                              "referred (except to safeguarding)")
    if consent == 'granted':
        return 'consent'
    if _tiers.is_sealed_tier(_tiers.tier_of(ticket)):
        raise PermissionError("This ticket is confidential: ask the student to agree to it "
                              "being shared before referring it")
    return 'standard'


# ── pre-filling ─────────────────────────────────────────────────────────


def _student(conn, ticket) -> dict:
    sid = ticket['student_id']
    row = conn.execute("SELECT first_name, last_name, email_address FROM students "
                       "WHERE student_id = ?", (sid,)).fetchone() if sid else None
    user = conn.execute("SELECT first_name, last_name, email FROM users WHERE username = ?",
                        (ticket['requester_username'],)).fetchone()
    source = row or user
    name = " ".join(p for p in ((source[0], source[1]) if source else ()) if p)
    email = (row[2] if row else None) or (user[2] if user else None) or ''
    return {'student_id': sid, 'name': name or str(sid or ticket['requester_username']),
            'email': email}


def _text(ticket, fields) -> str:
    summary = str(fields.get('summary') or '').strip() or \
        f"Support ticket #{ticket['ticket_id']}: {ticket['subject']}"
    if fields.get('include_description'):
        summary += "\n\n" + str(_tiers.reveal(ticket['description']) or '')
    return summary


def _ew_types(ticket) -> tuple[str, str]:
    category = str(ticket['category'] or '').lower()
    if 'financ' in category or 'hardship' in category:
        return 'financial', 'manual_meeting'
    if 'academic' in category or 'registration' in category:
        return 'academic', 'tutoring'
    if _tiers.is_health_ticket(ticket):
        return 'other', 'counseling'
    return 'other', 'manual_meeting'


def _grounds(ticket) -> str:
    if _tiers.is_health_ticket(ticket):
        return 'medical'
    return 'personal'


def prefill(conn, ticket, kind, fields=None) -> dict:
    """The values a referral of ``ticket`` to ``kind`` would be made with."""
    fields = dict(fields or {})
    who = _student(conn, ticket)
    text = _text(ticket, fields)
    if kind == 'early_warning':
        trigger, itype = _ew_types(ticket)
        return {'student_id': who['student_id'],
                'trigger_type': fields.get('trigger_type') or trigger,
                'intervention_type': fields.get('intervention_type') or itype,
                'priority': fields.get('priority') or _PRIORITY.get(
                    str(ticket['priority'] or '').lower(), 'medium'),
                'description': text, 'assigned_to': fields.get('assigned_to') or ''}
    if kind == 'mitigating_circumstances':
        return {'student_id': who['student_id'], 'grounds': fields.get('grounds') or _grounds(ticket),
                'description': text, 'module_code': fields.get('module_code'),
                'assessment_ref': fields.get('assessment_ref'),
                'period_start': fields.get('period_start'), 'period_end': fields.get('period_end'),
                'impact_statement': fields.get('impact_statement'),
                'requested_remedy': fields.get('requested_remedy')}
    if kind == 'hardship':
        return {'student_id': who['student_id'], 'fund_id': fields.get('fund_id'),
                'requested_amount': fields.get('requested_amount'),
                'household_income': fields.get('household_income'), 'circumstances': text}
    if kind == 'accessibility':
        return {'student_id': who['student_id'], 'student_name': who['name'],
                'student_email': who['email'],
                'accommodation_type': fields.get('accommodation_type') or 'Other',
                'description': text}
    return {'username': ticket['requester_username'] or who['student_id'], 'description': text}


# ── calling the other service ───────────────────────────────────────────


def _bus():
    from education_system.systems.university.services.bus import support_referrals_bus
    return support_referrals_bus


def _early_warning(values, username) -> str:
    from education_system.systems.university.domains.student_support.domain.early_warning import (
        case_links,
    )
    try:
        return str(case_links.raise_intervention(
            values['student_id'], values['trigger_type'], values['intervention_type'],
            values['priority'], values['description'], values['assigned_to'], actor=username))
    except case_links.CaseLinkError as exc:
        raise ValueError(str(exc)) from None


def _mitigating(values, username) -> str:
    return str(_bus().submit_mitigating_claim(values.pop('student_id'), submitted_by=username,
                                              **values))


def _hardship(values, username) -> str:
    fund_id = values['fund_id']
    if not fund_id:
        funds = _bus().hardship_funds()
        if len(funds) != 1:
            raise ValueError("Choose the hardship fund to apply to" if funds else
                             "There is no open hardship fund to apply to")
        fund_id = funds[0]['fund_id']
    try:
        amount = float(values['requested_amount'])
    except (TypeError, ValueError):
        raise ValueError("Say how much the student is asking for") from None
    income = values['household_income']
    return str(_bus().submit_hardship_application(
        values['student_id'], fund_id, amount, circumstances=values['circumstances'],
        household_income=float(income) if income not in (None, '') else None))


def _accessibility(values, username) -> str:
    if values['accommodation_type'] not in _bus().accommodation_types():
        raise ValueError("Choose one of: " + ", ".join(_bus().accommodation_types()))
    return str(_bus().submit_accommodation_request(
        values['student_id'], student_name=values['student_name'],
        student_email=values['student_email'],
        accommodation_type=values['accommodation_type'], description=values['description']))


_TARGETS = {'early_warning': _early_warning, 'mitigating_circumstances': _mitigating,
            'hardship': _hardship, 'accessibility': _accessibility}


# ── the use cases ───────────────────────────────────────────────────────


def _workable(conn, user, ticket_id):
    row = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                       (int(ticket_id),)).fetchone()
    if row is None:
        raise ValueError(f"Ticket #{ticket_id} was not found")
    if not _auth.can_work_ticket(user, row, conn):
        raise PermissionError("Only staff working this ticket can refer it")
    return row


def options(actor, ticket_id) -> dict:
    """What the "Refer to…" screen needs: per kind the pre-filled values and
    whether consent allows it (``{'kinds': {kind: {'label', 'allowed',
    'basis', 'blocked_reason', 'values'}}, 'share_consent', 'referrals'}``),
    plus the choices (hardship funds, MC grounds, adjustment types)."""
    user = _auth.require_auth(actor)
    with store.reading() as conn:
        row = _workable(conn, user, ticket_id)
        kinds = {}
        for kind, label in KINDS.items():
            entry = {'label': label, 'allowed': True, 'basis': None, 'blocked_reason': None}
            try:
                entry['basis'] = consent_basis(row, kind)
            except PermissionError as exc:
                entry.update(allowed=False, blocked_reason=str(exc))
            entry['values'] = prefill(conn, row, kind)
            kinds[kind] = entry
        existing = list_for_ticket_on(conn, row['ticket_id'])
    bus = _bus()
    return {'ticket_id': row['ticket_id'], 'share_consent': row['share_consent'],
            'kinds': kinds, 'referrals': existing,
            'choices': {'hardship_funds': bus.hardship_funds(),
                        'mitigating_grounds': bus.mitigating_grounds(),
                        'accommodation_types': bus.accommodation_types()}}


def refer(actor, ticket_id, kind, **fields) -> dict:
    """Refer a ticket to ``kind`` (see :data:`KINDS`), pre-filled from the
    ticket; ``fields`` override or complete the pre-filled values. Returns
    ``{'referral_id', 'kind', 'reference', 'ticket_id'}``."""
    user = _auth.require_auth(actor)
    if kind not in KINDS:
        raise ValueError(f"Unknown referral '{kind}'. Choose from: {', '.join(KINDS)}")
    with store.writing() as conn:
        schema.ensure_care_tables(conn)
        row = _workable(conn, user, ticket_id)
        basis = consent_basis(row, kind)
        values = prefill(conn, row, kind, fields)
        if kind != 'safeguarding' and not values.get('student_id'):
            raise ValueError("This ticket was not raised by a student, so it cannot be referred "
                             f"for a {KINDS[kind].lower()}")
        if kind == 'safeguarding' and safeguarding_reference(conn, row['ticket_id']):
            raise ValueError("A safeguarding concern has already been raised for this ticket")
        _tiers.record_view(user, row, purpose=f'refer:{kind}', conn=conn)
        referral_id = start(conn, row['ticket_id'], kind, user['username'], basis)
    if kind == 'safeguarding':
        return _refer_safeguarding(row, values, user, referral_id)
    try:
        reference = _TARGETS[kind](values, user['username'])
    except Exception as exc:
        finish(referral_id, error=str(exc))
        raise ValueError(f"The {KINDS[kind].lower()} could not be created: {exc}") from None
    finish(referral_id, target_ref=reference)
    return {'referral_id': referral_id, 'kind': kind, 'reference': reference,
            'ticket_id': row['ticket_id']}


def _refer_safeguarding(row, values, user, referral_id) -> dict:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        safety,
    )
    with store.reading() as conn:
        subject = safety._subject(conn, row)
    content = (f"Referred by {user['username']} from Student Support ticket "
               f"#{row['ticket_id']}.\n\n{values['description']}")
    try:
        reference = str(_bus().raise_safeguarding_concern(
            subject, content, snippet=values['description'], reporter_username=user['username']))
    except Exception as exc:
        finish(referral_id, error=str(exc))
        raise ValueError(f"The safeguarding concern could not be raised: {exc}") from None
    finish(referral_id, target_ref=reference)
    return {'referral_id': referral_id, 'kind': 'safeguarding', 'reference': reference,
            'ticket_id': row['ticket_id']}


def list_for_ticket_on(conn, ticket_id) -> list:
    if not _has_table(conn):
        return []
    return [dict(r) for r in conn.execute(
        "SELECT referral_id, kind, target_ref, status, consent_basis, error, created_by, "
        "created_at, completed_at FROM support_ticket_referrals WHERE ticket_id = ? "
        "ORDER BY referral_id", (ticket_id,)).fetchall()]


def list_for_ticket(actor, ticket_id) -> list:
    """The ticket's referrals (staff working the ticket)."""
    user = _auth.require_auth(actor)
    with store.reading() as conn:
        row = _workable(conn, user, ticket_id)
        return list_for_ticket_on(conn, row['ticket_id'])


__all__ = ['KINDS', 'DUTY_OF_CARE', 'consent_basis', 'prefill', 'options', 'refer',
           'list_for_ticket', 'safeguarding_reference', 'start', 'finish', 'note']
