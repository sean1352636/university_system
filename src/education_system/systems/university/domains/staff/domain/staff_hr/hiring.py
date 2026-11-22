"""From offer to first day: pre-employment checks, references, offers and
turning an accepted offer into a member of staff.

Recruiters and HR only (``access.can(actor, 'recruitment')`` or
``access.is_hr``); every change is written to the Staff HR audit trail.

**Checks.** ``staff_hr_check_requirements`` says which checks a job type
needs (``'*'`` = every job; with nothing set, :data:`DEFAULT_REQUIREMENTS`).
Clearing a job type's list falls back to ``'*'``, then to the defaults, so a
job never requires nothing. A check is ``pending`` / ``in_progress`` / ``cleared`` / ``failed`` /
``waived``; ``references`` is met by :data:`REFERENCES_REQUIRED`
satisfactory references with none judged unsatisfactory. A start date can
only be confirmed — and an unconditional offer only made — once every
required check has cleared.

**Offers.** One live offer (``made`` or ``accepted``) per application.
Confirming the start date makes a conditional offer unconditional.

**Hire** (:func:`hire`, on an accepted offer with every check cleared):

1. a ``staff`` register entry and a login through the university's staff
   provisioning service (``services/staff_provisioning``), with the
   password set-up e-mail — unless the applicant already has an account
   (matched on e-mail);
2. a ``staff_profiles`` row with the line manager (``manager_id``);
3. a ``staff_contracts`` row from the start date (``ContractManager``),
   with grade and FTE where the pay structure columns exist;
4. the onboarding template (``OnboardingManager.assign_template``);
5. the application marked hired and the checks moved onto the person, so
   right-to-work follow-ups and DBS re-checks reach them
   (``reminders``).

Every step is idempotent: a hire that stopped part-way can be run again.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.infrastructure.database import (
    staff_hr_ddl,
)
from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_hiring_schema import (
    CHECK_TYPES,
    DEFAULT_REQUIREMENTS,
    REQUIREMENT_TYPES,
)
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

CHECK_STATUSES = ('pending', 'in_progress', 'cleared', 'failed', 'waived')
DONE = ('cleared', 'waived')
DBS_LEVELS = ('basic', 'standard', 'enhanced', 'enhanced_barred')
RTW_DOCUMENTS = ('passport_uk', 'passport_irish', 'share_code', 'birth_certificate_ni',
                 'biometric_residence_permit', 'idsp_digital_check', 'other')
OFFER_TYPES = ('conditional', 'unconditional')
LIVE_OFFERS = ('made', 'accepted')
REFERENCES_REQUIRED = 2
#: Re-check a DBS certificate after this many years unless on the update service.
DBS_RECHECK_YEARS = 3

_USERNAME = re.compile(r'^[a-z0-9._-]{3,32}$')
_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_SHARE_CODE = re.compile(r'^[A-Z0-9]{9}$')
_DBS_CERT = re.compile(r'^\d{12}$')

__all__ = [
    'CHECK_TYPES', 'REQUIREMENT_TYPES', 'CHECK_STATUSES', 'DBS_LEVELS', 'RTW_DOCUMENTS',
    'OFFER_TYPES', 'REFERENCES_REQUIRED',
    'can_hire', 'required_checks', 'list_requirements', 'set_required_checks',
    'start_checks', 'record_check', 'list_checks', 'check_status',
    'request_reference', 'record_reference', 'list_references',
    'make_offer', 'accept_offer', 'decline_offer', 'withdraw_offer', 'confirm_start_date',
    'list_offers', 'get_offer', 'hire',
]


# ── plumbing ────────────────────────────────────────────────────────────


def _connect():
    conn = get_connection()
    staff_hr_ddl.apply_to_connection(conn)
    return conn


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _date(value: Any, label: str, required: bool = False) -> Optional[str]:
    text = str(value or '').strip()
    if not text:
        if required:
            raise ValueError(f"{label} is required")
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        raise ValueError(f"{label} must be a date (YYYY-MM-DD)") from None


def _add_years(day: str, years: int) -> str:
    d = date.fromisoformat(day)
    try:
        return d.replace(year=d.year + years).isoformat()
    except ValueError:      # 29 February
        return d.replace(year=d.year + years, day=28).isoformat()


def _add_months(day: str, months: int) -> str:
    d = date.fromisoformat(day)
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    for dom in (d.day, 30, 29, 28):
        try:
            return date(year, month, dom).isoformat()
        except ValueError:
            continue
    return d.isoformat()


def can_hire(actor: Any, conn=None) -> bool:
    """Recruiters and HR."""
    return access.can(actor, 'recruitment', conn) or access.is_hr(actor, conn)


def _gate(actor: Any, conn) -> dict:
    user = access.require_user(actor)
    if not can_hire(actor, conn):
        raise PermissionError("Only recruitment or HR can manage hiring")
    return user


def _application(conn, application_id) -> dict:
    row = conn.execute(
        "SELECT a.*, p.job_type, p.department, p.job_title AS posting_title, "
        "p.hiring_manager_id, p.salary_range "
        "FROM staff_recruitment_applications a "
        "LEFT JOIN staff_recruitment_postings p ON p.posting_id = a.posting_id "
        "WHERE a.application_id = ?", (int(application_id),)).fetchone()
    if not row:
        raise ValueError(f"Application {application_id} not found")
    app = dict(row)
    app['job_title'] = app.get('job_title') or app.get('posting_title')
    return app


def _mail(address: Optional[str], subject: str, body: str, to_ref: str) -> bool:
    """One e-mail through the university outbox (never raises)."""
    if not address:
        return False
    try:
        from education_system.systems.university.infrastructure.email.email_manager import (
            send_email,
        )
        outcome = send_email(address, subject, body, to_ref=to_ref,
                             in_app_copy=False, category='staff_hr_hiring')
        return outcome in ('sent to outbox', 'already sent')
    except Exception:
        logger.warning("Hiring e-mail %s not sent", to_ref, exc_info=True)
        return False


# ── required checks ─────────────────────────────────────────────────────


def required_checks(job_type: Optional[str], conn=None) -> list:
    """The checks (and ``references``) a job type must clear."""
    own = conn is None
    c = _connect() if own else conn
    try:
        rows = c.execute("SELECT job_type, check_type FROM staff_hr_check_requirements "
                         "WHERE job_type IN (?, '*')", (job_type or '*',)).fetchall()
        specific = [r[1] for r in rows if r[0] == (job_type or '*')]
        general = [r[1] for r in rows if r[0] == '*']
        # Never nothing: a job type with no rows of its own and no '*' rows
        # still needs the defaults.
        chosen = specific or general or list(DEFAULT_REQUIREMENTS)
        return [t for t in REQUIREMENT_TYPES if t in chosen]
    finally:
        if own:
            c.close()


def list_requirements(actor: Any) -> dict:
    """``{job_type: [check, ...]}`` (``'*'`` = every job)."""
    conn = _connect()
    try:
        _gate(actor, conn)
        out: dict = {}
        for job_type, check in conn.execute(
                "SELECT job_type, check_type FROM staff_hr_check_requirements "
                "ORDER BY job_type, check_type").fetchall():
            out.setdefault(job_type, []).append(check)
        if not out:
            out['*'] = list(DEFAULT_REQUIREMENTS)
        return out
    finally:
        conn.close()


def set_required_checks(actor: Any, job_type: str, checks) -> list:
    """Replace what ``job_type`` (``'*'`` = every job) requires."""
    job_type = str(job_type or '').strip() or '*'
    chosen = [str(c).strip() for c in (checks or []) if str(c).strip()]
    unknown = [c for c in chosen if c not in REQUIREMENT_TYPES]
    if unknown:
        raise ValueError(f"Unknown check(s): {', '.join(unknown)}")
    conn = _connect()
    try:
        _gate(actor, conn)
        me = access.username_of(actor)
        conn.execute("DELETE FROM staff_hr_check_requirements WHERE job_type = ?", (job_type,))
        for check in dict.fromkeys(chosen):
            conn.execute("INSERT INTO staff_hr_check_requirements (job_type, check_type, set_by) "
                         "VALUES (?, ?, ?)", (job_type, check, me))
        access.audit(conn, actor, 'hiring.requirements_set', None, 'job_type', job_type,
                     {'checks': chosen})
        conn.commit()
        return required_checks(job_type, conn)
    finally:
        conn.close()


# ── pre-employment checks ───────────────────────────────────────────────


def start_checks(actor: Any, application_id: int) -> list:
    """A ``pending`` row for every required check the application lacks."""
    conn = _connect()
    try:
        _gate(actor, conn)
        app = _application(conn, application_id)
        me = access.username_of(actor)
        created = []
        for check in required_checks(app.get('job_type'), conn):
            if check not in CHECK_TYPES:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO staff_hr_pre_employment_checks "
                "(application_id, check_type, status, created_by) VALUES (?, ?, 'pending', ?)",
                (app['application_id'], check, me))
            if cur.rowcount:
                created.append(check)
        if created:
            access.audit(conn, actor, 'hiring.checks_started', app.get('hired_username'),
                         'application', app['application_id'], {'checks': created})
        conn.commit()
        return created
    finally:
        conn.close()


def _validate_check(check_type: str, status: str, fields: dict) -> dict:
    out: dict = {}
    for key in ('check_date', 'follow_up_date', 'issue_date', 'recheck_date'):
        if key in fields:
            out[key] = _date(fields.get(key), key.replace('_', ' '))
    for key in ('document_type', 'share_code', 'checked_by', 'dbs_level',
                'certificate_number', 'details', 'notes'):
        if key in fields:
            out[key] = str(fields.get(key) or '').strip() or None
    if 'update_service' in fields:
        out['update_service'] = 1 if fields.get('update_service') in (
            True, 1, '1', 'yes', 'y', 'true', 'True', 'Yes') else 0
    if out.get('share_code'):
        out['share_code'] = out['share_code'].replace(' ', '').upper()
        if not _SHARE_CODE.match(out['share_code']):
            raise ValueError("A share code is 9 letters and digits")
    if out.get('dbs_level') and out['dbs_level'] not in DBS_LEVELS:
        raise ValueError(f"DBS level must be one of: {', '.join(DBS_LEVELS)}")
    if out.get('certificate_number'):
        out['certificate_number'] = out['certificate_number'].replace(' ', '')
        if not _DBS_CERT.match(out['certificate_number']):
            raise ValueError("A DBS certificate number is 12 digits")
    if out.get('document_type') and check_type == 'right_to_work' \
            and out['document_type'] not in RTW_DOCUMENTS:
        raise ValueError(f"Right-to-work document must be one of: {', '.join(RTW_DOCUMENTS)}")
    return out


def record_check(actor: Any, application_id: int, check_type: str, status: str,
                 **fields) -> dict:
    """Record the outcome or progress of one pre-employment check.

    Right to work: ``document_type``, ``share_code`` (online checks),
    ``checked_by`` (default: you), ``check_date`` (default: today),
    ``follow_up_date`` (time-limited permission). DBS: ``dbs_level``,
    ``certificate_number``, ``issue_date``, ``update_service``,
    ``recheck_date`` (default: issue + 3 years off the update service).
    """
    if check_type not in CHECK_TYPES:
        raise ValueError(f"Check must be one of: {', '.join(CHECK_TYPES)}")
    if status not in CHECK_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(CHECK_STATUSES)}")
    data = _validate_check(check_type, status, fields)
    conn = _connect()
    try:
        _gate(actor, conn)
        me = access.username_of(actor)
        app = _application(conn, application_id)
        existing = conn.execute(
            "SELECT * FROM staff_hr_pre_employment_checks WHERE application_id = ? "
            "AND check_type = ?", (app['application_id'], check_type)).fetchone()
        merged = {**(dict(existing) if existing else {}), **data}
        if status == 'cleared':
            merged['checked_by'] = merged.get('checked_by') or me
            merged['check_date'] = merged.get('check_date') or date.today().isoformat()
            if check_type == 'right_to_work':
                if not merged.get('document_type'):
                    raise ValueError("Say which document proved the right to work")
                if merged['document_type'] == 'share_code' and not merged.get('share_code'):
                    raise ValueError("An online right-to-work check needs the share code")
            if check_type == 'dbs':
                missing = [k for k in ('dbs_level', 'certificate_number', 'issue_date')
                           if not merged.get(k)]
                if missing:
                    raise ValueError("A cleared DBS check needs the "
                                     + ", ".join(m.replace('_', ' ') for m in missing))
                if not merged.get('recheck_date') and not merged.get('update_service'):
                    merged['recheck_date'] = _add_years(merged['issue_date'], DBS_RECHECK_YEARS)
        if status == 'waived' and not (merged.get('notes') or merged.get('details')):
            raise ValueError("Give a reason for waiving the check")
        cols = ('document_type', 'share_code', 'checked_by', 'check_date', 'follow_up_date',
                'dbs_level', 'certificate_number', 'issue_date', 'update_service',
                'recheck_date', 'details', 'notes')
        values = [merged.get(c) if c != 'update_service' else int(merged.get(c) or 0)
                  for c in cols]
        if existing:
            conn.execute(
                "UPDATE staff_hr_pre_employment_checks SET status = ?, "
                + ", ".join(f"{c} = ?" for c in cols)
                + ", staff_username = COALESCE(staff_username, ?), updated_at = ? "
                "WHERE check_id = ?",
                (status, *values, app.get('hired_username'), _now(), existing['check_id']))
            check_id = existing['check_id']
        else:
            check_id = conn.execute(
                "INSERT INTO staff_hr_pre_employment_checks (application_id, staff_username, "
                "check_type, status, " + ", ".join(cols) + ", created_by) VALUES "
                "(?, ?, ?, ?, " + ", ".join('?' * len(cols)) + ", ?)",
                (app['application_id'], app.get('hired_username'), check_type, status,
                 *values, me)).lastrowid
        # The share code and certificate number stay out of the audit trail.
        access.audit(conn, actor, f'hiring.check_{status}', app.get('hired_username'),
                     'pre_employment_check', check_id,
                     {'application_id': app['application_id'], 'check': check_type})
        conn.commit()
        return dict(conn.execute("SELECT * FROM staff_hr_pre_employment_checks "
                                 "WHERE check_id = ?", (check_id,)).fetchone())
    finally:
        conn.close()


def list_checks(actor: Any, application_id: Optional[int] = None,
                status: Optional[str] = None) -> list:
    conn = _connect()
    try:
        _gate(actor, conn)
        sql = ("SELECT c.*, a.applicant_name, a.job_title FROM staff_hr_pre_employment_checks c "
               "LEFT JOIN staff_recruitment_applications a "
               "ON a.application_id = c.application_id WHERE 1 = 1")
        params: list = []
        if application_id:
            sql += " AND c.application_id = ?"
            params.append(int(application_id))
        if status:
            sql += " AND c.status = ?"
            params.append(status)
        sql += " ORDER BY c.application_id DESC, c.check_type"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _references_state(conn, application_id: int) -> dict:
    rows = conn.execute("SELECT status, satisfactory FROM staff_hr_references "
                        "WHERE application_id = ?", (application_id,)).fetchall()
    good = sum(1 for r in rows if r[0] == 'received' and r[1] == 1)
    bad = sum(1 for r in rows if r[0] == 'received' and r[1] == 0)
    return {'requested': len(rows), 'satisfactory': good, 'unsatisfactory': bad,
            'cleared': good >= REFERENCES_REQUIRED and bad == 0}


def _status(conn, application_id: int) -> dict:
    app = _application(conn, application_id)
    required = required_checks(app.get('job_type'), conn)
    rows = {r['check_type']: r['status'] for r in conn.execute(
        "SELECT check_type, status FROM staff_hr_pre_employment_checks WHERE application_id = ?",
        (app['application_id'],)).fetchall()}
    refs = _references_state(conn, app['application_id'])
    checks, outstanding = {}, []
    for check in required:
        state = ('cleared' if refs['cleared'] else 'pending') if check == 'references' \
            else rows.get(check, 'not started')
        checks[check] = state
        if state not in DONE:
            outstanding.append(check)
    return {'application_id': app['application_id'], 'job_type': app.get('job_type'),
            'required': required, 'checks': checks, 'references': refs,
            'outstanding': outstanding, 'cleared': not outstanding}


def check_status(actor: Any, application_id: int) -> dict:
    """Which required checks have cleared and which are outstanding."""
    conn = _connect()
    try:
        _gate(actor, conn)
        return _status(conn, application_id)
    finally:
        conn.close()


# ── references ──────────────────────────────────────────────────────────


def request_reference(actor: Any, application_id: int, referee_name: str,
                      referee_email: str, relationship: str = '') -> int:
    """Record a reference request and e-mail the referee."""
    name = str(referee_name or '').strip()
    email = str(referee_email or '').strip()
    if not name:
        raise ValueError("The referee's name is required")
    if not _EMAIL.match(email):
        raise ValueError("A valid referee e-mail address is required")
    conn = _connect()
    try:
        _gate(actor, conn)
        app = _application(conn, application_id)
        me = access.username_of(actor)
        ref_id = conn.execute(
            "INSERT INTO staff_hr_references (application_id, referee_name, referee_email, "
            "relationship, status, requested_by, requested_at) "
            "VALUES (?, ?, ?, ?, 'requested', ?, ?)",
            (app['application_id'], name, email, str(relationship or '').strip() or None,
             me, _now())).lastrowid
        access.audit(conn, actor, 'hiring.reference_requested', None, 'reference', ref_id,
                     {'application_id': app['application_id']})
        conn.commit()
    finally:
        conn.close()
    body = (f"Dear {name},\n\n"
            f"{app.get('applicant_name') or 'An applicant'} has applied for the post of "
            f"{app.get('job_title') or 'a role'} at the university and has given your name "
            "as a referee.\n\n"
            "Please reply to this e-mail with a reference covering their dates of employment "
            "or study with you, their role, their suitability for the post, and anything that "
            "would give you concern about their working with students or vulnerable adults.\n\n"
            f"Our reference: REF-{ref_id}\n\nThank you,\nRecruitment team")
    _mail(email, f"Reference request: {app.get('applicant_name') or 'applicant'}", body,
          f"staff_hr:reference:{ref_id}")
    return ref_id


def record_reference(actor: Any, reference_id: int, *, status: str = 'received',
                     content: str = '', satisfactory: Optional[bool] = None,
                     notes: str = '') -> dict:
    """Record a reference received (or declined) and whether it is satisfactory."""
    if status not in ('requested', 'received', 'declined'):
        raise ValueError("Status must be requested, received or declined")
    if status == 'received' and satisfactory is None:
        raise ValueError("Say whether the reference is satisfactory")
    conn = _connect()
    try:
        _gate(actor, conn)
        row = conn.execute("SELECT * FROM staff_hr_references WHERE reference_id = ?",
                           (int(reference_id),)).fetchone()
        if not row:
            raise ValueError(f"Reference {reference_id} not found")
        sat = None if satisfactory is None or status != 'received' else int(bool(satisfactory))
        conn.execute(
            "UPDATE staff_hr_references SET status = ?, content = COALESCE(?, content), "
            "satisfactory = ?, assessed_by = ?, notes = COALESCE(?, notes), "
            "received_at = CASE WHEN ? = 'received' THEN COALESCE(received_at, ?) "
            "ELSE received_at END WHERE reference_id = ?",
            (status, str(content or '').strip() or None, sat, access.username_of(actor),
             str(notes or '').strip() or None, status, _now(), row['reference_id']))
        access.audit(conn, actor, 'hiring.reference_recorded', None, 'reference',
                     row['reference_id'], {'status': status, 'satisfactory': sat})
        conn.commit()
        return dict(conn.execute("SELECT * FROM staff_hr_references WHERE reference_id = ?",
                                 (row['reference_id'],)).fetchone())
    finally:
        conn.close()


def list_references(actor: Any, application_id: Optional[int] = None) -> list:
    conn = _connect()
    try:
        _gate(actor, conn)
        sql = ("SELECT r.*, a.applicant_name FROM staff_hr_references r "
               "LEFT JOIN staff_recruitment_applications a ON a.application_id = r.application_id")
        params: tuple = ()
        if application_id:
            sql += " WHERE r.application_id = ?"
            params = (int(application_id),)
        return [dict(r) for r in conn.execute(sql + " ORDER BY r.reference_id DESC",
                                              params).fetchall()]
    finally:
        conn.close()


# ── offers ──────────────────────────────────────────────────────────────


def _offer(conn, offer_id) -> dict:
    row = conn.execute("SELECT * FROM staff_hr_offers WHERE offer_id = ?",
                       (int(offer_id),)).fetchone()
    if not row:
        raise ValueError(f"Offer {offer_id} not found")
    return dict(row)


def get_offer(actor: Any, offer_id: int) -> dict:
    conn = _connect()
    try:
        _gate(actor, conn)
        return _offer(conn, offer_id)
    finally:
        conn.close()


def list_offers(actor: Any, status: Optional[str] = None) -> list:
    conn = _connect()
    try:
        _gate(actor, conn)
        sql = ("SELECT o.*, a.applicant_name, a.applicant_email FROM staff_hr_offers o "
               "LEFT JOIN staff_recruitment_applications a ON a.application_id = o.application_id")
        params: tuple = ()
        if status:
            sql += " WHERE o.status = ?"
            params = (status,)
        return [dict(r) for r in conn.execute(sql + " ORDER BY o.offer_id DESC",
                                              params).fetchall()]
    finally:
        conn.close()


def make_offer(actor: Any, application_id: int, *, offer_type: str = 'conditional',
               salary: Any = None, grade: str = '', start_date: str = '', fte: Any = 1.0,
               contract_type: str = '', end_date: str = '', probation_months: Any = 6,
               manager_id: str = '', onboarding_template_id: Any = None,
               conditions: str = '') -> int:
    """Offer the post. Unconditional only once every required check has cleared."""
    if offer_type not in OFFER_TYPES:
        raise ValueError("Offer type must be conditional or unconditional")
    start = _date(start_date, 'Start date', required=True)
    end = _date(end_date, 'End date')
    if end and end <= start:
        raise ValueError("The end date must be after the start date")
    try:
        pay = float(salary) if salary not in (None, '') else None
        fte_value = float(fte if fte not in (None, '') else 1.0)
        probation = int(probation_months if probation_months not in (None, '') else 6)
    except (TypeError, ValueError):
        raise ValueError("Salary, FTE and probation months must be numbers") from None
    if pay is not None and pay <= 0:
        raise ValueError("Salary must be more than zero")
    if not 0 < fte_value <= 1:
        raise ValueError("FTE must be more than 0 and at most 1")
    if probation < 0:
        raise ValueError("Probation months cannot be negative")
    conn = _connect()
    try:
        _gate(actor, conn)
        app = _application(conn, application_id)
        if app.get('status') in ('hired', 'rejected', 'withdrawn'):
            raise ValueError(f"The application is {app['status']}")
        if conn.execute("SELECT 1 FROM staff_hr_offers WHERE application_id = ? AND status IN "
                        "('made', 'accepted')", (app['application_id'],)).fetchone():
            raise ValueError("This application already has a live offer; withdraw it first")
        state = _status(conn, app['application_id'])
        if offer_type == 'unconditional' and not state['cleared']:
            raise ValueError("An unconditional offer needs every required check cleared "
                             f"(outstanding: {', '.join(state['outstanding'])})")
        manager = access.staff_key(manager_id, conn) if manager_id else None
        if manager_id and not manager:
            raise ValueError(f"Line manager '{manager_id}' is not a member of staff")
        manager = manager or access.staff_key(app.get('hiring_manager_id'), conn)
        if not conditions and offer_type == 'conditional':
            conditions = "Subject to satisfactory " + ", ".join(
                c.replace('_', ' ') for c in state['required'])
        me = access.username_of(actor)
        contract = (contract_type or '').strip() or (
            'fixed_term' if end else (app.get('job_type') or 'permanent'))
        offer_id = conn.execute(
            "INSERT INTO staff_hr_offers (application_id, offer_type, job_title, department, "
            "contract_type, salary, grade, fte, start_date, end_date, probation_months, "
            "manager_id, onboarding_template_id, conditions, status, made_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'made', ?)",
            (app['application_id'], offer_type, app.get('job_title'), app.get('department'),
             contract, pay, str(grade or '').strip() or None, fte_value, start, end,
             probation, manager,
             int(onboarding_template_id) if onboarding_template_id not in (None, '') else None,
             conditions or None, me)).lastrowid
        conn.execute("UPDATE staff_recruitment_applications SET status = 'offered' "
                     "WHERE application_id = ?", (app['application_id'],))
        access.audit(conn, actor, 'hiring.offer_made', app.get('hired_username'), 'offer',
                     offer_id, {'application_id': app['application_id'], 'type': offer_type,
                                'start_date': start})
        conn.commit()
    finally:
        conn.close()
    lines = [f"Dear {app.get('applicant_name') or 'applicant'},", "",
             f"We are pleased to offer you the post of {app.get('job_title') or 'the role'}"
             + (f" in {app['department']}" if app.get('department') else '') + ".", "",
             f"Start date: {start}", f"FTE: {fte_value:g}"]
    if pay is not None:
        lines.append(f"Salary: £{pay:,.2f} per year" + (f" (grade {grade})" if grade else ''))
    if offer_type == 'conditional':
        lines += ["", f"This offer is conditional. {conditions}"]
    lines += ["", "Please let the recruitment team know whether you accept.", "",
              "Recruitment team"]
    _mail(app.get('applicant_email'), f"Offer of employment: {app.get('job_title') or ''}",
          "\n".join(lines), f"staff_hr:offer:{offer_id}:made")
    return offer_id


def _respond(actor: Any, offer_id: int, new_status: str, note: str, allowed: tuple) -> dict:
    conn = _connect()
    try:
        _gate(actor, conn)
        offer = _offer(conn, offer_id)
        if offer['status'] not in allowed:
            raise ValueError(f"The offer is {offer['status']}")
        me = access.username_of(actor)
        if new_status == 'withdrawn':
            if not str(note or '').strip():
                raise ValueError("Give a reason for withdrawing the offer")
            conn.execute("UPDATE staff_hr_offers SET status = 'withdrawn', withdrawn_by = ?, "
                         "withdraw_reason = ?, responded_at = ? WHERE offer_id = ?",
                         (me, note.strip(), _now(), offer['offer_id']))
        else:
            conn.execute("UPDATE staff_hr_offers SET status = ?, responded_at = ?, "
                         "response_note = ? WHERE offer_id = ?",
                         (new_status, _now(), str(note or '').strip() or None,
                          offer['offer_id']))
        app_status = {'accepted': 'offer_accepted', 'declined': 'offer_declined',
                      'withdrawn': 'offer_withdrawn'}[new_status]
        conn.execute("UPDATE staff_recruitment_applications SET status = ? "
                     "WHERE application_id = ?", (app_status, offer['application_id']))
        access.audit(conn, actor, f'hiring.offer_{new_status}', None, 'offer',
                     offer['offer_id'], {'application_id': offer['application_id']})
        conn.commit()
        app = _application(conn, offer['application_id'])
        offer = _offer(conn, offer['offer_id'])
    finally:
        conn.close()
    if new_status == 'withdrawn':
        _mail(app.get('applicant_email'), f"Offer withdrawn: {offer.get('job_title') or ''}",
              f"Dear {app.get('applicant_name') or 'applicant'},\n\nWe are sorry to tell you "
              f"that our offer of the post of {offer.get('job_title') or 'the role'} has been "
              f"withdrawn.\n\nReason: {note.strip()}\n\nRecruitment team",
              f"staff_hr:offer:{offer['offer_id']}:withdrawn")
    return offer


def accept_offer(actor: Any, offer_id: int, note: str = '') -> dict:
    """Record the applicant accepting the offer."""
    return _respond(actor, offer_id, 'accepted', note, ('made',))


def decline_offer(actor: Any, offer_id: int, note: str = '') -> dict:
    """Record the applicant declining the offer."""
    return _respond(actor, offer_id, 'declined', note, ('made',))


def withdraw_offer(actor: Any, offer_id: int, reason: str) -> dict:
    """Withdraw a live offer (the applicant is told why)."""
    return _respond(actor, offer_id, 'withdrawn', reason, LIVE_OFFERS)


def confirm_start_date(actor: Any, offer_id: int, start_date: str = '') -> dict:
    """Confirm the start date of an accepted offer once every required check
    has cleared; the offer becomes unconditional."""
    conn = _connect()
    try:
        _gate(actor, conn)
        offer = _offer(conn, offer_id)
        if offer['status'] not in ('accepted', 'hired'):
            raise ValueError("Only an accepted offer can have its start date confirmed")
        state = _status(conn, offer['application_id'])
        if not state['cleared']:
            raise ValueError("The start date cannot be confirmed until every required check "
                             f"has cleared (outstanding: {', '.join(state['outstanding'])})")
        start = _date(start_date, 'Start date') or offer['start_date']
        if not start:
            raise ValueError("Start date is required")
        conn.execute("UPDATE staff_hr_offers SET start_date = ?, start_confirmed = 1, "
                     "offer_type = 'unconditional' WHERE offer_id = ?",
                     (start, offer['offer_id']))
        access.audit(conn, actor, 'hiring.start_confirmed', offer.get('staff_username'),
                     'offer', offer['offer_id'], {'start_date': start})
        conn.commit()
        app = _application(conn, offer['application_id'])
        offer = _offer(conn, offer['offer_id'])
    finally:
        conn.close()
    _mail(app.get('applicant_email'), f"Your start date: {start}",
          f"Dear {app.get('applicant_name') or 'applicant'},\n\nYour pre-employment checks "
          f"are complete and your offer of the post of {offer.get('job_title') or 'the role'} "
          f"is now unconditional.\n\nYour confirmed start date is {start}.\n\nRecruitment team",
          f"staff_hr:offer:{offer['offer_id']}:start:{start}")
    return offer


# ── hire ────────────────────────────────────────────────────────────────


def _split(name: str) -> tuple:
    parts = [p for p in str(name or '').strip().split() if p]
    if not parts:
        return '', ''
    return parts[0], ' '.join(parts[1:])


def _taken(conn, username: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM users WHERE LOWER(username) = LOWER(?)",
                             (username,)).fetchone()
                or conn.execute("SELECT 1 FROM staff WHERE LOWER(username) = LOWER(?)",
                                (username,)).fetchone())


def _new_username(conn, name: str) -> str:
    first, last = _split(name)
    base = '.'.join(re.sub(r'[^a-z0-9]', '', p.lower()) for p in (first, last) if p)
    base = re.sub(r'\.+', '.', base).strip('.')[:28] or 'staff'
    if len(base) < 3:
        base = f"{base}.staff"
    candidate, n = base, 1
    while _taken(conn, candidate):
        n += 1
        candidate = f"{base}{n}"
    return candidate


def _choose_username(conn, app: dict, offer: dict, requested: Optional[str]) -> tuple:
    """(username, existing_account)."""
    if offer.get('staff_username'):
        return offer['staff_username'], True
    if app.get('hired_username'):
        return app['hired_username'], True
    email = (app.get('applicant_email') or '').strip()
    if email:
        row = conn.execute("SELECT username FROM users WHERE LOWER(email) = LOWER(?)",
                           (email,)).fetchone()
        if row:
            return row[0], True
    if requested:
        username = requested.strip().lower()
        if not _USERNAME.match(username):
            raise ValueError("Username must be 3-32 lower-case letters, digits, '.', '_' or '-'")
        if _taken(conn, username):
            raise ValueError(f"The username {username} is already in use")
        return username, False
    return _new_username(conn, app.get('applicant_name')), False


def _pick_template(conn, offer: dict) -> Optional[int]:
    if offer.get('onboarding_template_id'):
        return int(offer['onboarding_template_id'])
    row = conn.execute(
        "SELECT template_id FROM onboarding_templates WHERE COALESCE(is_active, 1) = 1 "
        "AND COALESCE(template_type, 'onboarding') = 'onboarding' "
        "AND (department IS NULL OR department = '' OR department = ?) "
        "ORDER BY CASE WHEN department = ? THEN 0 ELSE 1 END, template_id LIMIT 1",
        (offer.get('department') or '', offer.get('department') or '')).fetchone()
    return row[0] if row else None


def _provision(member: dict, auth) -> dict:
    from education_system.systems.university.services import staff_provisioning
    return staff_provisioning.provision_staff_login(member, auth=auth)


def _send_activation(email: str) -> bool:
    try:
        from education_system.systems.university.services.student_provisioning import (
            send_student_activation,
        )
        return bool(send_student_activation(email))
    except Exception:
        logger.warning("Password set-up e-mail not sent to the new starter", exc_info=True)
        return False


def hire(actor: Any, offer_id: int, *, username: Optional[str] = None,
         onboarding_template_id: Any = None, auth=None) -> dict:
    """Turn an accepted offer, with every required check cleared, into a member
    of staff. Returns what was done (``username``, ``contract_id``,
    ``onboarding_assignment_id``, ``account_created``, ``activation_sent``,
    ``warnings``)."""
    from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.contract_manager import (
        ContractManager,
    )
    from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.employee_manager import (
        EmployeeManager,
    )
    from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.onboarding_manager import (
        OnboardingManager,
    )

    result: dict = {'warnings': []}
    conn = _connect()
    try:
        _gate(actor, conn)
        me = access.username_of(actor)
        offer = _offer(conn, offer_id)
        if offer['status'] == 'hired' and offer.get('contract_id'):
            raise ValueError(f"Already hired as {offer.get('staff_username')}")
        if offer['status'] not in ('accepted', 'hired'):
            raise ValueError("Only an accepted offer can be turned into a hire")
        state = _status(conn, offer['application_id'])
        if not state['cleared']:
            raise ValueError("Every required check must clear before the hire "
                             f"(outstanding: {', '.join(state['outstanding'])})")
        if not offer.get('start_date'):
            raise ValueError("The offer has no start date")
        app = _application(conn, offer['application_id'])
        email = (app.get('applicant_email') or '').strip()
        if not _EMAIL.match(email):
            raise ValueError("The application needs a valid e-mail address for the new account")
        name, existing = _choose_username(conn, app, offer, username)
        manager = offer.get('manager_id')
        if manager and manager == name:
            raise ValueError("A person cannot be their own line manager")
        # Record the chosen username first, so a hire that stops part-way
        # resumes with the same account.
        conn.execute("UPDATE staff_hr_offers SET staff_username = ? WHERE offer_id = ?",
                     (name, offer['offer_id']))
        conn.execute("UPDATE staff_recruitment_applications SET hired_username = ? "
                     "WHERE application_id = ?", (name, app['application_id']))
        has_user = bool(conn.execute("SELECT 1 FROM users WHERE username = ?",
                                     (name,)).fetchone())
        staff_row = conn.execute("SELECT id FROM staff WHERE username = ?", (name,)).fetchone()
        staff_id = staff_row[0] if staff_row else None
        if staff_id is None:
            staff_id = conn.execute(
                "INSERT INTO staff (username, password_hash, name, email, phone, role, "
                "hire_date, status) VALUES (?, '!', ?, ?, ?, 'staff', ?, 'active')",
                (name, app.get('applicant_name') or name, email, app.get('applicant_phone'),
                 offer['start_date'])).lastrowid
        conn.commit()
    finally:
        conn.close()

    result['username'] = name
    result['account_created'] = False
    result['activation_sent'] = False
    if not has_user:
        member = {'id': staff_id, 'username': name, 'name': app.get('applicant_name') or name,
                  'email': email, 'role': 'staff'}
        login = _provision(member, auth)
        conn = _connect()
        try:
            made = bool(conn.execute("SELECT 1 FROM users WHERE username = ?",
                                     (name,)).fetchone())
        finally:
            conn.close()
        if not made:
            raise RuntimeError("The staff login could not be created"
                               + (f": {login.get('reason')}" if login.get('reason') else '')
                               + "; nothing else was changed - try the hire again")
        result['account_created'] = True
        if login.get('shared_ok'):
            result['activation_sent'] = _send_activation(email)
        if not result['activation_sent']:
            result['warnings'].append("Password set-up e-mail not sent - resend it from "
                                      "user management")
    elif not existing:
        result['warnings'].append(f"{name} already had an account; it was reused")

    profile = EmployeeManager.get_profile(name)
    profile_data = {'department': offer.get('department'), 'job_title': offer.get('job_title'),
                    'employment_type': 'part-time' if (offer.get('fte') or 1) < 1
                    else 'full-time',
                    'hire_date': offer['start_date'], 'contract_end_date': offer.get('end_date'),
                    'manager_id': manager}
    if profile:
        conn = _connect()
        try:
            conn.execute("UPDATE staff_profiles SET department = COALESCE(?, department), "
                         "job_title = COALESCE(?, job_title), manager_id = COALESCE(?, manager_id), "
                         "hire_date = COALESCE(hire_date, ?), "
                         "contract_end_date = ?, updated_at = ? WHERE user_id = ?",
                         (profile_data['department'], profile_data['job_title'], manager,
                          offer['start_date'], offer.get('end_date'), _now(), name))
            conn.commit()
        finally:
            conn.close()
    else:
        EmployeeManager.create_profile(name, **profile_data)

    contract_id = offer.get('contract_id')
    if not contract_id:
        start = offer['start_date']
        probation = int(offer.get('probation_months') or 0)
        hours = round(37.5 * float(offer.get('fte') or 1), 2)
        contract_id = ContractManager.create_contract(
            name, contract_type=offer.get('contract_type') or 'permanent', start_date=start,
            end_date=offer.get('end_date'), salary=offer.get('salary'), status='active',
            probation_end_date=_add_months(start, probation) if probation else None,
            working_hours_per_week=hours, department=offer.get('department'),
            job_title=offer.get('job_title'), manager_id=manager, created_by=me,
            terms=offer.get('conditions'))
    conn = _connect()
    try:
        # The pay structure's contract columns, where they exist.
        cols = staff_hr_ddl.columns(conn.execute, 'staff_contracts')
        extra = {}
        if 'fte' in cols and offer.get('fte') not in (None, ''):
            extra['fte'] = offer['fte']
        grade = offer.get('grade')
        if grade and 'grade_code' in cols:
            known = staff_hr_ddl.table_exists(conn.execute, 'pay_grades') and conn.execute(
                "SELECT 1 FROM pay_grades WHERE grade_code = ?", (grade,)).fetchone()
            if known:
                extra['grade_code'] = grade
            else:
                result['warnings'].append(f"Grade {grade} is not a pay grade; payroll should "
                                          "set the contract's grade and spine point")
        elif grade:
            result['warnings'].append("Grade not stored on the contract (no pay structure yet)")
        if extra:
            conn.execute("UPDATE staff_contracts SET "  # nosec B608 - fixed column names
                         + ", ".join(f"{k} = ?" for k in extra) + " WHERE contract_id = ?",
                         (*extra.values(), contract_id))
        template = (int(onboarding_template_id) if onboarding_template_id not in (None, '')
                    else _pick_template(conn, offer))
        already = conn.execute("SELECT assignment_id FROM onboarding_assignments "
                               "WHERE user_id = ? AND status != 'cancelled' "
                               "ORDER BY assignment_id DESC LIMIT 1", (name,)).fetchone()
        conn.execute("UPDATE staff_hr_offers SET contract_id = ?, start_confirmed = 1, "
                     "offer_type = 'unconditional' WHERE offer_id = ?",
                     (contract_id, offer['offer_id']))
        conn.commit()
    finally:
        conn.close()
    result['contract_id'] = contract_id

    assignment = already[0] if already else None
    if assignment is None and template:
        try:
            assignment = OnboardingManager.assign_template(
                name, template, me, start_date=offer['start_date'], recipient_email=email,
                staff_name=app.get('applicant_name') or name,
                department=offer.get('department') or '', line_manager=manager or '')
        except Exception as exc:
            logger.warning("Onboarding not assigned to %s", name, exc_info=True)
            result['warnings'].append(f"Onboarding not assigned: {exc}")
    elif assignment is None:
        result['warnings'].append("No onboarding template to assign - set one up and assign "
                                  "it from Onboarding")
    result['onboarding_assignment_id'] = assignment

    conn = _connect()
    try:
        conn.execute("UPDATE staff_hr_offers SET status = 'hired', hired_by = ?, hired_at = ? "
                     "WHERE offer_id = ?", (me, _now(), offer['offer_id']))
        conn.execute("UPDATE staff_recruitment_applications SET status = 'hired' "
                     "WHERE application_id = ?", (app['application_id'],))
        conn.execute("UPDATE staff_hr_pre_employment_checks SET staff_username = ? "
                     "WHERE application_id = ?", (name, app['application_id']))
        access.audit(conn, actor, 'hiring.hired', name, 'offer', offer['offer_id'],
                     {'application_id': app['application_id'], 'contract_id': contract_id,
                      'onboarding_assignment_id': assignment,
                      'account_created': result['account_created']})
        if manager:
            try:
                from education_system.systems.university.infrastructure.email.messages_inbox import (
                    deliver_inbox_message_on,
                )
                deliver_inbox_message_on(
                    conn, manager, f"New starter: {app.get('applicant_name') or name}",
                    f"{app.get('applicant_name') or name} ({name}) joins as "
                    f"{offer.get('job_title') or 'a member of staff'} on "
                    f"{offer['start_date']} and reports to you.")
            except Exception:
                logger.warning("New-starter notice not delivered to %s", manager, exc_info=True)
        conn.commit()
    finally:
        conn.close()
    return result
