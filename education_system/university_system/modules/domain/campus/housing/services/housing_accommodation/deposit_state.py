"""Deposit lifecycle state machine.

The lifecycle of a held deposit was previously implicit — scattered across
`payments.status`, `housing_deposit_deductions.status`, and the deductions'
`acknowledgement_status`. That made "what stage is this deposit at?" a join
query and made retrospective audit painful.

This module makes the state explicit on `housing_assignments.deposit_state`
and writes every transition to `housing_deposit_state_log`.

States:
    Held                — deposit received, no deductions raised
    Deductions Proposed — at least one Proposed deduction exists
    Disputed            — at least one Proposed deduction is in Disputed status
    Refunded            — refund posted, no deductions consumed
    Partially Refunded  — refund posted with some deductions
    Forfeited           — deductions consumed the entire deposit

Terminal states are Refunded / Partially Refunded / Forfeited.
"""

from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_connection, generate_id, log_read,
)


HELD = 'Held'
DEDUCTIONS_PROPOSED = 'Deductions Proposed'
DISPUTED = 'Disputed'
REFUNDED = 'Refunded'
PARTIALLY_REFUNDED = 'Partially Refunded'
FORFEITED = 'Forfeited'

STATES = (HELD, DEDUCTIONS_PROPOSED, DISPUTED,
          REFUNDED, PARTIALLY_REFUNDED, FORFEITED)
TERMINAL = (REFUNDED, PARTIALLY_REFUNDED, FORFEITED)

# Allowed forward transitions. None on LHS means "from nothing" (initial).
ALLOWED = {
    None:                  {HELD},
    HELD:                  {DEDUCTIONS_PROPOSED, REFUNDED, FORFEITED},
    DEDUCTIONS_PROPOSED:   {DISPUTED, DEDUCTIONS_PROPOSED, REFUNDED,
                            PARTIALLY_REFUNDED, FORFEITED, HELD},
    DISPUTED:              {DEDUCTIONS_PROPOSED, DISPUTED,
                            REFUNDED, PARTIALLY_REFUNDED, FORFEITED},
}


class IllegalTransition(Exception):
    pass


def current_state(cursor, assignment_id):
    cursor.execute(
        'SELECT deposit_state FROM housing_assignments WHERE assignment_id = ?',
        (assignment_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def is_terminal(state):
    return state in TERMINAL


def transition(cursor, assignment_id, to_state, *, reason, actor, allow_idempotent=True):
    """Move an assignment's deposit to `to_state`, logging the change.

    Raises IllegalTransition if the move isn't permitted from the current state.
    If `allow_idempotent` and the assignment is already in to_state, this is a
    no-op (no log row). Returns the previous state (or None if first set).
    """
    if to_state not in STATES:
        raise IllegalTransition(f"Unknown state: {to_state!r}")

    prev = current_state(cursor, assignment_id)
    if prev == to_state:
        if allow_idempotent:
            return prev
        raise IllegalTransition(f"Already in {to_state!r}")
    if is_terminal(prev):
        raise IllegalTransition(
            f"{assignment_id} is in terminal state {prev!r}; cannot move to {to_state!r}"
        )

    allowed = ALLOWED.get(prev, set())
    if to_state not in allowed:
        raise IllegalTransition(
            f"Cannot transition {prev!r} → {to_state!r} for {assignment_id}. "
            f"Allowed: {sorted(allowed)}"
        )

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO housing_deposit_state_log
        (log_id, assignment_id, from_state, to_state, reason, actor, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (generate_id('STL'), assignment_id, prev, to_state, reason, actor, timestamp))
    cursor.execute('''
        UPDATE housing_assignments
        SET deposit_state = ?, updated_at = ?
        WHERE assignment_id = ?
    ''', (to_state, timestamp, assignment_id))
    return prev


def reconcile_from_deductions(cursor, assignment_id, *, actor='system'):
    """Recompute the right non-terminal state based on the current deduction set.

    Used after deduction inserts / dispute changes / dispute resolutions so the
    state always reflects current rows without callers needing to compute it.
    No-op if assignment is already terminal.
    """
    prev = current_state(cursor, assignment_id)
    if is_terminal(prev):
        return prev

    cursor.execute('''
        SELECT
            SUM(CASE WHEN status = 'Proposed' THEN 1 ELSE 0 END) AS proposed_n,
            SUM(CASE WHEN status = 'Proposed' AND acknowledgement_status = 'Disputed'
                     THEN 1 ELSE 0 END) AS disputed_n
        FROM housing_deposit_deductions
        WHERE assignment_id = ?
    ''', (assignment_id,))
    proposed_n, disputed_n = cursor.fetchone() or (0, 0)
    proposed_n = proposed_n or 0
    disputed_n = disputed_n or 0

    if disputed_n > 0:
        target = DISPUTED
    elif proposed_n > 0:
        target = DEDUCTIONS_PROPOSED
    else:
        target = HELD

    if target == prev:
        return prev
    try:
        transition(cursor, assignment_id, target,
                   reason='reconcile_from_deductions', actor=actor)
    except IllegalTransition:
        # If the previous state isn't in our graph (legacy data), force it.
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO housing_deposit_state_log
            (log_id, assignment_id, from_state, to_state, reason, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (generate_id('STL'), assignment_id, prev, target,
              'reconcile (forced)', actor, timestamp))
        cursor.execute(
            'UPDATE housing_assignments SET deposit_state = ?, updated_at = ? '
            'WHERE assignment_id = ?',
            (target, timestamp, assignment_id),
        )
    return target


@log_read(module="housing", description="Viewing deposit state")
def view_deposit_state():
    """Show the deposit state of every assignment with a deposit history."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in.")
        return
    if not (auth.check_permission('manage_accommodations')
            or auth.check_permission('view_accommodations')):
        print("You don't have permission to view deposit state.")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
                   a.deposit_state,
                   (SELECT created_at FROM housing_deposit_state_log
                    WHERE assignment_id = a.assignment_id
                    ORDER BY created_at DESC LIMIT 1)
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.deposit_state IS NOT NULL
               OR EXISTS (SELECT 1 FROM payments p
                          WHERE p.source_type = 'housing'
                            AND p.payment_type = 'Deposit'
                            AND p.reference_id = a.assignment_id)
            ORDER BY a.deposit_state, a.assignment_id
        ''')
        rows = cursor.fetchall()
        if not rows:
            print("No deposit lifecycle data yet.")
            return

        print("\nDeposit State per Assignment:")
        print("=" * 70)
        by_state = {}
        for r in rows:
            by_state.setdefault(r[4] or '(unset)', []).append(r)
        for state, items in by_state.items():
            print(f"\n{state} ({len(items)}):")
            for aid, sid, first, last, _st, last_change in items:
                tail = f" — last change {last_change}" if last_change else ""
                print(f"  {first} {last} ({sid}) — {aid}{tail}")

        pick = input("\nEnter assignment ID to see its log (blank to skip): ").strip()
        if pick:
            cursor.execute('''
                SELECT from_state, to_state, reason, actor, created_at
                FROM housing_deposit_state_log
                WHERE assignment_id = ?
                ORDER BY created_at
            ''', (pick,))
            log = cursor.fetchall()
            if not log:
                print("No log entries for that assignment.")
            else:
                print(f"\nState log for {pick}:")
                for fr, to, reason, actor, at in log:
                    fr_t = fr or '(none)'
                    print(f"  {at}  {fr_t} → {to}  by {actor}  ({reason or '-'})")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
