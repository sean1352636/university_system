from __future__ import annotations

from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3

from education_system.university_system.modules.domain.finance.core.finance_context import get_connection, get_current_user
from education_system.university_system.modules.domain.finance.core.security_automation import (
    log_audit_action,
    send_email_notification,
)
from education_system.university_system.modules.domain.finance.core.communications import send_arrangement_confirmation
from education_system.university_system.modules.domain.finance.core.students import student_exists, get_student_name

def approve_reject_aid_application():
    """Approve or reject financial aid applications"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get pending applications
        cursor.execute('''
        SELECT sfa.aid_id, sfa.student_id, s.first_name, s.last_name,
               fat.aid_name, sfa.awarded_amount, sfa.application_date, sfa.notes
        FROM student_financial_aid sfa
        JOIN students s ON sfa.student_id = s.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE sfa.status = 'pending'
        ORDER BY sfa.application_date
        ''')

        pending_apps = cursor.fetchall()

        if not pending_apps:
            print("No pending financial aid applications found.")
            conn.close()
            return

        print(f"\nPending Financial Aid Applications:")
        print("=" * 100)
        for i, app in enumerate(pending_apps, 1):
            aid_id, student_id, first_name, last_name, aid_name, amount, app_date, notes = app
            student_name = f"{first_name} {last_name}"

            print(f"{i}. Aid ID {aid_id} - {student_name} ({student_id})")
            print(f"   Type: {aid_name}")
            print(f"   Requested: £{amount:.2f}")
            print(f"   Applied: {app_date}")
            print(f"   Notes: {notes[:100]}...")
            print("-" * 100)

        # Select application to review
        app_choice = input(f"\nSelect application to review (1-{len(pending_apps)}): ").strip()
        try:
            app_index = int(app_choice) - 1
            if 0 <= app_index < len(pending_apps):
                selected_app = pending_apps[app_index]
                aid_id = selected_app[0]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

        # Show full application details
        print(f"\nReviewing Application ID: {aid_id}")
        print(f"Student: {selected_app[2]} {selected_app[3]} ({selected_app[1]})")
        print(f"Aid Type: {selected_app[4]}")
        print(f"Requested Amount: £{selected_app[5]:.2f}")
        print(f"Application Date: {selected_app[6]}")
        print(f"Notes: {selected_app[7]}")

        # Get student's financial history
        cursor.execute('''
        SELECT COUNT(*) as previous_aid, SUM(awarded_amount) as total_previous
        FROM student_financial_aid
        WHERE student_id = ? AND status = 'approved' AND aid_id != ?
        ''', (selected_app[1], aid_id))

        aid_history = cursor.fetchone()
        previous_count, total_previous = aid_history

        print(f"Previous aid received: {previous_count or 0} applications, £{total_previous or 0:.2f} total")

        # Decision
        print("\nDecision options:")
        print("1. Approve (full amount)")
        print("2. Approve (partial amount)")
        print("3. Reject")
        print("4. Request more information")

        decision = input("Enter decision (1-4): ").strip()

        now = datetime.now()
        approval_date = now.strftime('%Y-%m-%d')
        updated_at = now.strftime('%Y-%m-%d %H:%M:%S')

        if decision == '1':
            # Approve full amount
            approved_amount = selected_app[5]
            new_status = 'approved'

            cursor.execute('''
            UPDATE student_financial_aid
            SET status = ?, approved_by = ?, approval_date = ?, updated_at = ?
            WHERE aid_id = ?
            ''', (new_status, get_current_user()['username'] if get_current_user() else 'system', approval_date, updated_at, aid_id))

            print(f"Application approved for full amount: £{approved_amount:.2f}")

        elif decision == '2':
            # Approve partial amount
            while True:
                try:
                    approved_amount = float(input(f"Enter approved amount (max £{selected_app[5]:.2f}): £"))
                    if approved_amount <= 0:
                        print("Amount must be greater than zero.")
                        continue
                    if approved_amount > selected_app[5]:
                        print("Approved amount cannot exceed requested amount.")
                        continue
                    break
                except ValueError:
                    print("Invalid input. Please enter a valid amount.")

            new_status = 'approved'

            cursor.execute('''
            UPDATE student_financial_aid
            SET status = ?, awarded_amount = ?, remaining_amount = ?, approved_by = ?,
                approval_date = ?, updated_at = ?
            WHERE aid_id = ?
            ''', (new_status, approved_amount, approved_amount, get_current_user()['username'] if get_current_user() else 'system',
                  approval_date, updated_at, aid_id))

            print(f"Application approved for partial amount: £{approved_amount:.2f}")

        elif decision == '3':
            # Reject
            rejection_reason = input("Enter rejection reason: ").strip()
            if not rejection_reason:
                print("Rejection reason is required.")
                conn.close()
                return

            new_status = 'rejected'

            cursor.execute('''
            UPDATE student_financial_aid
            SET status = ?, approved_by = ?, approval_date = ?,
                notes = notes || ' | REJECTED: ' || ?, updated_at = ?
            WHERE aid_id = ?
            ''', (new_status, get_current_user()['username'] if get_current_user() else 'system', approval_date,
                  rejection_reason, updated_at, aid_id))

            print(f"Application rejected. Reason: {rejection_reason}")

        elif decision == '4':
            # Request more information
            info_request = input("Enter information request: ").strip()
            if not info_request:
                print("Information request is required.")
                conn.close()
                return

            new_status = 'pending'

            cursor.execute('''
            UPDATE student_financial_aid
            SET notes = notes || ' | INFO REQUEST: ' || ?, updated_at = ?
            WHERE aid_id = ?
            ''', (info_request, updated_at, aid_id))

            print(f"Information requested from student: {info_request}")

        else:
            print("Invalid decision.")
            conn.close()
            return

        conn.commit()

        # Log the action
        log_audit_action('review_aid_application', 'student_financial_aid', str(aid_id), {
            'decision': decision,
            'reviewer': get_current_user()['username'] if get_current_user() else 'system',
            'approved_amount': approved_amount if decision in ['1', '2'] else 0
        })

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def manage_aid_types():
    """Manage financial aid types"""
    global auth

    while True:
        print("\n" + "=" * 40)
        print("FINANCIAL AID TYPES MANAGEMENT")
        print("=" * 40)
        print("1. View Aid Types")
        print("2. Create New Aid Type")
        print("3. Edit Aid Type")
        print("4. Deactivate Aid Type")
        print("5. Return to Financial Aid Menu")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            view_aid_types()
        elif choice == '2':
            create_aid_type()
        elif choice == '3':
            edit_aid_type()
        elif choice == '4':
            deactivate_aid_type()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

def view_aid_types():
    """View all financial aid types"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT aid_type_id, aid_name, aid_category, max_amount,
               eligibility_criteria, requires_repayment, interest_rate, is_active
        FROM financial_aid_types
        ORDER BY aid_category, aid_name
        ''')

        aid_types = cursor.fetchall()

        if not aid_types:
            print("No financial aid types found.")
            return

        print(f"\nFinancial Aid Types:")
        print("=" * 120)
        print(f"{'ID':<5} {'Name':<25} {'Category':<15} {'Max Amount':<15} {'Repayment':<10} {'Interest':<8} {'Active':<8}")
        print("-" * 120)

        for aid_type in aid_types:
            aid_id, name, category, max_amt, criteria, repayment, interest, active = aid_type
            max_amt_str = f"£{max_amt:.2f}" if max_amt else "Unlimited"
            repayment_str = "Yes" if repayment else "No"
            interest_str = f"{interest}%" if interest else "N/A"
            active_str = "Yes" if active else "No"

            print(f"{aid_id:<5} {name:<25} {category:<15} {max_amt_str:<15} {repayment_str:<10} {interest_str:<8} {active_str:<8}")

        print("=" * 120)
        conn.close()

    except Exception as e:
        print(f"Error viewing aid types: {e}")

def create_aid_type():
    """Create a new financial aid type"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nCreating New Financial Aid Type:")

        aid_name = input("Enter aid name: ").strip()
        if not aid_name:
            print("Aid name is required.")
            return

        categories = ['grant', 'loan', 'work_study', 'emergency', 'scholarship']
        print("\nAvailable categories:")
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat.title()}")

        cat_choice = input("Select category (1-5): ").strip()
        try:
            cat_index = int(cat_choice) - 1
            if 0 <= cat_index < len(categories):
                aid_category = categories[cat_index]
            else:
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return

        description = input("Enter description: ").strip()

        max_amount_input = input("Enter maximum amount (or press Enter for unlimited): ").strip()
        max_amount = float(max_amount_input) if max_amount_input else None

        eligibility = input("Enter eligibility criteria: ").strip()

        renewable = input("Is this aid renewable? (y/n): ").strip().lower() == 'y'

        requires_repayment = input("Does this aid require repayment? (y/n): ").strip().lower() == 'y'

        interest_rate = None
        if requires_repayment:
            interest_input = input("Enter interest rate (%) or press Enter for 0%: ").strip()
            interest_rate = float(interest_input) if interest_input else 0.0

        grace_period = None
        if requires_repayment:
            grace_input = input("Enter grace period (months) or press Enter for 0: ").strip()
            grace_period = int(grace_input) if grace_input else 0

        # Create the aid type
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO financial_aid_types
        (aid_name, aid_category, description, max_amount, eligibility_criteria,
         is_renewable, requires_repayment, interest_rate, grace_period_months,
         is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (aid_name, aid_category, description, max_amount, eligibility,
              renewable, requires_repayment, interest_rate, grace_period,
              1, now, now))

        aid_type_id = cursor.lastrowid

        conn.commit()

        print(f"\nFinancial aid type created successfully!")
        print(f"Aid Type ID: {aid_type_id}")
        print(f"Name: {aid_name}")
        print(f"Category: {aid_category.title()}")

        conn.close()

    except Exception as e:
        print(f"Error creating aid type: {e}")

def edit_aid_type():
    """Edit an existing financial aid type"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        aid_type_id = input("Enter aid type ID to edit: ").strip()

        cursor.execute('''
        SELECT aid_name, aid_category, description, max_amount, eligibility_criteria,
               is_renewable, requires_repayment, interest_rate, grace_period_months
        FROM financial_aid_types
        WHERE aid_type_id = ?
        ''', (aid_type_id,))

        aid_type = cursor.fetchone()

        if not aid_type:
            print("Aid type not found.")
            return

        print(f"\nEditing Aid Type {aid_type_id}:")
        print(f"Current name: {aid_type[0]}")

        new_name = input(f"Enter new name (or press Enter to keep '{aid_type[0]}'): ").strip()
        if not new_name:
            new_name = aid_type[0]

        new_description = input(f"Enter new description (or press Enter to keep current): ").strip()
        if not new_description:
            new_description = aid_type[2]

        # Update the aid type
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE financial_aid_types
        SET aid_name = ?, description = ?, updated_at = ?
        WHERE aid_type_id = ?
        ''', (new_name, new_description, now, aid_type_id))

        conn.commit()

        print(f"Aid type {aid_type_id} updated successfully!")

        conn.close()

    except Exception as e:
        print(f"Error editing aid type: {e}")

