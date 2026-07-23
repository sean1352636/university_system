"""Deposit interest accrual.

Long-held deposits earn interest while they sit on the balance sheet at 2510
Tenant Deposits Held. UK statute doesn't mandate that ASTs pay deposit interest
to the tenant, but the data should still capture it because:

  • DPS Custodial pays interest to whoever the scheme rules say (often retained).
  • DPS Insured / MyDeposits / TDS leave the deposit with the landlord; disputes
    over earned interest are common on long stays.
  • Scotland and several non-UK jurisdictions DO require tenant interest credit.

Per-assignment policy field decides who the accrued interest belongs to:

  'Tenant'   — credited to the student at refund (added to refund_amount)
  'Landlord' — recognised as Other Income (4300) when the refund posts
  'Scheme'   — tracked for transparency but the scheme handles payout off-platform

Accrual is simple daily: amount = principal × (rate/100) × days / 365. Each run
slices from `deposit_interest_last_accrual_date` (or first deposit date) to
today, writes an audit row, and bumps the running total. Idempotent: if the
last accrual date is today, nothing happens.
"""

import datetime as _dt

from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_connection, generate_id, log_create, log_read,
)


INTEREST_POLICIES = ['Tenant', 'Landlord', 'Scheme']


def _held_deposit_for(cursor, assignment_id):
    cursor.execute('''
        SELECT COALESCE(SUM(amount), 0)
        FROM payments
        WHERE source_type = 'housing'
          AND payment_type = 'Deposit'
          AND status = 'Completed'
          AND reference_id = ?
    ''', (assignment_id,))
    return float(cursor.fetchone()[0] or 0)


def _first_deposit_date(cursor, assignment_id):
    cursor.execute('''
        SELECT MIN(payment_date) FROM payments
        WHERE source_type = 'housing' AND payment_type = 'Deposit'
          AND status = 'Completed' AND reference_id = ?
    ''', (assignment_id,))
    row = cursor.fetchone()
    return row[0][:10] if row and row[0] else None


def _accrue_one(cursor, assignment_id, rate, last_accrual, today, principal, created_by):
    """Compute and persist a single accrual slice for an assignment.

    Returns (days, amount). If days <= 0 returns (0, 0.0) and writes nothing.
    """
    last_d = _dt.datetime.strptime(last_accrual, '%Y-%m-%d').date()
    today_d = _dt.datetime.strptime(today, '%Y-%m-%d').date()
    days = (today_d - last_d).days
    if days <= 0 or principal <= 0 or rate <= 0:
        return 0, 0.0
    amount = round(principal * (rate / 100.0) * days / 365.0, 2)
    if amount <= 0:
        return days, 0.0

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO housing_deposit_interest_accruals
        (accrual_id, assignment_id, period_start, period_end,
         principal, annual_rate, days, amount, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (generate_id('ACR'), assignment_id, last_accrual, today,
          principal, rate, days, amount, created_by, timestamp))

    cursor.execute('''
        UPDATE housing_assignments
        SET deposit_interest_accrued = COALESCE(deposit_interest_accrued, 0) + ?,
            deposit_interest_last_accrual_date = ?,
            updated_at = ?
        WHERE assignment_id = ?
    ''', (amount, today, timestamp, assignment_id))
    return days, amount


@log_create(module="housing", description="Accruing deposit interest")
def accrue_deposit_interest():
    """Run a one-shot accrual for every assignment with a held deposit + rate."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in.")
        return
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to accrue deposit interest.")
        return

    today = _dt.date.today().isoformat()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT assignment_id, deposit_interest_rate,
                   deposit_interest_last_accrual_date
            FROM housing_assignments
            WHERE COALESCE(deposit_interest_rate, 0) > 0
        ''')
        candidates = cursor.fetchall()
        if not candidates:
            print("No assignments with a deposit interest rate set. "
                  "Use Record Deposit Protection to capture a rate.")
            return

        total_amount = 0.0
        total_days = 0
        accrued_count = 0
        for aid, rate, last in candidates:
            principal = _held_deposit_for(cursor, aid)
            if principal <= 0:
                continue
            last_accrual = last or _first_deposit_date(cursor, aid)
            if not last_accrual:
                continue
            days, amount = _accrue_one(
                cursor, aid, float(rate), last_accrual, today, principal,
                created_by=auth.current_user['username'],
            )
            if amount > 0:
                accrued_count += 1
                total_amount += amount
                total_days += days
        conn.commit()

        if accrued_count == 0:
            print(f"No new interest to accrue (all up-to-date as of {today}).")
        else:
            print(f"\nAccrued interest on {accrued_count} assignment(s) through {today}.")
            print(f"  Total days slice (sum): {total_days}")
            print(f"  Total interest:         £{total_amount:,.2f}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()


@log_read(module="housing", description="Viewing deposit interest accruals")
def view_interest_accruals():
    """Show running interest totals plus per-period audit slices."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in.")
        return
    if not (auth.check_permission('manage_accommodations')
            or auth.check_permission('view_accommodations')):
        print("You don't have permission to view interest accruals.")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
                   a.deposit_interest_rate, a.deposit_interest_policy,
                   COALESCE(a.deposit_interest_accrued, 0),
                   a.deposit_interest_last_accrual_date
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            WHERE COALESCE(a.deposit_interest_rate, 0) > 0
               OR COALESCE(a.deposit_interest_accrued, 0) > 0
            ORDER BY a.assignment_id
        ''')
        rows = cursor.fetchall()
        if not rows:
            print("No deposit interest tracked yet.")
            return

        print("\nDeposit Interest — Per-Assignment Totals")
        print("=" * 70)
        grand = 0.0
        for aid, sid, first, last, rate, policy, accrued, last_date in rows:
            held = _held_deposit_for(cursor, aid)
            grand += float(accrued or 0)
            print(f"\n  {first} {last} ({sid}) — assignment {aid}")
            print(f"    Held: £{held:,.2f} | Rate: {rate or 0:.2f}% | "
                  f"Policy: {policy or '(unset)'}")
            print(f"    Accrued: £{accrued or 0:,.2f} | Last run: {last_date or '(never)'}")
        print("-" * 70)
        print(f"  Total accrued across assignments: £{grand:,.2f}")

        show_detail = input("\nShow per-period audit slices? (y/n): ").strip().lower()
        if show_detail == 'y':
            cursor.execute('''
                SELECT assignment_id, period_start, period_end,
                       principal, annual_rate, days, amount
                FROM housing_deposit_interest_accruals
                ORDER BY assignment_id, period_start
            ''')
            slices = cursor.fetchall()
            if not slices:
                print("No accrual rows recorded.")
                return
            print("\nAccrual Slices:")
            current_aid = None
            for aid, ps, pe, p, r, d, a in slices:
                if aid != current_aid:
                    current_aid = aid
                    print(f"\n  {aid}:")
                print(f"    {ps} → {pe}  £{p:,.2f} @ {r:.2f}% × {d}d = £{a:,.2f}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()


def accrued_interest_for(cursor, assignment_id):
    """Helper used by the refund flow."""
    cursor.execute(
        'SELECT COALESCE(deposit_interest_accrued, 0), deposit_interest_policy '
        'FROM housing_assignments WHERE assignment_id = ?',
        (assignment_id,),
    )
    row = cursor.fetchone()
    if not row:
        return 0.0, None
    return float(row[0] or 0), row[1]
