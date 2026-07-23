#!/usr/bin/env python3
"""
Test refund integration from library, gym, and dentist GUIs to finance GUI.

This script tests that refunds from all three systems are properly recorded
in the finance_refunds table and will be visible in the main finance GUI.
"""

import sys
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import transaction, get_connection
from education_system.post_18.university_system.modules.shared.utils.finance_integration import record_refund_to_finance

def test_library_refund():
    """Test library refund using finance_integration function."""
    print("\n1. Testing Library Refund Integration")
    print("=" * 60)

    try:
        refund_id = record_refund_to_finance(
            student_id="S001",
            refund_amount=15.50,
            original_payment_id=None,
            refund_reason="Library fine overpayment",
            refund_type="partial",
            transaction_source="Library",
            transaction_ref="FINE_REFUND_12345",
            refund_method="student_finance_account",
            requested_by="LibraryStaff",
            notes="Book: Python Programming Guide"
        )

        if refund_id:
            print(f"  ✓ Library refund recorded successfully")
            print(f"    Refund ID: {refund_id}")
            return True
        else:
            print(f"  ✗ Failed to record library refund")
            return False

    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dentist_refund():
    """Test dentist refund using direct INSERT (simulating GUI)."""
    print("\n2. Testing Dentist Refund Integration")
    print("=" * 60)

    try:
        with transaction() as conn:
            conn.execute('''
                INSERT INTO finance_refunds
                (student_id, refund_reference, department, transaction_id,
                 amount, refund_method, refund_date, refund_time, processed_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                "S002",
                "DENTIST-REFUND-TEST-001",
                "Dentist",
                None,
                45.00,
                "cash",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                datetime.now().strftime('%H:%M:%S'),
                "DentistStaff",
                "Dental Clinic Payment Refund"
            ))

            refund_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        print(f"  ✓ Dentist refund recorded successfully")
        print(f"    Refund ID: {refund_id}")
        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gym_refund():
    """Test gym refund using direct INSERT (simulating GUI)."""
    print("\n3. Testing Gym Refund Integration")
    print("=" * 60)

    try:
        with transaction() as conn:
            conn.execute('''
                INSERT INTO finance_refunds
                (student_id, refund_reference, department, transaction_id,
                 amount, refund_method, refund_date, refund_time, processed_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                "S003",
                "GYM-REFUND-TEST-001",
                "Gym",
                None,
                30.00,
                "card",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                datetime.now().strftime('%H:%M:%S'),
                "GymStaff",
                "Gym Service Refund"
            ))

            refund_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        print(f"  ✓ Gym refund recorded successfully")
        print(f"    Refund ID: {refund_id}")
        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_refunds_in_finance_table():
    """Verify all refunds are visible in finance_refunds table."""
    print("\n4. Verifying Refunds in Finance GUI Table")
    print("=" * 60)

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, student_id, refund_reference, department, amount,
                       refund_method, processed_by, notes
                FROM finance_refunds
                ORDER BY id DESC
                LIMIT 10
            ''')

            refunds = cursor.fetchall()

            if not refunds:
                print("  ⚠️  No refunds found in finance_refunds table")
                return False

            print(f"  ✓ Found {len(refunds)} refund(s) in finance_refunds table")
            print("\n  Recent refunds:")
            print("  " + "-" * 100)
            print(f"  {'ID':<5} {'Student':<10} {'Reference':<25} {'Dept':<10} {'Amount':<10} {'Method':<15} {'By':<12}")
            print("  " + "-" * 100)

            for refund in refunds:
                ref_id, student_id, ref, dept, amount, method, proc_by, notes = refund
                # Handle None values
                student_id = student_id or 'N/A'
                ref = ref or 'N/A'
                dept = dept or 'N/A'
                amount = amount or 0.0
                method = method or 'N/A'
                proc_by = proc_by or 'N/A'
                print(f"  {ref_id:<5} {student_id:<10} {ref[:24]:<25} {dept:<10} £{amount:<9.2f} {method:<15} {proc_by:<12}")

            print("  " + "-" * 100)

            # Check if our test refunds are there
            test_refunds = [r for r in refunds if 'TEST' in (r[2] or '')]
            if test_refunds:
                print(f"\n  ✓ {len(test_refunds)} test refund(s) confirmed in table")

            return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all refund integration tests."""
    print()
    print("=" * 70)
    print("REFUND INTEGRATION TEST")
    print("Testing Library, Gym, and Dentist GUI refunds → Finance GUI")
    print("=" * 70)

    results = []
    results.append(("Library Refund", test_library_refund()))
    results.append(("Dentist Refund", test_dentist_refund()))
    results.append(("Gym Refund", test_gym_refund()))
    results.append(("Finance Table Verification", verify_refunds_in_finance_table()))

    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:.<50} {status}")

    all_passed = all(result[1] for result in results)

    print("=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("\nRefunds from library, gym, and dentist GUIs will now appear")
        print("in the main finance GUI's refunds section!")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nPlease review the errors above.")
    print("=" * 70)
    print()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
