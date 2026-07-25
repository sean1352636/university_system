"""
Graduation Ceremony Operations

Adds the operational layer on top of ``GraduationAuditManager``:

* CeremonyManager       — schedule ceremonies (date/time/venue/capacity/cohort).
* RsvpManager           — graduand RSVP + guest-ticket allocation.
* GownOrderManager      — robing / gown orders, supplier + collection slot.
* SeatPlanManager       — auto-assign seats with accessibility markers, export CSV.
* StageScriptManager    — generate the announcer's stage script with name
                          pronunciation, in announcement order.

All operations are best-effort on emails: the new email templates
(``student_lifecycle/graduation``, ``events/rsvp_confirmation``) are fired
where it makes sense, but a send failure never blocks the data write.
"""

from __future__ import annotations

import csv
import io
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from education_system.systems.university.infrastructure.database.db import (
    get_connection, transaction,
)

logger = logging.getLogger("graduation_ceremony")

# Where graduand-attendance notifications are sent. Falls back to the
# configured outgoing sender address, then to a sensible default, so the admin
# always receives the RSVP roll-up even on a fresh install.
DEFAULT_GRADUATION_OFFICE_EMAIL = "graduation.office@university.ac.uk"


def _admin_email() -> str:
    """Resolve the graduation-office / admin recipient for roll-up emails."""
    try:
        from education_system.systems.university.infrastructure.email.config import config
        addr = (config.get('graduation_office_email')
                or config.get('sender_email') or '').strip()
        if addr:
            return addr
    except Exception:
        logger.debug("could not read email config for admin address", exc_info=True)
    return DEFAULT_GRADUATION_OFFICE_EMAIL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lookup_student(conn, student_id: str) -> Dict[str, str]:
    """Return ``{'name','email','course'}`` for *student_id*, with safe defaults."""
    try:
        row = conn.execute(
            "SELECT TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) AS name,"
            "       COALESCE(email_address,'') AS email,"
            "       COALESCE(course,'')        AS course"
            "  FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        if row:
            return {
                'name':   (row['name'] or '').strip() or student_id,
                'email':  (row['email'] or '').strip(),
                'course': (row['course'] or '').strip(),
            }
    except sqlite3.Error:
        logger.exception("student lookup failed sid=%s", student_id)
    return {'name': student_id, 'email': '', 'course': ''}


def _send_ceremony_email(template_name: str, recipient: str,
                        vars_: Dict[str, Any]) -> bool:
    """Best-effort dispatch via the shared email infrastructure."""
    if not recipient:
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
    subject, body = render_template(template_name, vars_)
    if not subject or not body:
        return False
    try:
        send_email(recipient_email=recipient, subject=subject, body=body)
        return True
    except Exception:
        logger.exception("send_email failed template=%s recipient=%s",
                         template_name, recipient)
        return False


def _seat_for_student(ceremony_id: int, student_id: str) -> Optional[Dict[str, Any]]:
    """Return the seat-plan row for *student_id*, or ``None`` if not yet seated."""
    try:
        for s in SeatPlanManager.list_plan(ceremony_id):
            if str(s.get('student_id')) == str(student_id):
                return s
    except Exception:
        logger.debug("seat lookup failed sid=%s", student_id, exc_info=True)
    return None


def _seat_info_text(seat: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    """Render ``(seat_info, accessibility_line)`` for the confirmation email."""
    if not seat:
        return ("Your seat has not been allocated yet — you'll be notified once "
                "the seat plan is published.", "")
    seat_info = (f"Section {seat.get('section')} · Row {seat.get('row_label')} "
                 f"· Seat {seat.get('seat_number')}")
    access_line = ("This is an accessibility seat with step-free stage access."
                   if seat.get('is_accessibility') else "")
    return seat_info, access_line


def _build_admin_rsvp_vars(ceremony: Dict[str, Any],
                           recorded_student: str,
                           recorded_status: str) -> Dict[str, Any]:
    """Assemble the variables for the admin attendance roll-up email."""
    ceremony_id = ceremony['ceremony_id']
    cap = CeremonyManager.capacity_summary(ceremony_id)
    going = RsvpManager.list_rsvps(ceremony_id, status='going')

    seat_by_sid = {}
    try:
        for s in SeatPlanManager.list_plan(ceremony_id):
            seat_by_sid[str(s.get('student_id'))] = (
                f"{s.get('row_label')}-{s.get('seat_number')} ({s.get('section')})")
    except Exception:
        logger.debug("seat plan lookup failed for admin summary", exc_info=True)

    lines = []
    for r in going:
        name = (r.get('student_name') or '').strip() or r['student_id']
        seat = seat_by_sid.get(str(r['student_id']), '(unassigned)')
        guests = int(r.get('num_guests') or 0)
        lines.append(f"  • {name} ({r['student_id']}) — seat {seat}; guests: {guests}")
    attendee_list = "\n".join(lines) if lines else "  (no graduands going yet)"

    return {
        'ceremony_name':     ceremony['ceremony_name'],
        'ceremony_date':     ceremony['ceremony_date'],
        'ceremony_time':     ceremony['ceremony_time'],
        'venue':             ceremony['venue'],
        'total_going':       cap['graduands'],
        'total_guests':      cap['guests'],
        'total_seats_taken': cap['total'],
        'capacity':          cap['capacity'],
        'attendee_list':     attendee_list,
        'recorded_student':  recorded_student,
        'recorded_status':   recorded_status,
    }


# ---------------------------------------------------------------------------
# CeremonyManager
# ---------------------------------------------------------------------------

class CeremonyManager:
    """Create / update / list graduation ceremonies."""

    @staticmethod
    def create_ceremony(ceremony_name: str, ceremony_date: str,
                        ceremony_time: str, venue: str, capacity: int,
                        cohort_filter: str = "",
                        rsvp_deadline: str = "",
                        guest_tickets_per_graduand: int = 2,
                        notes: str = "") -> int:
        with transaction() as conn:
            cur = conn.execute(
                """INSERT INTO graduation_ceremonies (
                       ceremony_name, ceremony_date, ceremony_time, venue,
                       capacity, cohort_filter, rsvp_deadline,
                       guest_tickets_per_graduand, notes
                   ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (ceremony_name, ceremony_date, ceremony_time, venue,
                 int(capacity), cohort_filter, rsvp_deadline or None,
                 int(guest_tickets_per_graduand), notes),
            )
            return cur.lastrowid

    @staticmethod
    def update_ceremony(ceremony_id: int, **fields) -> bool:
        allowed = {
            'ceremony_name', 'ceremony_date', 'ceremony_time', 'venue',
            'capacity', 'cohort_filter', 'rsvp_deadline',
            'guest_tickets_per_graduand', 'status', 'notes',
        }
        sets, params = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                params.append(v)
        if not sets:
            return False
        params.append(ceremony_id)
        with transaction() as conn:
            cur = conn.execute(
                f"UPDATE graduation_ceremonies SET {', '.join(sets)} WHERE ceremony_id = ?",
                params,
            )
            return cur.rowcount > 0

    @staticmethod
    def complete_ceremony(ceremony_id: int) -> Tuple[int, int]:
        """Mark a ceremony 'completed' and congratulate every graduand who
        attended (RSVP'd 'going').

        Returns ``(emails_sent, graduands_total)``. The notification is
        idempotent: if the ceremony is already 'completed' no emails are
        re-sent (returns ``(0, 0)``). Email dispatch is best-effort and never
        raises — a mail failure must not stop the ceremony being closed."""
        ceremony = CeremonyManager.get_ceremony(ceremony_id)
        if not ceremony:
            return (0, 0)

        already_completed = (ceremony.get('status') or '').strip().lower() == 'completed'
        CeremonyManager.update_ceremony(ceremony_id, status='completed')
        if already_completed:
            return (0, 0)

        return CeremonyManager.notify_graduands_completed(ceremony_id)

    @staticmethod
    def notify_graduands_completed(ceremony_id: int) -> Tuple[int, int]:
        """Email a congratulations / next-steps message to every graduand who
        RSVP'd 'going' for *ceremony_id*. Returns ``(sent, total_graduands)``.

        Best-effort: per-recipient failures are logged and skipped; the method
        never raises."""
        ceremony = CeremonyManager.get_ceremony(ceremony_id)
        if not ceremony:
            return (0, 0)

        graduands = RsvpManager.list_rsvps(ceremony_id, status='going')
        sent = 0
        for r in graduands:
            email = (r.get('email') or '').strip()
            if not email:
                continue
            name = (r.get('student_name') or '').strip() or str(r.get('student_id', ''))
            ok = _send_ceremony_email(
                'student_lifecycle/graduation_ceremony_completed', email, {
                    'student_name':  name,
                    'ceremony_name': ceremony['ceremony_name'],
                    'ceremony_date': ceremony['ceremony_date'],
                    'ceremony_time': ceremony['ceremony_time'],
                    'venue':         ceremony['venue'],
                    'course':        (r.get('course') or '').strip() or 'N/A',
                })
            if ok:
                sent += 1
        logger.info("ceremony %s completed: %d/%d graduand emails sent",
                    ceremony_id, sent, len(graduands))
        return (sent, len(graduands))

    @staticmethod
    def get_ceremony(ceremony_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM graduation_ceremonies WHERE ceremony_id = ?",
                (ceremony_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_ceremonies(status: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM graduation_ceremonies WHERE status = ? "
                    "ORDER BY ceremony_date, ceremony_time",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM graduation_ceremonies "
                    "ORDER BY ceremony_date DESC, ceremony_time"
                ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_venues() -> List[Dict[str, Any]]:
        """Return active buildings for the venue picker.

        Each entry is ``{building_id, building_name, building_code, label}``.
        Sourced from the shared ``buildings`` table so ceremony venues stay
        consistent with the rest of the system. Best-effort: returns an empty
        list if the table is absent (e.g. facilities schema not initialised)."""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT building_id, building_name, building_code "
                    "  FROM buildings "
                    " WHERE COALESCE(is_active, 1) = 1 "
                    " ORDER BY building_name"
                ).fetchall()
        except sqlite3.Error:
            logger.debug("buildings table unavailable for venue picker",
                         exc_info=True)
            return []
        venues = []
        for r in rows:
            name = (r['building_name'] or '').strip()
            code = (r['building_code'] or '').strip()
            if not name:
                continue
            venues.append({
                'building_id':   r['building_id'],
                'building_name': name,
                'building_code': code,
                'label':         f"{name} ({code})" if code else name,
            })
        return venues

    @staticmethod
    def capacity_summary(ceremony_id: int) -> Dict[str, int]:
        """Return seats consumed: ``{graduands, guests, total, capacity, free}``.
        Only RSVPs with status 'going' are counted."""
        with get_connection() as conn:
            cap_row = conn.execute(
                "SELECT capacity FROM graduation_ceremonies WHERE ceremony_id = ?",
                (ceremony_id,),
            ).fetchone()
            counts = conn.execute(
                """SELECT COUNT(*) AS graduands,
                          COALESCE(SUM(num_guests),0) AS guests
                     FROM ceremony_rsvps
                    WHERE ceremony_id = ? AND rsvp_status = 'going'""",
                (ceremony_id,),
            ).fetchone()
        capacity = int(cap_row['capacity']) if cap_row else 0
        graduands = int(counts['graduands']) if counts else 0
        guests    = int(counts['guests']) if counts else 0
        total     = graduands + guests
        return {
            'graduands': graduands,
            'guests':    guests,
            'total':     total,
            'capacity':  capacity,
            'free':      max(0, capacity - total),
        }


# ---------------------------------------------------------------------------
# RsvpManager
# ---------------------------------------------------------------------------

class RsvpManager:
    """Record graduand RSVPs and allocate guest tickets."""

    @staticmethod
    def record_rsvp(ceremony_id: int, student_id: str,
                    rsvp_status: str, num_guests: int = 0,
                    accessibility_notes: str = "",
                    name_pronunciation: str = "",
                    send_confirmation: bool = True) -> int:
        """Upsert an RSVP. *rsvp_status* in {going, not_going, interested, pending}.

        Enforces the ceremony's ``guest_tickets_per_graduand`` cap and rejects
        any RSVP that would push the venue past its overall capacity."""
        rsvp_status = (rsvp_status or '').strip().lower()
        if rsvp_status not in {'going', 'not_going', 'interested', 'pending'}:
            raise ValueError(f"invalid rsvp_status: {rsvp_status}")

        ceremony = CeremonyManager.get_ceremony(ceremony_id)
        if not ceremony:
            raise ValueError(f"ceremony {ceremony_id} not found")

        max_guests = int(ceremony.get('guest_tickets_per_graduand') or 0)
        if num_guests < 0:
            num_guests = 0
        if num_guests > max_guests:
            raise ValueError(
                f"requested {num_guests} guests, limit is {max_guests} per graduand"
            )

        # Capacity gate — only matters when this RSVP would consume seats.
        if rsvp_status == 'going':
            cap = CeremonyManager.capacity_summary(ceremony_id)
            # Subtract this student's existing seats (if any) so they aren't
            # double-counted on update.
            existing = RsvpManager._existing_seats(ceremony_id, student_id)
            available = cap['free'] + existing
            seats_requested = 1 + num_guests
            if seats_requested > available:
                raise ValueError(
                    f"ceremony at capacity: {available} seats available, "
                    f"{seats_requested} requested"
                )

        with transaction() as conn:
            cur = conn.execute(
                """INSERT INTO ceremony_rsvps
                       (ceremony_id, student_id, rsvp_status, num_guests,
                        accessibility_notes, name_pronunciation)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(ceremony_id, student_id) DO UPDATE SET
                       rsvp_status         = excluded.rsvp_status,
                       num_guests          = excluded.num_guests,
                       accessibility_notes = excluded.accessibility_notes,
                       name_pronunciation  = excluded.name_pronunciation,
                       recorded_at         = datetime('now')""",
                (ceremony_id, student_id, rsvp_status, num_guests,
                 accessibility_notes, name_pronunciation),
            )
            rsvp_id = cur.lastrowid
            if not rsvp_id:
                # ON CONFLICT path: pull the existing row's id.
                row = conn.execute(
                    "SELECT rsvp_id FROM ceremony_rsvps "
                    "WHERE ceremony_id = ? AND student_id = ?",
                    (ceremony_id, student_id),
                ).fetchone()
                rsvp_id = row['rsvp_id'] if row else 0

            # Look up the student for the confirmation email — same conn so
            # callers can override the lookup table on a test DB.
            if send_confirmation:
                stud = _lookup_student(conn, student_id)
            else:
                stud = None

        if send_confirmation:
            RsvpManager._send_rsvp_notifications(
                ceremony, student_id, stud, rsvp_status, num_guests)
        return rsvp_id

    # display name for each RSVP status, shared by the emails.
    _STATUS_DISPLAY = {
        'going':      'Going',
        'not_going':  'Not Going',
        'interested': 'Interested',
        'pending':    'Pending',
    }

    @staticmethod
    def _send_rsvp_notifications(ceremony: Dict[str, Any], student_id: str,
                                 stud: Optional[Dict[str, str]],
                                 rsvp_status: str, num_guests: int) -> None:
        """Best-effort: confirm to the graduand (with seat + ceremony detail)
        and send the Graduation Office an updated attendance roll-up.

        Never raises — a mail failure must not roll back the RSVP write."""
        ceremony_id = ceremony['ceremony_id']
        status_display = RsvpManager._STATUS_DISPLAY.get(rsvp_status, rsvp_status)

        # --- graduand confirmation -------------------------------------
        if stud and stud.get('email'):
            seat = _seat_for_student(ceremony_id, student_id)
            seat_info, access_line = _seat_info_text(seat)
            _send_ceremony_email(
                'student_lifecycle/graduation_rsvp_confirmation', stud['email'], {
                    'student_name':        stud['name'],
                    'ceremony_name':       ceremony['ceremony_name'],
                    'ceremony_date':       ceremony['ceremony_date'],
                    'ceremony_time':       ceremony['ceremony_time'],
                    'venue':               ceremony['venue'],
                    'rsvp_status_display': status_display,
                    'num_guests':          num_guests,
                    'rsvp_recorded_on':    datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'seat_info':           seat_info,
                    'accessibility_line':  access_line,
                })

        # --- admin / graduation-office roll-up -------------------------
        recorded_name = (stud['name'] if stud else student_id)
        _send_ceremony_email(
            'student_lifecycle/graduation_admin_rsvp', _admin_email(),
            _build_admin_rsvp_vars(
                ceremony, f"{recorded_name} ({student_id})", status_display))

    @staticmethod
    def _existing_seats(ceremony_id: int, student_id: str) -> int:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT rsvp_status, num_guests FROM ceremony_rsvps
                    WHERE ceremony_id = ? AND student_id = ?""",
                (ceremony_id, student_id),
            ).fetchone()
        if not row or row['rsvp_status'] != 'going':
            return 0
        return 1 + int(row['num_guests'] or 0)

    @staticmethod
    def list_rsvps(ceremony_id: int,
                   status: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            q = ("SELECT r.*, "
                 "       TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')) AS student_name,"
                 "       COALESCE(s.email_address,'') AS email,"
                 "       COALESCE(s.course,'')        AS course"
                 "  FROM ceremony_rsvps r"
                 "  LEFT JOIN students s ON s.student_id = r.student_id"
                 " WHERE r.ceremony_id = ?")
            params = [ceremony_id]
            if status:
                q += " AND r.rsvp_status = ?"
                params.append(status.lower())
            q += " ORDER BY student_name, r.student_id"
            rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GownOrderManager
# ---------------------------------------------------------------------------

class GownOrderManager:
    """Robing / gown orders per graduand."""

    GOWN_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL']
    HAT_SIZES  = ['54', '55', '56', '57', '58', '59', '60', '61', '62', '63']

    # Hire pricing (GBP). The gown is mandatory to cross the stage; the hood
    # and mortarboard (hat) are charged only when ordered.
    GOWN_HIRE_FEE = 45.00
    HOOD_FEE      = 15.00
    HAT_FEE       = 10.00

    PAYMENT_METHODS = ['cash', 'card', 'student_finance_account']
    PAYMENT_METHOD_DISPLAY = {
        'cash':                    'Cash',
        'card':                    'Card',
        'student_finance_account': 'Student Finance Account',
    }

    @staticmethod
    def quote(gown_size: str = "", hood_subject: str = "",
              hat_size: str = "") -> float:
        """Price a gown order from the chosen items. Returns the total in GBP."""
        total = 0.0
        if (gown_size or '').strip():
            total += GownOrderManager.GOWN_HIRE_FEE
        if (hood_subject or '').strip():
            total += GownOrderManager.HOOD_FEE
        if (hat_size or '').strip():
            total += GownOrderManager.HAT_FEE
        return round(total, 2)

    @staticmethod
    def create_order(ceremony_id: int, student_id: str,
                     gown_size: str = "", hood_subject: str = "",
                     hat_size: str = "", supplier: str = "",
                     collection_slot: str = "") -> int:
        cost = GownOrderManager.quote(gown_size, hood_subject, hat_size)
        with transaction() as conn:
            cur = conn.execute(
                """INSERT INTO ceremony_gown_orders
                       (ceremony_id, student_id, gown_size, hood_subject,
                        hat_size, supplier, collection_slot, cost)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(ceremony_id, student_id) DO UPDATE SET
                       gown_size       = excluded.gown_size,
                       hood_subject    = excluded.hood_subject,
                       hat_size        = excluded.hat_size,
                       supplier        = excluded.supplier,
                       collection_slot = excluded.collection_slot,
                       cost            = excluded.cost""",
                (ceremony_id, student_id, gown_size, hood_subject,
                 hat_size, supplier, collection_slot, cost),
            )
            row = conn.execute(
                "SELECT order_id FROM ceremony_gown_orders "
                "WHERE ceremony_id = ? AND student_id = ?",
                (ceremony_id, student_id),
            ).fetchone()
            return row['order_id'] if row else (cur.lastrowid or 0)

    @staticmethod
    def get_order(order_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM ceremony_gown_orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def process_payment(order_id: int, payment_method: str,
                        processed_by: str = "system",
                        send_receipt: bool = True) -> Dict[str, Any]:
        """Take payment for a gown order by cash, card or student finance account.

        For ``student_finance_account`` the student's available credit balance
        (``student_credits``) is located and the order cost is deducted from it;
        the payment is recorded against the finance ``payments`` table and posted
        to the general ledger. Cash/card payments are recorded the same way but
        without touching the credit balance.

        Returns a summary dict; raises ``ValueError`` on a bad method, an
        already-paid order, or insufficient finance-account funds.
        """
        method = (payment_method or '').strip().lower()
        if method not in GownOrderManager.PAYMENT_METHODS:
            raise ValueError(f"invalid payment method: {payment_method}")

        order = GownOrderManager.get_order(order_id)
        if not order:
            raise ValueError(f"gown order {order_id} not found")
        if (order.get('payment_status') or 'unpaid') == 'paid':
            raise ValueError("this gown order has already been paid for")

        student_id = order['student_id']
        amount = float(order.get('cost') or 0) or GownOrderManager.quote(
            order.get('gown_size', ''), order.get('hood_subject', ''),
            order.get('hat_size', ''))
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        reference = f"GOWN-{order_id}"

        # All money movement happens atomically in one transaction.
        with transaction() as conn:
            balance_remaining: Optional[float] = None
            if method == 'student_finance_account':
                balance_remaining = GownOrderManager._charge_finance_account(
                    conn, student_id, amount, now)

            cur = conn.execute(
                """INSERT INTO payments
                       (student_id, amount, currency, payment_method,
                        transaction_id, payment_date, status, notes,
                        created_by, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (student_id, amount, 'GBP',
                 GownOrderManager.PAYMENT_METHOD_DISPLAY[method],
                 reference, now[:10], 'completed',
                 f"Graduation gown order {reference}", processed_by, now),
            )
            payment_id = cur.lastrowid

            conn.execute(
                """UPDATE ceremony_gown_orders
                      SET payment_method    = ?,
                          payment_status    = 'paid',
                          payment_reference = ?,
                          finance_payment_id = ?,
                          paid_at           = ?,
                          cost              = ?
                    WHERE order_id = ?""",
                (method, reference, payment_id, now, amount, order_id),
            )

        # Post to the general ledger (best-effort, never blocks the receipt).
        try:
            from education_system.systems.university.domain.finance.ledger import (
                notify_ledger,
            )
            notify_ledger('payment', payment_id, posted_by='graduation_gown')
        except Exception:
            logger.warning("ledger hook failed for gown payment %s", payment_id,
                           exc_info=True)

        if send_receipt:
            GownOrderManager._send_receipt(
                order, method, amount, reference, now, balance_remaining)

        return {
            'order_id':          order_id,
            'payment_id':        payment_id,
            'amount':            amount,
            'payment_method':    method,
            'reference':         reference,
            'balance_remaining': balance_remaining,
        }

    @staticmethod
    def _charge_finance_account(conn, student_id: str, amount: float,
                                now: str) -> float:
        """Deduct *amount* from the student's available credit balance (FIFO).

        Returns the remaining balance after the deduction. Raises ``ValueError``
        if the student has insufficient available funds."""
        credits = conn.execute(
            """SELECT credit_id, remaining_amount
                 FROM student_credits
                WHERE student_id = ? AND status = 'active' AND remaining_amount > 0
                  AND (expiry_date IS NULL OR expiry_date >= date('now'))
                ORDER BY created_at, credit_id""",
            (student_id,),
        ).fetchall()
        available = round(sum(float(c['remaining_amount']) for c in credits), 2)
        if available < amount:
            raise ValueError(
                f"insufficient student finance account balance: "
                f"£{available:.2f} available, £{amount:.2f} required"
            )

        to_charge = amount
        for c in credits:
            if to_charge <= 0:
                break
            rem = float(c['remaining_amount'])
            take = min(rem, to_charge)
            new_rem = round(rem - take, 2)
            conn.execute(
                """UPDATE student_credits
                      SET remaining_amount = ?,
                          status = CASE WHEN ? <= 0 THEN 'used' ELSE status END,
                          updated_at = ?
                    WHERE credit_id = ?""",
                (new_rem, new_rem, now, c['credit_id']),
            )
            to_charge = round(to_charge - take, 2)
        return round(available - amount, 2)

    @staticmethod
    def _send_receipt(order: Dict[str, Any], method: str, amount: float,
                      reference: str, now: str,
                      balance_remaining: Optional[float]) -> None:
        """Best-effort emailed receipt for a paid gown order."""
        with get_connection() as conn:
            stud = _lookup_student(conn, order['student_id'])
        if not stud.get('email'):
            return
        ceremony = CeremonyManager.get_ceremony(order['ceremony_id']) or {}
        balance_line = ''
        if balance_remaining is not None:
            balance_line = (f"Finance account balance remaining: "
                            f"£{balance_remaining:.2f}")
        _send_ceremony_email('finance/graduation_gown_receipt', stud['email'], {
            'student_name':           stud['name'],
            'ceremony_name':          ceremony.get('ceremony_name', ''),
            'ceremony_date':          ceremony.get('ceremony_date', ''),
            'gown_size':              order.get('gown_size', '') or '—',
            'hat_size':               order.get('hat_size', '') or '—',
            'hood_subject':           order.get('hood_subject', '') or '—',
            'cost':                   f"{amount:.2f}",
            'payment_method_display': GownOrderManager.PAYMENT_METHOD_DISPLAY[method],
            'payment_reference':      reference,
            'payment_date':           now,
            'balance_line':           balance_line,
        })

    @staticmethod
    def update_status(order_id: int, status: str) -> bool:
        if status not in {'ordered', 'arrived', 'collected', 'returned', 'cancelled'}:
            raise ValueError(f"invalid status: {status}")
        with transaction() as conn:
            cur = conn.execute(
                "UPDATE ceremony_gown_orders SET status = ? WHERE order_id = ?",
                (status, order_id),
            )
            return cur.rowcount > 0

    @staticmethod
    def list_orders(ceremony_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT o.*,
                          TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')) AS student_name
                     FROM ceremony_gown_orders o
                     LEFT JOIN students s ON s.student_id = o.student_id
                    WHERE o.ceremony_id = ?
                    ORDER BY student_name, o.student_id""",
                (ceremony_id,),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# SeatPlanManager
# ---------------------------------------------------------------------------

class SeatPlanManager:
    """Generate and export the seat plan for a ceremony.

    The auto-assign algorithm:

    * Pulls every ``rsvp_status = 'going'`` graduand for the ceremony.
    * Sorts alphabetically by surname so the announcer's script and the seat
      plan share the same order.
    * Drops any graduand with a non-empty ``accessibility_notes`` into the
      accessibility block (rows starting at ``ACC-1``); the rest fill the
      main block starting at ``A-1``.
    * Seats fill row-by-row up to ``seats_per_row``; the row label advances
      when full (A-1 ... A-12 then B-1 ...).
    """

    DEFAULT_SEATS_PER_ROW = 12

    @staticmethod
    def clear_assignments(ceremony_id: int) -> int:
        with transaction() as conn:
            cur = conn.execute(
                "DELETE FROM ceremony_seat_assignments WHERE ceremony_id = ?",
                (ceremony_id,),
            )
            return cur.rowcount

    @staticmethod
    def auto_assign(ceremony_id: int,
                    seats_per_row: int = DEFAULT_SEATS_PER_ROW,
                    accessibility_rows: int = 1) -> int:
        """Wipe and regenerate the seat plan. Returns number of seats assigned."""
        rsvps = RsvpManager.list_rsvps(ceremony_id, status='going')
        if not rsvps:
            SeatPlanManager.clear_assignments(ceremony_id)
            return 0

        def _surname(r: Dict[str, Any]) -> str:
            n = (r.get('student_name') or '').strip()
            if not n:
                return r.get('student_id', '')
            parts = n.split()
            return parts[-1].lower() if parts else n.lower()

        accessibility = sorted(
            [r for r in rsvps if (r.get('accessibility_notes') or '').strip()],
            key=_surname,
        )
        regular = sorted(
            [r for r in rsvps if not (r.get('accessibility_notes') or '').strip()],
            key=_surname,
        )

        assignments: List[Tuple] = []

        # Accessibility block — rows ACC-1, ACC-2 ...
        for i, r in enumerate(accessibility):
            row_idx = i // seats_per_row
            seat_no = (i % seats_per_row) + 1
            if row_idx >= accessibility_rows:
                # Overflow into regular block if accessibility rows fill up.
                regular.insert(0, r)
                continue
            assignments.append((
                ceremony_id, r['student_id'], 'ACC',
                f"ACC-{row_idx + 1}", seat_no, 1,
                r.get('accessibility_notes', ''),
            ))

        # Regular block — rows A-1, A-2 ... B-1 ... after 26 rows it wraps to AA-1.
        for i, r in enumerate(regular):
            row_idx = i // seats_per_row
            seat_no = (i % seats_per_row) + 1
            label = SeatPlanManager._row_label(row_idx)
            assignments.append((
                ceremony_id, r['student_id'], 'MAIN',
                label, seat_no, 0, '',
            ))

        with transaction() as conn:
            conn.execute(
                "DELETE FROM ceremony_seat_assignments WHERE ceremony_id = ?",
                (ceremony_id,),
            )
            conn.executemany(
                """INSERT INTO ceremony_seat_assignments
                       (ceremony_id, student_id, section, row_label,
                        seat_number, is_accessibility, notes)
                   VALUES (?,?,?,?,?,?,?)""",
                assignments,
            )
        return len(assignments)

    @staticmethod
    def _row_label(idx: int) -> str:
        """0 → A, 25 → Z, 26 → AA, 27 → AB, ..."""
        letters = ''
        n = idx
        while True:
            letters = chr(ord('A') + n % 26) + letters
            n = n // 26 - 1
            if n < 0:
                break
        return letters

    @staticmethod
    def list_plan(ceremony_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT a.section, a.row_label, a.seat_number,
                          a.is_accessibility, a.notes, a.student_id,
                          TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')) AS student_name,
                          COALESCE(s.course,'') AS course
                     FROM ceremony_seat_assignments a
                     LEFT JOIN students s ON s.student_id = a.student_id
                    WHERE a.ceremony_id = ?
                    ORDER BY a.section, a.row_label, a.seat_number""",
                (ceremony_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def export_csv(ceremony_id: int) -> str:
        """Return the seat plan as a CSV string ready to write to disk."""
        plan = SeatPlanManager.list_plan(ceremony_id)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([
            "Section", "Row", "Seat", "Student ID", "Student Name",
            "Course", "Accessibility", "Notes",
        ])
        for r in plan:
            writer.writerow([
                r.get('section', ''),
                r.get('row_label', ''),
                r.get('seat_number', ''),
                r.get('student_id', ''),
                r.get('student_name', ''),
                r.get('course', ''),
                'YES' if r.get('is_accessibility') else '',
                r.get('notes', ''),
            ])
        return out.getvalue()


# ---------------------------------------------------------------------------
# StageScriptManager
# ---------------------------------------------------------------------------

class StageScriptManager:
    """Generate the announcer's stage script in seat-plan order."""

    @staticmethod
    def build_script(ceremony_id: int,
                     include_pronunciation: bool = True) -> str:
        ceremony = CeremonyManager.get_ceremony(ceremony_id)
        if not ceremony:
            raise ValueError(f"ceremony {ceremony_id} not found")
        plan = SeatPlanManager.list_plan(ceremony_id)
        # We also need name_pronunciation, which lives on the RSVP row.
        pron_by_sid = {}
        for r in RsvpManager.list_rsvps(ceremony_id, status='going'):
            pron_by_sid[r['student_id']] = (r.get('name_pronunciation') or '').strip()

        lines: List[str] = []
        lines.append("=" * 70)
        lines.append(f" STAGE SCRIPT — {ceremony['ceremony_name']}")
        lines.append(f" {ceremony['ceremony_date']}  {ceremony['ceremony_time']}")
        lines.append(f" Venue: {ceremony['venue']}")
        lines.append("=" * 70)
        lines.append("")

        if not plan:
            lines.append("(no seated graduands — run the seat-plan generator first)")
            return "\n".join(lines)

        idx = 1
        last_section = None
        for r in plan:
            section = r.get('section', 'MAIN')
            if section != last_section:
                lines.append(f"\n— {section} block —\n")
                last_section = section
            name = (r.get('student_name') or '').strip() or r.get('student_id', '')
            course = (r.get('course') or '').strip()
            sid = r.get('student_id', '')
            pron = pron_by_sid.get(sid, '')

            row = f"{idx:>4}. [{r.get('row_label')}-{r.get('seat_number')}] {name}"
            if course:
                row += f" — {course}"
            if r.get('is_accessibility'):
                row += "   [ACCESSIBILITY — stage ramp]"
            lines.append(row)
            if include_pronunciation and pron:
                lines.append(f"      pron.: {pron}")
            idx += 1

        lines.append("")
        lines.append("=" * 70)
        lines.append(f" Total graduands to announce: {idx - 1}")
        lines.append("=" * 70)
        return "\n".join(lines)

    @staticmethod
    def export_name_pronunciation_csv(ceremony_id: int) -> str:
        """Standalone CSV of student id + name + pronunciation — easy to send
        to an external announcer who doesn't want the full script."""
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["Order", "Student ID", "Student Name",
                         "Course", "Pronunciation", "Accessibility"])
        plan = SeatPlanManager.list_plan(ceremony_id)
        pron_by_sid = {r['student_id']: (r.get('name_pronunciation') or '').strip()
                       for r in RsvpManager.list_rsvps(ceremony_id, status='going')}
        for i, r in enumerate(plan, start=1):
            writer.writerow([
                i,
                r.get('student_id', ''),
                (r.get('student_name') or '').strip(),
                (r.get('course') or '').strip(),
                pron_by_sid.get(r.get('student_id', ''), ''),
                'YES' if r.get('is_accessibility') else '',
            ])
        return out.getvalue()


__all__ = [
    'CeremonyManager', 'RsvpManager', 'GownOrderManager',
    'SeatPlanManager', 'StageScriptManager',
]
