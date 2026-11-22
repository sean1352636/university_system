"""
Contract Manager - Staff contract and employment management.

Provides functionality for:
- Contract creation and tracking
- Renewal alerts (30/60/90 days)
- Probation period tracking
- Probation review scheduling
- Contract amendment history
- Grade, spine point, FTE and pension scheme (``pay_structure`` / ``pensions``)

Who may do what (``access``): contract screens are HR's or payroll's; a
person sees their own contracts; a line manager sees their reports'
contract terms but never the pay (:data:`PAY_FIELDS` are removed).
Methods take ``actor`` and check it; ``actor=None`` is a trusted internal
call (jobs, subscribers, tests).
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import _people as people
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608


#: Contract columns that reveal pay (hidden from a line manager).
PAY_FIELDS = ('salary', 'salary_currency', 'pay_frequency', 'spine_point', 'salary_override',
              'salary_override_reason', 'salary_override_by', 'pension_scheme')
#: Pay-structure columns set through ``pay_structure.assign``.
ASSIGN_FIELDS = ('grade_code', 'spine_point', 'fte', 'pension_scheme', 'salary_override',
                 'salary_override_reason')


def can_manage_contracts(actor: Any, conn=None) -> bool:
    return access.is_hr(actor, conn) or access.can(actor, 'payroll', conn)


def _require_contracts(actor: Any, conn=None) -> Optional[str]:
    """HR or payroll (None = trusted internal call)."""
    if actor is None:
        return None
    access.require_user(actor)
    if not can_manage_contracts(actor, conn):
        raise PermissionError("Only HR or payroll can manage contracts")
    return access.username_of(actor)


def _shown(actor: Any, contract: Optional[Dict[str, Any]], conn) -> Optional[Dict[str, Any]]:
    """``contract`` as ``actor`` may see it (pay removed for a manager),
    or None when they may not see it at all."""
    if contract is None or actor is None:
        return contract
    user = str(contract.get('user_id'))
    if user == access.username_of(actor) or can_manage_contracts(actor, conn):
        return contract
    if access.can_view_person(actor, user, conn):
        return {k: v for k, v in contract.items() if k not in PAY_FIELDS}
    return None


def _owner_view(actor: Any, user_id: str, conn) -> str:
    """The username asked about; raises unless ``actor`` may see their contracts."""
    user = access.staff_key(user_id, conn) or str(user_id)
    if not (user == access.username_of(actor) or can_manage_contracts(actor, conn)
            or access.can_view_person(actor, user, conn)):
        raise PermissionError("You cannot see this person's contract")
    return user


class ContractManager:
    """Manager for staff contracts and employment records."""

    @staticmethod
    def propose_contract_renewal(current_contract_id: int, recipient_email: str,
                                 new_contract_type: str, new_start_date: str,
                                 new_end_date: str, response_by: str,
                                 fte: str = "1.0", salary_grade: str = "(see HR portal)",
                                 decision_maker: str = "Department Head",
                                 staff_name: str = "",
                                 department: str = "",
                                 renewal_notes: str = "") -> bool:
        """Email a staff member with proposed contract-renewal terms. Best-effort."""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT user_id, end_date FROM staff_contracts WHERE contract_id = ?",
                    (current_contract_id,),
                ).fetchone()
        except Exception:
            row = None
        from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.leave_manager import (
            _send_staff_hr_email,
        )
        return _send_staff_hr_email('contract_renewal', recipient_email, {
            'staff_id':            (row[0] if row else '(unknown)'),
            'staff_name':          staff_name or (row[0] if row else 'Staff Member'),
            'department':          department or '(see HR portal)',
            'current_contract_id': current_contract_id,
            'current_end_date':    (row[1] if row else '(unknown)'),
            'new_contract_type':   new_contract_type,
            'new_start_date':      new_start_date,
            'new_end_date':        new_end_date,
            'fte':                 fte,
            'salary_grade':        salary_grade,
            'decision_maker':      decision_maker,
            'response_by':         response_by,
            'renewal_notes':       renewal_notes or '(no further notes)',
        })

    # ==================== CONTRACT CRUD ====================

    @staticmethod
    def create_contract(user_id: str, actor: Any = None, **data) -> int:
        """Create a new staff contract.

        Pay structure (optional): ``grade_code`` (else the job title's grade),
        ``spine_point``, ``fte``, ``pension_scheme`` (enrols the person),
        ``salary_override`` + ``salary_override_reason``. With a spine point
        the salary is the point's current full-time value."""
        pay_given = actor is not None or any(data.get(k) not in (None, '') for k in ASSIGN_FIELDS)
        with transaction() as conn:
            if actor is not None:
                me = _require_contracts(actor, conn)
                user_id = access.staff_key(user_id, conn)
                if not user_id:
                    raise ValueError("No member of staff by that name")
                data['created_by'] = me
            if pay_given:
                from education_system.systems.university.domains.staff.domain.staff_hr import (
                    pay_structure,
                    pensions,
                )
                pay_structure.ensure(conn)
                if not data.get('grade_code'):
                    data['grade_code'] = pay_structure.grade_for_job(data.get('job_title'), conn)
                pay_structure.validate_assignment(conn, data.get('grade_code'),
                                                  data.get('spine_point'))
                if data.get('fte') not in (None, ''):
                    data['fte'] = pay_structure.check_fte(data['fte'])
                pensions.check_scheme(conn, data.get('pension_scheme'))
                if data.get('salary_override') not in (None, '') and \
                        not str(data.get('salary_override_reason') or '').strip():
                    raise ValueError("A salary override needs a reason")
            cursor = conn.execute('''
                INSERT INTO staff_contracts (
                    user_id, contract_type, start_date, end_date, salary,
                    salary_currency, pay_frequency, terms, status,
                    renewal_date, probation_end_date, notice_period_days,
                    working_hours_per_week, department, job_title,
                    manager_id, document_path, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('contract_type', 'permanent'),
                data.get('start_date'),
                data.get('end_date'),
                data.get('salary'),
                data.get('salary_currency', 'GBP'),
                data.get('pay_frequency', 'monthly'),
                data.get('terms'),
                data.get('status', 'active'),
                data.get('renewal_date'),
                data.get('probation_end_date'),
                data.get('notice_period_days', 30),
                data.get('working_hours_per_week', 37.5),
                data.get('department'),
                data.get('job_title'),
                data.get('manager_id'),
                data.get('document_path'),
                data.get('created_by'),
            ))
            contract_id = cursor.lastrowid

            if pay_given:
                extra = {k: data.get(k) for k in ASSIGN_FIELDS if data.get(k) not in (None, '')}
                if extra.get('salary_override') is not None:
                    extra['salary_override_by'] = data.get('created_by')
                if extra:
                    sets = ', '.join(validate_identifier(k, "column") + ' = ?' for k in extra)
                    conn.execute('UPDATE staff_contracts SET ' + sets + ' WHERE contract_id = ?',
                                 list(extra.values()) + [contract_id])
                row = conn.execute('SELECT * FROM staff_contracts WHERE contract_id = ?',
                                   (contract_id,)).fetchone()
                derived = pay_structure.derive_salary(conn, dict(row))
                if derived['source'] != 'contract':
                    conn.execute('UPDATE staff_contracts SET salary = ? WHERE contract_id = ?',
                                 (derived['full_time'], contract_id))
                if data.get('pension_scheme'):
                    pensions.enrol_in(conn, user_id, data['pension_scheme'],
                                      data.get('start_date') or datetime.now().date().isoformat(),
                                      data.get('created_by'))
                if actor is not None:
                    access.audit(conn, actor, 'contract.created', subject=user_id,
                                 entity='staff_contract', entity_id=contract_id,
                                 details={k: v for k, v in extra.items() if k not in PAY_FIELDS})

            # Create renewal alerts if end_date is set
            if data.get('end_date'):
                ContractManager._create_renewal_alerts(conn, contract_id, data['end_date'], user_id)

            log_activity('create', 'staff_contract', details={
                'contract_id': contract_id, 'user_id': user_id
            })
            return contract_id

    @staticmethod
    def get_contract(contract_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """Get a contract by ID (as ``actor`` may see it)."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM staff_contracts WHERE contract_id = ?
            ''', (contract_id,)).fetchone()
            contract = dict(row) if row else None
            if contract and actor is not None:
                shown = _shown(actor, contract, conn)
                if shown is None:
                    raise PermissionError("You cannot see this contract")
                return shown
            return contract

    @staticmethod
    def get_user_contracts(user_id: str, include_inactive: bool = False,
                           actor: Any = None) -> List[Dict[str, Any]]:
        """Get all contracts for a user."""
        with get_connection() as conn:
            if actor is not None:
                user_id = _owner_view(actor, user_id, conn)
            if include_inactive:
                rows = conn.execute('''
                    SELECT * FROM staff_contracts
                    WHERE user_id = ?
                    ORDER BY start_date DESC
                ''', (user_id,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM staff_contracts
                    WHERE user_id = ? AND status = 'active'
                    ORDER BY start_date DESC
                ''', (user_id,)).fetchall()
            return [_shown(actor, dict(row), conn) for row in rows]

    @staticmethod
    def get_active_contract(user_id: str, actor: Any = None) -> Optional[Dict[str, Any]]:
        """Get the current active contract for a user."""
        with get_connection() as conn:
            if actor is not None:
                user_id = _owner_view(actor, user_id, conn)
            row = conn.execute('''
                SELECT * FROM staff_contracts
                WHERE user_id = ? AND status = 'active'
                ORDER BY start_date DESC LIMIT 1
            ''', (user_id,)).fetchone()
            return _shown(actor, dict(row), conn) if row else None

    @staticmethod
    def update_contract(contract_id: int, actor: Any = None, **data) -> bool:
        """Update a contract. With ``actor`` (HR or payroll), pay-structure
        fields go through ``pay_structure.assign`` (validated, salary
        re-derived) and a spine-point contract's salary can only change by
        an override with a reason."""
        if not data:
            return False
        if actor is not None:
            with get_connection() as conn:
                _require_contracts(actor, conn)
                current = conn.execute("SELECT * FROM staff_contracts WHERE contract_id = ?",
                                       (contract_id,)).fetchone()
            if not current:
                raise ValueError("Contract not found")
            current = dict(current)
            pay = {k: data.pop(k) for k in list(data) if k in ASSIGN_FIELDS}
            if 'salary' in data and current.get('spine_point') is not None \
                    and pay.get('spine_point', current.get('spine_point')) is not None:
                raise ValueError("This salary comes from the pay spine; set an override "
                                 "with a reason instead")
            if pay:
                from education_system.systems.university.domains.staff.domain.staff_hr import (
                    pay_structure,
                )
                pay_structure.assign(
                    actor, contract_id, grade_code=pay.get('grade_code'),
                    spine_point=pay.get('spine_point'), fte=pay.get('fte'),
                    pension_scheme=pay.get('pension_scheme'),
                    salary_override=pay.get('salary_override'),
                    override_reason=pay.get('salary_override_reason'))
            if not data:
                return True

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('contract_id', 'created_at', 'user_id'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(contract_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_contracts SET ' + ', '.join(fields) + ' WHERE contract_id = ?',
                values)
            if actor is not None:
                access.audit(conn, actor, 'contract.updated', entity='staff_contract',
                             entity_id=contract_id,
                             details={'fields': sorted(k for k in data)})
            log_activity('update', 'staff_contract', details={
                'contract_id': contract_id, 'updated_fields': list(data.keys())
            })
            return True

    @staticmethod
    def terminate_contract(contract_id: int, termination_date: str,
                          reason: str = None, terminated_by: str = None,
                          actor: Any = None) -> bool:
        """Terminate a contract (the person's pension membership ends the day
        after; payroll pays them up to the termination date)."""
        user_id_for_event: str | None = None
        with transaction() as conn:
            if actor is not None:
                terminated_by = _require_contracts(actor, conn)
            row = conn.execute(
                "SELECT user_id FROM staff_contracts WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()
            user_id_for_event = str(row[0]) if row and row[0] else None
            conn.execute('''
                UPDATE staff_contracts
                SET status = 'terminated', end_date = ?, updated_at = ?
                WHERE contract_id = ?
            ''', (termination_date, datetime.now().isoformat(), contract_id))
            if user_id_for_event:
                try:
                    left = (datetime.fromisoformat(termination_date[:10]) + timedelta(days=1)
                            ).date().isoformat()
                    conn.execute("UPDATE pension_memberships SET opted_out_on = ?, "
                                 "opt_out_reason = 'left employment' WHERE user_id = ? "
                                 "AND opted_out_on IS NULL", (left, user_id_for_event))
                except Exception:
                    logger.debug("pension membership not closed", exc_info=True)
            if actor is not None:
                access.audit(conn, actor, 'contract.terminated', subject=user_id_for_event,
                             entity='staff_contract', entity_id=contract_id,
                             details={'termination_date': termination_date, 'reason': reason})

            log_activity('update', 'staff_contract', details={
                'contract_id': contract_id,
                'action': 'terminated',
                'termination_date': termination_date,
                'reason': reason
            })

        # Cross-domain: publish staff.contract.ended so module
        # scheduling can flag any future slots taught by this staff
        # member as needing reassignment, and so cert_bus / email_bus
        # can notify line managers. Best-effort.
        try:
            from education_system.systems.university.infrastructure.event_bus import publish
            publish("staff.contract.ended",
                    contract_id=contract_id,
                    staff_id=user_id_for_event,
                    ends_on=termination_date,
                    reason=reason,
                    terminated_by=terminated_by)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        # Cross-domain: flag forward-dated module_schedule rows as
        # needing reassignment. Adds a nullable 'reassignment_needed'
        # column on first use; sets it for slots whose instructor
        # matches and which still run on or after the termination
        # date. Idempotent.
        if user_id_for_event:
            try:
                from education_system.systems.university.infrastructure.database.db import (
                    get_connection,
                )
                with get_connection() as conn2:
                    cols = {r[1] for r in conn2.execute(
                        "PRAGMA table_info(module_schedule)"
                    ).fetchall()}
                    if cols and 'reassignment_needed' not in cols:
                        try:
                            conn2.execute(
                                "ALTER TABLE module_schedule ADD COLUMN "
                                "reassignment_needed TEXT"
                            )
                        except Exception:
                            logger.debug("Suppressed exception", exc_info=True)
                    # instructor_id is instructors.id; the person is reached
                    # through instructors.staff_id -> staff.username, or the
                    # e-mail address shared with their login. A slot still
                    # runs after the date unless its recurrence or year ended.
                    conn2.execute(
                        "UPDATE module_schedule "
                        "SET reassignment_needed = ? "
                        "WHERE instructor_id IN ("
                        "    SELECT i.id FROM instructors i "
                        "    LEFT JOIN staff s ON s.id = i.staff_id "
                        "    LEFT JOIN users u ON u.email = i.email "
                        "    WHERE s.username = ? OR u.username = ?) "
                        "  AND COALESCE(recurrence_until, '9999-12-31') >= ? "
                        "  AND (COALESCE(year, 0) = 0 OR year >= ?)",
                        (f"contract_ended:{contract_id}",
                         user_id_for_event, user_id_for_event,
                         termination_date[:10], int(termination_date[:4])),
                    )
                    conn2.commit()
            except Exception:
                logger.warning(
                    "Failed to flag workload reassignment after contract %s ended",
                    contract_id, exc_info=True)

        return True

    # ==================== CONTRACT AMENDMENTS ====================

    @staticmethod
    def create_amendment(contract_id: int, actor: Any = None, **data) -> int:
        """Create a contract amendment."""
        with transaction() as conn:
            if actor is not None:
                _require_contracts(actor, conn)
                access.audit(conn, actor, 'contract.amendment', entity='staff_contract',
                             entity_id=contract_id,
                             details={'field': data.get('field_changed')})
            cursor = conn.execute('''
                INSERT INTO contract_amendments (
                    contract_id, change_type, field_changed, old_value,
                    new_value, effective_date, reason, approved_by,
                    approved_date, status, document_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                contract_id,
                data.get('change_type'),
                data.get('field_changed'),
                data.get('old_value'),
                data.get('new_value'),
                data.get('effective_date'),
                data.get('reason'),
                data.get('approved_by'),
                data.get('approved_date'),
                data.get('status', 'pending'),
                data.get('document_path'),
            ))
            amendment_id = cursor.lastrowid
            log_activity('create', 'contract_amendment', details={
                'amendment_id': amendment_id, 'contract_id': contract_id
            })
            return amendment_id

    @staticmethod
    def get_contract_amendments(contract_id: int, actor: Any = None) -> List[Dict[str, Any]]:
        """Get all amendments for a contract."""
        with get_connection() as conn:
            _require_contracts(actor, conn)
            rows = conn.execute('''
                SELECT * FROM contract_amendments
                WHERE contract_id = ?
                ORDER BY effective_date DESC
            ''', (contract_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_amendment(amendment_id: int, approved_by: str, actor: Any = None) -> bool:
        """Approve a contract amendment (HR or payroll: ``actor``, else the
        person ``approved_by`` names; never an amendment to their own
        contract)."""
        with transaction() as conn:
            who = people.decider(actor, approved_by, conn)
            approved_by = _require_contracts(who, conn)
            row = conn.execute("SELECT c.user_id FROM contract_amendments a JOIN staff_contracts c "
                               "ON c.contract_id = a.contract_id WHERE a.amendment_id = ?",
                               (amendment_id,)).fetchone()
            if row and row[0] == approved_by:
                raise PermissionError("You cannot approve an amendment to your own contract")
            access.audit(conn, who, 'contract.amendment_approved',
                         subject=row[0] if row else None,
                         entity='contract_amendment', entity_id=amendment_id)
            conn.execute('''
                UPDATE contract_amendments
                SET status = 'approved', approved_by = ?, approved_date = ?
                WHERE amendment_id = ?
            ''', (approved_by, datetime.now().isoformat(), amendment_id))
            log_activity('update', 'contract_amendment', details={
                'amendment_id': amendment_id, 'action': 'approved'
            })
            return True

    # ==================== PROBATION MANAGEMENT ====================

    @staticmethod
    def create_probation_review(user_id: str, actor: Any = None, **data) -> int:
        """Create a probation review (HR, payroll or the line manager)."""
        with transaction() as conn:
            if actor is not None:
                user_id = access.staff_key(user_id, conn) or str(user_id)
                if not (can_manage_contracts(actor, conn)
                        or access.can_manage_person(actor, user_id, conn)):
                    raise PermissionError("Only their line manager or HR can review probation")
                data['reviewer_id'] = data.get('reviewer_id') or access.username_of(actor)
            cursor = conn.execute('''
                INSERT INTO probation_reviews (
                    user_id, contract_id, review_date, reviewer_id,
                    review_type, outcome, performance_rating, strengths,
                    areas_for_improvement, comments, objectives_met,
                    recommendation, next_review_date, probation_extended,
                    extension_reason, extension_end_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('contract_id'),
                data.get('review_date'),
                data.get('reviewer_id'),
                data.get('review_type', 'mid-probation'),
                data.get('outcome'),
                data.get('performance_rating'),
                data.get('strengths'),
                data.get('areas_for_improvement'),
                data.get('comments'),
                data.get('objectives_met'),
                data.get('recommendation'),
                data.get('next_review_date'),
                data.get('probation_extended', False),
                data.get('extension_reason'),
                data.get('extension_end_date'),
            ))
            review_id = cursor.lastrowid
            log_activity('create', 'probation_review', details={
                'review_id': review_id, 'user_id': user_id
            })
            return review_id

    @staticmethod
    def get_probation_reviews(user_id: str, actor: Any = None) -> List[Dict[str, Any]]:
        """Get all probation reviews for a user."""
        with get_connection() as conn:
            if actor is not None:
                user_id = _owner_view(actor, user_id, conn)
            rows = conn.execute('''
                SELECT * FROM probation_reviews
                WHERE user_id = ?
                ORDER BY review_date DESC
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_pending_probation_reviews(manager_id: str = None,
                                      actor: Any = None) -> List[Dict[str, Any]]:
        """Active contracts whose probation ends within 30 days or is overdue,
        and whose probation has not been decided (no final review passed or
        failed). ``manager_id``: only people below that manager in the line
        (or naming them on the contract). Each row carries ``days_left``
        (negative = overdue) and ``overdue``."""
        with get_connection() as conn:
            today = datetime.now().date().isoformat()
            query = '''
                SELECT c.*, TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, ''))
                       as employee_name,
                       CAST(julianday(c.probation_end_date) - julianday(?) AS INTEGER) AS days_left
                FROM staff_contracts c
                LEFT JOIN users u ON u.username = c.user_id
                WHERE c.status = 'active'
                AND c.probation_end_date IS NOT NULL AND c.probation_end_date != ''
                AND c.probation_end_date <= date(?, '+30 days')
                AND NOT EXISTS (
                    SELECT 1 FROM probation_reviews r
                    WHERE r.contract_id = c.contract_id AND r.review_type = 'final'
                      AND r.outcome IN ('pass', 'fail'))
            '''
            params = [today, today]
            query += ' ORDER BY c.probation_end_date ASC'
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
            if manager_id:
                manager = access.staff_key(manager_id, conn) or str(manager_id)
                team = set(access.reports_of(manager, conn, deep=True))
                rows = [r for r in rows
                        if r['user_id'] in team or (r.get('manager_id') or '') == manager]
            for r in rows:
                r['employee_name'] = r.get('employee_name') or r.get('user_id')
                r['overdue'] = (r.get('days_left') or 0) < 0
            if actor is not None and not can_manage_contracts(actor, conn):
                rows = [_shown(actor, r, conn) for r in
                        access.filter_people(rows, actor, conn=conn)]
            return rows

    @staticmethod
    def extend_probation(contract_id: int, new_end_date: str,
                        reason: str, extended_by: str, actor: Any = None) -> bool:
        """Extend a probation period."""
        with transaction() as conn:
            if actor is not None:
                extended_by = _require_contracts(actor, conn)
                access.audit(conn, actor, 'contract.probation_extended',
                             entity='staff_contract', entity_id=contract_id,
                             details={'new_end_date': new_end_date, 'reason': reason})
            conn.execute('''
                UPDATE staff_contracts
                SET probation_end_date = ?, updated_at = ?
                WHERE contract_id = ?
            ''', (new_end_date, datetime.now().isoformat(), contract_id))

            log_activity('update', 'staff_contract', details={
                'contract_id': contract_id,
                'action': 'probation_extended',
                'new_end_date': new_end_date,
                'reason': reason
            })
            return True

    @staticmethod
    def complete_probation(contract_id: int, outcome: str,
                          completed_by: str, actor: Any = None) -> bool:
        """Mark probation as completed."""
        with transaction() as conn:
            if actor is not None:
                completed_by = _require_contracts(actor, conn)
                access.audit(conn, actor, 'contract.probation_completed',
                             entity='staff_contract', entity_id=contract_id,
                             details={'outcome': outcome})
            # Clear probation end date to indicate completion
            conn.execute('''
                UPDATE staff_contracts
                SET probation_end_date = NULL, updated_at = ?
                WHERE contract_id = ?
            ''', (datetime.now().isoformat(), contract_id))

            log_activity('update', 'staff_contract', details={
                'contract_id': contract_id,
                'action': 'probation_completed',
                'outcome': outcome
            })
            return True

    # ==================== RENEWAL ALERTS ====================

    @staticmethod
    def _create_renewal_alerts(conn, contract_id: int, end_date: str, user_id: str):
        """Create renewal alerts for a contract (internal method)."""
        end_dt = datetime.fromisoformat(end_date)
        alerts = [
            (90, '90_day_warning'),
            (60, '60_day_warning'),
            (30, '30_day_warning'),
            (14, '14_day_warning'),
            (7, '7_day_warning'),
        ]

        for days, alert_type in alerts:
            alert_date = (end_dt - timedelta(days=days)).isoformat()
            try:
                conn.execute('''
                    INSERT INTO contract_renewal_alerts
                    (contract_id, alert_type, alert_date, days_before_expiry, recipient_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (contract_id, alert_type, alert_date, days, user_id))
            except Exception:
                # Table may not exist in minimal test schemas; ignore gracefully.
                return

    @staticmethod
    def get_pending_renewal_alerts() -> List[Dict[str, Any]]:
        """Get all pending renewal alerts that need to be sent."""
        with get_connection() as conn:
            today = datetime.now().date().isoformat()
            rows = conn.execute('''
                SELECT a.*, c.user_id, c.job_title, c.department, c.end_date
                FROM contract_renewal_alerts a
                JOIN staff_contracts c ON a.contract_id = c.contract_id
                WHERE a.sent = 0
                AND a.alert_date <= ?
                AND c.status = 'active'
                ORDER BY a.alert_date ASC
            ''', (today,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def mark_alert_sent(alert_id: int) -> bool:
        """Mark a renewal alert as sent."""
        with transaction() as conn:
            conn.execute('''
                UPDATE contract_renewal_alerts
                SET sent = 1, sent_date = ?
                WHERE alert_id = ?
            ''', (datetime.now().isoformat(), alert_id))
            return True

    @staticmethod
    def get_expiring_contracts(days_ahead: int = 90, days: int = None,
                               actor: Any = None) -> List[Dict[str, Any]]:
        """Get contracts expiring within the specified number of days."""
        if days is not None:
            days_ahead = days
        with get_connection() as conn:
            _require_contracts(actor, conn)
            today = datetime.now().date().isoformat()
            future = (datetime.now().date() + timedelta(days=days_ahead)).isoformat()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='staff_profiles'"
            )
            has_profiles = cursor.fetchone() is not None

            if has_profiles:
                rows = conn.execute('''
                    SELECT c.*, p.employee_id, p.bio as employee_name
                    FROM staff_contracts c
                    LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                    WHERE c.status = 'active'
                    AND c.end_date IS NOT NULL
                    AND c.end_date BETWEEN ? AND ?
                    ORDER BY c.end_date ASC
                ''', (today, future)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT c.*
                    FROM staff_contracts c
                    WHERE c.status = 'active'
                    AND c.end_date IS NOT NULL
                    AND c.end_date BETWEEN ? AND ?
                    ORDER BY c.end_date ASC
                ''', (today, future)).fetchall()
            return [dict(row) for row in rows]

    # ==================== REPORTING ====================

    @staticmethod
    def get_contract_statistics(actor: Any = None) -> Dict[str, Any]:
        """Get contract statistics."""
        with get_connection() as conn:
            _require_contracts(actor, conn)
            stats = {}

            # Total active contracts
            row = conn.execute('''
                SELECT COUNT(*) as count FROM staff_contracts WHERE status = 'active'
            ''').fetchone()
            stats['total_active'] = row['count'] if row else 0

            # By contract type
            rows = conn.execute('''
                SELECT contract_type, COUNT(*) as count
                FROM staff_contracts
                WHERE status = 'active'
                GROUP BY contract_type
            ''').fetchall()
            stats['by_type'] = {row['contract_type']: row['count'] for row in rows}

            # Expiring soon (30 days)
            today = datetime.now().date().isoformat()
            future_30 = (datetime.now().date() + timedelta(days=30)).isoformat()
            row = conn.execute('''
                SELECT COUNT(*) as count
                FROM staff_contracts
                WHERE status = 'active'
                AND end_date BETWEEN ? AND ?
            ''', (today, future_30)).fetchone()
            stats['expiring_30_days'] = row['count'] if row else 0

            # In probation
            row = conn.execute('''
                SELECT COUNT(*) as count
                FROM staff_contracts
                WHERE status = 'active'
                AND probation_end_date IS NOT NULL
                AND probation_end_date >= ?
            ''', (today,)).fetchone()
            stats['in_probation'] = row['count'] if row else 0

            return stats

    @staticmethod
    def search_contracts(search_term: str = None, department: str = None,
                        contract_type: str = None, status: str = 'active',
                        actor: Any = None) -> List[Dict[str, Any]]:
        """Search contracts with filters (a manager finds their reports'
        contracts without pay; anyone else only their own)."""
        with get_connection() as conn:
            query = '''
                SELECT c.*, p.employee_id
                FROM staff_contracts c
                LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                WHERE 1=1
            '''
            params = []

            if status:
                query += ' AND c.status = ?'
                params.append(status)

            if department:
                query += ' AND c.department = ?'
                params.append(department)

            if contract_type:
                query += ' AND c.contract_type = ?'
                params.append(contract_type)

            if search_term:
                query += ''' AND (c.user_id LIKE ? OR c.job_title LIKE ?
                            OR p.employee_id LIKE ?)'''
                search_pattern = f'%{search_term}%'
                params.extend([search_pattern, search_pattern, search_pattern])

            query += ' ORDER BY c.start_date DESC'
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
            if actor is not None and not can_manage_contracts(actor, conn):
                rows = [_shown(actor, r, conn) for r in
                        access.filter_people(rows, actor, conn=conn)]
            return rows
