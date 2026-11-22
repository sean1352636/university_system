"""
Leave Manager

Handles leave requests, balances, approvals,
leave types, and leave calendar functionality.

Everyone is keyed by username (``access.staff_key`` turns a legacy
``users.id`` into one). Requests count *working days* (the person's
working pattern less bank holidays and closures — ``leave_rules``), are
checked against the remaining balance and overlapping leave, and only
someone who may approve for the person (``access.can_approve_for``) can
approve, reject or cancel for them. Balances are allocated by the
entitlement rules (``entitlement``) the first time they are needed.
Sick leave is absence, not an allowance: a sick leave request becomes an
absence episode (``absence``); family leave is booked from its case
(``family_leave``).

Old call shapes still work: ``approve_request(rid, approver_id)`` takes
the approver's role from ``users``; pass ``actor=`` (an auth object or
user dict) to have the signed-in session checked instead.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr import entitlement
from education_system.systems.university.domains.staff.domain.staff_hr import leave_rules as lr
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


def _send_staff_hr_email(template_name: str, recipient_email: str,
                         vars_: Dict[str, Any]) -> bool:
    """Render ``staff_hr/<template_name>`` and dispatch best-effort.

    Skips silently when *recipient_email* is empty."""
    if not recipient_email:
        logger.debug("staff_hr/%s skipped: no recipient", template_name)
        return False
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False
    subject, body = render_template(f"staff_hr/{template_name}", vars_)
    if not subject or not body:
        logger.error("template render failed: staff_hr/%s", template_name)
        return False
    try:
        send_email(recipient_email=recipient_email, subject=subject, body=body)
        logger.info("sent staff_hr/%s to %s", template_name, recipient_email)
        return True
    except Exception:
        logger.exception("send_email failed staff_hr/%s recipient=%s",
                         template_name, recipient_email)
        return False


class LeaveManager:
    """Manager for leave requests and balances."""

    # ==================== LEAVE TYPES ====================

    @staticmethod
    def get_leave_types(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all leave types."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM leave_types WHERE is_active = 1
                    ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM leave_types ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_leave_type(leave_type_id: int) -> Optional[Dict[str, Any]]:
        """Get a leave type by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM leave_types WHERE leave_type_id = ?
            ''', (leave_type_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_leave_type(name: str, **data) -> int:
        """Create a new leave type."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO leave_types (
                    name, description, max_days_per_year,
                    requires_approval, is_paid, color_code, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                data.get('description'),
                data.get('max_days_per_year', 0),
                data.get('requires_approval', 1),
                data.get('is_paid', 1),
                data.get('color_code', '#3498db'),
                data.get('is_active', 1),
            ))
            leave_type_id = cursor.lastrowid
            log_activity('create', 'leave_type',
                        details={'leave_type_id': leave_type_id, 'name': name})
            return leave_type_id

    @staticmethod
    def update_leave_type(leave_type_id: int, **data) -> bool:
        """Update a leave type."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('leave_type_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(leave_type_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE leave_types SET ' + ', '.join(fields) + ' WHERE leave_type_id = ?',
                values)
            log_activity('update', 'leave_type',
                        details={'leave_type_id': leave_type_id})
            return True

    # ==================== LEAVE BALANCES ====================

    @staticmethod
    def get_balance(user_id: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Leave balances for a user and leave year (default: the current
        one; this and next year's are allocated by the entitlement rules
        when missing)."""
        with lr.write() as conn:
            key = _key(user_id, conn)
            current = lr.leave_year_of(None, conn)
            target = year or current
            if target in (current, current + 1):
                for t in conn.execute("SELECT leave_type_id FROM leave_types "
                                      "WHERE is_active = 1").fetchall():
                    if entitlement.is_balanced(t[0], conn):
                        entitlement.ensure_balance(key, t[0], target, conn)
            rows = conn.execute('''
                SELECT b.*, t.name as leave_type_name, t.color_code
                FROM leave_balances b
                JOIN leave_types t ON b.leave_type_id = t.leave_type_id
                WHERE b.user_id = ? AND b.year = ?
                ORDER BY t.name
            ''', (key, target)).fetchall()
            return [_with_remaining(dict(row), conn) for row in rows]

    @staticmethod
    def get_balance_for_type(user_id: str, leave_type_id: int,
                             year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get leave balance for a specific leave type."""
        with get_connection() as conn:
            lr.ensure(conn)
            key = _key(user_id, conn)
            row = conn.execute('''
                SELECT b.*, t.name as leave_type_name
                FROM leave_balances b
                JOIN leave_types t ON b.leave_type_id = t.leave_type_id
                WHERE b.user_id = ? AND b.leave_type_id = ? AND b.year = ?
            ''', (key, leave_type_id, year or lr.leave_year_of(None, conn))).fetchone()
            return _with_remaining(dict(row), conn) if row else None

    @staticmethod
    def allocate_balance(user_id: str, leave_type_id: int, year: int,
                         allocated_days: float, carried_over: float = 0,
                         actor: Any = None) -> int:
        """Set a balance by hand (kept by the daily recalculation). With
        ``actor`` it must be HR."""
        if actor is not None:
            return entitlement.set_manual(actor, user_id, leave_type_id, year,
                                          allocated_days, carried_over)['balance_id']
        with transaction() as conn:
            lr.ensure(conn)
            key = _key(user_id, conn)
            existing = conn.execute('''
                SELECT balance_id FROM leave_balances
                WHERE user_id = ? AND leave_type_id = ? AND year = ?
            ''', (key, leave_type_id, year)).fetchone()

            if existing:
                conn.execute('''
                    UPDATE leave_balances
                    SET allocated_days = ?, carried_over = ?, allocation_basis = 'manual',
                        updated_at = ?
                    WHERE balance_id = ?
                ''', (allocated_days, carried_over, datetime.now().isoformat(),
                      existing[0]))
                log_activity('update', 'leave_balance', user_id=key,
                            details={'balance_id': existing[0]})
                return existing[0]
            cursor = conn.execute('''
                INSERT INTO leave_balances (
                    user_id, leave_type_id, year,
                    allocated_days, used_days, carried_over, allocation_basis
                ) VALUES (?, ?, ?, ?, 0, ?, 'manual')
            ''', (key, leave_type_id, year, allocated_days, carried_over))
            balance_id = cursor.lastrowid
            log_activity('create', 'leave_balance', user_id=key,
                        details={'balance_id': balance_id})
            return balance_id

    @staticmethod
    def update_used_days(user_id: str, leave_type_id: int, year: int,
                         days_change: float) -> bool:
        """Update used days for a leave balance (add or subtract)."""
        with transaction() as conn:
            lr.ensure(conn)
            key = _key(user_id, conn)
            entitlement.ensure_balance(key, leave_type_id, year, conn)
            conn.execute('''
                UPDATE leave_balances
                SET used_days = used_days + ?, updated_at = ?
                WHERE user_id = ? AND leave_type_id = ? AND year = ?
            ''', (days_change, datetime.now().isoformat(),
                  key, leave_type_id, year))
            return True

    # ==================== LEAVE REQUESTS ====================

    @staticmethod
    def count_days(user_id: str, start_date: str, end_date: str,
                   start_half: bool = False, end_half: bool = False) -> float:
        """Working days a booking would use."""
        with get_connection() as conn:
            lr.ensure(conn)
            return lr.working_days(_key(user_id, conn), start_date, end_date, conn,
                                   start_half, end_half)

    @staticmethod
    def submit_request(user_id: str, leave_type_id: int, start_date: str,
                       end_date: str, **data) -> int:
        """Submit a leave request (``data``: reason, document_path,
        start_half, end_half, actor, allow_overlap). Returns the request id.

        Raises ValueError for no working days, an overlap with other
        leave or not enough balance; PermissionError when ``actor`` books
        for someone they cannot act for. A sick leave request is recorded
        as an absence episode (its booking's id is returned)."""
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        if end < start:
            raise ValueError("The end date is before the start date")
        actor = data.get('actor')
        with get_connection() as conn:
            lr.ensure(conn)
            key = _key(user_id, conn)
            if actor is not None and access.username_of(actor) != key and \
                    not access.can_manage_person(actor, key, conn):
                raise PermissionError("Only their line manager or HR can book leave for someone")
            rule = entitlement.rule_for(leave_type_id, conn)
            leave_type = conn.execute("SELECT * FROM leave_types WHERE leave_type_id = ?",
                                      (leave_type_id,)).fetchone()
            leave_type = dict(leave_type) if leave_type else None
        if not leave_type:
            raise ValueError("No such leave type")
        if rule['basis'] == 'absence':
            from education_system.systems.university.domains.staff.domain.staff_hr import absence
            episode_id = absence.record(actor or lr.actor_for(key), key, start_date, end_date,
                                        reason_category='Other',
                                        reason_detail=data.get('reason'),
                                        first_day_half=bool(data.get('start_half')))
            with get_connection() as conn:
                return conn.execute("SELECT leave_request_id FROM staff_absence_episodes "
                                    "WHERE episode_id = ?", (episode_id,)).fetchone()[0]
        if rule['basis'] == 'case':
            raise ValueError(f"{leave_type['name']} is booked through a family leave case")
        if not leave_type['is_active']:
            raise ValueError(f"{leave_type['name']} is no longer offered")
        start_half, end_half = bool(data.get('start_half')), bool(data.get('end_half'))
        with lr.write() as conn:
            by_year = lr.working_days_by_year(key, start, end, conn, start_half, end_half)
            total_days = round(sum(by_year.values()), 2)
            if total_days <= 0:
                raise ValueError("Those dates contain none of your working days")
            if not data.get('allow_overlap'):
                clash = _conflicts(conn, key, start_date, end_date)
                if clash:
                    c = clash[0]
                    raise ValueError(f"This overlaps your {c['leave_type_name']} from "
                                     f"{c['start_date']} to {c['end_date']} ({c['status']})")
            _check_balance(conn, key, leave_type_id, by_year, rule)
            auto = not leave_type['requires_approval']
            cursor = conn.execute('''
                INSERT INTO leave_requests (
                    user_id, leave_type_id, start_date, end_date,
                    total_days, working_days, start_half, end_half, reason, document_path,
                    status, approved_by, approved_date, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'leave', ?, ?)
            ''', (
                key, leave_type_id, start_date, end_date, total_days, total_days,
                int(start_half), int(end_half), data.get('reason'), data.get('document_path'),
                'approved' if auto else 'pending', 'automatic' if auto else None,
                lr.now() if auto else None, lr.now(), lr.now(),
            ))
            request_id = cursor.lastrowid
            if auto:
                _use(conn, key, leave_type_id, by_year, rule, +1)
                lr.publish_change(key, 'approved', start_date, end_date, leave_type_id, 'leave')
            access.audit(conn, actor or key, 'leave_requested', key, 'leave_requests',
                         request_id, {'days': total_days})
            log_activity('create', 'leave_request', user_id=key,
                        details={'request_id': request_id, 'days': total_days})
            if not auto:
                name = access.display_name(key, conn)
                for person in access.approvers_for(key, conn):
                    lr.mail(person, f"Leave request from {name}",
                            f"{name} has asked for {total_days:g} days of {leave_type['name']} "
                            f"from {start_date} to {end_date}. Please approve or reject it in "
                            "Staff HR > Leave > Pending Approvals.", actor)
            return request_id

    @staticmethod
    def get_request(request_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """Get a leave request by ID (with ``actor``: only one they may see)."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT r.*, t.name as leave_type_name, t.color_code
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                WHERE r.request_id = ?
            ''', (request_id,)).fetchone()
            if row and actor is not None and \
                    not access.can_view_person(actor, row['user_id'], conn):
                raise PermissionError("You cannot see this leave request")
            return dict(row) if row else None

    @staticmethod
    def get_requests(user_id: str, status: Optional[str] = None,
                     year: Optional[int] = None,
                     limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get leave requests for a user."""
        with get_connection() as conn:
            query = '''
                SELECT r.*, t.name as leave_type_name, t.color_code
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                WHERE r.user_id = ?
            '''
            params: list = [_key(user_id, conn)]

            if status:
                query += ' AND r.status = ?'
                params.append(status)

            if year:
                query += " AND strftime('%Y', r.start_date) = ?"
                params.append(str(year))

            query += ' ORDER BY r.created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_pending_approvals(approver_id: str,
                              department: Optional[str] = None,
                              actor: Any = None) -> List[Dict[str, Any]]:
        """Pending requests the approver may decide: anyone below them in
        the line, or anyone when they are HR (never their own)."""
        with get_connection() as conn:
            who = _actor(actor, approver_id, conn)
            query = '''
                SELECT r.*, t.name as leave_type_name, t.color_code,
                       p.department, p.job_title,
                       u.first_name, u.last_name, u.email
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                LEFT JOIN staff_profiles p ON r.user_id = p.user_id
                LEFT JOIN users u ON u.username = r.user_id
                WHERE r.status = 'pending'
            '''
            params: list = []
            if department:
                query += ' AND p.department = ?'
                params.append(department)
            query += ' ORDER BY r.created_at'
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
            return [r for r in rows if access.can_approve_for(who, r['user_id'], conn)]

    @staticmethod
    def approve_request(request_id: int, approver_id: str,
                        recipient_email: str = "",
                        staff_name: str = "", actor: Any = None) -> bool:
        """Approve a pending leave request (False when it is not pending).

        Raises PermissionError unless the approver may approve for the
        person, ValueError when the balance no longer covers it."""
        with lr.write() as conn:
            who = _actor(actor, approver_id, conn)
            approver = access.username_of(who)
            request = conn.execute('''
                SELECT * FROM leave_requests WHERE request_id = ? AND status = 'pending'
            ''', (request_id,)).fetchone()
            if not request:
                return False
            request = dict(request)
            user_id = request['user_id']
            if not access.can_approve_for(who, user_id, conn):
                raise PermissionError("You cannot approve leave for this person")
            rule = entitlement.rule_for(request['leave_type_id'], conn)
            by_year = lr.working_days_by_year(user_id, request['start_date'],
                                              request['end_date'], conn,
                                              bool(request.get('start_half')),
                                              bool(request.get('end_half')))
            _check_balance(conn, user_id, request['leave_type_id'], by_year, rule,
                           exclude_request=request_id)
            total_days = round(sum(by_year.values()), 2)
            conn.execute('''
                UPDATE leave_requests
                SET status = 'approved',
                    approved_by = ?,
                    approved_date = ?,
                    total_days = ?,
                    working_days = ?,
                    updated_at = ?
                WHERE request_id = ?
            ''', (approver, lr.now(), total_days, total_days, lr.now(), request_id))
            _use(conn, user_id, request['leave_type_id'], by_year, rule, +1)
            access.audit(conn, who, 'leave_approved', user_id, 'leave_requests', request_id)
            log_activity('approve', 'leave_request',
                        details={'request_id': request_id, 'approver': approver})
            lr.publish_change(user_id, 'approved', request['start_date'], request['end_date'],
                              request['leave_type_id'], 'leave')
            year = lr.leave_year_of(request['start_date'], conn)
            balance = conn.execute("SELECT * FROM leave_balances WHERE user_id = ? AND "
                                   "leave_type_id = ? AND year = ?",
                                   (user_id, request['leave_type_id'], year)).fetchone()
            leave_type = conn.execute("SELECT name FROM leave_types WHERE leave_type_id = ?",
                                      (request['leave_type_id'],)).fetchone()
            mail = {
                'staff_id':        user_id,
                'staff_name':      staff_name or access.display_name(user_id, conn),
                'request_id':      request_id,
                'leave_type':      (leave_type[0] if leave_type else '') or '(unspecified)',
                'start_date':      request['start_date'],
                'end_date':        request['end_date'],
                'total_days':      total_days,
                'approver':        approver,
                'approved_on':     datetime.now().date().isoformat(),
                'remaining_days':  entitlement.remaining(dict(balance)) if balance
                                   else '(see HR portal)',
            }
            address = recipient_email or access.email_of(user_id, conn) or ''
        # after the commit: the e-mail goes out on its own connection
        try:
            _send_staff_hr_email('leave_approved', address, mail)
        except Exception:
            logger.exception("leave-approval email dispatch failed rid=%s", request_id)
        return True

    @staticmethod
    def reject_request(request_id: int, approver_id: str, reason: str,
                       recipient_email: str = "",
                       staff_name: str = "", actor: Any = None) -> bool:
        """Reject a pending leave request (False when it is not pending)."""
        with lr.write() as conn:
            who = _actor(actor, approver_id, conn)
            approver = access.username_of(who)
            detail = conn.execute(
                """SELECT r.user_id, r.start_date, r.end_date, r.total_days,
                          COALESCE(lt.name, '') AS leave_type
                     FROM leave_requests r
                     LEFT JOIN leave_types lt ON lt.leave_type_id = r.leave_type_id
                    WHERE r.request_id = ? AND r.status = 'pending'""",
                (request_id,),
            ).fetchone()
            if not detail:
                return False
            if not access.can_approve_for(who, detail[0], conn):
                raise PermissionError("You cannot reject leave for this person")
            conn.execute('''
                UPDATE leave_requests
                SET status = 'rejected',
                    approved_by = ?,
                    approved_date = ?,
                    rejection_reason = ?,
                    updated_at = ?
                WHERE request_id = ? AND status = 'pending'
            ''', (approver, lr.now(), reason, lr.now(), request_id))
            access.audit(conn, who, 'leave_rejected', detail[0], 'leave_requests', request_id,
                         {'reason': reason})
            log_activity('reject', 'leave_request',
                        details={'request_id': request_id, 'approver': approver})
            mail = {
                'staff_id':         detail[0],
                'staff_name':       staff_name or access.display_name(detail[0], conn),
                'request_id':       request_id,
                'leave_type':       detail[4] or '(unspecified)',
                'start_date':       detail[1],
                'end_date':         detail[2],
                'total_days':       detail[3],
                'approver':         approver,
                'approved_on':      datetime.now().date().isoformat(),
                'rejection_reason': reason or '(no reason supplied)',
            }
            address = recipient_email or access.email_of(detail[0], conn) or ''
        try:
            _send_staff_hr_email('leave_rejected', address, mail)
        except Exception:
            logger.exception("leave-rejection email dispatch failed rid=%s", request_id)
        return True

    @staticmethod
    def cancel_request(request_id: int, user_id: str, actor: Any = None) -> bool:
        """Cancel a pending request, or approved leave that has not started
        (the days go back on the balance): the person themselves, or
        someone who approves for them."""
        with lr.write() as conn:
            who = _actor(actor, user_id, conn)
            me = access.username_of(who)
            request = conn.execute("SELECT * FROM leave_requests WHERE request_id = ?",
                                   (request_id,)).fetchone()
            if not request:
                return False
            request = dict(request)
            if (request.get('source') or 'leave') != 'leave':
                raise ValueError("Absence and family leave are changed from their own records")
            if request['user_id'] != me and not access.can_approve_for(who, request['user_id'],
                                                                        conn):
                return False
            started = lr.as_date(request['start_date']) <= lr.today()
            if request['status'] == 'approved' and not started:
                rule = entitlement.rule_for(request['leave_type_id'], conn)
                by_year = lr.working_days_by_year(request['user_id'], request['start_date'],
                                                  request['end_date'], conn,
                                                  bool(request.get('start_half')),
                                                  bool(request.get('end_half')))
                _use(conn, request['user_id'], request['leave_type_id'], by_year, rule, -1)
                lr.publish_change(request['user_id'], 'cancelled', request['start_date'],
                                  request['end_date'], request['leave_type_id'], 'leave')
            elif request['status'] != 'pending':
                return False
            conn.execute('''
                UPDATE leave_requests
                SET status = 'cancelled', cancelled_by = ?, updated_at = ?
                WHERE request_id = ?
            ''', (me, lr.now(), request_id))
            access.audit(conn, who, 'leave_cancelled', request['user_id'], 'leave_requests',
                         request_id)
            log_activity('cancel', 'leave_request', user_id=request['user_id'],
                        details={'request_id': request_id})
            if me != request['user_id']:
                lr.mail(request['user_id'], "Your leave has been cancelled",
                        f"Your leave from {request['start_date']} to {request['end_date']} was "
                        f"cancelled by {access.display_name(me, conn)}.", who)
            return True

    # ==================== LEAVE CALENDAR ====================

    @staticmethod
    def get_calendar(department: Optional[str] = None,
                     month: Optional[int] = None,
                     year: Optional[int] = None,
                     actor: Any = None) -> List[Dict[str, Any]]:
        """Approved leave overlapping a month. With ``actor``: their own
        department plus everyone they manage (HR: everyone). Absence shows
        as 'Absent' to anyone who may not see the person's record."""
        current_year = year or datetime.now().year
        current_month = month or datetime.now().month
        first = date(current_year, current_month, 1)
        last = (date(current_year + current_month // 12, current_month % 12 + 1, 1)
                - timedelta(days=1))

        with get_connection() as conn:
            lr.ensure(conn)
            query = '''
                SELECT r.*, t.name as leave_type_name, t.color_code,
                       p.department, u.first_name, u.last_name
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                LEFT JOIN staff_profiles p ON r.user_id = p.user_id
                LEFT JOIN users u ON u.username = r.user_id
                WHERE r.status = 'approved'
                  AND r.start_date <= ? AND r.end_date >= ?
            '''
            params: list = [last.isoformat(), first.isoformat()]

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            query += ' ORDER BY r.start_date'
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
            if actor is None:
                for r in rows:
                    if r.get('source') == 'absence':
                        r['leave_type_name'] = 'Absent'
                return rows
            if not access.is_hr(actor, conn):
                me = access.username_of(actor)
                mine = conn.execute("SELECT department FROM staff_profiles WHERE user_id = ?",
                                    (me,)).fetchone()
                team = set(access.visible_people(actor, conn) or [])
                rows = [r for r in rows if r['user_id'] in team or
                        (mine and mine[0] and r.get('department') == mine[0])]
            for r in rows:
                if r.get('source') in ('absence', 'family_leave') and \
                        not access.can_view_person(actor, r['user_id'], conn):
                    r['leave_type_name'] = 'Absent' if r['source'] == 'absence' else 'On leave'
            return rows

    @staticmethod
    def check_conflicts(user_id: str, start_date: str, end_date: str,
                        exclude_request_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Check for conflicting leave requests."""
        with get_connection() as conn:
            return _conflicts(conn, _key(user_id, conn), start_date, end_date,
                              exclude_request_id)

    # ==================== REPORTS ====================

    @staticmethod
    def get_leave_summary(department: Optional[str] = None,
                          year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get leave usage summary by department or overall."""
        with get_connection() as conn:
            lr.ensure(conn)
            query = '''
                SELECT p.department,
                       t.name as leave_type,
                       SUM(b.allocated_days) as total_allocated,
                       SUM(b.used_days) as total_used,
                       SUM(b.allocated_days + b.carried_over
                           - COALESCE(b.carry_over_expired, 0) - b.used_days
                           - COALESCE(b.bank_holiday_days, 0)) as total_remaining,
                       COUNT(DISTINCT b.user_id) as staff_count
                FROM leave_balances b
                JOIN leave_types t ON b.leave_type_id = t.leave_type_id
                LEFT JOIN staff_profiles p ON p.user_id = b.user_id
                WHERE b.year = ?
            '''
            params: list = [year or lr.leave_year_of(None, conn)]

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            query += ' GROUP BY p.department, t.name ORDER BY p.department, t.name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_balance_summary(year: Optional[int] = None) -> Dict[str, Dict[str, float]]:
        """Allocated, used and remaining days per leave type across everyone
        (the leave year's balances: :meth:`get_leave_summary` without the
        split by department)."""
        summary: Dict[str, Dict[str, float]] = {}
        for row in LeaveManager.get_leave_summary(year=year):
            totals = summary.setdefault(row['leave_type'], {
                'total_allocated': 0, 'total_used': 0, 'total_remaining': 0})
            for field in totals:
                totals[field] += row[field] or 0
        return summary

    @staticmethod
    def get_leave_summary_report(year: Optional[int] = None) -> Dict[str, int]:
        """How many leave requests start in a calendar year (default this
        one), by outcome."""
        wanted = str(year or date.today().year)
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT status, COUNT(*) FROM leave_requests
                WHERE substr(start_date, 1, 4) = ? GROUP BY status
            ''', (wanted,)).fetchall()
        counts = {r[0]: r[1] for r in rows}
        return {
            'year': int(wanted),
            'total_requests': sum(counts.values()),
            'approved': counts.get('approved', 0),
            'pending': counts.get('pending', 0),
            'rejected': counts.get('rejected', 0),
        }

    @staticmethod
    def get_usage_report(period: Optional[str] = None) -> Dict[str, Any]:
        """Approved leave taken in a month (``YYYY-MM``, default this one).
        A request spilling over the month counts its share of the days."""
        first, last, label = _month_bounds(period)
        by_type: Dict[str, float] = {}
        people_away = set()
        with get_connection() as conn:
            for row in _approved_leave(conn, first, last):
                days = _days_within(row, first, last)
                by_type[row['leave_type']] = by_type.get(row['leave_type'], 0) + days
                people_away.add(row['user_id'])
        return {
            'period': label,
            'total_days': round(sum(by_type.values()), 2),
            'employees_count': len(people_away),
            'by_type': {k: round(v, 2) for k, v in sorted(by_type.items())},
        }

    @staticmethod
    def get_absence_trends(months: int = 6) -> Dict[str, Any]:
        """Days of approved leave of every kind (sickness and family leave
        are recorded as leave requests too) in each of the last ``months``
        months, oldest first, and the monthly average."""
        today = date.today()
        index = today.year * 12 + today.month - 1
        labels = [f'{(index - back) // 12:04d}-{(index - back) % 12 + 1:02d}'
                  for back in range(months - 1, -1, -1)]
        monthly: Dict[str, float] = {}
        with get_connection() as conn:
            for label in labels:
                first, last, _ = _month_bounds(label)
                monthly[label] = round(sum(_days_within(row, first, last) for row in
                                           _approved_leave(conn, first, last)), 2)
        return {
            'monthly': monthly,
            'average': sum(monthly.values()) / len(monthly) if monthly else 0.0,
        }


# ==================== helpers ====================


def _month_bounds(period: Optional[str]) -> tuple:
    """``(first day, last day, YYYY-MM)`` of a month (default this one)."""
    try:
        first = (datetime.strptime(period.strip(), '%Y-%m').date() if period
                 else date.today().replace(day=1))
    except ValueError:
        raise ValueError("Period must be in the form YYYY-MM") from None
    after = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first.isoformat(), (after - timedelta(days=1)).isoformat(), first.strftime('%Y-%m')


def _approved_leave(conn, first: str, last: str) -> list:
    """Approved requests overlapping the two dates, with their type's name."""
    return conn.execute('''
        SELECT r.user_id, r.start_date, r.end_date, r.total_days, t.name AS leave_type
        FROM leave_requests r JOIN leave_types t ON r.leave_type_id = t.leave_type_id
        WHERE r.status = 'approved' AND r.start_date <= ? AND r.end_date >= ?
    ''', (last, first)).fetchall()


def _days_within(row, first: str, last: str) -> float:
    """A request's days falling between two dates, by its share of the
    calendar days it spans."""
    start = date.fromisoformat(str(row['start_date'])[:10])
    end = date.fromisoformat(str(row['end_date'])[:10])
    span = (end - start).days + 1
    overlap = (min(end, date.fromisoformat(last)) - max(start, date.fromisoformat(first))).days + 1
    if span <= 0 or overlap <= 0:
        return 0.0
    return float(row['total_days'] or 0) * overlap / span


def _key(user_id: Any, conn) -> str:
    """The username for whatever id a caller holds."""
    return access.staff_key(user_id, conn) or str(user_id)


def _actor(actor: Any, fallback: Any, conn) -> dict:
    """The deciding person: ``actor`` when given, else built from the id
    an old-style caller passed."""
    who = access.user_of(actor) if actor is not None else lr.actor_for(fallback, conn)
    if not who or not access.username_of(who):
        raise PermissionError("Please sign in")
    return who


def _with_remaining(row: dict, conn) -> dict:
    row['remaining_days'] = entitlement.remaining(row)
    pending = conn.execute(
        "SELECT COALESCE(SUM(COALESCE(working_days, total_days)), 0) FROM leave_requests "
        "WHERE user_id = ? AND leave_type_id = ? AND status = 'pending'",
        (row['user_id'], row['leave_type_id'])).fetchone()[0]
    row['pending_days'] = float(pending or 0)
    return row


def _conflicts(conn, key: str, start_date: str, end_date: str,
               exclude_request_id: Optional[int] = None) -> List[Dict[str, Any]]:
    query = '''
        SELECT r.*, t.name as leave_type_name
        FROM leave_requests r
        JOIN leave_types t ON r.leave_type_id = t.leave_type_id
        WHERE r.user_id = ?
          AND r.status IN ('pending', 'approved')
          AND r.start_date <= ?
          AND r.end_date >= ?
    '''
    params: list = [key, end_date, start_date]
    if exclude_request_id:
        query += ' AND r.request_id != ?'
        params.append(exclude_request_id)
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _check_balance(conn, key: str, leave_type_id: int, by_year: dict, rule: dict,
                   exclude_request: Optional[int] = None) -> None:
    """Raise ValueError when a balanced type has not got the days left
    (pending requests count against it too)."""
    if rule['basis'] not in entitlement.BALANCED or lr.setting('allow_negative_balance', conn):
        return
    for year, days in by_year.items():
        balance = entitlement.ensure_balance(key, leave_type_id, year, conn)
        if balance is None:
            continue
        y_start, y_end = lr.leave_year_bounds(year, conn)
        pending = 0.0
        for r in conn.execute("SELECT * FROM leave_requests WHERE user_id = ? AND "
                              "leave_type_id = ? AND status = 'pending' AND request_id != ? "
                              "AND start_date <= ? AND end_date >= ?",
                              (key, leave_type_id, exclude_request or -1, y_end.isoformat(),
                               y_start.isoformat())).fetchall():
            pending += lr.working_days_by_year(key, r['start_date'], r['end_date'], conn,
                                               bool(r['start_half']),
                                               bool(r['end_half'])).get(year, 0.0)
        left = entitlement.remaining(balance) - pending
        if days > left + 1e-9:
            raise ValueError(f"Not enough {rule.get('leave_type_name') or 'leave'} left in the "
                             f"{year} leave year: {days:g} days asked, {max(left, 0):g} "
                             "available (after pending requests)")


def _use(conn, key: str, leave_type_id: int, by_year: dict, rule: dict, sign: int) -> None:
    """Add (``sign`` 1) or give back (-1) days on the balance of each
    leave year a booking touches."""
    if rule['basis'] not in entitlement.BALANCED:
        return
    for year, days in by_year.items():
        entitlement.ensure_balance(key, leave_type_id, year, conn)
        conn.execute("UPDATE leave_balances SET used_days = MAX(0, used_days + ?), "
                     "updated_at = ? WHERE user_id = ? AND leave_type_id = ? AND year = ?",
                     (sign * days, lr.now(), key, leave_type_id, year))
