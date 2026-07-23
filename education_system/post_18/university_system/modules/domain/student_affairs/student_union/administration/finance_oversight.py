# Standard library imports
import os
import random
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import string
from datetime import datetime
from typing import Optional

# Local imports
from education_system.post_18.university_system.infrastructure.database.db import DatabaseManager, get_connection
from education_system.post_18.university_system.core.i18n import get_text
from education_system.post_18.university_system.infrastructure.email import send_confirmation_email
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager

# --- Shared auth wiring ---
try:
    from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    # Fallback so type hints don't explode if import order differs in some environments
    class UserAuth:  # type: ignore
        pass
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# This module will receive the shared auth instance from the app entrypoint.
auth: Optional[UserAuth] = None

def set_auth(auth_obj: UserAuth) -> None:
    """Inject the shared authentication instance for this module."""
    global auth
    auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)
# --- end auth wiring ---

def submit_expense_request():
    """Submit an expense request for a club"""
    global auth

    if not auth or not auth.current_user:
        print(get_text("student_union.finance_oversight.login_required_submit"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print(get_text("student_union.finance_oversight.no_student_record"))
            conn.close()
            return

        student_id = result[0]

        # Get clubs where user is an officer
        cursor.execute('''
        SELECT c.club_id, c.club_name
        FROM student_clubs c
        WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
        AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id, student_id, student_id))

        clubs = cursor.fetchall()

        if not clubs:
            print(get_text("student_union.finance_oversight.not_club_officer"))
            conn.close()
            return

        print("\n" + get_text("student_union.finance_oversight.your_clubs"))
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")

        choice = input(get_text("student_union.finance_oversight.select_club_prompt")).strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print(get_text("student_union.finance_oversight.invalid_selection"))
            conn.close()
            return

        club_id = clubs[int(choice)-1][0]
        club_name = clubs[int(choice)-1][1]

        print("\n" + get_text("student_union.finance_oversight.submitting_expense_for", club_name=club_name))

        expense_type = input(get_text("student_union.finance_oversight.expense_type_prompt")).strip()
        if not expense_type:
            print(get_text("student_union.finance_oversight.expense_type_empty"))
            conn.close()
            return

        try:
            amount = float(input(get_text("student_union.finance_oversight.amount_prompt")).strip())
            if amount <= 0:
                print(get_text("student_union.finance_oversight.amount_positive"))
                conn.close()
                return
        except ValueError:
            print(get_text("student_union.finance_oversight.invalid_amount"))
            conn.close()
            return

        description = input(get_text("student_union.finance_oversight.description_prompt")).strip()
        if not description:
            print(get_text("student_union.finance_oversight.description_empty"))
            conn.close()
            return

        budget_category = input(get_text("student_union.finance_oversight.budget_category_prompt")).strip()
        receipt_path = input(get_text("student_union.finance_oversight.receipt_path_prompt")).strip()

        # Check club budget
        cursor.execute('''
        SELECT SUM(allocated_budget - spent_amount) as available_budget
        FROM club_budgets
        WHERE club_id = ? AND fiscal_year = ?
        ''', (club_id, datetime.now().strftime('%Y')))

        budget_result = cursor.fetchone()
        available_budget = budget_result[0] if budget_result[0] else 0

        if amount > available_budget:
            print(get_text("student_union.finance_oversight.budget_exceeded_warning", amount=f"{amount:.2f}", available=f"{available_budget:.2f}"))
            confirm = input(get_text("student_union.finance_oversight.continue_anyway")).strip().lower()
            if confirm != 'y':
                conn.close()
                return

        # Submit expense request
        request_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO club_expenses (
            club_id, requester_id, expense_type, amount, description,
            receipt_path, request_date, status, budget_category
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            club_id, student_id, expense_type, amount, description,
            receipt_path, request_date, 'pending', budget_category
        ))

        conn.commit()
        expense_id = cursor.lastrowid

        print(get_text("student_union.finance_oversight.expense_submitted", expense_id=expense_id))
        print(get_text("student_union.finance_oversight.request_pending"))

        conn.close()

    except sqlite3.Error as e:
        print(get_text("student_union.finance_oversight.database_error", error=str(e)))
    except Exception as e:
        print(get_text("student_union.finance_oversight.error_occurred", error=str(e)))

def approve_expense_requests():
    """Approve or reject expense requests (for authorized users)"""
    global auth

    if not auth or not auth.current_user:
        print(get_text("student_union.finance_oversight.login_required_approve"))
        return

    if not (auth.check_permission('manage_all_clubs') or auth.check_permission('manage_own_club')):
        print(get_text("student_union.finance_oversight.no_permission_approve"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print(get_text("student_union.finance_oversight.no_student_record"))
            conn.close()
            return

        student_id = result[0]

        # Get pending expense requests
        if auth.check_permission('manage_all_clubs'):
            # Admin can see all requests
            cursor.execute('''
            SELECT e.expense_id, e.club_id, c.club_name, s.first_name, s.last_name,
                   e.expense_type, e.amount, e.description, e.request_date
            FROM club_expenses e
            JOIN student_clubs c ON e.club_id = c.club_id
            JOIN students s ON e.requester_id = s.student_id
            WHERE e.status = 'pending'
            ORDER BY e.request_date
            ''')
        else:
            # Club officers can only see their club's requests
            cursor.execute('''
            SELECT e.expense_id, e.club_id, c.club_name, s.first_name, s.last_name,
                   e.expense_type, e.amount, e.description, e.request_date
            FROM club_expenses e
            JOIN student_clubs c ON e.club_id = c.club_id
            JOIN students s ON e.requester_id = s.student_id
            WHERE e.status = 'pending'
            AND (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            ORDER BY e.request_date
            ''', (student_id, student_id, student_id))

        requests = cursor.fetchall()

        if not requests:
            print(get_text("student_union.finance_oversight.no_pending_requests"))
            conn.close()
            return

        print("\n" + get_text("student_union.finance_oversight.pending_requests_title"))
        print("========================")

        for i, request in enumerate(requests):
            print(f"\n{i+1}. " + get_text("student_union.finance_oversight.request_id", request_id=request[0]))
            print("   " + get_text("student_union.finance_oversight.club_label", club=request[2]))
            print("   " + get_text("student_union.finance_oversight.requested_by", name=f"{request[3]} {request[4]}"))
            print("   " + get_text("student_union.finance_oversight.type_label", type=request[5]))
            print("   " + get_text("student_union.finance_oversight.amount_label", amount=f"{request[6]:.2f}"))
            print("   " + get_text("student_union.finance_oversight.description_label", description=request[7]))
            print("   " + get_text("student_union.finance_oversight.date_label", date=request[8]))
            print("-" * 40)

        choice = input("\n" + get_text("student_union.finance_oversight.enter_request_number")).strip()

        if choice == '0':
            conn.close()
            return

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(requests):
            print(get_text("student_union.finance_oversight.invalid_selection"))
            conn.close()
            return

        selected = requests[int(choice)-1]
        expense_id = selected[0]
        club_id = selected[1]
        amount = selected[6]

        print("\n" + get_text("student_union.finance_oversight.processing_request", expense_id=expense_id))
        print("1. " + get_text("student_union.finance_oversight.approve_option"))
        print("2. " + get_text("student_union.finance_oversight.reject_option"))
        print("3. " + get_text("student_union.finance_oversight.request_info_option"))

        action = input(get_text("student_union.finance_oversight.choose_action")).strip()

        if action == '1':
            # Approve request
            approval_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            UPDATE club_expenses
            SET status = 'approved', approval_date = ?, approver_id = ?
            WHERE expense_id = ?
            ''', ('approved', approval_date, student_id, expense_id))

            # Update club budget if exists
            cursor.execute('''
            UPDATE club_budgets
            SET spent_amount = spent_amount + ?
            WHERE club_id = ? AND fiscal_year = ?
            ''', (amount, club_id, datetime.now().strftime('%Y')))

            print("Expense request approved successfully!")

        elif action == '2':
            # Reject request
            reason = input("Reason for rejection: ").strip()
            approval_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            UPDATE club_expenses
            SET status = 'rejected', approval_date = ?, approver_id = ?, description = ?
            WHERE expense_id = ?
            ''', ('rejected', approval_date, student_id, f"{selected[7]} | REJECTED: {reason}", expense_id))

            print("Expense request rejected.")

        elif action == '3':
            # Request more info
            info_needed = input("What additional information is needed? ").strip()

            cursor.execute('''
            UPDATE club_expenses
            SET description = ?
            WHERE expense_id = ?
            ''', (f"{selected[7]} | INFO NEEDED: {info_needed}", expense_id))

            print("Request updated with information needed.")

        else:
            print("Invalid choice.")
            conn.close()
            return

        conn.commit()
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