def deactivate_aid_type():
    """Deactivate a financial aid type"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        aid_type_id = input("Enter aid type ID to deactivate: ").strip()

        cursor.execute('''
        SELECT aid_name FROM financial_aid_types
        WHERE aid_type_id = ? AND is_active = 1
        ''', (aid_type_id,))

        aid_type = cursor.fetchone()

        if not aid_type:
            print("Aid type not found or already inactive.")
            return

        confirm = input(f"Deactivate aid type '{aid_type[0]}'? (y/n): ").strip().lower()
        if confirm != 'y':
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE financial_aid_types
        SET is_active = 0, updated_at = ?
        WHERE aid_type_id = ?
        ''', (now, aid_type_id))

        conn.commit()

        print(f"Aid type '{aid_type[0]}' deactivated successfully!")

        conn.close()

    except Exception as e:
        print(f"Error deactivating aid type: {e}")

def review_pending_aid_applications():
    """Review pending aid applications in detail"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT sfa.aid_id, sfa.student_id, s.first_name, s.last_name,
               fat.aid_name, sfa.awarded_amount, sfa.application_date, sfa.notes
        FROM student_financial_aid sfa
        JOIN students s ON sfa.student_id = s.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE sfa.status = 'pending'
        ORDER BY sfa.application_date
        ''')

        applications = cursor.fetchall()

        if not applications:
            print("No pending applications found.")
            return

        print(f"\nPending Aid Applications Review:")
        print("=" * 80)

        for app in applications:
            aid_id, student_id, first_name, last_name, aid_name, amount, app_date, notes = app

            print(f"\nApplication ID: {aid_id}")
            print(f"Student: {first_name} {last_name} ({student_id})")
            print(f"Aid Type: {aid_name}")
            print(f"Requested: £{amount:.2f}")
            print(f"Applied: {app_date}")
            print(f"Notes: {notes}")

            # Get student's academic performance
            cursor.execute('''
            SELECT course, enrollment_date, status
            FROM students
            WHERE student_id = ?
            ''', (student_id,))

            student_info = cursor.fetchone()
            if student_info:
                print(f"Course: {student_info[0]}")
                print(f"Enrollment: {student_info[1]}")
                print(f"Status: {student_info[2]}")

            # Get payment history
            cursor.execute('''
            SELECT COUNT(*), SUM(amount)
            FROM payments
            WHERE student_id = ? AND status = 'completed'
            ''', (student_id,))

            payment_history = cursor.fetchone()
            if payment_history and payment_history[0]:
                print(f"Payment History: {payment_history[0]} payments, £{payment_history[1]:.2f} total")

            print("-" * 80)

        conn.close()

    except Exception as e:
        print(f"Error reviewing applications: {e}")

def track_loan_repayments():
    """Track loan repayments for students"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get loans requiring repayment
        cursor.execute('''
        SELECT sfa.aid_id, sfa.student_id, s.first_name, s.last_name,
               fat.aid_name, sfa.awarded_amount, sfa.disbursed_amount,
               sfa.repayment_start_date, sfa.monthly_payment_amount, sfa.total_repaid
        FROM student_financial_aid sfa
        JOIN students s ON sfa.student_id = s.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE fat.requires_repayment = 1 AND sfa.status = 'disbursed'
        ORDER BY sfa.repayment_start_date
        ''')

        loans = cursor.fetchall()

        if not loans:
            print("No loans requiring repayment found.")
            return

        print(f"\nLoan Repayment Tracking:")
        print("=" * 120)
        print(f"{'Aid ID':<8} {'Student':<25} {'Loan Type':<20} {'Amount':<12} {'Repaid':<12} {'Monthly':<10} {'Start Date':<12}")
        print("-" * 120)

        total_outstanding = 0

        for loan in loans:
            aid_id, student_id, first_name, last_name, aid_name, awarded, disbursed, start_date, monthly, repaid = loan
            student_name = f"{first_name} {last_name}"
            outstanding = (disbursed or 0) - (repaid or 0)

            print(f"{aid_id:<8} {student_name:<25} {aid_name:<20} £{disbursed or 0:<11.2f} £{repaid or 0:<11.2f} £{monthly or 0:<9.2f} {start_date or 'TBD':<12}")
            total_outstanding += outstanding

        print("-" * 120)
        print(f"Total Outstanding: £{total_outstanding:.2f}")
        print("=" * 120)

        conn.close()

    except Exception as e:
        print(f"Error tracking loan repayments: {e}")

def process_loan_payment(loans):
    """Process a loan repayment"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(f"\nAvailable loans for payment:")
        for i, loan in enumerate(loans, 1):
            aid_id, student_id, first_name, last_name = loan[:4]
            print(f"{i}. Aid ID {aid_id} - {first_name} {last_name} ({student_id})")

        choice = input("Select loan (number): ").strip()
        try:
            loan_index = int(choice) - 1
            if 0 <= loan_index < len(loans):
                selected_loan = loans[loan_index]
            else:
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return

        aid_id, student_id, first_name, last_name, aid_name, awarded, disbursed, start_date, monthly, repaid = selected_loan
        outstanding = (disbursed or 0) - (repaid or 0)

        print(f"\nLoan Details:")
        print(f"Student: {first_name} {last_name}")
        print(f"Outstanding: £{outstanding:.2f}")
        print(f"Monthly Payment: £{monthly or 0:.2f}")

        payment_amount = float(input("Enter payment amount: £"))

        if payment_amount <= 0:
            print("Invalid payment amount.")
            return

        if payment_amount > outstanding:
            print("Payment amount exceeds outstanding balance.")
            payment_amount = outstanding

        # Record the payment
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payment_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
        INSERT INTO payments
        (student_id, amount, payment_method, payment_date, notes, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, payment_amount, 'Loan Repayment', payment_date,
              f'Loan repayment for Aid ID {aid_id}',
              get_current_user()['username'] if get_current_user() else 'system', now))
        loan_payment_id = cursor.lastrowid

        # Update loan record
        new_total_repaid = (repaid or 0) + payment_amount

        cursor.execute('''
        UPDATE student_financial_aid
        SET total_repaid = ?, updated_at = ?
        WHERE aid_id = ?
        ''', (new_total_repaid, now, aid_id))

        conn.commit()

        # Auto-post to GL (never raises)
        try:
            from education_system.university_system.modules.domain.finance.ledger import notify_ledger
            notify_ledger('payment', loan_payment_id, posted_by='aid_loan_repayment')
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

        print(f"Loan payment processed successfully!")
        print(f"Payment: £{payment_amount:.2f}")
        print(f"New outstanding balance: £{outstanding - payment_amount:.2f}")

        conn.close()

    except Exception as e:
        print(f"Error processing loan payment: {e}")

def aid_distribution_summary():
    """Generate aid distribution summary report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT fat.aid_category, fat.aid_name,
               COUNT(sfa.aid_id) as applications,
               SUM(CASE WHEN sfa.status = 'approved' THEN 1 ELSE 0 END) as approved,
               SUM(CASE WHEN sfa.status = 'approved' THEN sfa.awarded_amount ELSE 0 END) as total_awarded,
               SUM(sfa.disbursed_amount) as total_disbursed
        FROM financial_aid_types fat
        LEFT JOIN student_financial_aid sfa ON fat.aid_type_id = sfa.aid_type_id
        GROUP BY fat.aid_type_id, fat.aid_category, fat.aid_name
        ORDER BY fat.aid_category, total_awarded DESC
        ''')

        data = cursor.fetchall()

        print(f"\nFinancial Aid Distribution Summary:")
        print("=" * 100)
        print(f"{'Category':<15} {'Aid Type':<25} {'Apps':<6} {'Approved':<8} {'Awarded':<12} {'Disbursed':<12}")
        print("-" * 100)

        category_totals = {}

        for row in data:
            category, aid_name, apps, approved, awarded, disbursed = row

            print(f"{category:<15} {aid_name:<25} {apps or 0:<6} {approved or 0:<8} £{awarded or 0:<11.2f} £{disbursed or 0:<11.2f}")

            if category not in category_totals:
                category_totals[category] = {'awarded': 0, 'disbursed': 0}
            category_totals[category]['awarded'] += awarded or 0
            category_totals[category]['disbursed'] += disbursed or 0

        print("-" * 100)
        print("Category Totals:")
        for category, totals in category_totals.items():
            print(f"{category}: Awarded £{totals['awarded']:,.2f}, Disbursed £{totals['disbursed']:,.2f}")

        print("=" * 100)

        conn.close()

    except Exception as e:
        print(f"Error generating aid distribution summary: {e}")

