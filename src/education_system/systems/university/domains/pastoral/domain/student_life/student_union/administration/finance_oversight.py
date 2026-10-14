# Standard library imports
import os
import random
from education_system.systems.university.infrastructure.database.db import sqlite3
import string
from datetime import datetime
from typing import Optional

# Local imports
from education_system.systems.university.infrastructure.database.db import DatabaseManager, get_connection
from education_system.systems.university.infrastructure.i18n import get_text
from education_system.systems.university.infrastructure.email import send_confirmation_email
from education_system.systems.university.domains.academics.domain.services.academic_calendar.calendar_core import AcademicCalendarManager
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.identity import (
    current_student_id as _current_student_id,
)

# --- Shared auth wiring ---
try:
    from education_system.systems.university.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
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
        print(get_text("student_union.finance_oversight.login_required_submit", default="Login Required Submit"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = _current_student_id(cursor, auth)

        if not student_id:
            print(get_text("student_union.finance_oversight.no_student_record", default="No Student Record."))
            conn.close()
            return


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
            print(get_text("student_union.finance_oversight.not_club_officer", default="Not Club Officer"))
            conn.close()
            return

        print("\n" + get_text("student_union.finance_oversight.your_clubs", default="Your Clubs"))
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")

        choice = input(get_text("student_union.finance_oversight.select_club_prompt", default="Select Club: ")).strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print(get_text("student_union.finance_oversight.invalid_selection", default="Invalid Selection."))
            conn.close()
            return

        club_id = clubs[int(choice)-1][0]
        club_name = clubs[int(choice)-1][1]

        print("\n" + get_text("student_union.finance_oversight.submitting_expense_for", club_name=club_name, default="Submitting Expense For {club_name}"))

        expense_type = input(get_text("student_union.finance_oversight.expense_type_prompt", default="Expense Type: ")).strip()
        if not expense_type:
            print(get_text("student_union.finance_oversight.expense_type_empty", default="Expense Type Empty"))
            conn.close()
            return

        try:
            amount = float(input(get_text("student_union.finance_oversight.amount_prompt", default="Amount: ")).strip())
            if amount <= 0:
                print(get_text("student_union.finance_oversight.amount_positive", default="Amount Positive"))
                conn.close()
                return
        except ValueError:
            print(get_text("student_union.finance_oversight.invalid_amount", default="Invalid Amount."))
            conn.close()
            return

        description = input(get_text("student_union.finance_oversight.description_prompt", default="Description: ")).strip()
        if not description:
            print(get_text("student_union.finance_oversight.description_empty", default="Description Empty"))
            conn.close()
            return

        budget_category = input(get_text("student_union.finance_oversight.budget_category_prompt", default="Budget Category: ")).strip()
        receipt_path = input(get_text("student_union.finance_oversight.receipt_path_prompt", default="Receipt Path: ")).strip()

        # Check club budget
        cursor.execute('''
        SELECT SUM(allocated_budget - spent_amount) as available_budget
        FROM club_budgets
        WHERE club_id = ? AND fiscal_year = ?
        ''', (club_id, datetime.now().strftime('%Y')))

        budget_result = cursor.fetchone()
        available_budget = budget_result[0] if budget_result[0] else 0

        if amount > available_budget:
            print(get_text("student_union.finance_oversight.budget_exceeded_warning", amount=f"{amount:.2f}", available=f"{available_budget:.2f}", default="Budget Exceeded Warning {amount} {available}"))
            confirm = input(get_text("student_union.finance_oversight.continue_anyway", default="Continue Anyway")).strip().lower()
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

        print(get_text("student_union.finance_oversight.expense_submitted", expense_id=expense_id, default="Expense Submitted {expense_id}"))
        print(get_text("student_union.finance_oversight.request_pending", default="Request Pending"))

        conn.close()

    except sqlite3.Error as e:
        print(get_text("student_union.finance_oversight.database_error", error=str(e), default="Database Error {error}"))
    except Exception as e:
        print(get_text("student_union.finance_oversight.error_occurred", error=str(e), default="Error Occurred. {error}"))

def approve_expense_requests():
    """Approve or reject expense requests (for authorized users)"""
    global auth

    if not auth or not auth.current_user:
        print(get_text("student_union.finance_oversight.login_required_approve", default="Login Required Approve"))
        return

    if not (auth.check_permission('manage_all_clubs') or auth.check_permission('manage_own_club')):
        print(get_text("student_union.finance_oversight.no_permission_approve", default="No Permission Approve."))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = _current_student_id(cursor, auth)

        if not student_id:
            print(get_text("student_union.finance_oversight.no_student_record", default="No Student Record."))
            conn.close()
            return


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
            print(get_text("student_union.finance_oversight.no_pending_requests", default="No Pending Requests."))
            conn.close()
            return

        print("\n" + get_text("student_union.finance_oversight.pending_requests_title", default="===== PENDING REQUESTS ====="))
        print("========================")

        for i, request in enumerate(requests):
            print(f"\n{i+1}. " + get_text("student_union.finance_oversight.request_id", request_id=request[0], default="Request ID {request_id}"))
            print("   " + get_text("student_union.finance_oversight.club_label", club=request[2], default="Club: {club}"))
            print("   " + get_text("student_union.finance_oversight.requested_by", name=f"{request[3]} {request[4]}", default="Requested By {name}"))
            print("   " + get_text("student_union.finance_oversight.type_label", type=request[5], default="Type: {type}"))
            print("   " + get_text("student_union.finance_oversight.amount_label", amount=f"{request[6]:.2f}", default="Amount: {amount}"))
            print("   " + get_text("student_union.finance_oversight.description_label", description=request[7], default="Description: {description}"))
            print("   " + get_text("student_union.finance_oversight.date_label", date=request[8], default="Date: {date}"))
            print("-" * 40)

        choice = input("\n" + get_text("student_union.finance_oversight.enter_request_number", default="Enter Request Number: ")).strip()

        if choice == '0':
            conn.close()
            return

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(requests):
            print(get_text("student_union.finance_oversight.invalid_selection", default="Invalid Selection."))
            conn.close()
            return

        selected = requests[int(choice)-1]
        expense_id = selected[0]
        club_id = selected[1]
        amount = selected[6]

        print("\n" + get_text("student_union.finance_oversight.processing_request", expense_id=expense_id, default="Processing Request {expense_id}"))
        print("1. " + get_text("student_union.finance_oversight.approve_option", default="Approve Option"))
        print("2. " + get_text("student_union.finance_oversight.reject_option", default="Reject Option"))
        print("3. " + get_text("student_union.finance_oversight.request_info_option", default="Request Info Option"))

        action = input(get_text("student_union.finance_oversight.choose_action", default="Choose Action")).strip()

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
