"""End-of-tenancy deposit refund workflow.

Deposits are recorded as `payment_type='Deposit'` via record_payment and credit
the 2510 Tenant Deposits Held liability account on posting. At move-out, this
module:

  1. Lists assignments that have a held deposit balance.
  2. Links the latest Move-out inspection (for context — findings/action_required).
  3. Lets staff enter itemised damage/cleaning deductions.
  4. Computes the refund as `held - deductions`.
  5. Posts a single balanced GL journal that releases the deposit liability,
     recognises the deductions as accommodation income, and pays out the refund.
  6. Marks the deposit payment as Refunded (or Partially Refunded) and writes
     each deduction to housing_deposit_deductions for audit.
"""

from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import common as _common
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_connection, generate_id, log_create,
)


def _fetch_assignments_with_held_deposit(cursor):
    """Return assignments where a deposit was paid and not yet refunded."""
    cursor.execute('''
        SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
               r.room_number, b.building_name,
               SUM(p.amount) AS deposit_held
        FROM payments p
        JOIN housing_assignments a ON p.reference_id = a.assignment_id
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE p.source_type = 'housing'
          AND p.payment_type = 'Deposit'
          AND p.status = 'Completed'
        GROUP BY a.assignment_id
        HAVING deposit_held > 0
        ORDER BY a.assignment_id
    ''')
    return cursor.fetchall()


def _latest_move_out_inspection(cursor, room_id):
    cursor.execute('''
        SELECT inspection_id, inspection_date, status, findings, action_required
        FROM housing_inspections
        WHERE room_id = ? AND inspection_type = 'Move-out'
        ORDER BY inspection_date DESC
        LIMIT 1
    ''', (room_id,))
    return cursor.fetchone()


def _deposit_payment_ids(cursor, assignment_id):
    cursor.execute('''
        SELECT source_payment_id, payment_id, amount
        FROM payments
        WHERE source_type = 'housing'
          AND payment_type = 'Deposit'
          AND status = 'Completed'
          AND reference_id = ?
        ORDER BY payment_date
    ''', (assignment_id,))
    return cursor.fetchall()


def _post_refund_journal(deposit_held, total_deductions, refund_amount,
                         assignment_id, posted_by, tenant_interest=0.0):
    """Post the refund journal.

    Always:                   Dr 2510 (deposit_held — principal liability)
    If damages > 0:           Cr 4360 (recognise as accommodation income)
    If tenant_interest > 0:   Dr 5400 (interest expense for the tenant share)
    If refund_amount > 0:     Cr 1010 (cash paid to student)

    The refund_amount passed in already includes tenant_interest when the
    policy entitles the student to it. Returns the journal_id, or None if no
    principal was held.
    """
    if deposit_held <= 0:
        return None

    try:
        from education_system.systems.university.domain.finance.ledger import posting
        from education_system.systems.university.domain.finance.ledger.hooks import get_connection as gl_conn
    except Exception as exc:
        print(f"Ledger module unavailable — refund recorded operationally only ({exc}).")
        return None

    lines = [
        {'account_code': '2510', 'debit': float(deposit_held),
         'memo': f"Release held deposit for assignment {assignment_id}"},
    ]
    if tenant_interest > 0:
        lines.append({
            'account_code': '5400', 'debit': float(tenant_interest),
            'memo': f"Tenant deposit interest paid — assignment {assignment_id}",
        })
    if total_deductions > 0:
        lines.append({
            'account_code': '4360', 'credit': float(total_deductions),
            'memo': f"Damage/cleaning deductions for assignment {assignment_id}",
        })
    if refund_amount > 0:
        lines.append({
            'account_code': '1010', 'credit': float(refund_amount),
            'memo': f"Deposit refund for assignment {assignment_id}",
        })

    conn = gl_conn()
    try:
        cur = conn.cursor()
        return posting._post_journal(
            conn,
            entity_id=posting._default_entity_id(cur),
            journal_date=datetime.datetime.now().strftime('%Y-%m-%d'),
            description=f"Deposit refund — assignment {assignment_id}",
            source_type='deposit_refund',
            source_id=assignment_id,
            posted_by=posted_by,
            lines=lines,
        )
    finally:
        conn.close()


