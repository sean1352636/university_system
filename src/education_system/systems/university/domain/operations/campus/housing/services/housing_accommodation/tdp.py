"""UK Tenancy Deposit Protection (TDP) tracking for housing assignments.

Under the Housing Act 2004, deposits taken on Assured Shorthold Tenancies must
be protected in a government-approved scheme (DPS, MyDeposits, TDS) within 30
days of receipt, and the prescribed information given to the tenant in the same
window. Failure exposes the landlord to penalties of 1–3× the deposit and bars
section 21 possession.

Halls of residence let to students by their own institution are excluded from
AST status (Housing Act 1988, Schedule 1 paragraph 8) and therefore exempt —
the data model captures this with an explicit `tdp_exempt_reason` rather than
leaving fields NULL, so audits can distinguish "exempt by design" from "not
yet done".

Tracked per assignment:
  tdp_scheme                 — DPS / MyDeposits / TDS / Exempt
  tdp_scheme_reference       — scheme-issued certificate or deposit ID
  tdp_protected_at           — date deposit was lodged with the scheme
  tdp_prescribed_info_sent_at — date prescribed info reached the tenant
  tdp_deadline               — first deposit receipt + 30 days
  tdp_exempt_reason          — when scheme = 'Exempt'
"""

import datetime as _dt

from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import common as _common
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_connection, log_create, log_read,
)


TDP_SCHEMES = ['DPS', 'MyDeposits', 'TDS', 'Exempt']
TDP_STATUTORY_DAYS = 30


def _first_deposit_date(cursor, assignment_id):
    """Return ISO date of the earliest Completed deposit payment for an assignment."""
    cursor.execute('''
        SELECT MIN(payment_date)
        FROM payments
        WHERE source_type = 'housing'
          AND payment_type = 'Deposit'
          AND status = 'Completed'
          AND reference_id = ?
    ''', (assignment_id,))
    row = cursor.fetchone()
    return (row[0] or None) if row else None


def _compute_deadline(payment_date_iso):
    """Return ISO date for payment_date + 30 days."""
    if not payment_date_iso:
        return None
    dt = _dt.datetime.strptime(payment_date_iso[:10], '%Y-%m-%d').date()
    return (dt + _dt.timedelta(days=TDP_STATUTORY_DAYS)).isoformat()