def aid_by_academic_year():
    """Generate aid report by academic year"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        academic_year = input("Enter academic year (e.g., 2023-2024) or press Enter for current: ").strip()
        if not academic_year:
            current_year = datetime.now().year
            academic_year = f"{current_year}-{current_year + 1}"

        cursor.execute('''
        SELECT fat.aid_category,
               COUNT(sfa.aid_id) as total_applications,
               SUM(CASE WHEN sfa.status = 'approved' THEN 1 ELSE 0 END) as approved_count,
               SUM(CASE WHEN sfa.status = 'approved' THEN sfa.awarded_amount ELSE 0 END) as total_awarded,
               AVG(CASE WHEN sfa.status = 'approved' THEN sfa.awarded_amount ELSE NULL END) as avg_award
        FROM student_financial_aid sfa
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE strftime('%Y', sfa.application_date) = ?
        GROUP BY fat.aid_category
        ORDER BY total_awarded DESC
        ''', (academic_year.split('-')[0],))

        data = cursor.fetchall()

        if not data:
            print(f"No aid data found for academic year {academic_year}")
            return

        print(f"\nFinancial Aid Report - Academic Year {academic_year}:")
        print("=" * 80)
        print(f"{'Category':<15} {'Applications':<12} {'Approved':<10} {'Total Awarded':<15} {'Avg Award':<12}")
        print("-" * 80)

        grand_total = 0

        for row in data:
            category, apps, approved, awarded, avg_award = row
            print(f"{category:<15} {apps:<12} {approved:<10} £{awarded:>13,.2f} £{avg_award or 0:>10.2f}")
            grand_total += awarded

        print("-" * 80)
        print(f"Grand Total Awarded: £{grand_total:,.2f}")
        print("=" * 80)

        conn.close()

    except Exception as e:
        print(f"Error generating academic year report: {e}")

def aid_effectiveness_analysis():
    """Analyze aid effectiveness"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Analyze aid impact on student retention and performance
        cursor.execute('''
        SELECT
            CASE WHEN sfa.aid_id IS NOT NULL THEN 'With Aid' ELSE 'Without Aid' END as aid_status,
            COUNT(DISTINCT s.student_id) as student_count,
            SUM(CASE WHEN s.status = 'active' THEN 1 ELSE 0 END) as active_students,
            (SUM(CASE WHEN s.status = 'active' THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT s.student_id)) as retention_rate
        FROM students s
        LEFT JOIN student_financial_aid sfa ON s.student_id = sfa.student_id AND sfa.status = 'approved'
        GROUP BY CASE WHEN sfa.aid_id IS NOT NULL THEN 'With Aid' ELSE 'Without Aid' END
        ''')

        effectiveness_data = cursor.fetchall()

        print(f"\nFinancial Aid Effectiveness Analysis:")
        print("=" * 60)
        print(f"{'Category':<15} {'Students':<10} {'Active':<8} {'Retention Rate':<15}")
        print("-" * 60)

        for row in effectiveness_data:
            category, total, active, retention = row
            print(f"{category:<15} {total:<10} {active:<8} {retention:.1f}%")

        print("=" * 60)

        # Aid utilization by type
        cursor.execute('''
        SELECT fat.aid_name,
               COUNT(sfa.aid_id) as applications,
               SUM(CASE WHEN sfa.status = 'approved' THEN 1 ELSE 0 END) as approved,
               (SUM(CASE WHEN sfa.status = 'approved' THEN 1 ELSE 0 END) * 100.0 / COUNT(sfa.aid_id)) as approval_rate
        FROM financial_aid_types fat
        JOIN student_financial_aid sfa ON fat.aid_type_id = sfa.aid_type_id
        GROUP BY fat.aid_type_id, fat.aid_name
        HAVING applications > 0
        ORDER BY approval_rate DESC
        ''')

        utilization_data = cursor.fetchall()

        print(f"\nAid Type Utilization:")
        print("=" * 60)
        print(f"{'Aid Type':<25} {'Applications':<12} {'Approved':<10} {'Approval Rate':<12}")
        print("-" * 60)

        for row in utilization_data:
            aid_name, apps, approved, rate = row
            print(f"{aid_name:<25} {apps:<12} {approved:<10} {rate:.1f}%")

        print("=" * 60)

        conn.close()

    except Exception as e:
        print(f"Error analyzing aid effectiveness: {e}")