@log_create(module="housing", description="Processing deposit refund")
def process_deposit_refund():
    """Interactive end-of-tenancy deposit refund."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in to process deposit refunds.")
        return
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to process deposit refunds.")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()

        rows = _fetch_assignments_with_held_deposit(cursor)
        if not rows:
            print("No assignments with a held deposit found.")
            return

        print("\nAssignments with Held Deposits:")
        print("=" * 60)
        for i, r in enumerate(rows, 1):
            print(f"{i}. {r[2]} {r[3]} ({r[1]}) — Room {r[4]}, {r[5]}")
            print(f"   Assignment: {r[0]} | Deposit held: £{r[6]:,.2f}")

        while True:
            try:
                choice = int(input("\nSelect assignment (number, 0 to cancel): "))
                if choice == 0:
                    return
                if 1 <= choice <= len(rows):
                    selected = rows[choice - 1]
                    break
                print(f"Enter 1–{len(rows)} or 0.")
            except ValueError:
                print("Enter a valid number.")

        assignment_id, student_id, first, last, room_number, building, deposit_held = selected
        deposit_held = float(deposit_held)

        # Refuse to proceed if the assignment's deposit is already in a terminal
        # lifecycle state — Refunded / Partially Refunded / Forfeited.
        try:
            from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import deposit_state as _ds
            current = _ds.current_state(cursor, assignment_id)
            if _ds.is_terminal(current):
                print(f"\nAssignment {assignment_id} is in terminal state "
                      f"'{current}'. Cannot re-refund.")
                return
        except Exception:
            pass

        # Bring interest accrual up to today before computing the refund so the
        # student isn't shortchanged by stale accrual state.
        try:
            from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import interest as _interest
            today_iso = datetime.datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                'SELECT deposit_interest_rate, deposit_interest_last_accrual_date '
                'FROM housing_assignments WHERE assignment_id = ?',
                (assignment_id,),
            )
            row = cursor.fetchone()
            if row and row[0] and float(row[0]) > 0:
                last_accrual = row[1] or _interest._first_deposit_date(cursor, assignment_id)
                if last_accrual:
                    _interest._accrue_one(
                        cursor, assignment_id, float(row[0]),
                        last_accrual, today_iso, deposit_held,
                        created_by=auth.current_user.get('username', 'housing'),
                    )
                    conn.commit()
            accrued_interest, interest_policy = _interest.accrued_interest_for(
                cursor, assignment_id,
            )
        except Exception as _e:
            accrued_interest, interest_policy = 0.0, None

        # Surface room_id and move-out inspection for context.
        cursor.execute(
            'SELECT room_id FROM housing_assignments WHERE assignment_id = ?',
            (assignment_id,),
        )
        room_row = cursor.fetchone()
        room_id = room_row[0] if room_row else None

        inspection = _latest_move_out_inspection(cursor, room_id) if room_id else None
        inspection_id = inspection[0] if inspection else None

        print(f"\nProcessing refund for {first} {last} ({student_id})")
        print(f"Deposit held: £{deposit_held:,.2f}")
        if inspection:
            print(f"\nLatest Move-out Inspection ({inspection[1]}, status={inspection[2]}):")
            if inspection[3]:
                print(f"  Findings: {inspection[3]}")
            if inspection[4]:
                print(f"  Action required: {inspection[4]}")
        else:
            print("\nNo Move-out inspection on record for this room.")
            cont = input("Proceed anyway? (y/n): ").strip().lower()
            if cont != 'y':
                return

        # Refuse to proceed if any proposed rows are in an unresolved dispute.
        # Resolution (uphold / reduce / waive) must happen first via
        # resolve_deduction_disputes().
        cursor.execute('''
            SELECT description, amount, dispute_reason
            FROM housing_deposit_deductions
            WHERE assignment_id = ? AND status = 'Proposed'
              AND acknowledgement_status = 'Disputed'
        ''', (assignment_id,))
        open_disputes = cursor.fetchall()
        if open_disputes:
            print("\nCannot process refund — unresolved disputes:")
            for desc, amt, reason in open_disputes:
                print(f"  - {desc} (£{amt:,.2f}) — disputed: {reason}")
            print("Resolve via 'Resolve Deduction Disputes' first.")
            return

        # Preload any deductions already proposed at inspection time. Each row
        # carries its origin id so it can be marked Applied (not re-inserted) when
        # the journal posts. Waived rows are excluded.
        cursor.execute('''
            SELECT deduction_id, description, amount, inspection_id
            FROM housing_deposit_deductions
            WHERE assignment_id = ? AND status = 'Proposed'
            ORDER BY created_at
        ''', (assignment_id,))
        proposed = cursor.fetchall()
        if proposed:
            print("\nProposed deductions from inspection(s):")
            for ded_id, desc, amt, ins in proposed:
                origin = f" (inspection {ins})" if ins else ""
                print(f"  - {desc}: £{amt:,.2f}{origin}")
            print(f"  Subtotal: £{sum(p[2] for p in proposed):,.2f}")
            keep = input("\nApply these proposed deductions? (y/n): ").strip().lower()
            if keep != 'y':
                print("Discarding proposed rows — they will be deleted, not applied.")
                cursor.execute('''
                    DELETE FROM housing_deposit_deductions
                    WHERE assignment_id = ? AND status = 'Proposed'
                ''', (assignment_id,))
                proposed = []

        # Existing proposed rows + any newly-entered ones.
        existing_deductions = [(ded_id, desc, float(amt)) for ded_id, desc, amt, _ in proposed]

        # Itemised additional deductions.
        print("\nEnter any additional deductions (blank description to finish).")
        new_deductions = []
        while True:
            desc = input("Deduction description: ").strip()
            if not desc:
                break
            while True:
                try:
                    amt = float(input(f"  Amount for '{desc}': £"))
                    if amt < 0:
                        print("  Amount cannot be negative.")
                        continue
                    if amt == 0:
                        print("  Skipping zero-amount deduction.")
                        amt = None
                    break
                except ValueError:
                    print("  Enter a valid amount.")
            if amt:
                new_deductions.append((desc, amt))

        # Combined list used for display + totalling.
        deductions = [(desc, amt) for _, desc, amt in existing_deductions] + new_deductions

        total_deductions = sum(amt for _, amt in deductions)
        if total_deductions > deposit_held:
            print(f"\nDeductions (£{total_deductions:,.2f}) exceed deposit held "
                  f"(£{deposit_held:,.2f}). Excess must be recovered separately "
                  f"as a damage charge — capping deduction at deposit held.")
            # Cap the deduction-against-deposit; the excess remains owed by the
            # student but isn't part of this journal.
            capped = deposit_held
        else:
            capped = total_deductions
        # Apply interest by policy. Tenant: added to the cash refund and booked
        # as interest expense. Landlord/Scheme: not paid out here.
        tenant_interest = round(accrued_interest, 2) if (
            interest_policy == 'Tenant' and accrued_interest > 0
        ) else 0.0
        refund_amount = round(deposit_held - capped + tenant_interest, 2)

        print("\nSummary:")
        print(f"  Deposit held:        £{deposit_held:,.2f}")
        print(f"  Total deductions:    £{capped:,.2f}")
        if accrued_interest > 0:
            policy_text = interest_policy or '(unset)'
            print(f"  Interest accrued:    £{accrued_interest:,.2f} (policy: {policy_text})")
            if tenant_interest > 0:
                print(f"    → paid to tenant   £{tenant_interest:,.2f}")
            elif interest_policy == 'Landlord':
                print("    → retained by landlord (no payout)")
            elif interest_policy == 'Scheme':
                print("    → handled by scheme (no payout)")
        print(f"  Refund to student:   £{refund_amount:,.2f}")
        if not deductions:
            print("  (no deductions on deposit principal)")
        else:
            for desc, amt in deductions:
                print(f"    - {desc}: £{amt:,.2f}")

        confirm = input("\nPost refund and update records? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        posted_by = auth.current_user.get('username', 'housing')

        # Existing Proposed rows: flip to Applied (preserves their inspection_id).
        # New rows: insert as Applied straight away.
        deposit_rows = _deposit_payment_ids(cursor, assignment_id)
        primary_deposit_id = deposit_rows[0][0] if deposit_rows else None

        if existing_deductions:
            cursor.execute('''
                UPDATE housing_deposit_deductions
                SET status = 'Applied', applied_at = ?, deposit_payment_id = ?
                WHERE assignment_id = ? AND status = 'Proposed'
            ''', (timestamp, primary_deposit_id, assignment_id))

        for desc, amt in new_deductions:
            cursor.execute('''
                INSERT INTO housing_deposit_deductions
                (deduction_id, assignment_id, deposit_payment_id, inspection_id,
                 description, amount, status, created_by, created_at, applied_at)
                VALUES (?, ?, ?, ?, ?, ?, 'Applied', ?, ?, ?)
            ''', (generate_id('DED'), assignment_id, primary_deposit_id,
                  inspection_id, desc, amt, posted_by, timestamp, timestamp))

        # Mark deposit payments as refunded. With multiple deposit rows, mark
        # them all the same way — the aggregate status reflects the assignment.
        new_status = 'Refunded' if refund_amount > 0 and capped == 0 else (
            'Partially Refunded' if refund_amount > 0 else 'Forfeited'
        )
        cursor.execute('''
            UPDATE payments
            SET status = ?, updated_at = ?
            WHERE source_type = 'housing'
              AND payment_type = 'Deposit'
              AND reference_id = ?
        ''', (new_status, timestamp, assignment_id))

        # Transition the deposit lifecycle state to its terminal value. Mirrors
        # new_status: Refunded / Partially Refunded / Forfeited.
        try:
            from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import deposit_state as _ds
            _ds.transition(
                cursor, assignment_id, new_status,
                reason=f"refund: deductions £{capped:,.2f}, refund £{refund_amount:,.2f}",
                actor=posted_by,
            )
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("deposit state transition failed: %s", _e)

        conn.commit()

        # Post GL journal (best-effort — operational record is already saved).
        try:
            journal_id = _post_refund_journal(
                deposit_held, capped, refund_amount, assignment_id, posted_by,
                tenant_interest=tenant_interest,
            )
            if journal_id:
                print(f"\nGL journal posted (id={journal_id}).")
        except Exception as exc:
            print(f"\nWarning: GL journal failed to post ({exc}). "
                  f"Operational records saved — re-post via finance tools.")

        print(f"\nDeposit refund processed. Status set to '{new_status}'.")
        if refund_amount > 0:
            print(f"Issue £{refund_amount:,.2f} to {first} {last} ({student_id}).")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Error processing deposit refund: {e}")
        conn.rollback()
    finally:
        conn.close()


@log_create(module="housing", description="Viewing deposit ledger")
def view_deposit_ledger():
    """List all held deposits with status."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in to view the deposit ledger.")
        return
    if not (auth.check_permission('manage_accommodations')
            or auth.check_permission('view_accommodations')):
        print("You don't have permission to view the deposit ledger.")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
                   r.room_number, b.building_name,
                   SUM(p.amount) AS deposit_total,
                   GROUP_CONCAT(DISTINCT p.status)
            FROM payments p
            JOIN housing_assignments a ON p.reference_id = a.assignment_id
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE p.source_type = 'housing' AND p.payment_type = 'Deposit'
            GROUP BY a.assignment_id
            ORDER BY a.assignment_id
        ''')
        rows = cursor.fetchall()

        if not rows:
            print("No deposit payments on record.")
            return

        print("\nDeposit Ledger:")
        print("=" * 80)
        held_total = 0.0
        for r in rows:
            print(f"  {r[2]} {r[3]} ({r[1]}) — Room {r[4]}, {r[5]}")
            print(f"    Assignment {r[0]}: £{r[6]:,.2f} [{r[7]}]")
            if 'Completed' in (r[7] or ''):
                held_total += float(r[6])
        print("-" * 80)
        print(f"  Total still held (status=Completed): £{held_total:,.2f}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Acknowledgement / dispute workflow
# ---------------------------------------------------------------------------

def _resolve_current_student_id(cursor, auth):
    """Return the student_id linked to the current user, or None."""
    cursor.execute('SELECT student_id FROM users WHERE id = ?',
                   (auth.current_user['id'],))
    row = cursor.fetchone()
    return row[0] if row and row[0] else None


@log_create(module="housing", description="Student reviewing deposit deductions")
def student_review_deductions():
    """Show the current student their proposed deductions; allow ack/dispute."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in to review deductions.")
        return
    if not auth.check_permission('view_own_record'):
        print("You don't have permission to view your deductions.")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        student_id = _resolve_current_student_id(cursor, auth)
        if not student_id:
            print("No student ID associated with your account.")
            return

        cursor.execute('''
            SELECT d.deduction_id, d.assignment_id, d.description, d.amount,
                   d.acknowledgement_status, d.dispute_reason,
                   d.dispute_resolution_notes, i.inspection_date
            FROM housing_deposit_deductions d
            JOIN housing_assignments a ON d.assignment_id = a.assignment_id
            LEFT JOIN housing_inspections i ON d.inspection_id = i.inspection_id
            WHERE a.student_id = ? AND d.status = 'Proposed'
            ORDER BY d.created_at
        ''', (student_id,))
        rows = cursor.fetchall()

        if not rows:
            print("You have no proposed deductions awaiting review.")
            return

        print("\nProposed Deductions for Review:")
        print("=" * 60)
        for i, r in enumerate(rows, 1):
            ded_id, _aid, desc, amt, ack, reason, resolution, ins_date = r
            origin = f" (move-out inspection {ins_date})" if ins_date else ""
            print(f"\n{i}. {desc} — £{amt:,.2f}{origin}")
            print(f"   Status: {ack}")
            if reason:
                print(f"   Your dispute: {reason}")
            if resolution:
                print(f"   Resolution: {resolution}")

        print("\nActions: enter a row number to act on it, or 0 to finish.")
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        while True:
            try:
                pick = int(input("\nRow (0 to finish): "))
            except ValueError:
                print("Enter a valid number.")
                continue
            if pick == 0:
                break
            if not 1 <= pick <= len(rows):
                print(f"Enter 1–{len(rows)} or 0.")
                continue

            row = rows[pick - 1]
            ded_id, _aid, _desc, _amt, ack, _reason, _resolution, _ins = row
            if ack == 'Resolved':
                print("This deduction has been resolved and can't be re-disputed here.")
                continue

            print("  1. Acknowledge (accept this deduction)")
            print("  2. Dispute (raise a reason)")
            print("  3. Cancel")
            act = input("  Action: ").strip()

            if act == '1':
                cursor.execute('''
                    UPDATE housing_deposit_deductions
                    SET acknowledgement_status = 'Acknowledged',
                        acknowledged_at = ?,
                        dispute_reason = NULL
                    WHERE deduction_id = ? AND status = 'Proposed'
                ''', (timestamp, ded_id))
                print("  Acknowledged.")
            elif act == '2':
                reason = input("  Reason for dispute: ").strip()
                if not reason:
                    print("  Dispute reason required — skipped.")
                    continue
                cursor.execute('''
                    UPDATE housing_deposit_deductions
                    SET acknowledgement_status = 'Disputed',
                        dispute_reason = ?,
                        acknowledged_at = NULL
                    WHERE deduction_id = ? AND status = 'Proposed'
                ''', (reason, ded_id))
                print("  Disputed — housing staff will review.")
            else:
                continue
            # Reconcile deposit state after the dispute flag may have changed.
            try:
                from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import deposit_state
                # Grab the assignment_id for this row.
                cursor.execute(
                    'SELECT assignment_id FROM housing_deposit_deductions WHERE deduction_id = ?',
                    (ded_id,),
                )
                aid_row = cursor.fetchone()
                if aid_row:
                    deposit_state.reconcile_from_deductions(
                        cursor, aid_row[0],
                        actor=auth.current_user.get('username', student_id),
                    )
            except Exception:
                pass
            conn.commit()

            # Refresh the row in memory for subsequent renders.
            cursor.execute('''
                SELECT deduction_id, assignment_id, description, amount,
                       acknowledgement_status, dispute_reason,
                       dispute_resolution_notes,
                       (SELECT inspection_date FROM housing_inspections
                        WHERE inspection_id = housing_deposit_deductions.inspection_id)
                FROM housing_deposit_deductions WHERE deduction_id = ?
            ''', (ded_id,))
            rows[pick - 1] = cursor.fetchone()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()


@log_create(module="housing", description="Resolving deduction disputes")
def resolve_deduction_disputes():
    """Staff: list Disputed deductions and resolve each (uphold/reduce/waive)."""
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in to resolve disputes.")
        return
    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to resolve deduction disputes.")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT d.deduction_id, d.assignment_id, a.student_id,
                   s.first_name, s.last_name,
                   d.description, d.amount, d.dispute_reason
            FROM housing_deposit_deductions d
            JOIN housing_assignments a ON d.assignment_id = a.assignment_id
            JOIN students s ON a.student_id = s.student_id
            WHERE d.status = 'Proposed'
              AND d.acknowledgement_status = 'Disputed'
            ORDER BY d.created_at
        ''')
        rows = cursor.fetchall()

        if not rows:
            print("No disputed deductions awaiting resolution.")
            return

        print("\nDisputed Deductions:")
        print("=" * 60)
        for i, r in enumerate(rows, 1):
            _did, _aid, sid, first, last, desc, amt, reason = r
            print(f"\n{i}. {first} {last} ({sid})")
            print(f"   {desc} — £{amt:,.2f}")
            print(f"   Dispute: {reason}")

        while True:
            try:
                pick = int(input("\nRow to resolve (0 to finish): "))
            except ValueError:
                print("Enter a valid number.")
                continue
            if pick == 0:
                break
            if not 1 <= pick <= len(rows):
                print(f"Enter 1–{len(rows)} or 0.")
                continue
            ded_id, _aid, _sid, _first, _last, _desc, current_amt, _reason = rows[pick - 1]

            print("  1. Uphold (keep amount as-is)")
            print("  2. Reduce (lower the amount)")
            print("  3. Waive (set amount to £0 — effectively cancels this deduction)")
            print("  4. Cancel")
            act = input("  Action: ").strip()

            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            resolver = auth.current_user.get('username', 'staff')
            notes = ''
            new_amount = float(current_amt)

            if act == '1':
                notes = input("  Notes (rationale for upholding): ").strip()
            elif act == '2':
                while True:
                    try:
                        new_amount = float(input(f"  New amount (current £{current_amt:,.2f}): £"))
                        if new_amount < 0:
                            print("  Amount cannot be negative.")
                            continue
                        if new_amount >= float(current_amt):
                            print("  New amount must be lower than current — use Uphold to keep it.")
                            continue
                        break
                    except ValueError:
                        print("  Enter a valid amount.")
                notes = input("  Notes: ").strip()
            elif act == '3':
                new_amount = 0.0
                notes = input("  Notes (rationale for waiving): ").strip()
            else:
                continue

            if new_amount == 0.0 and act != '1':
                # Waived (or reduced to zero): drop the row from the proposed set
                # by marking it 'Waived' under status so process_deposit_refund
                # ignores it.
                cursor.execute('''
                    UPDATE housing_deposit_deductions
                    SET amount = 0,
                        status = 'Waived',
                        acknowledgement_status = 'Resolved',
                        dispute_resolution_notes = ?,
                        dispute_resolved_by = ?,
                        dispute_resolved_at = ?
                    WHERE deduction_id = ?
                ''', (notes or 'Waived', resolver, timestamp, ded_id))
            else:
                cursor.execute('''
                    UPDATE housing_deposit_deductions
                    SET amount = ?,
                        acknowledgement_status = 'Resolved',
                        dispute_resolution_notes = ?,
                        dispute_resolved_by = ?,
                        dispute_resolved_at = ?
                    WHERE deduction_id = ?
                ''', (new_amount, notes or None, resolver, timestamp, ded_id))
            # Reconcile state — if this was the last open dispute, the
            # assignment moves back from Disputed to Deductions Proposed.
            try:
                from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import deposit_state
                cursor.execute(
                    'SELECT assignment_id FROM housing_deposit_deductions WHERE deduction_id = ?',
                    (ded_id,),
                )
                aid_row = cursor.fetchone()
                if aid_row:
                    deposit_state.reconcile_from_deductions(
                        cursor, aid_row[0], actor=resolver,
                    )
            except Exception:
                pass
            conn.commit()
            print("  Resolved.")

            # Refresh the row so re-prints reflect the new state.
            cursor.execute('''
                SELECT d.deduction_id, d.assignment_id, a.student_id,
                       s.first_name, s.last_name,
                       d.description, d.amount, d.dispute_reason
                FROM housing_deposit_deductions d
                JOIN housing_assignments a ON d.assignment_id = a.assignment_id
                JOIN students s ON a.student_id = s.student_id
                WHERE d.deduction_id = ?
            ''', (ded_id,))
            rows[pick - 1] = cursor.fetchone()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