def set_deposit_deadline_if_unset(cursor, assignment_id, payment_date_iso):
    """Stamp tdp_deadline on the assignment from the first deposit if absent.

    Called from record_payment when a Deposit row is written. Idempotent —
    leaves existing deadline alone so a later deposit row doesn't slide it.
    """
    cursor.execute(
        'SELECT tdp_deadline FROM housing_assignments WHERE assignment_id = ?',
        (assignment_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    if row[0]:
        return row[0]
    deadline = _compute_deadline(payment_date_iso)
    if not deadline:
        return None
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'UPDATE housing_assignments SET tdp_deadline = ?, updated_at = ? '
        'WHERE assignment_id = ?',
        (deadline, timestamp, assignment_id),
    )
    return deadline


def _classify(scheme, protected_at, info_sent_at, deadline):
    """Return ('Protected'|'Pending'|'Overdue'|'Exempt'|'Unprotected', days_remaining_or_overdue)."""
    if scheme == 'Exempt':
        return 'Exempt', None
    if scheme and protected_at and info_sent_at:
        return 'Protected', None
    today = _dt.date.today()
    if deadline:
        deadline_d = _dt.datetime.strptime(deadline[:10], '%Y-%m-%d').date()
        delta = (deadline_d - today).days
        if delta < 0:
            return 'Overdue', delta  # negative = days past
        return 'Pending', delta
    return 'Unprotected', None


@log_create(module="housing", description="Recording deposit protection")
def record_deposit_protection():
    """Interactive TDP entry against an assignment that has a held deposit."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in.")
        return
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to record deposit protection.")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
                   r.room_number, b.building_name,
                   SUM(p.amount) AS deposit_held,
                   a.tdp_scheme, a.tdp_deadline
            FROM payments p
            JOIN housing_assignments a ON p.reference_id = a.assignment_id
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE p.source_type = 'housing'
              AND p.payment_type = 'Deposit'
              AND p.status = 'Completed'
            GROUP BY a.assignment_id
            ORDER BY a.assignment_id
        ''')
        rows = cursor.fetchall()
        if not rows:
            print("No assignments with completed deposit payments.")
            return

        print("\nAssignments with Held Deposits:")
        print("=" * 70)
        for i, r in enumerate(rows, 1):
            scheme_text = r[7] or 'Unprotected'
            deadline_text = f" (deadline {r[8]})" if r[8] else ""
            print(f"{i}. {r[2]} {r[3]} ({r[1]}) — Room {r[4]}, {r[5]}")
            print(f"   Held: £{r[6]:,.2f} | Scheme: {scheme_text}{deadline_text}")

        while True:
            try:
                pick = int(input("\nSelect assignment (0 to cancel): "))
            except ValueError:
                print("Enter a valid number.")
                continue
            if pick == 0:
                return
            if 1 <= pick <= len(rows):
                selected = rows[pick - 1]
                break
            print(f"Enter 1–{len(rows)} or 0.")

        assignment_id = selected[0]

        print("\nSelect TDP Scheme:")
        for i, s in enumerate(TDP_SCHEMES, 1):
            print(f"  {i}. {s}")
        while True:
            try:
                sc = int(input("Scheme number: "))
            except ValueError:
                print("Enter a valid number.")
                continue
            if 1 <= sc <= len(TDP_SCHEMES):
                scheme = TDP_SCHEMES[sc - 1]
                break
            print(f"Enter 1–{len(TDP_SCHEMES)}.")

        if scheme == 'Exempt':
            print("\nCommon exemption: 'Education Schedule 1' — halls let by the "
                  "institution to its own students are excluded from AST status.")
            reason = input("Exemption reason: ").strip()
            if not reason:
                print("Exemption reason required — aborting.")
                return
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE housing_assignments
                SET tdp_scheme = 'Exempt',
                    tdp_exempt_reason = ?,
                    tdp_scheme_reference = NULL,
                    tdp_protected_at = NULL,
                    tdp_prescribed_info_sent_at = NULL,
                    updated_at = ?
                WHERE assignment_id = ?
            ''', (reason, timestamp, assignment_id))
            conn.commit()
            print("Marked Exempt with reason recorded.")
            return

        scheme_ref = input(f"{scheme} certificate / deposit reference: ").strip()
        if not scheme_ref:
            print("Reference required — aborting.")
            return

        while True:
            protected_at = input("Date protected (YYYY-MM-DD, blank = today): ").strip()
            if not protected_at:
                protected_at = _dt.date.today().isoformat()
                break
            try:
                _dt.datetime.strptime(protected_at, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date.")

        while True:
            info_sent_at = input("Prescribed info sent to tenant on (YYYY-MM-DD, blank = today): ").strip()
            if not info_sent_at:
                info_sent_at = _dt.date.today().isoformat()
                break
            try:
                _dt.datetime.strptime(info_sent_at, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date.")

        # Recompute / backfill the deadline from the first deposit if missing.
        first_dep = _first_deposit_date(cursor, assignment_id)
        deadline = _compute_deadline(first_dep) if first_dep else None

        # Warn if past deadline.
        if deadline:
            d = _dt.datetime.strptime(deadline[:10], '%Y-%m-%d').date()
            p = _dt.datetime.strptime(protected_at, '%Y-%m-%d').date()
            if p > d:
                days_late = (p - d).days
                print(f"\nWARNING: protection date is {days_late} day(s) past the "
                      f"30-day statutory deadline ({deadline}). Penalty exposure "
                      f"of 1–3× the deposit applies under Housing Act 2004 s.214.")

        # Optional: interest rate + policy. Lets the accrual engine track
        # interest on the held deposit and the refund flow apply it correctly.
        interest_rate = 0.0
        interest_policy = None
        set_int = input("\nTrack interest on this deposit? (y/n): ").strip().lower()
        if set_int == 'y':
            while True:
                raw = input("  Annual interest rate (%, e.g. 2.5): ").strip()
                try:
                    interest_rate = float(raw)
                    if interest_rate < 0:
                        print("  Rate cannot be negative.")
                        continue
                    break
                except ValueError:
                    print("  Enter a number.")
            policies = ['Tenant', 'Landlord', 'Scheme']
            print("  Interest policy:")
            for i, p in enumerate(policies, 1):
                print(f"    {i}. {p}")
            while True:
                try:
                    pp = int(input("  Choice: "))
                    if 1 <= pp <= len(policies):
                        interest_policy = policies[pp - 1]
                        break
                except ValueError:
                    pass
                print(f"  Enter 1–{len(policies)}.")

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE housing_assignments
            SET tdp_scheme = ?,
                tdp_scheme_reference = ?,
                tdp_protected_at = ?,
                tdp_prescribed_info_sent_at = ?,
                tdp_deadline = COALESCE(tdp_deadline, ?),
                tdp_exempt_reason = NULL,
                deposit_interest_rate = COALESCE(?, deposit_interest_rate),
                deposit_interest_policy = COALESCE(?, deposit_interest_policy),
                updated_at = ?
            WHERE assignment_id = ?
        ''', (scheme, scheme_ref, protected_at, info_sent_at, deadline,
              interest_rate if set_int == 'y' else None,
              interest_policy,
              timestamp, assignment_id))
        conn.commit()
        print(f"\nDeposit protection recorded for assignment {assignment_id}.")
        print(f"  Scheme: {scheme}  Ref: {scheme_ref}")
        print(f"  Protected: {protected_at}  Prescribed info: {info_sent_at}")
        if set_int == 'y':
            print(f"  Interest: {interest_rate:.2f}% (policy: {interest_policy})")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()


@log_read(module="housing", description="TDP compliance report")
def tdp_compliance_report():
    """Show TDP state for every assignment with a held deposit."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in.")
        return
    if not (auth.check_permission('manage_accommodations')
            or auth.check_permission('view_accommodations')):
        print("You don't have permission to view the TDP report.")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
                   r.room_number, b.building_name,
                   SUM(CASE WHEN p.status = 'Completed' THEN p.amount ELSE 0 END) AS held,
                   a.tdp_scheme, a.tdp_scheme_reference,
                   a.tdp_protected_at, a.tdp_prescribed_info_sent_at,
                   a.tdp_deadline, a.tdp_exempt_reason,
                   MIN(p.payment_date)
            FROM housing_assignments a
            JOIN payments p ON p.reference_id = a.assignment_id
                            AND p.source_type = 'housing'
                            AND p.payment_type = 'Deposit'
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            GROUP BY a.assignment_id
            ORDER BY a.tdp_deadline
        ''')
        rows = cursor.fetchall()
        if not rows:
            print("No deposit payments on record — nothing to report.")
            return

        buckets = {'Protected': [], 'Pending': [], 'Overdue': [],
                   'Exempt': [], 'Unprotected': []}
        for r in rows:
            (aid, sid, first, last, room, bld, held, scheme, ref,
             protected_at, info_sent_at, deadline, exempt_reason, first_dep) = r
            held = float(held or 0)
            if held <= 0:
                continue  # fully refunded — outside compliance window
            state, delta = _classify(scheme, protected_at, info_sent_at, deadline)
            buckets[state].append({
                'aid': aid, 'sid': sid, 'name': f"{first} {last}",
                'room': room, 'bld': bld, 'held': held,
                'scheme': scheme, 'ref': ref,
                'protected_at': protected_at, 'info_sent_at': info_sent_at,
                'deadline': deadline, 'exempt_reason': exempt_reason,
                'first_dep': first_dep, 'delta': delta,
            })

        print("\nTenancy Deposit Protection — Compliance Report")
        print("=" * 70)
        order = ['Overdue', 'Pending', 'Unprotected', 'Protected', 'Exempt']
        for state in order:
            items = buckets[state]
            if not items:
                continue
            print(f"\n{state} ({len(items)}):")
            for it in items:
                line = f"  {it['name']} ({it['sid']}) — Room {it['room']}, {it['bld']}"
                print(line)
                print(f"    Assignment {it['aid']} | Held: £{it['held']:,.2f}")
                if state == 'Protected':
                    print(f"    {it['scheme']} ref {it['ref']} — protected {it['protected_at']}, info sent {it['info_sent_at']}")
                elif state == 'Pending':
                    print(f"    Deadline {it['deadline']} — {it['delta']} day(s) remaining")
                elif state == 'Overdue':
                    print(f"    Deadline {it['deadline']} — {-it['delta']} day(s) PAST DEADLINE — penalty exposure")
                elif state == 'Exempt':
                    print(f"    Exempt: {it['exempt_reason'] or '(reason not recorded)'}")
                else:
                    print(f"    First deposit {it['first_dep']} — deadline not set; "
                          f"re-run init or record protection now")

        n_breaches = len(buckets['Overdue'])
        if n_breaches:
            print(f"\n{n_breaches} assignment(s) past the 30-day deadline. "
                  f"Each carries 1–3× deposit penalty exposure under HA 2004 s.214.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
