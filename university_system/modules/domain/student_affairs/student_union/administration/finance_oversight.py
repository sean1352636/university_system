# Standard library imports
import os
import random
from university_system.infrastructure.database.db import sqlite3
import string
from datetime import datetime
from typing import Optional

# Local imports
from university_system.infrastructure.database.db import DatabaseManager, get_connection
from university_system.infrastructure.email import send_confirmation_email
from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager

# --- Shared auth wiring ---
try:
    from university_system.infrastructure.auth.user_authentication import UserAuth, get_current_user, set_auth_instance
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
        print("You must be logged in to submit expense requests.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
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
            print("You are not an officer of any club.")
            conn.close()
            return
        
        print("\nYour clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")
        
        choice = input("Select a club for the expense request (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return
        
        club_id = clubs[int(choice)-1][0]
        club_name = clubs[int(choice)-1][1]
        
        print(f"\nSubmitting expense request for {club_name}")
        
        expense_type = input("Expense type (e.g., Catering, Equipment, Venue): ").strip()
        if not expense_type:
            print("Expense type cannot be empty.")
            conn.close()
            return
        
        try:
            amount = float(input("Amount (£): ").strip())
            if amount <= 0:
                print("Amount must be positive.")
                conn.close()
                return
        except ValueError:
            print("Invalid amount format.")
            conn.close()
            return
        
        description = input("Description: ").strip()
        if not description:
            print("Description cannot be empty.")
            conn.close()
            return
        
        budget_category = input("Budget category (leave blank if unsure): ").strip()
        receipt_path = input("Receipt file path (optional): ").strip()
        
        # Check club budget
        cursor.execute('''
        SELECT SUM(allocated_budget - spent_amount) as available_budget
        FROM club_budgets
        WHERE club_id = ? AND fiscal_year = ?
        ''', (club_id, datetime.now().strftime('%Y')))
        
        budget_result = cursor.fetchone()
        available_budget = budget_result[0] if budget_result[0] else 0
        
        if amount > available_budget:
            print(f"Warning: Requested amount (£{amount:.2f}) exceeds available budget (£{available_budget:.2f})")
            confirm = input("Continue anyway? (y/n): ").strip().lower()
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
        
        print(f"Expense request submitted successfully! Request ID: {expense_id}")
        print("Your request is pending approval.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def approve_expense_requests():
    """Approve or reject expense requests (for authorized users)"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to approve expenses.")
        return
    
    if not (auth.check_permission('manage_all_clubs') or auth.check_permission('manage_own_club')):
        print("You don't have permission to approve expenses.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
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
            print("No pending expense requests found.")
            conn.close()
            return
        
        print("\nPending Expense Requests:")
        print("========================")
        
        for i, request in enumerate(requests):
            print(f"\n{i+1}. Request ID: {request[0]}")
            print(f"   Club: {request[2]}")
            print(f"   Requested by: {request[3]} {request[4]}")
            print(f"   Type: {request[5]}")
            print(f"   Amount: £{request[6]:.2f}")
            print(f"   Description: {request[7]}")
            print(f"   Date: {request[8]}")
            print("-" * 40)
        
        choice = input("\nEnter the number of the request to process (or 0 to exit): ").strip()
        
        if choice == '0':
            conn.close()
            return
        
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(requests):
            print("Invalid selection.")
            conn.close()
            return
        
        selected = requests[int(choice)-1]
        expense_id = selected[0]
        club_id = selected[1]
        amount = selected[6]
        
        print(f"\nProcessing Request ID: {expense_id}")
        print("1. Approve request")
        print("2. Reject request")
        print("3. Request more information")
        
        action = input("Choose an action: ").strip()
        
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
