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

from education_system.university_system.infrastructure.database.db import (
    get_connection, transaction,
)

logger = logging.getLogger("graduation_ceremony")


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
        from education_system.university_system.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.university_system.infrastructure.email.email_service import (
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

        if send_confirmation and stud:
            display_map = {
                'going':       'Going',
                'not_going':   'Not Going',
                'interested':  'Interested',
                'pending':     'Pending',
            }
            status_msg_map = {
                'going':      "Your seat (and guest tickets) are reserved. We'll be in touch with practical details closer to the day.",
                'not_going':  "We've recorded that you won't be attending. The University will arrange in-absentia conferral; your parchment will be posted to you.",
                'interested': "Thanks for letting us know — please firm up your RSVP before the deadline so seats can be allocated.",
                'pending':    "Your RSVP is logged as pending; please confirm before the deadline.",
            }
            _send_ceremony_email('events/rsvp_confirmation', stud['email'], {
                'recipient_name':       stud['name'],
                'event_name':           ceremony['ceremony_name'],
                'event_date':           ceremony['ceremony_date'],
                'start_time':           ceremony['ceremony_time'],
                'end_time':             '(see programme)',
                'location':             ceremony['venue'],
                'rsvp_status_display':  display_map[rsvp_status],
                'num_guests':           num_guests,
                'rsvp_recorded_on':     datetime.now().strftime('%Y-%m-%d %H:%M'),
                'event_id':             f"GRAD-{ceremony_id}",
                'status_specific_message': status_msg_map[rsvp_status],
            })
        return rsvp_id

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

    @staticmethod
    def create_order(ceremony_id: int, student_id: str,
                     gown_size: str = "", hood_subject: str = "",
                     hat_size: str = "", supplier: str = "",
                     collection_slot: str = "") -> int:
        with transaction() as conn:
            cur = conn.execute(
                """INSERT INTO ceremony_gown_orders
                       (ceremony_id, student_id, gown_size, hood_subject,
                        hat_size, supplier, collection_slot)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(ceremony_id, student_id) DO UPDATE SET
                       gown_size       = excluded.gown_size,
                       hood_subject    = excluded.hood_subject,
                       hat_size        = excluded.hat_size,
                       supplier        = excluded.supplier,
                       collection_slot = excluded.collection_slot""",
                (ceremony_id, student_id, gown_size, hood_subject,
                 hat_size, supplier, collection_slot),
            )
            row = conn.execute(
                "SELECT order_id FROM ceremony_gown_orders "
                "WHERE ceremony_id = ? AND student_id = ?",
                (ceremony_id, student_id),
            ).fetchone()
            return row['order_id'] if row else (cur.lastrowid or 0)

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