def view_aid_application_detail(aid_id):
    """View detailed aid application information"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT sfa.aid_id, sfa.student_id, s.first_name, s.last_name, s.email_address,
               fat.aid_name, fat.aid_category, sfa.awarded_amount, sfa.disbursed_amount,
               sfa.status, sfa.application_date, sfa.approval_date, sfa.approved_by,
               sfa.notes, fat.requires_repayment, sfa.repayment_start_date
        FROM student_financial_aid sfa
        JOIN students s ON sfa.student_id = s.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE sfa.aid_id = ?
        ''', (aid_id,))

        application = cursor.fetchone()

        if not application:
            print(f"Aid application {aid_id} not found.")
            return

        (aid_id, student_id, first_name, last_name, email, aid_name, category,
         awarded, disbursed, status, app_date, approval_date, approved_by,
         notes, requires_repayment, repayment_start) = application

        print(f"\nFinancial Aid Application Details - ID: {aid_id}")
        print("=" * 60)
        print(f"Student: {first_name} {last_name} ({student_id})")
        print(f"Email: {email}")
        print(f"Aid Type: {aid_name} ({category.title()})")
        print(f"Awarded Amount: £{awarded:.2f}")
        print(f"Disbursed Amount: £{disbursed or 0:.2f}")
        print(f"Status: {status.title()}")
        print(f"Application Date: {app_date}")

        if approval_date:
            print(f"Approval Date: {approval_date}")
        if approved_by:
            print(f"Approved By: {approved_by}")

        if requires_repayment:
            print(f"Requires Repayment: Yes")
            if repayment_start:
                print(f"Repayment Start: {repayment_start}")
        else:
            print(f"Requires Repayment: No")

        if notes:
            print(f"Notes: {notes}")

        print("=" * 60)

        conn.close()

    except Exception as e:
        print(f"Error viewing aid application detail: {e}")

def apply_aid_to_fees(student_id, amount, aid_id):
    """Apply financial aid directly to student fees"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get outstanding fees
        cursor.execute('''
        SELECT sf.student_fee_id, ft.fee_name, sf.amount,
               COALESCE(SUM(pa.amount), 0) as paid_amount,
               sf.amount - COALESCE(SUM(pa.amount), 0) as outstanding
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.student_id = ? AND sf.status IN ('unpaid', 'partial')
        GROUP BY sf.student_fee_id
        HAVING outstanding > 0
        ORDER BY sf.due_date
        ''', (student_id,))

        fees = cursor.fetchall()

        if not fees:
            print(f"No outstanding fees to apply aid to for student {student_id}")
            return

        # Apply aid to fees
        remaining_aid = amount
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        aid_payment_ids = []
        for fee_id, fee_name, total_amount, paid_amount, outstanding in fees:
            if remaining_aid <= 0:
                break

            application_amount = min(remaining_aid, outstanding)

            # Create payment record
            cursor.execute('''
            INSERT INTO payments
            (student_id, amount, payment_method, payment_date, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, application_amount, 'Financial Aid',
                  datetime.now().strftime('%Y-%m-%d'),
                  f'Aid disbursement (ID: {aid_id}) applied to {fee_name}',
                  get_current_user()['username'] if get_current_user() else 'system', now))

            payment_id = cursor.lastrowid
            aid_payment_ids.append(payment_id)

            # Create payment allocation
            cursor.execute('''
            INSERT INTO payment_allocations
            (payment_id, student_fee_id, amount, created_at)
            VALUES (?, ?, ?, ?)
            ''', (payment_id, fee_id, application_amount, now))

            # Update fee status
            new_paid_amount = paid_amount + application_amount
            new_status = 'paid' if new_paid_amount >= total_amount else 'partial'

            cursor.execute('''
            UPDATE student_fees
            SET status = ?, updated_at = ?
            WHERE student_fee_id = ?
            ''', (new_status, now, fee_id))

            remaining_aid -= application_amount
            print(f"Applied £{application_amount:.2f} aid to {fee_name}")

        conn.commit()
        conn.close()

        # Auto-post each aid-disbursement payment to GL (never raises)
        try:
            from education_system.university_system.modules.domain.finance.ledger import notify_ledger
            for pid in aid_payment_ids:
                notify_ledger('payment', pid, posted_by='aid_disbursement')
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

    except Exception as e:
        print(f"Error applying aid to fees: {e}")

def create_payment_arrangement():
    """Create payment arrangements for collection cases"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = input("Enter student ID for payment arrangement: ").strip()

        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            return

        # Check for active collection case
        cursor.execute('''
        SELECT case_id, total_debt, case_status
        FROM collection_cases
        WHERE student_id = ? AND case_status NOT IN ('resolved', 'closed')
        ORDER BY created_at DESC
        LIMIT 1
        ''', (student_id,))

        case = cursor.fetchone()

        if not case:
            print(f"No active collection case found for student {student_id}.")
            return

        case_id, total_debt, case_status = case

        print(f"\nCreating Payment Arrangement:")
        print(f"Student: {get_student_name(student_id)} ({student_id})")
        print(f"Collection Case: {case_id}")
        print(f"Total Debt: £{total_debt:.2f}")

        # Get arrangement details
        try:
            arrangement_amount = float(input("Enter arrangement amount: £"))
            if arrangement_amount <= 0 or arrangement_amount > total_debt:
                print("Invalid arrangement amount.")
                return
        except ValueError:
            print("Invalid amount.")
            return

        # Get payment schedule
        print("\nPayment schedule options:")
        print("1. Single payment")
        print("2. Weekly payments")
        print("3. Monthly payments")
        print("4. Custom schedule")

        schedule_choice = input("Select schedule (1-4): ").strip()

        if schedule_choice == '1':
            # Single payment
            payment_date = input("Enter payment date (YYYY-MM-DD): ").strip()
            schedule_info = f"Single payment of £{arrangement_amount:.2f} due on {payment_date}"

        elif schedule_choice == '2':
            # Weekly payments
            num_weeks = int(input("Enter number of weeks: "))
            weekly_amount = arrangement_amount / num_weeks
            start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            schedule_info = f"£{weekly_amount:.2f} weekly for {num_weeks} weeks starting {start_date}"

        elif schedule_choice == '3':
            # Monthly payments
            num_months = int(input("Enter number of months: "))
            monthly_amount = arrangement_amount / num_months
            start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            schedule_info = f"£{monthly_amount:.2f} monthly for {num_months} months starting {start_date}"

        else:
            # Custom schedule
            schedule_info = input("Enter custom payment schedule details: ").strip()

        # Get agreement terms
        terms = input("Enter agreement terms and conditions: ").strip()

        # Update collection case with arrangement
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        arrangement_notes = f"PAYMENT ARRANGEMENT: {schedule_info}. Terms: {terms}. Arranged by: {get_current_user()['username'] if get_current_user() else 'system'}"

        cursor.execute('''
        UPDATE collection_cases
        SET case_status = 'in_progress',
            notes = COALESCE(notes, '') || ' | ' || ?,
            updated_at = ?
        WHERE case_id = ?
        ''', (arrangement_notes, now, case_id))

        conn.commit()

        print(f"\nPayment arrangement created successfully!")
        print(f"Case ID: {case_id}")
        print(f"Arrangement: {schedule_info}")
        print(f"Status updated to: In Progress")

        # Send confirmation to student
        send_arrangement_confirmation(student_id, case_id, schedule_info)

        conn.close()

    except Exception as e:
        print(f"Error creating payment arrangement: {e}")
