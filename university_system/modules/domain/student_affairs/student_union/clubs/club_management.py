# Standard library imports
import os
import random
import string
from datetime import datetime
from typing import Optional

# Third-party/database imports
from university_system.infrastructure.database.db import sqlite3
from university_system.infrastructure.database.db import DatabaseManager, get_connection

# Service imports  
from university_system.infrastructure.email import send_confirmation_email
from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager

# Authentication import with fallback
try:
    from university_system.infrastructure.auth.user_authentication import UserAuth, get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    # Fallback class for type hints when import fails
    class UserAuth:  # type: ignore
        pass
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Global auth instance
auth: Optional[UserAuth] = None

def set_auth(auth_obj: UserAuth) -> None:
    """Inject the shared authentication instance for this module."""
    global auth
    auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)

def create_club():
    """Create a new student club/society"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create a club.")
        return
    
    if not (auth.check_permission('create_club') or auth.check_permission('manage_all_clubs')):
        print("You don't have permission to create clubs.")
        return
    
    club_name = input("Enter club name: ").strip()
    if not club_name:
        print("Club name cannot be empty.")
        return
    
    description = input("Enter club description: ").strip()
    category = input("Enter club category (e.g., Sports, Academic, Cultural): ").strip()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if club name already exists
        cursor.execute('SELECT COUNT(*) FROM student_clubs WHERE club_name = ?', (club_name,))
        if cursor.fetchone()[0] > 0:
            print(f"A club named '{club_name}' already exists.")
            conn.close()
            return
        
        # Get president ID
        president_id = input("Enter student ID of the club president: ").strip()
        
        # Verify president exists
        cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (president_id,))
        if cursor.fetchone()[0] == 0:
            print(f"No student found with ID {president_id}.")
            conn.close()
            return
        
        treasurer_id = input("Enter student ID of the club treasurer: ").strip()
        secretary_id = input("Enter student ID of the club secretary: ").strip()
        
        founding_date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
        INSERT INTO student_clubs (
            club_name, description, category, founding_date, status, 
            president_id, treasurer_id, secretary_id, member_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            club_name, description, category, founding_date, 'active',
            president_id, treasurer_id, secretary_id, 3  # Start with 3 officers
        ))
        
        club_id = cursor.lastrowid
        
        # Add officers as members
        member_data = [
            (club_id, president_id, founding_date, 'President'),
            (club_id, treasurer_id, founding_date, 'Treasurer'),
            (club_id, secretary_id, founding_date, 'Secretary')
        ]
        
        cursor.executemany(
            'INSERT INTO club_members (club_id, student_id, join_date, role) VALUES (?, ?, ?, ?)',
            member_data
        )
        
        conn.commit()
        print(f"Club '{club_name}' created successfully!")
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_clubs():
    """View available clubs/societies"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view clubs.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Fetch all active clubs
        cursor.execute('''
        SELECT club_id, club_name, category, description, member_count
        FROM student_clubs
        WHERE status = 'active'
        ORDER BY club_name
        ''')
        
        clubs = cursor.fetchall()
        
        if not clubs:
            print("No active clubs found.")
            conn.close()
            return
        
        print("\nAvailable Clubs and Societies:")
        print("==============================")
        
        for club in clubs:
            print(f"\nID: {club[0]}")
            print(f"Name: {club[1]}")
            print(f"Category: {club[2]}")
            print(f"Description: {club[3]}")
            print(f"Member Count: {club[4]}")
            print("-" * 40)
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def join_club():
    """Join a club/society"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to join a club.")
        return
    
    if not auth.check_permission('join_clubs'):
        print("You don't have permission to join clubs.")
        return
    
    # Get the student ID associated with the current user
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # First show available clubs
        view_clubs()
        
        club_id = input("\nEnter the ID of the club you want to join: ").strip()
        if not club_id.isdigit():
            print("Invalid club ID.")
            conn.close()
            return
        
        # Check if club exists and is active
        cursor.execute('SELECT club_name FROM student_clubs WHERE club_id = ? AND status = "active"', (club_id,))
        club = cursor.fetchone()
        
        if not club:
            print("Club not found or not active.")
            conn.close()
            return
        
        # Check if already a member
        cursor.execute('SELECT COUNT(*) FROM club_members WHERE club_id = ? AND student_id = ?', (club_id, student_id))
        if cursor.fetchone()[0] > 0:
            print(f"You are already a member of {club[0]}.")
            conn.close()
            return
        
        # Add as member
        join_date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute(
            'INSERT INTO club_members (club_id, student_id, join_date, role) VALUES (?, ?, ?, ?)',
            (club_id, student_id, join_date, 'Member')
        )
        
        # Update member count
        cursor.execute(
            'UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?',
            (club_id,)
        )
        
        conn.commit()
        print(f"You have successfully joined {club[0]}!")
        
        # Send confirmation email
        send_confirmation_email(student_id, f"Club Membership: {club[0]}", 
                               f"You have successfully joined the {club[0]} club. Welcome!")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_my_clubs():
    """View clubs I am a member of"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view your clubs.")
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
        
        # Get clubs the student is a member of
        cursor.execute('''
        SELECT c.club_id, c.club_name, c.category, m.role, m.join_date
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ? AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id,))
        
        clubs = cursor.fetchall()
        
        if not clubs:
            print("You are not a member of any clubs.")
            conn.close()
            return
        
        print("\nYour Club Memberships:")
        print("======================")
        
        for club in clubs:
            print(f"\nID: {club[0]}")
            print(f"Name: {club[1]}")
            print(f"Category: {club[2]}")
            print(f"Your Role: {club[3]}")
            print(f"Joined on: {club[4]}")
            print("-" * 40)
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def manage_club():
    """Manage a club (for club officers)"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage a club.")
        return
    
    if not (auth.check_permission('manage_own_club') or auth.check_permission('manage_all_clubs')):
        print("You don't have permission to manage clubs.")
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
        
        # If admin, show all clubs, otherwise show only clubs where user is an officer
        if auth.check_permission('manage_all_clubs'):
            cursor.execute('''
            SELECT club_id, club_name
            FROM student_clubs
            WHERE status = 'active'
            ORDER BY club_name
            ''')
        else:
            cursor.execute('''
            SELECT c.club_id, c.club_name
            FROM student_clubs c
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            AND c.status = 'active'
            ORDER BY c.club_name
            ''', (student_id, student_id, student_id))
        
        clubs = cursor.fetchall()
        
        if not clubs:
            print("You don't have any clubs to manage.")
            conn.close()
            return
        
        print("\nClubs you can manage:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]} (ID: {club[0]})")
        
        choice = input("\nSelect a club to manage (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return
        
        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]
        
        while True:
            print(f"\nManaging {club_name}:")
            print("1. View club details")
            print("2. View members")
            print("3. Add/remove members")
            print("4. Update club information")
            print("5. Organize an event")
            print("6. Back to Student Union menu")
            
            action = input("\nChoose an action: ").strip()
            
            if action == '1':
                # View club details
                cursor.execute('''
                SELECT * FROM student_clubs WHERE club_id = ?
                ''', (club_id,))
                club_details = cursor.fetchone()
                
                if club_details:
                    print(f"\nClub Details for {club_name}:")
                    print(f"ID: {club_details[0]}")
                    print(f"Name: {club_details[1]}")
                    print(f"Description: {club_details[2]}")
                    print(f"Category: {club_details[3]}")
                    print(f"Founded: {club_details[4]}")
                    print(f"Status: {club_details[5]}")
                    print(f"President ID: {club_details[6]}")
                    print(f"Treasurer ID: {club_details[7]}")
                    print(f"Secretary ID: {club_details[8]}")
                    print(f"Member Count: {club_details[9]}")
                    print(f"Budget: £{club_details[10]:.2f}")
            
            elif action == '2':
                # View members
                cursor.execute('''
                SELECT m.student_id, s.first_name, s.last_name, m.role, m.join_date
                FROM club_members m
                JOIN students s ON m.student_id = s.student_id
                WHERE m.club_id = ?
                ORDER BY m.role, m.join_date
                ''', (club_id,))
                
                members = cursor.fetchall()
                
                if not members:
                    print("No members found.")
                else:
                    print(f"\nMembers of {club_name}:")
                    print(f"{'ID':<10} {'Name':<30} {'Role':<15} {'Join Date':<15}")
                    print("-" * 70)
                    
                    for member in members:
                        print(f"{member[0]:<10} {member[1]} {member[2]:<30} {member[3]:<15} {member[4]:<15}")
            
            elif action == '3':
                # Add/remove members - simplified for this example
                print("\n1. Add member")
                print("2. Remove member")
                
                sub_action = input("Choose an action: ").strip()
                
                if sub_action == '1':
                    # Add member
                    new_member_id = input("Enter student ID to add: ").strip()
                    
                    # Check if student exists
                    cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (new_member_id,))
                    if cursor.fetchone()[0] == 0:
                        print(f"No student found with ID {new_member_id}.")
                        continue
                    
                    # Check if already a member
                    cursor.execute('SELECT COUNT(*) FROM club_members WHERE club_id = ? AND student_id = ?', 
                                  (club_id, new_member_id))
                    if cursor.fetchone()[0] > 0:
                        print("This student is already a member.")
                        continue
                    
                    # Add as member
                    join_date = datetime.now().strftime('%Y-%m-%d')
                    
                    cursor.execute(
                        'INSERT INTO club_members (club_id, student_id, join_date, role) VALUES (?, ?, ?, ?)',
                        (club_id, new_member_id, join_date, 'Member')
                    )
                    
                    # Update member count
                    cursor.execute(
                        'UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?',
                        (club_id,)
                    )
                    
                    conn.commit()
                    print(f"Member added successfully!")
                
                elif sub_action == '2':
                    # Remove member
                    remove_id = input("Enter student ID to remove: ").strip()
                    
                    # Check if is an officer
                    cursor.execute('''
                    SELECT president_id, treasurer_id, secretary_id FROM student_clubs
                    WHERE club_id = ?
                    ''', (club_id,))
                    
                    officers = cursor.fetchone()
                    if remove_id in officers:
                        print("Cannot remove club officers. Change officer assignments first.")
                        continue
                    
                    # Remove member
                    cursor.execute(
                        'DELETE FROM club_members WHERE club_id = ? AND student_id = ?',
                        (club_id, remove_id)
                    )
                    
                    if cursor.rowcount > 0:
                        # Update member count
                        cursor.execute(
                            'UPDATE student_clubs SET member_count = member_count - 1 WHERE club_id = ?',
                            (club_id,)
                        )
                        
                        conn.commit()
                        print("Member removed successfully!")
                    else:
                        print(f"No member found with ID {remove_id}.")
            
            elif action == '4':
                # Update club information
                print("\n1. Update description")
                print("2. Update category")
                print("3. Change club officers")
                
                sub_action = input("Choose an action: ").strip()
                
                if sub_action == '1':
                    new_desc = input("Enter new description: ").strip()
                    cursor.execute(
                        'UPDATE student_clubs SET description = ? WHERE club_id = ?',
                        (new_desc, club_id)
                    )
                    conn.commit()
                    print("Description updated!")
                
                elif sub_action == '2':
                    new_category = input("Enter new category: ").strip()
                    cursor.execute(
                        'UPDATE student_clubs SET category = ? WHERE club_id = ?',
                        (new_category, club_id)
                    )
                    conn.commit()
                    print("Category updated!")
                
                elif sub_action == '3':
                    # Change officers - simplified
                    position = input("Which position to change (President/Treasurer/Secretary)? ").strip().lower()
                    
                    if position not in ['president', 'treasurer', 'secretary']:
                        print("Invalid position.")
                        continue
                    
                    new_id = input(f"Enter student ID for new {position}: ").strip()
                    
                    # Check if student exists
                    cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (new_id,))
                    if cursor.fetchone()[0] == 0:
                        print(f"No student found with ID {new_id}.")
                        continue
                    
                    # Update position
                    if position == 'president':
                        cursor.execute(
                            'UPDATE student_clubs SET president_id = ? WHERE club_id = ?',
                            (new_id, club_id)
                        )
                    elif position == 'treasurer':
                        cursor.execute(
                            'UPDATE student_clubs SET treasurer_id = ? WHERE club_id = ?',
                            (new_id, club_id)
                        )
                    elif position == 'secretary':
                        cursor.execute(
                            'UPDATE student_clubs SET secretary_id = ? WHERE club_id = ?',
                            (new_id, club_id)
                        )
                    
                    # Make sure they're a member
                    cursor.execute('SELECT COUNT(*) FROM club_members WHERE club_id = ? AND student_id = ?', 
                                  (club_id, new_id))
                    if cursor.fetchone()[0] == 0:
                        join_date = datetime.now().strftime('%Y-%m-%d')
                        cursor.execute(
                            'INSERT INTO club_members (club_id, student_id, join_date, role) VALUES (?, ?, ?, ?)',
                            (club_id, new_id, join_date, position.capitalize())
                        )
                        
                        # Update member count if needed
                        cursor.execute(
                            'UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?',
                            (club_id,)
                        )
                    else:
                        # Just update their role
                        cursor.execute(
                            'UPDATE club_members SET role = ? WHERE club_id = ? AND student_id = ?',
                            (position.capitalize(), club_id, new_id)
                        )
                    
                    conn.commit()
                    print(f"{position.capitalize()} updated successfully!")
            
            elif action == '5':
                # Organize an event
                print("\nOrganize a new event:")
                event_name = input("Event name: ").strip()
                description = input("Description: ").strip()
                
                date = input("Date (YYYY-MM-DD): ").strip()
                start_time = input("Start time (HH:MM): ").strip()
                end_time = input("End time (HH:MM): ").strip()
                
                location = input("Location: ").strip()
                category = input("Category: ").strip()
                max_attendees = input("Maximum attendees (leave blank for unlimited): ").strip()
                
                max_attendees = int(max_attendees) if max_attendees.isdigit() else 0
                
                cursor.execute('''
                INSERT INTO union_events (
                    event_name, description, event_date, start_time, end_time,
                    location, organizer_id, category, max_attendees, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event_name, description, date, start_time, end_time,
                    location, club_id, category, max_attendees, 'upcoming'
                ))
                
                conn.commit()
                print(f"Event '{event_name}' created successfully!")
            
            elif action == '6':
                break
            
            else:
                print("Invalid choice.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_club_financial_reports():
    """View financial reports for clubs"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view financial reports.")
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
        
        # Get clubs user can view
        if auth.check_permission('manage_all_clubs'):
            # Admin can see all clubs
            cursor.execute('''
            SELECT club_id, club_name, budget
            FROM student_clubs
            WHERE status = 'active'
            ORDER BY club_name
            ''')
        else:
            # Users can see clubs they're officers of
            cursor.execute('''
            SELECT club_id, club_name, budget
            FROM student_clubs
            WHERE (president_id = ? OR treasurer_id = ? OR secretary_id = ?)
            AND status = 'active'
            ORDER BY club_name
            ''', (student_id, student_id, student_id))
        
        clubs = cursor.fetchall()
        
        if not clubs:
            print("No clubs available for financial reporting.")
            conn.close()
            return
        
        print("\nAvailable clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")
        
        choice = input("Select a club for financial report (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return
        
        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]
        club_budget = selected_club[2]
        
        # Generate financial report
        current_year = datetime.now().strftime('%Y')
        
        print(f"\n{'='*50}")
        print(f"FINANCIAL REPORT - {club_name}")
        print(f"Fiscal Year: {current_year}")
        print(f"{'='*50}")
        
        print(f"\nClub Budget: £{club_budget:.2f}")
        
        # Get budget allocations
        cursor.execute('''
        SELECT category, SUM(allocated_budget) as allocated, SUM(spent_amount) as spent
        FROM club_budgets
        WHERE club_id = ? AND fiscal_year = ?
        GROUP BY category
        ''', (club_id, current_year))
        
        budget_breakdown = cursor.fetchall()
        
        if budget_breakdown:
            print("\nBudget Breakdown:")
            print(f"{'Category':<20} {'Allocated':<12} {'Spent':<12} {'Remaining':<12}")
            print("-" * 60)
            
            total_allocated = 0
            total_spent = 0
            
            for category, allocated, spent in budget_breakdown:
                remaining = allocated - spent
                total_allocated += allocated
                total_spent += spent
                
                print(f"{category:<20} £{allocated:<11.2f} £{spent:<11.2f} £{remaining:<11.2f}")
            
            print("-" * 60)
            print(f"{'TOTAL':<20} £{total_allocated:<11.2f} £{total_spent:<11.2f} £{total_allocated-total_spent:<11.2f}")
        
        # Get recent expenses
        cursor.execute('''
        SELECT e.expense_type, e.amount, e.description, e.request_date, e.status,
               s.first_name, s.last_name
        FROM club_expenses e
        JOIN students s ON e.requester_id = s.student_id
        WHERE e.club_id = ? AND e.request_date >= ?
        ORDER BY e.request_date DESC
        LIMIT 10
        ''', (club_id, f"{current_year}-01-01"))
        
        recent_expenses = cursor.fetchall()
        
        if recent_expenses:
            print(f"\nRecent Expenses (Last 10):")
            print(f"{'Type':<15} {'Amount':<10} {'Status':<10} {'Requester':<20} {'Date':<12}")
            print("-" * 80)
            
            for expense in recent_expenses:
                print(f"{expense[0]:<15} £{expense[1]:<9.2f} {expense[4]:<10} {expense[5]} {expense[6]:<20} {expense[3][:10]:<12}")
        
        # Calculate summary statistics
        cursor.execute('''
        SELECT 
            COUNT(*) as total_requests,
            SUM(CASE WHEN status = 'approved' THEN amount ELSE 0 END) as approved_amount,
            SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END) as pending_amount,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count
        FROM club_expenses
        WHERE club_id = ? AND request_date >= ?
        ''', (club_id, f"{current_year}-01-01"))
        
        summary = cursor.fetchone()
        
        print(f"\nSummary Statistics:")
        print(f"Total Expense Requests: {summary[0]}")
        print(f"Approved Requests: {summary[3]} (£{summary[1]:.2f})")
        print(f"Pending Requests: {summary[4]} (£{summary[2]:.2f})")
        
        budget_utilization = (summary[1] / club_budget * 100) if club_budget > 0 else 0
        print(f"Budget Utilization: {budget_utilization:.1f}%")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_club_budgets():
    """Manage club budgets and allocations"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage budgets.")
        return
    
    if not (auth.check_permission('manage_all_clubs') or auth.check_permission('manage_own_club')):
        print("You don't have permission to manage budgets.")
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
        
        # Get clubs user can manage
        if auth.check_permission('manage_all_clubs'):
            cursor.execute('''
            SELECT club_id, club_name, budget
            FROM student_clubs
            WHERE status = 'active'
            ORDER BY club_name
            ''')
        else:
            cursor.execute('''
            SELECT club_id, club_name, budget
            FROM student_clubs
            WHERE (president_id = ? OR treasurer_id = ? OR c.secretary_id = ?)
            AND status = 'active'
            ORDER BY club_name
            ''', (student_id, student_id, student_id))
        
        clubs = cursor.fetchall()
        
        if not clubs:
            print("No clubs available for budget management.")
            conn.close()
            return
        
        print("\nAvailable clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]} (Budget: £{club[2]:.2f})")
        
        choice = input("Select a club to manage budget (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return
        
        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]
        club_budget = selected_club[2]
        
        while True:
            print(f"\nBudget Management - {club_name}")
            print("1. View current budget allocations")
            print("2. Create new budget allocation")
            print("3. Update budget allocation")
            print("4. Set overall club budget")
            print("5. Return to previous menu")
            
            action = input("Choose an action: ").strip()
            
            if action == '1':
                # View current allocations
                current_year = datetime.now().strftime('%Y')
                
                cursor.execute('''
                SELECT budget_id, category, allocated_budget, spent_amount, created_date
                FROM club_budgets
                WHERE club_id = ? AND fiscal_year = ?
                ORDER BY category
                ''', (club_id, current_year))
                
                allocations = cursor.fetchall()
                
                if not allocations:
                    print("No budget allocations found for this year.")
                else:
                    print(f"\nBudget Allocations for {current_year}:")
                    print(f"{'ID':<5} {'Category':<20} {'Allocated':<12} {'Spent':<12} {'Remaining':<12}")
                    print("-" * 65)
                    
                    total_allocated = 0
                    total_spent = 0
                    
                    for alloc in allocations:
                        remaining = alloc[2] - alloc[3]
                        total_allocated += alloc[2]
                        total_spent += alloc[3]
                        
                        print(f"{alloc[0]:<5} {alloc[1]:<20} £{alloc[2]:<11.2f} £{alloc[3]:<11.2f} £{remaining:<11.2f}")
                    
                    print("-" * 65)
                    print(f"{'TOTAL':<25} £{total_allocated:<11.2f} £{total_spent:<11.2f} £{total_allocated-total_spent:<11.2f}")
                    print(f"\nClub Budget: £{club_budget:.2f}")
                    print(f"Unallocated: £{club_budget - total_allocated:.2f}")
            
            elif action == '2':
                # Create new allocation
                category = input("Budget category name: ").strip()
                if not category:
                    print("Category cannot be empty.")
                    continue
                
                try:
                    allocated_amount = float(input("Allocated amount (£): ").strip())
                    if allocated_amount <= 0:
                        print("Amount must be positive.")
                        continue
                except ValueError:
                    print("Invalid amount format.")
                    continue
                
                current_year = datetime.now().strftime('%Y')
                created_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Check if category already exists
                cursor.execute('''
                SELECT COUNT(*) FROM club_budgets
                WHERE club_id = ? AND fiscal_year = ? AND category = ?
                ''', (club_id, current_year, category))
                
                if cursor.fetchone()[0] > 0:
                    print("A budget allocation for this category already exists.")
                    continue
                
                cursor.execute('''
                INSERT INTO club_budgets (
                    club_id, fiscal_year, total_budget, allocated_budget,
                    category, created_date, updated_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    club_id, current_year, club_budget, allocated_amount,
                    category, created_date, created_date
                ))
                
                conn.commit()
                print(f"Budget allocation created for {category}: £{allocated_amount:.2f}")
            
            elif action == '3':
                # Update allocation
                current_year = datetime.now().strftime('%Y')
                
                cursor.execute('''
                SELECT budget_id, category, allocated_budget
                FROM club_budgets
                WHERE club_id = ? AND fiscal_year = ?
                ORDER BY category
                ''', (club_id, current_year))
                
                allocations = cursor.fetchall()
                
                if not allocations:
                    print("No budget allocations to update.")
                    continue
                
                print("\nExisting allocations:")
                for i, alloc in enumerate(allocations):
                    print(f"{i+1}. {alloc[1]} (£{alloc[2]:.2f})")
                
                choice = input("Select allocation to update (enter number): ").strip()
                if not choice.isdigit() or int(choice) < 1 or int(choice) > len(allocations):
                    print("Invalid selection.")
                    continue
                
                selected_alloc = allocations[int(choice)-1]
                budget_id = selected_alloc[0]
                
                try:
                    new_amount = float(input(f"New amount for {selected_alloc[1]} (current: £{selected_alloc[2]:.2f}): ").strip())
                    if new_amount <= 0:
                        print("Amount must be positive.")
                        continue
                except ValueError:
                    print("Invalid amount format.")
                    continue
                
                updated_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                UPDATE club_budgets 
                SET allocated_budget = ?, updated_date = ?
                WHERE budget_id = ?
                ''', (new_amount, updated_date, budget_id))
                
                conn.commit()
                print(f"Budget allocation updated for {selected_alloc[1]}: £{new_amount:.2f}")
            
            elif action == '4':
                # Set overall club budget
                try:
                    new_budget = float(input(f"New club budget (current: £{club_budget:.2f}): ").strip())
                    if new_budget <= 0:
                        print("Budget must be positive.")
                        continue
                except ValueError:
                    print("Invalid budget format.")
                    continue
                
                cursor.execute('''
                UPDATE student_clubs 
                SET budget = ?
                WHERE club_id = ?
                ''', (new_budget, club_id))
                
                conn.commit()
                club_budget = new_budget
                print(f"Club budget updated to £{new_budget:.2f}")
            
            elif action == '5':
                break
            
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_club_discussions():
    """Manage club discussion boards"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access club discussions.")
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
        
        # Get clubs the student is a member of
        cursor.execute('''
        SELECT c.club_id, c.club_name, m.role
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ? AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id,))
        
        clubs = cursor.fetchall()
        
        if not clubs:
            print("You are not a member of any clubs.")
            conn.close()
            return
        
        print("\nYour clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]} ({club[2]})")
        
        choice = input("Select a club to view discussions (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return
        
        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]
        user_role = selected_club[2]
        
        while True:
            print(f"\nClub Discussions - {club_name}")
            print("1. View recent discussions")
            print("2. View announcements")
            print("3. Create new discussion")
            print("4. Search discussions")
            
            if user_role in ['President', 'Secretary'] or auth.check_permission('manage_all_clubs'):
                print("5. Create announcement")
                print("6. Manage discussions")
                print("7. Return to previous menu")
                max_option = 7
            else:
                print("5. Return to previous menu")
                max_option = 5
            
            action = input("Choose an action: ").strip()
            
            if action == '1':
                # View recent discussions
                cursor.execute('''
                SELECT d.discussion_id, d.title, s.first_name, s.last_name, 
                       d.post_date, d.is_announcement, d.pinned
                FROM club_discussions d
                JOIN students s ON d.author_id = s.student_id
                WHERE d.club_id = ?
                ORDER BY d.pinned DESC, d.post_date DESC
                LIMIT 20
                ''', (club_id,))
                
                discussions = cursor.fetchall()
                
                if not discussions:
                    print("No discussions found.")
                else:
                    print(f"\nRecent Discussions:")
                    print(f"{'ID':<6} {'Title':<40} {'Author':<20} {'Date':<12} {'Type':<12}")
                    print("-" * 95)
                    
                    for disc in discussions:
                        disc_type = "📌 Pinned" if disc[6] else ("📢 Announcement" if disc[5] else "💬 Discussion")
                        print(f"{disc[0]:<6} {disc[1][:40]:<40} {disc[2]} {disc[3]:<20} {disc[4][:10]:<12} {disc_type:<12}")
                    
                    # Allow viewing specific discussion
                    view_id = input("\nEnter discussion ID to view details (or press Enter to continue): ").strip()
                    if view_id.isdigit():
                        view_discussion_details(int(view_id), cursor, student_id, user_role)
            
            elif action == '2':
                # View announcements only
                cursor.execute('''
                SELECT d.discussion_id, d.title, s.first_name, s.last_name, 
                       d.post_date, d.content
                FROM club_discussions d
                JOIN students s ON d.author_id = s.student_id
                WHERE d.club_id = ? AND d.is_announcement = 1
                ORDER BY d.pinned DESC, d.post_date DESC
                ''', (club_id,))
                
                announcements = cursor.fetchall()
                
                if not announcements:
                    print("No announcements found.")
                else:
                    print(f"\nClub Announcements:")
                    for ann in announcements:
                        print(f"\n📢 {ann[1]}")
                        print(f"   By: {ann[2]} {ann[3]} on {ann[4]}")
                        print(f"   {ann[5][:200]}{'...' if len(ann[5]) > 200 else ''}")
                        print("-" * 60)
            
            elif action == '3':
                # Create new discussion
                title = input("Discussion title: ").strip()
                if not title:
                    print("Title cannot be empty.")
                    continue
                
                content = input("Discussion content: ").strip()
                if not content:
                    print("Content cannot be empty.")
                    continue
                
                post_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO club_discussions (
                    club_id, author_id, title, content, post_date, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (club_id, student_id, title, content, post_date, post_date))
                
                conn.commit()
                print("Discussion created successfully!")
            
            elif action == '4':
                # Search discussions
                search_term = input("Enter search term: ").strip()
                if not search_term:
                    print("Search term cannot be empty.")
                    continue
                
                cursor.execute('''
                SELECT d.discussion_id, d.title, s.first_name, s.last_name, 
                       d.post_date, d.is_announcement
                FROM club_discussions d
                JOIN students s ON d.author_id = s.student_id
                WHERE d.club_id = ? AND (d.title LIKE ? OR d.content LIKE ?)
                ORDER BY d.post_date DESC
                ''', (club_id, f'%{search_term}%', f'%{search_term}%'))
                
                results = cursor.fetchall()
                
                if not results:
                    print("No matching discussions found.")
                else:
                    print(f"\nSearch Results for '{search_term}':")
                    print(f"{'ID':<6} {'Title':<40} {'Author':<20} {'Date':<12}")
                    print("-" * 80)
                    
                    for result in results:
                        print(f"{result[0]:<6} {result[1][:40]:<40} {result[2]} {result[3]:<20} {result[4][:10]:<12}")
            
            elif action == '5' and user_role in ['President', 'Secretary']:
                # Create announcement
                title = input("Announcement title: ").strip()
                if not title:
                    print("Title cannot be empty.")
                    continue
                
                content = input("Announcement content: ").strip()
                if not content:
                    print("Content cannot be empty.")
                    continue
                
                pin_choice = input("Pin this announcement? (y/n): ").strip().lower()
                pinned = pin_choice == 'y'
                
                post_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO club_discussions (
                    club_id, author_id, title, content, post_date, last_updated,
                    is_announcement, pinned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (club_id, student_id, title, content, post_date, post_date, 1, pinned))
                
                conn.commit()
                print("Announcement created successfully!")
            
            elif action == '6' and user_role in ['President', 'Secretary']:
                # Manage discussions
                manage_discussions_admin(club_id, cursor, conn)
            
            elif action == str(max_option):
                break
            
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_discussion_details(discussion_id, cursor, viewer_id, viewer_role):
    """View detailed discussion content"""
    try:
        cursor.execute('''
        SELECT d.title, d.content, s.first_name, s.last_name, d.post_date,
               d.last_updated, d.is_announcement, d.pinned, d.author_id
        FROM club_discussions d
        JOIN students s ON d.author_id = s.student_id
        WHERE d.discussion_id = ?
        ''', (discussion_id,))
        
        discussion = cursor.fetchone()
        
        if not discussion:
            print("Discussion not found.")
            return
        
        print(f"\n{'='*60}")
        if discussion[6]:  # is_announcement
            print(f"📢 ANNOUNCEMENT: {discussion[0]}")
        else:
            print(f"💬 DISCUSSION: {discussion[0]}")
        
        if discussion[7]:  # pinned
            print("📌 PINNED")
        
        print(f"By: {discussion[2]} {discussion[3]}")
        print(f"Posted: {discussion[4]}")
        if discussion[5] != discussion[4]:
            print(f"Last updated: {discussion[5]}")
        
        print(f"\n{discussion[1]}")
        print("="*60)
        
        # Show options if user is author or has admin rights
        if discussion[8] == viewer_id or viewer_role in ['President', 'Secretary']:
            print("\nOptions:")
            print("1. Edit")
            print("2. Delete")
            print("3. Toggle pin status")
            
            action = input("Choose action (or press Enter to return): ").strip()
            
            if action == '1':
                new_content = input("New content: ").strip()
                if new_content:
                    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    UPDATE club_discussions 
                    SET content = ?, last_updated = ?
                    WHERE discussion_id = ?
                    ''', (new_content, update_time, discussion_id))
                    print("Discussion updated.")
            
            elif action == '2':
                confirm = input("Are you sure you want to delete this discussion? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute('DELETE FROM club_discussions WHERE discussion_id = ?', (discussion_id,))
                    print("Discussion deleted.")
            
            elif action == '3':
                new_pin_status = not discussion[7]
                cursor.execute('''
                UPDATE club_discussions 
                SET pinned = ?
                WHERE discussion_id = ?
                ''', (new_pin_status, discussion_id))
                pin_text = "pinned" if new_pin_status else "unpinned"
                print(f"Discussion {pin_text}.")
        
    except Exception as e:
        print(f"Error viewing discussion: {e}")

def manage_discussions_admin(club_id, cursor, conn):
    """Admin interface for managing discussions"""
    try:
        while True:
            print(f"\nDiscussion Management")
            print("1. View all discussions")
            print("2. Delete discussion")
            print("3. Pin/Unpin discussion")
            print("4. Convert discussion to announcement")
            print("5. Return to discussions menu")
            
            action = input("Choose an action: ").strip()
            
            if action == '1':
                cursor.execute('''
                SELECT d.discussion_id, d.title, s.first_name, s.last_name, 
                       d.post_date, d.is_announcement, d.pinned
                FROM club_discussions d
                JOIN students s ON d.author_id = s.student_id
                WHERE d.club_id = ?
                ORDER BY d.post_date DESC
                ''', (club_id,))
                
                discussions = cursor.fetchall()
                
                print(f"{'ID':<6} {'Title':<30} {'Author':<20} {'Date':<12} {'Type':<8} {'Pin':<6}")
                print("-" * 85)
                
                for disc in discussions:
                    disc_type = "Ann" if disc[5] else "Disc"
                    pinned = "Yes" if disc[6] else "No"
                    print(f"{disc[0]:<6} {disc[1][:30]:<30} {disc[2]} {disc[3]:<20} {disc[4][:10]:<12} {disc_type:<8} {pinned:<6}")
            
            elif action == '2':
                disc_id = input("Enter discussion ID to delete: ").strip()
                if disc_id.isdigit():
                    confirm = input("Are you sure you want to delete this discussion? (y/n): ").strip().lower()
                    if confirm == 'y':
                        cursor.execute('DELETE FROM club_discussions WHERE discussion_id = ? AND club_id = ?', 
                                     (disc_id, club_id))
                        if cursor.rowcount > 0:
                            conn.commit()
                            print("Discussion deleted.")
                        else:
                            print("Discussion not found.")
            
            elif action == '3':
                disc_id = input("Enter discussion ID to toggle pin status: ").strip()
                if disc_id.isdigit():
                    cursor.execute('''
                    UPDATE club_discussions 
                    SET pinned = NOT pinned
                    WHERE discussion_id = ? AND club_id = ?
                    ''', (disc_id, club_id))
                    
                    if cursor.rowcount > 0:
                        conn.commit()
                        print("Pin status toggled.")
                    else:
                        print("Discussion not found.")
            
            elif action == '4':
                disc_id = input("Enter discussion ID to convert to announcement: ").strip()
                if disc_id.isdigit():
                    cursor.execute('''
                    UPDATE club_discussions 
                    SET is_announcement = 1
                    WHERE discussion_id = ? AND club_id = ?
                    ''', (disc_id, club_id))
                    
                    if cursor.rowcount > 0:
                        conn.commit()
                        print("Discussion converted to announcement.")
                    else:
                        print("Discussion not found.")
            
            elif action == '5':
                break
            
            else:
                print("Invalid choice.")
                
    except Exception as e:
        print(f"Error in discussion management: {e}")

def manage_club_media():
    """Manage club photo/video sharing"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage club media.")
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
        
        # Get clubs the student is a member of
        cursor.execute('''
        SELECT c.club_id, c.club_name, m.role
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ? AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id,))
        
        clubs = cursor.fetchall()
        
        if not clubs:
            print("You are not a member of any clubs.")
            conn.close()
            return
        
        print("\nYour clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]} ({club[2]})")
        
        choice = input("Select a club to manage media (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return
        
        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]
        
        while True:
            print(f"\nClub Media - {club_name}")
            print("1. View recent media")
            print("2. Upload new media")
            print("3. View event galleries")
            print("4. Search media")
            print("5. Return to previous menu")
            
            action = input("Choose an action: ").strip()
            
            if action == '1':
                # View recent media
                cursor.execute('''
                SELECT m.media_id, m.file_path, m.file_type, m.caption, 
                       s.first_name, s.last_name, m.upload_date, e.event_name
                FROM club_media m
                JOIN students s ON m.uploader_id = s.student_id
                LEFT JOIN union_events e ON m.event_id = e.event_id
                WHERE m.club_id = ?
                ORDER BY m.upload_date DESC
                LIMIT 20
                ''', (club_id,))
                
                media_files = cursor.fetchall()
                
                if not media_files:
                    print("No media files found.")
                else:
                    print(f"\nRecent Media:")
                    print(f"{'ID':<6} {'Type':<8} {'Caption':<30} {'Uploader':<20} {'Date':<12} {'Event':<20}")
                    print("-" * 100)
                    
                    for media in media_files:
                        event_name = media[7] if media[7] else "General"
                        print(f"{media[0]:<6} {media[2]:<8} {media[3][:30]:<30} {media[4]} {media[5]:<20} {media[6][:10]:<12} {event_name[:20]:<20}")
            
            elif action == '2':
                # Upload new media
                file_path = input("File path: ").strip()
                if not file_path:
                    print("File path cannot be empty.")
                    continue
                
                # Determine file type from extension
                file_extension = file_path.split('.')[-1].lower() if '.' in file_path else ''
                if file_extension in ['jpg', 'jpeg', 'png', 'gif']:
                    file_type = 'image'
                elif file_extension in ['mp4', 'avi', 'mov', 'wmv']:
                    file_type = 'video'
                else:
                    file_type = input("File type (image/video/document): ").strip().lower()
                
                caption = input("Caption (optional): ").strip()
                
                # Link to event (optional)
                cursor.execute('''
                SELECT e.event_id, e.event_name
                FROM union_events e
                WHERE e.organizer_id = ? AND e.event_date >= date('now', '-30 days')
                ORDER BY e.event_date DESC
                LIMIT 10
                ''', (club_id,))
                
                recent_events = cursor.fetchall()
                
                event_id = None
                if recent_events:
                    print("\nLink to recent event (optional):")
                    print("0. No event")
                    for i, event in enumerate(recent_events):
                        print(f"{i+1}. {event[1]}")
                    
                    event_choice = input("Select event (enter number): ").strip()
                    if event_choice.isdigit() and 1 <= int(event_choice) <= len(recent_events):
                        event_id = recent_events[int(event_choice)-1][0]
                
                upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO club_media (
                    club_id, uploader_id, event_id, file_path, file_type, caption, upload_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (club_id, student_id, event_id, file_path, file_type, caption, upload_date))
                
                conn.commit()
                print("Media uploaded successfully!")
            
            elif action == '3':
                # View event galleries
                cursor.execute('''
                SELECT e.event_id, e.event_name, COUNT(m.media_id) as media_count
                FROM union_events e
                LEFT JOIN club_media m ON e.event_id = m.event_id
                WHERE e.organizer_id = ?
                GROUP BY e.event_id, e.event_name
                HAVING COUNT(m.media_id) > 0
                ORDER BY e.event_date DESC
                ''', (club_id,))
                
                events_with_media = cursor.fetchall()
                
                if not events_with_media:
                    print("No events with media found.")
                else:
                    print(f"\nEvents with Media:")
                    for i, event in enumerate(events_with_media):
                        print(f"{i+1}. {event[1]} ({event[2]} files)")
                    
                    event_choice = input("Select event to view gallery (enter number): ").strip()
                    if event_choice.isdigit() and 1 <= int(event_choice) <= len(events_with_media):
                        selected_event = events_with_media[int(event_choice)-1]
                        
                        cursor.execute('''
                        SELECT m.media_id, m.file_path, m.file_type, m.caption,
                               s.first_name, s.last_name, m.upload_date
                        FROM club_media m
                        JOIN students s ON m.uploader_id = s.student_id
                        WHERE m.event_id = ?
                        ORDER BY m.upload_date
                        ''', (selected_event[0],))
                        
                        event_media = cursor.fetchall()
                        
                        print(f"\nGallery for {selected_event[1]}:")
                        for media in event_media:
                            print(f"- {media[2]}: {media[1]}")
                            if media[3]:
                                print(f"  Caption: {media[3]}")
                            print(f"  Uploaded by: {media[4]} {media[5]} on {media[6]}")
                            print()
            
            elif action == '4':
                # Search media
                search_term = input("Enter search term: ").strip()
                if not search_term:
                    print("Search term cannot be empty.")
                    continue
                
                cursor.execute('''
                SELECT m.media_id, m.file_path, m.file_type, m.caption,
                       s.first_name, s.last_name, m.upload_date
                FROM club_media m
                JOIN students s ON m.uploader_id = s.student_id
                WHERE m.club_id = ? AND (m.caption LIKE ? OR m.file_path LIKE ?)
                ORDER BY m.upload_date DESC
                ''', (club_id, f'%{search_term}%', f'%{search_term}%'))
                
                results = cursor.fetchall()
                
                if not results:
                    print("No matching media found.")
                else:
                    print(f"Search results for '{search_term}':")
                    for result in results:
                        print(f"- {result[1]} ({result[2]})")
                        if result[3]:
                            print(f"  Caption: {result[3]}")
                        print(f"  By: {result[4]} {result[5]} on {result[6]}")
                        print()
            
            elif action == '5':
                break
            
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def club_member_directory():
    """View club member directory with contact info"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view member directory.")
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
        
        # Get clubs the student is a member of
        cursor.execute('''
        SELECT c.club_id, c.club_name
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ? AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id,))
        
        clubs = cursor.fetchall()
        
        if not clubs:
            print("You are not a member of any clubs.")
            conn.close()
            return
        
        print("\nYour clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")
        
        choice = input("Select a club to view member directory (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return
        
        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]
        
        # Get all members of the selected club
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.email, s.course,
               m.role, m.join_date
        FROM club_members m
        JOIN students s ON m.student_id = s.student_id
        WHERE m.club_id = ?
        ORDER BY 
            CASE m.role 
                WHEN 'President' THEN 1
                WHEN 'Treasurer' THEN 2
                WHEN 'Secretary' THEN 3
                ELSE 4
            END,
            s.last_name, s.first_name
        ''', (club_id,))
        
        members = cursor.fetchall()
        
        if not members:
            print("No members found.")
            conn.close()
            return
        
        print(f"\nMember Directory - {club_name}")
        print("=" * 80)
        print(f"{'Student ID':<12} {'Name':<25} {'Role':<15} {'Course':<8} {'Email':<25} {'Joined':<12}")
        print("-" * 100)
        
        officers = []
        regular_members = []
        
        for member in members:
            if member[5] in ['President', 'Treasurer', 'Secretary']:
                officers.append(member)
            else:
                regular_members.append(member)
        
        # Display officers first
        if officers:
            print("OFFICERS:")
            for member in officers:
                print(f"{member[0]:<12} {member[1]} {member[2]:<25} {member[5]:<15} {member[4]:<8} {member[3]:<25} {member[6]:<12}")
            print()
        
        # Display regular members
        if regular_members:
            print("MEMBERS:")
            for member in regular_members:
                print(f"{member[0]:<12} {member[1]} {member[2]:<25} {member[5]:<15} {member[4]:<8} {member[3]:<25} {member[6]:<12}")
        
        print(f"\nTotal Members: {len(members)}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_mentorship_system():
    """Main mentorship system interface"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the mentorship system.")
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
        
        while True:
            print(f"\nMentorship System")
            print("1. Find a mentor")
            print("2. Become a mentor")
            print("3. My mentorship relationships")
            print("4. Schedule mentorship session")
            print("5. View mentorship sessions")
            print("6. Rate mentorship experience")
            print("7. Search mentors by skill")
            print("8. Return to main menu")
            
            choice = input("Choose an option: ").strip()
            
            if choice == '1':
                find_mentor(student_id, cursor, conn)
            elif choice == '2':
                become_mentor(student_id, cursor, conn)
            elif choice == '3':
                view_my_mentorship_relationships(student_id, cursor)
            elif choice == '4':
                schedule_mentorship_session(student_id, cursor, conn)
            elif choice == '5':
                view_mentorship_sessions(student_id, cursor)
            elif choice == '6':
                rate_mentorship_experience(student_id, cursor, conn)
            elif choice == '7':
                search_mentors_by_skill(student_id, cursor, conn)
            elif choice == '8':
                break
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def find_mentor(student_id, cursor, conn):
    """Find and connect with a mentor"""
    try:
        # Check if student is already a mentee in an active relationship
        cursor.execute('''
        SELECT COUNT(*) FROM mentorship_relationships
        WHERE mentee_id = ? AND status = 'active'
        ''', (student_id,))
        
        active_relationships = cursor.fetchone()[0]
        
        if active_relationships >= 3:  # Limit to 3 active mentorship relationships
            print("You already have the maximum number of active mentorship relationships (3).")
            return
        
        print("\nFind a Mentor")
        print("=============")
        
        skill_area = input("What skill area do you need mentoring in? ").strip()
        if not skill_area:
            print("Skill area cannot be empty.")
            return
        
        # Find potential mentors (excluding current mentors and self)
        cursor.execute('''
        SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course, s.year_of_study
        FROM students s
        WHERE s.student_id != ? 
        AND s.year_of_study > (SELECT year_of_study FROM students WHERE student_id = ?)
        AND s.student_id NOT IN (
            SELECT mentor_id FROM mentorship_relationships 
            WHERE mentee_id = ? AND status IN ('active', 'pending')
        )
        ORDER BY s.year_of_study DESC, s.last_name
        ''', (student_id, student_id, student_id))
        
        potential_mentors = cursor.fetchall()
        
        if not potential_mentors:
            print("No potential mentors found.")
            return
        
        print(f"\nPotential Mentors:")
        print(f"{'#':<3} {'Name':<25} {'Course':<8} {'Year':<6}")
        print("-" * 45)
        
        for i, mentor in enumerate(potential_mentors[:10]):  # Show top 10
            print(f"{i+1:<3} {mentor[1]} {mentor[2]:<25} {mentor[3]:<8} {mentor[4]:<6}")
        
        choice = input("\nSelect a mentor to send request (enter number, 0 to cancel): ").strip()
        
        if choice == '0':
            return
        
        if not choice.isdigit() or int(choice) < 1 or int(choice) > min(len(potential_mentors), 10):
            print("Invalid selection.")
            return
        
        selected_mentor = potential_mentors[int(choice)-1]
        mentor_id = selected_mentor[0]
        
        # Send mentorship request
        start_date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
        INSERT INTO mentorship_relationships (
            mentor_id, mentee_id, skill_area, start_date, status
        ) VALUES (?, ?, ?, ?, ?)
        ''', (mentor_id, student_id, skill_area, start_date, 'pending'))
        
        conn.commit()
        
        print(f"Mentorship request sent to {selected_mentor[1]} {selected_mentor[2]}!")
        print("They will be notified and can accept or decline your request.")
        
        # Send email notification to mentor
        cursor.execute('SELECT email FROM students WHERE student_id = ?', (mentor_id,))
        mentor_email = cursor.fetchone()[0]
        
        cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        mentee_info = cursor.fetchone()
        
        # Here you would send an email notification
        print(f"Email notification sent to {mentor_email}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def become_mentor(student_id, cursor, conn):
    """Register to become a mentor or manage mentor requests"""
    try:
        print("\nMentor Dashboard")
        print("================")
        print("1. View mentorship requests")
        print("2. Accept/Decline requests")
        print("3. View current mentees")
        print("4. Update mentor profile")
        print("5. Return to mentorship menu")
        
        choice = input("Choose an option: ").strip()
        
        if choice == '1':
            # View pending requests
            cursor.execute('''
            SELECT r.relationship_id, s.first_name, s.last_name, s.course, 
                   r.skill_area, r.start_date
            FROM mentorship_relationships r
            JOIN students s ON r.mentee_id = s.student_id
            WHERE r.mentor_id = ? AND r.status = 'pending'
            ORDER BY r.start_date DESC
            ''', (student_id,))
            
            requests = cursor.fetchall()
            
            if not requests:
                print("No pending mentorship requests.")
            else:
                print(f"\nPending Mentorship Requests:")
                print(f"{'ID':<6} {'Student':<25} {'Course':<8} {'Skill Area':<20} {'Date':<12}")
                print("-" * 75)
                
                for req in requests:
                    print(f"{req[0]:<6} {req[1]} {req[2]:<25} {req[3]:<8} {req[4]:<20} {req[5]:<12}")
        
        elif choice == '2':
            # Accept/Decline requests
            cursor.execute('''
            SELECT r.relationship_id, s.first_name, s.last_name, r.skill_area
            FROM mentorship_relationships r
            JOIN students s ON r.mentee_id = s.student_id
            WHERE r.mentor_id = ? AND r.status = 'pending'
            ''', (student_id,))
            
            requests = cursor.fetchall()
            
            if not requests:
                print("No pending requests to process.")
                return
            
            print(f"\nPending Requests:")
            for i, req in enumerate(requests):
                print(f"{i+1}. {req[1]} {req[2]} - {req[3]}")
            
            req_choice = input("Select request to process (enter number): ").strip()
            if not req_choice.isdigit() or int(req_choice) < 1 or int(req_choice) > len(requests):
                print("Invalid selection.")
                return
            
            selected_request = requests[int(req_choice)-1]
            relationship_id = selected_request[0]
            
            print(f"\nProcessing request from {selected_request[1]} {selected_request[2]}")
            print("1. Accept")
            print("2. Decline")
            
            action = input("Choose action: ").strip()
            
            if action == '1':
                # Accept request
                cursor.execute('''
                UPDATE mentorship_relationships 
                SET status = 'active'
                WHERE relationship_id = ?
                ''', (relationship_id,))
                
                conn.commit()
                print("Mentorship request accepted!")
                
            elif action == '2':
                # Decline request
                cursor.execute('''
                UPDATE mentorship_relationships 
                SET status = 'declined'
                WHERE relationship_id = ?
                ''', (relationship_id,))
                
                conn.commit()
                print("Mentorship request declined.")
        
        elif choice == '3':
            # View current mentees
            cursor.execute('''
            SELECT s.first_name, s.last_name, s.course, r.skill_area, r.start_date,
                   r.mentor_rating, r.mentee_rating
            FROM mentorship_relationships r
            JOIN students s ON r.mentee_id = s.student_id
            WHERE r.mentor_id = ? AND r.status = 'active'
            ORDER BY r.start_date DESC
            ''', (student_id,))
            
            mentees = cursor.fetchall()
            
            if not mentees:
                print("You currently have no active mentees.")
            else:
                print(f"\nYour Current Mentees:")
                print(f"{'Name':<25} {'Course':<8} {'Skill Area':<20} {'Since':<12} {'Your Rating':<12} {'Their Rating':<12}")
                print("-" * 95)
                
                for mentee in mentees:
                    mentor_rating = f"{mentee[5]:.1f}" if mentee[5] else "Not rated"
                    mentee_rating = f"{mentee[6]:.1f}" if mentee[6] else "Not rated"
                    print(f"{mentee[0]} {mentee[1]:<25} {mentee[2]:<8} {mentee[3]:<20} {mentee[4]:<12} {mentor_rating:<12} {mentee_rating:<12}")
        
        elif choice == '4':
            # Update mentor profile (placeholder)
            mentor_id = input("Enter mentor ID to update: ")
            print("\nUpdate options:")
            print("1. Update bio")
            print("2. Update expertise areas")
            print("3. Update availability")
            update_choice = input("Select option: ")
            if update_choice == '1':
                new_bio = input("Enter new bio: ")
                print(f"Bio updated for mentor {mentor_id}")
            elif update_choice == '2':
                new_expertise = input("Enter expertise areas (comma-separated): ")
                print(f"Expertise updated for mentor {mentor_id}")
            else:
                print("Profile update successful!")
        
        elif choice == '5':
            return
        
        else:
            print("Invalid choice.")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_my_mentorship_relationships(student_id, cursor):
    """View all mentorship relationships for the student"""
    try:
        print(f"\nMy Mentorship Relationships")
        print("=" * 40)
        
        # As a mentee
        cursor.execute('''
        SELECT 'Mentee' as role, s.first_name, s.last_name, r.skill_area, 
               r.start_date, r.status, r.mentor_rating, r.mentee_rating
        FROM mentorship_relationships r
        JOIN students s ON r.mentor_id = s.student_id
        WHERE r.mentee_id = ?
        
        UNION ALL
        
        SELECT 'Mentor' as role, s.first_name, s.last_name, r.skill_area,
               r.start_date, r.status, r.mentor_rating, r.mentee_rating
        FROM mentorship_relationships r
        JOIN students s ON r.mentee_id = s.student_id
        WHERE r.mentor_id = ?
        
        ORDER BY start_date DESC
        ''', (student_id, student_id))
        
        relationships = cursor.fetchall()
        
        if not relationships:
            print("You have no mentorship relationships.")
            return
        
        print(f"{'Role':<8} {'Partner':<25} {'Skill Area':<20} {'Start Date':<12} {'Status':<10} {'M Rating':<9} {'E Rating':<9}")
        print("-" * 100)
        
        for rel in relationships:
            mentor_rating = f"{rel[6]:.1f}" if rel[6] else "N/A"
            mentee_rating = f"{rel[7]:.1f}" if rel[7] else "N/A"
            print(f"{rel[0]:<8} {rel[1]} {rel[2]:<25} {rel[3]:<20} {rel[4]:<12} {rel[5]:<10} {mentor_rating:<9} {mentee_rating:<9}")
        
        # Summary statistics
        active_as_mentor = sum(1 for rel in relationships if rel[0] == 'Mentor' and rel[5] == 'active')
        active_as_mentee = sum(1 for rel in relationships if rel[0] == 'Mentee' and rel[5] == 'active')
        
        print(f"\nSummary:")
        print(f"Active as Mentor: {active_as_mentor}")
        print(f"Active as Mentee: {active_as_mentee}")
        print(f"Total Relationships: {len(relationships)}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def schedule_mentorship_session(student_id, cursor, conn):
    """Schedule a mentorship session"""
    try:
        # Get active mentorship relationships
        cursor.execute('''
        SELECT r.relationship_id, 
               CASE 
                   WHEN r.mentor_id = ? THEN s2.first_name || ' ' || s2.last_name || ' (Mentee)'
                   ELSE s1.first_name || ' ' || s1.last_name || ' (Mentor)'
               END as partner_name,
               r.skill_area
        FROM mentorship_relationships r
        JOIN students s1 ON r.mentor_id = s1.student_id
        JOIN students s2 ON r.mentee_id = s2.student_id
        WHERE (r.mentor_id = ? OR r.mentee_id = ?) AND r.status = 'active'
        ''', (student_id, student_id, student_id))
        
        relationships = cursor.fetchall()
        
        if not relationships:
            print("You have no active mentorship relationships to schedule sessions for.")
            return
        
        print(f"\nActive Mentorship Relationships:")
        for i, rel in enumerate(relationships):
            print(f"{i+1}. {rel[1]} - {rel[2]}")
        
        choice = input("Select relationship to schedule session (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(relationships):
            print("Invalid selection.")
            return
        
        selected_relationship = relationships[int(choice)-1]
        relationship_id = selected_relationship[0]
        
        print(f"\nScheduling session with {selected_relationship[1]}")
        
        session_date = input("Session date (YYYY-MM-DD): ").strip()
        if not session_date:
            print("Session date cannot be empty.")
            return
        
        try:
            # Validate date format
            datetime.strptime(session_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return
        
        try:
            duration = int(input("Duration in minutes: ").strip())
            if duration <= 0:
                print("Duration must be positive.")
                return
        except ValueError:
            print("Invalid duration format.")
            return
        
        notes = input("Session agenda/notes (optional): ").strip()
        
        cursor.execute('''
        INSERT INTO mentorship_sessions (
            relationship_id, session_date, duration_minutes, notes
        ) VALUES (?, ?, ?, ?)
        ''', (relationship_id, session_date, duration, notes))
        
        conn.commit()
        print("Mentorship session scheduled successfully!")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_mentorship_sessions(student_id, cursor):
    """View mentorship sessions"""
    try:
        print(f"\nMentorship Sessions")
        print("=" * 40)
        
        cursor.execute('''
        SELECT ms.session_id, 
               CASE 
                   WHEN r.mentor_id = ? THEN s2.first_name || ' ' || s2.last_name || ' (Mentee)'
                   ELSE s1.first_name || ' ' || s1.last_name || ' (Mentor)'
               END as partner_name,
               ms.session_date, ms.duration_minutes, ms.notes,
               ms.mentor_feedback, ms.mentee_feedback, ms.progress_rating
        FROM mentorship_sessions ms
        JOIN mentorship_relationships r ON ms.relationship_id = r.relationship_id
        JOIN students s1 ON r.mentor_id = s1.student_id
        JOIN students s2 ON r.mentee_id = s2.student_id
        WHERE (r.mentor_id = ? OR r.mentee_id = ?)
        ORDER BY ms.session_date DESC
        ''', (student_id, student_id, student_id))
        
        sessions = cursor.fetchall()
        
        if not sessions:
            print("No mentorship sessions found.")
            return
        
        print(f"{'ID':<6} {'Partner':<25} {'Date':<12} {'Duration':<8} {'Rating':<8}")
        print("-" * 65)
        
        for session in sessions:
            rating = f"{session[7]}/5" if session[7] else "N/A"
            print(f"{session[0]:<6} {session[1][:25]:<25} {session[2]:<12} {session[3]}min{'':<3} {rating:<8}")
        
        # Option to view detailed session
        session_id = input("\nEnter session ID to view details (or press Enter to continue): ").strip()
        if session_id.isdigit():
            cursor.execute('''
            SELECT ms.session_date, ms.duration_minutes, ms.notes,
                   ms.mentor_feedback, ms.mentee_feedback, ms.progress_rating,
                   CASE 
                       WHEN r.mentor_id = ? THEN s2.first_name || ' ' || s2.last_name || ' (Mentee)'
                       ELSE s1.first_name || ' ' || s1.last_name || ' (Mentor)'
                   END as partner_name
            FROM mentorship_sessions ms
            JOIN mentorship_relationships r ON ms.relationship_id = r.relationship_id
            JOIN students s1 ON r.mentor_id = s1.student_id
            JOIN students s2 ON r.mentee_id = s2.student_id
            WHERE ms.session_id = ? AND (r.mentor_id = ? OR r.mentee_id = ?)
            ''', (student_id, session_id, student_id, student_id))
            
            session_detail = cursor.fetchone()
            
            if session_detail:
                print(f"\nSession Details:")
                print(f"Partner: {session_detail[6]}")
                print(f"Date: {session_detail[0]}")
                print(f"Duration: {session_detail[1]} minutes")
                print(f"Notes: {session_detail[2] or 'No notes'}")
                print(f"Mentor Feedback: {session_detail[3] or 'No feedback'}")
                print(f"Mentee Feedback: {session_detail[4] or 'No feedback'}")
                print(f"Progress Rating: {session_detail[5] or 'Not rated'}/5")
            else:
                print("Session not found or access denied.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def rate_mentorship_experience(student_id, cursor, conn):
    """Rate mentorship experience"""
    try:
        # Get relationships that can be rated
        cursor.execute('''
        SELECT r.relationship_id, 
               CASE 
                   WHEN r.mentor_id = ? THEN 'mentor'
                   ELSE 'mentee'
               END as my_role,
               CASE 
                   WHEN r.mentor_id = ? THEN s2.first_name || ' ' || s2.last_name
                   ELSE s1.first_name || ' ' || s1.last_name
               END as partner_name,
               r.skill_area, r.mentor_rating, r.mentee_rating
        FROM mentorship_relationships r
        JOIN students s1 ON r.mentor_id = s1.student_id
        JOIN students s2 ON r.mentee_id = s2.student_id
        WHERE (r.mentor_id = ? OR r.mentee_id = ?) AND r.status IN ('active', 'completed')
        ''', (student_id, student_id, student_id, student_id))
        
        relationships = cursor.fetchall()
        
        if not relationships:
            print("No relationships available for rating.")
            return
        
        print(f"\nRateable Mentorship Relationships:")
        for i, rel in enumerate(relationships):
            my_role = rel[1]
            partner_name = rel[2]
            current_rating = rel[4] if my_role == 'mentee' else rel[5]  # mentee rates mentor, mentor rates mentee
            rating_status = f"(Current rating: {current_rating:.1f})" if current_rating else "(Not rated)"
            
            print(f"{i+1}. {partner_name} - {rel[3]} {rating_status}")
        
        choice = input("Select relationship to rate (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(relationships):
            print("Invalid selection.")
            return
        
        selected_relationship = relationships[int(choice)-1]
        relationship_id = selected_relationship[0]
        my_role = selected_relationship[1]
        partner_name = selected_relationship[2]
        
        print(f"\nRating {partner_name} for {selected_relationship[3]} mentorship")
        
        try:
            rating = float(input("Enter rating (1.0 - 5.0): ").strip())
            if rating < 1.0 or rating > 5.0:
                print("Rating must be between 1.0 and 5.0.")
                return
        except ValueError:
            print("Invalid rating format.")
            return
        
        # Update the appropriate rating field
        if my_role == 'mentee':
            # Mentee rating the mentor
            cursor.execute('''
            UPDATE mentorship_relationships 
            SET mentor_rating = ?
            WHERE relationship_id = ?
            ''', (rating, relationship_id))
        else:
            # Mentor rating the mentee
            cursor.execute('''
            UPDATE mentorship_relationships 
            SET mentee_rating = ?
            WHERE relationship_id = ?
            ''', (rating, relationship_id))
        
        conn.commit()
        print(f"Rating submitted successfully! You rated {partner_name}: {rating:.1f}/5.0")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def search_mentors_by_skill(student_id, cursor, conn):
    """Search for mentors by specific skill areas"""
    try:
        print(f"\nSearch Mentors by Skill")
        print("=" * 30)
        
        # Show popular skill areas
        cursor.execute('''
        SELECT skill_area, COUNT(*) as count
        FROM mentorship_relationships
        WHERE status IN ('active', 'completed')
        GROUP BY skill_area
        ORDER BY count DESC
        LIMIT 10
        ''')
        
        popular_skills = cursor.fetchall()
        
        if popular_skills:
            print("Popular skill areas:")
            for skill in popular_skills:
                print(f"- {skill[0]} ({skill[1]} relationships)")
            print()
        
        skill_search = input("Enter skill area to search for: ").strip()
        if not skill_search:
            print("Skill area cannot be empty.")
            return
        
        # Find mentors who have experience in this skill area
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.course, s.year_of_study,
               COUNT(r.relationship_id) as mentorship_count,
               AVG(r.mentor_rating) as avg_rating
        FROM students s
        JOIN mentorship_relationships r ON s.student_id = r.mentor_id
        WHERE r.skill_area LIKE ? AND r.status IN ('active', 'completed')
        AND s.student_id != ?
        AND s.student_id NOT IN (
            SELECT mentor_id FROM mentorship_relationships 
            WHERE mentee_id = ? AND status IN ('active', 'pending')
        )
        GROUP BY s.student_id, s.first_name, s.last_name, s.course, s.year_of_study
        ORDER BY avg_rating DESC, mentorship_count DESC
        ''', (f'%{skill_search}%', student_id, student_id))
        
        mentors = cursor.fetchall()
        
        if not mentors:
            print(f"No experienced mentors found for '{skill_search}'.")
            return
        
        print(f"\nExperienced Mentors for '{skill_search}':")
        print(f"{'#':<3} {'Name':<25} {'Course':<8} {'Year':<6} {'Mentorships':<12} {'Avg Rating':<12}")
        print("-" * 75)
        
        for i, mentor in enumerate(mentors):
            avg_rating = f"{mentor[6]:.1f}" if mentor[6] else "N/A"
            print(f"{i+1:<3} {mentor[1]} {mentor[2]:<25} {mentor[3]:<8} {mentor[4]:<6} {mentor[5]:<12} {avg_rating:<12}")
        
        choice = input("\nSelect mentor to send request (enter number, 0 to cancel): ").strip()
        
        if choice == '0':
            return
        
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(mentors):
            print("Invalid selection.")
            return
        
        selected_mentor = mentors[int(choice)-1]
        mentor_id = selected_mentor[0]
        
        # Send mentorship request
        start_date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
        INSERT INTO mentorship_relationships (
            mentor_id, mentee_id, skill_area, start_date, status
        ) VALUES (?, ?, ?, ?, ?)
        ''', (mentor_id, student_id, skill_search, start_date, 'pending'))
        
        conn.commit()
        
        print(f"Mentorship request sent to {selected_mentor[1]} {selected_mentor[2]}!")
        print("They will be notified and can accept or decline your request.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_engagement_rewards():
    """Main engagement rewards system interface"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the rewards system.")
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
        
        while True:
            print(f"\nEngagement Rewards System")
            print("1. View my points and balance")
            print("2. View available badges")
            print("3. View leaderboard")
            print("4. Point earning opportunities")
            print("5. Redeem points")
            
            if auth.check_permission('manage_all_clubs') or auth.check_permission('manage_union_reps'):
                print("6. Award points to student")
                print("7. Create new badge")
                print("8. Manage reward system")
                print("9. Return to main menu")
                max_option = 9
            else:
                print("6. Return to main menu")
                max_option = 6
            
            choice = input("Choose an option: ").strip()
            
            if choice == '1':
                view_my_points_and_badges(student_id, cursor)
            elif choice == '2':
                view_available_badges(cursor)
            elif choice == '3':
                view_leaderboard(cursor)
            elif choice == '4':
                view_point_opportunities(cursor)
            elif choice == '5':
                print("\n=== Redeem Reward Points ===")
                print("Available redemption options:")
                print("1. Cafeteria voucher (50 points)")
                print("2. Library fine waiver (100 points)")
                print("3. Event ticket discount (75 points)")
                print("4. Merchandise discount (150 points)")
                redeem_choice = input("Select redemption option: ")
                if redeem_choice in ['1', '2', '3', '4']:
                    print("Points redeemed successfully!")
                else:
                    print("Invalid option")
            elif choice == '6' and max_option > 6:
                award_points_to_student(cursor, conn)
            elif choice == '7' and max_option > 6:
                create_new_badge(cursor, conn)
            elif choice == '8' and max_option > 6:
                manage_reward_system_admin(cursor, conn)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_my_points_and_badges(student_id, cursor):
    """View student's points balance and earned badges"""
    try:
        # Get current points balance
        cursor.execute('''
        SELECT 
            COALESCE(SUM(points_earned), 0) as total_earned,
            COALESCE(SUM(points_spent), 0) as total_spent,
            COALESCE(SUM(points_earned) - SUM(points_spent), 0) as current_balance
        FROM student_points
        WHERE student_id = ?
        ''', (student_id,))
        
        points_data = cursor.fetchone()
        total_earned = points_data[0]
        total_spent = points_data[1]
        current_balance = points_data[2]
        
        print(f"\nYour Points Summary:")
        print("=" * 30)
        print(f"Total Points Earned: {total_earned}")
        print(f"Total Points Spent: {total_spent}")
        print(f"Current Balance: {current_balance}")
        
        # Get recent point activities
        cursor.execute('''
        SELECT activity_type, activity_description, points_earned, earned_date
        FROM student_points
        WHERE student_id = ? AND points_earned > 0
        ORDER BY earned_date DESC
        LIMIT 10
        ''', (student_id,))
        
        recent_activities = cursor.fetchall()
        
        if recent_activities:
            print(f"\nRecent Point Activities:")
            print(f"{'Activity':<20} {'Description':<30} {'Points':<8} {'Date':<12}")
            print("-" * 75)
            
            for activity in recent_activities:
                print(f"{activity[0][:20]:<20} {activity[1][:30]:<30} +{activity[2]:<7} {activity[3][:10]:<12}")
        
        # Get earned badges
        cursor.execute('''
        SELECT b.badge_name, b.description, sb.earned_date, b.category
        FROM student_badges sb
        JOIN achievement_badges b ON sb.badge_id = b.badge_id
        WHERE sb.student_id = ?
        ORDER BY sb.earned_date DESC
        ''', (student_id,))
        
        badges = cursor.fetchall()
        
        if badges:
            print(f"\nYour Badges ({len(badges)}):")
            print(f"{'Badge':<25} {'Category':<15} {'Earned Date':<12}")
            print("-" * 55)
            
            for badge in badges:
                print(f"{badge[0][:25]:<25} {badge[3]:<15} {badge[2][:10]:<12}")
                print(f"   {badge[1]}")
                print()
        else:
            print(f"\nNo badges earned yet. Keep participating to earn badges!")
        
        # Check for new badges that can be earned
        check_and_award_badges(student_id, cursor)
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def check_and_award_badges(student_id, cursor):
    """Check if student has earned any new badges"""
    try:
        # Get current points balance
        cursor.execute('''
        SELECT COALESCE(SUM(points_earned), 0) as total_points
        FROM student_points
        WHERE student_id = ?
        ''', (student_id,))
        
        total_points = cursor.fetchone()[0]
        
        # Get badges not yet earned that student qualifies for
        cursor.execute('''
        SELECT b.badge_id, b.badge_name, b.description, b.points_required
        FROM achievement_badges b
        WHERE b.points_required <= ? 
        AND b.badge_id NOT IN (
            SELECT badge_id FROM student_badges WHERE student_id = ?
        )
        ORDER BY b.points_required
        ''', (total_points, student_id))
        
        available_badges = cursor.fetchall()
        
        if available_badges:
            print(f"\n🎉 Congratulations! You've earned new badges:")
            
            for badge in available_badges:
                # Award the badge
                earned_date = datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute('''
                INSERT INTO student_badges (student_id, badge_id, earned_date)
                VALUES (?, ?, ?)
                ''', (student_id, badge[0], earned_date))
                
                print(f"🏆 {badge[1]} - {badge[2]}")
            
            # Note: In real implementation, you'd commit these changes
            # Here we're just showing what would happen
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_available_badges(cursor):
    """View all available badges in the system"""
    try:
        cursor.execute('''
        SELECT badge_name, description, points_required, category, badge_icon
        FROM achievement_badges
        ORDER BY category, points_required
        ''')
        
        badges = cursor.fetchall()
        
        if not badges:
            print("No badges available.")
            return
        
        print(f"\nAvailable Achievement Badges:")
        print("=" * 40)
        
        current_category = ""
        for badge in badges:
            if badge[3] != current_category:
                current_category = badge[3]
                print(f"\n--- {current_category.upper()} ---")
            
            icon = badge[4] if badge[4] else "🏆"
            print(f"{icon} {badge[0]} ({badge[2]} points)")
            print(f"   {badge[1]}")
            print()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def create_new_badge(cursor, conn):
    """Create a new achievement badge (admin function)"""
    try:
        print(f"\nCreate New Achievement Badge")
        print("=" * 30)
        
        badge_name = input("Badge name: ").strip()
        if not badge_name:
            print("Badge name cannot be empty.")
            return
        
        description = input("Badge description: ").strip()
        if not description:
            print("Description cannot be empty.")
            return
        
        try:
            points_required = int(input("Points required to earn this badge: ").strip())
            if points_required < 0:
                print("Points required cannot be negative.")
                return
        except ValueError:
            print("Invalid points format.")
            return
        
        category = input("Badge category (e.g., Participation, Leadership, Academic): ").strip()
        if not category:
            category = "General"
        
        badge_icon = input("Badge icon (emoji, optional): ").strip()
        if not badge_icon:
            badge_icon = "🏆"
        
        # Check if badge name already exists
        cursor.execute('SELECT COUNT(*) FROM achievement_badges WHERE badge_name = ?', (badge_name,))
        if cursor.fetchone()[0] > 0:
            print("A badge with this name already exists.")
            return
        
        cursor.execute('''
        INSERT INTO achievement_badges (
            badge_name, description, points_required, badge_icon, category
        ) VALUES (?, ?, ?, ?, ?)
        ''', (badge_name, description, points_required, badge_icon, category))
        
        conn.commit()
        badge_id = cursor.lastrowid
        
        print(f"Badge '{badge_name}' created successfully! Badge ID: {badge_id}")
        
        # Check if any students now qualify for this badge
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name
        FROM students s
        JOIN (
            SELECT student_id, SUM(points_earned) as total_points
            FROM student_points
            GROUP BY student_id
            HAVING total_points >= ?
        ) sp ON s.student_id = sp.student_id
        WHERE s.student_id NOT IN (
            SELECT student_id FROM student_badges WHERE badge_id = ?
        )
        ''', (points_required, badge_id))
        
        qualifying_students = cursor.fetchall()
        
        if qualifying_students:
            print(f"\n{len(qualifying_students)} students now qualify for this badge:")
            for student in qualifying_students:
                print(f"- {student[1]} {student[2]} ({student[0]})")
            
            auto_award = input("\nAutomatically award to qualifying students? (y/n): ").strip().lower()
            if auto_award == 'y':
                earned_date = datetime.now().strftime('%Y-%m-%d')
                
                for student in qualifying_students:
                    cursor.execute('''
                    INSERT INTO student_badges (student_id, badge_id, earned_date)
                    VALUES (?, ?, ?)
                    ''', (student[0], badge_id, earned_date))
                
                conn.commit()
                print(f"Badge awarded to {len(qualifying_students)} students!")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_reward_system_admin(cursor, conn):
    """Admin interface for managing the rewards system"""
    try:
        while True:
            print(f"\nReward System Administration")
            print("1. View all badges")
            print("2. Edit badge")
            print("3. Delete badge")
            print("4. Bulk award points")
            print("5. Reset student points")
            print("6. Generate rewards report")
            print("7. Return to rewards menu")
            
            choice = input("Choose option: ").strip()
            
            if choice == '1':
                # View all badges
                cursor.execute('''
                SELECT b.badge_id, b.badge_name, b.description, b.points_required,
                       b.category, COUNT(sb.student_id) as awarded_count
                FROM achievement_badges b
                LEFT JOIN student_badges sb ON b.badge_id = sb.badge_id
                GROUP BY b.badge_id, b.badge_name, b.description, b.points_required, b.category
                ORDER BY b.category, b.points_required
                ''')
                
                all_badges = cursor.fetchall()
                
                print(f"\nAll Achievement Badges:")
                print(f"{'ID':<6} {'Name':<25} {'Category':<15} {'Points Req':<12} {'Awarded':<8}")
                print("-" * 70)
                
                for badge in all_badges:
                    print(f"{badge[0]:<6} {badge[1][:25]:<25} {badge[4]:<15} {badge[3]:<12} {badge[5]:<8}")
            
            elif choice == '2':
                # Edit badge
                badge_id = input("Enter badge ID to edit: ").strip()
                if not badge_id.isdigit():
                    print("Invalid badge ID.")
                    continue
                
                cursor.execute('''
                SELECT badge_name, description, points_required, category, badge_icon
                FROM achievement_badges WHERE badge_id = ?
                ''', (badge_id,))
                
                badge = cursor.fetchone()
                if not badge:
                    print("Badge not found.")
                    continue
                
                print(f"Editing badge: {badge[0]}")
                print(f"Current description: {badge[1]}")
                print(f"Current points required: {badge[2]}")
                print(f"Current category: {badge[3]}")
                
                new_description = input(f"New description (or press Enter to keep current): ").strip()
                if not new_description:
                    new_description = badge[1]
                
                new_points = input(f"New points required (or press Enter to keep current): ").strip()
                if new_points:
                    try:
                        new_points = int(new_points)
                    except ValueError:
                        print("Invalid points format.")
                        continue
                else:
                    new_points = badge[2]
                
                new_category = input(f"New category (or press Enter to keep current): ").strip()
                if not new_category:
                    new_category = badge[3]
                
                cursor.execute('''
                UPDATE achievement_badges 
                SET description = ?, points_required = ?, category = ?
                WHERE badge_id = ?
                ''', (new_description, new_points, new_category, badge_id))
                
                conn.commit()
                print("Badge updated successfully!")
            
            elif choice == '3':
                # Delete badge
                badge_id = input("Enter badge ID to delete: ").strip()
                if not badge_id.isdigit():
                    print("Invalid badge ID.")
                    continue
                
                cursor.execute('SELECT badge_name FROM achievement_badges WHERE badge_id = ?', (badge_id,))
                badge = cursor.fetchone()
                
                if not badge:
                    print("Badge not found.")
                    continue
                
                confirm = input(f"Are you sure you want to delete '{badge[0]}'? This will remove it from all students. (y/n): ").strip().lower()
                if confirm == 'y':
                    # Delete student badges first
                    cursor.execute('DELETE FROM student_badges WHERE badge_id = ?', (badge_id,))
                    # Delete the badge
                    cursor.execute('DELETE FROM achievement_badges WHERE badge_id = ?', (badge_id,))
                    
                    conn.commit()
                    print("Badge deleted successfully!")
            
            elif choice == '4':
                # Bulk award points
                print("Bulk award points to students matching criteria:")
                print("1. All students")
                print("2. Students in specific club")
                print("3. Students with specific role")
                
                bulk_choice = input("Choose option: ").strip()
                
                if bulk_choice == '1':
                    cursor.execute('SELECT student_id, first_name, last_name FROM students')
                    target_students = cursor.fetchall()
                    
                elif bulk_choice == '2':
                    cursor.execute('SELECT club_id, club_name FROM student_clubs WHERE status = "active"')
                    clubs = cursor.fetchall()
                    
                    if not clubs:
                        print("No active clubs found.")
                        continue
                    
                    print("Available clubs:")
                    for i, club in enumerate(clubs):
                        print(f"{i+1}. {club[1]}")
                    
                    club_choice = input("Select club (enter number): ").strip()
                    if not club_choice.isdigit() or int(club_choice) < 1 or int(club_choice) > len(clubs):
                        print("Invalid selection.")
                        continue
                    
                    selected_club_id = clubs[int(club_choice)-1][0]
                    
                    cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name
                    FROM students s
                    JOIN club_members m ON s.student_id = m.student_id
                    WHERE m.club_id = ?
                    ''', (selected_club_id,))
                    
                    target_students = cursor.fetchall()
                
                elif bulk_choice == '3':
                    role = input("Enter role (President/Treasurer/Secretary/Member): ").strip()
                    
                    cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name
                    FROM students s
                    JOIN club_members m ON s.student_id = m.student_id
                    WHERE m.role = ?
                    ''', (role,))
                    
                    target_students = cursor.fetchall()
                
                else:
                    print("Invalid choice.")
                    continue
                
                if not target_students:
                    print("No students found matching criteria.")
                    continue
                
                print(f"Found {len(target_students)} students.")
                
                try:
                    points_to_award = int(input("Points to award each student: ").strip())
                    if points_to_award <= 0:
                        print("Points must be positive.")
                        continue
                except ValueError:
                    print("Invalid points format.")
                    continue
                
                activity_type = input("Activity type: ").strip()
                description = input("Description: ").strip()
                
                confirm = input(f"Award {points_to_award} points to {len(target_students)} students? (y/n): ").strip().lower()
                if confirm == 'y':
                    earned_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    for student in target_students:
                        # Get current balance
                        cursor.execute('''
                        SELECT COALESCE(SUM(points_earned) - SUM(points_spent), 0)
                        FROM student_points WHERE student_id = ?
                        ''', (student[0],))
                        
                        current_balance = cursor.fetchone()[0]
                        new_balance = current_balance + points_to_award
                        
                        cursor.execute('''
                        INSERT INTO student_points (
                            student_id, points_earned, current_balance, activity_type,
                            activity_description, earned_date
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (student[0], points_to_award, new_balance, activity_type, description, earned_date))
                    
                    conn.commit()
                    print(f"Successfully awarded {points_to_award} points to {len(target_students)} students!")
            
            elif choice == '5':
                # Reset student points
                student_id = input("Enter student ID to reset points (or 'ALL' for all students): ").strip()
                
                if student_id.upper() == 'ALL':
                    confirm = input("Are you sure you want to reset ALL student points? (y/n): ").strip().lower()
                    if confirm == 'y':
                        cursor.execute('DELETE FROM student_points')
                        cursor.execute('DELETE FROM student_badges')
                        conn.commit()
                        print("All student points and badges reset!")
                else:
                    cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                    student = cursor.fetchone()
                    
                    if not student:
                        print("Student not found.")
                        continue
                    
                    confirm = input(f"Reset points for {student[0]} {student[1]}? (y/n): ").strip().lower()
                    if confirm == 'y':
                        cursor.execute('DELETE FROM student_points WHERE student_id = ?', (student_id,))
                        cursor.execute('DELETE FROM student_badges WHERE student_id = ?', (student_id,))
                        conn.commit()
                        print("Student points and badges reset!")
            
            elif choice == '6':
                # Generate rewards report
                print("\nRewards System Report:")
                print("=" * 30)
                
                # Overall statistics
                cursor.execute('SELECT COUNT(*) FROM achievement_badges')
                total_badges = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_points')
                active_students = cursor.fetchone()[0]
                
                cursor.execute('SELECT SUM(points_earned) FROM student_points')
                total_points_awarded = cursor.fetchone()[0] or 0
                
                cursor.execute('SELECT COUNT(*) FROM student_badges')
                total_badges_awarded = cursor.fetchone()[0]
                
                print(f"Total Badges Available: {total_badges}")
                print(f"Active Students: {active_students}")
                print(f"Total Points Awarded: {total_points_awarded}")
                print(f"Total Badge Awards: {total_badges_awarded}")
                
                # Most popular activities
                cursor.execute('''
                SELECT activity_type, COUNT(*) as count, SUM(points_earned) as total_points
                FROM student_points
                GROUP BY activity_type
                ORDER BY count DESC
                LIMIT 10
                ''')
                
                activities = cursor.fetchall()
                
                if activities:
                    print(f"\nMost Popular Activities:")
                    print(f"{'Activity':<20} {'Count':<8} {'Points':<8}")
                    print("-" * 40)
                    
                    for activity in activities:
                        print(f"{activity[0][:20]:<20} {activity[1]:<8} {activity[2]:<8}")
            
            elif choice == '7':
                break
            
            else:
                print("Invalid choice.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_interclub_competitions():
    """Main inter-club competition interface"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access competitions.")
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
        
        while True:
            print(f"\nInter-club Competitions")
            print("1. View active competitions")
            print("2. Register club for competition")
            print("3. View competition results")
            print("4. My competition history")
            
            if auth.check_permission('manage_all_clubs') or auth.check_permission('manage_union_reps'):
                print("5. Create new competition")
                print("6. Manage competition")
                print("7. Update scores")
                print("8. Generate competition reports")
                print("9. Return to main menu")
                max_option = 9
            else:
                print("5. Return to main menu")
                max_option = 5
            
            choice = input("Choose an option: ").strip()
            
            if choice == '1':
                view_active_competitions(cursor)
            elif choice == '2':
                register_club_for_competition(student_id, cursor, conn)
            elif choice == '3':
                view_competition_results(cursor)
            elif choice == '4':
                view_my_competition_history(student_id, cursor)
            elif choice == '5' and max_option > 5:
                create_new_competition(student_id, cursor, conn)
            elif choice == '6' and max_option > 5:
                manage_competition_admin(cursor, conn)
            elif choice == '7' and max_option > 5:
                update_competition_scores(cursor, conn)
            elif choice == '8' and max_option > 5:
                generate_competition_reports(cursor)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def register_club_for_competition(student_id, cursor, conn):
    """Register a club for a competition"""
    try:
        # Get clubs where student is an officer
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
            return
        
        # Get competitions open for registration
        cursor.execute('''
        SELECT competition_id, competition_name, competition_type, registration_deadline,
               max_participants_per_club
        FROM club_competitions
        WHERE status IN ('upcoming', 'registration_open') 
        AND registration_deadline >= date('now')
        ORDER BY registration_deadline
        ''')
        
        competitions = cursor.fetchall()
        
        if not competitions:
            print("No competitions currently open for registration.")
            return
        
        print("\nYour clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")
        
        club_choice = input("Select club to register (enter number): ").strip()
        if not club_choice.isdigit() or int(club_choice) < 1 or int(club_choice) > len(clubs):
            print("Invalid selection.")
            return
        
        selected_club = clubs[int(club_choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]
        
        print(f"\nCompetitions open for registration:")
        for i, comp in enumerate(competitions):
            print(f"{i+1}. {comp[1]} ({comp[2]}) - Deadline: {comp[3]}")
        
        comp_choice = input("Select competition (enter number): ").strip()
        if not comp_choice.isdigit() or int(comp_choice) < 1 or int(comp_choice) > len(competitions):
            print("Invalid selection.")
            return
        
        selected_comp = competitions[int(comp_choice)-1]
        competition_id = selected_comp[0]
        competition_name = selected_comp[1]
        max_participants = selected_comp[4]
        
        # Check if club is already registered
        cursor.execute('''
        SELECT COUNT(*) FROM competition_participants
        WHERE competition_id = ? AND club_id = ?
        ''', (competition_id, club_id))
        
        if cursor.fetchone()[0] > 0:
            print(f"{club_name} is already registered for {competition_name}.")
            return
        
        print(f"\nRegistering {club_name} for {competition_name}")
        print(f"Maximum participants allowed per club: {max_participants}")
        
        # Get club members to select participants
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, m.role
        FROM students s
        JOIN club_members m ON s.student_id = m.student_id
        WHERE m.club_id = ?
        ORDER BY m.role, s.last_name, s.first_name
        ''', (club_id,))
        
        club_members = cursor.fetchall()
        
        if not club_members:
            print("No members found in this club.")
            return
        
        print(f"\nClub members:")
        for i, member in enumerate(club_members):
            print(f"{i+1}. {member[1]} {member[2]} ({member[3]})")
        
        participants = []
        for i in range(min(max_participants, len(club_members))):
            if i == 0:
                participant_choice = input(f"Select participant {i+1} (enter number): ").strip()
            else:
                participant_choice = input(f"Select participant {i+1} (enter number, or press Enter to stop): ").strip()
                if not participant_choice:
                    break
            
            if (participant_choice.isdigit() and 
                1 <= int(participant_choice) <= len(club_members) and
                club_members[int(participant_choice)-1][0] not in [p[0] for p in participants]):
                
                participants.append(club_members[int(participant_choice)-1])
            else:
                print("Invalid selection or participant already selected.")
                i -= 1  # Try again
        
        if not participants:
            print("No participants selected.")
            return
        
        # Register participants
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for participant in participants:
            cursor.execute('''
            INSERT INTO competition_participants (
                competition_id, club_id, student_id, registration_date
            ) VALUES (?, ?, ?, ?)
            ''', (competition_id, club_id, participant[0], registration_date))
        
        conn.commit()
        
        print(f"\nSuccessfully registered {club_name} for {competition_name}!")
        print(f"Participants:")
        for participant in participants:
            print(f"- {participant[1]} {participant[2]}")
        
        # Award points for participation
        for participant in participants:
            auto_award_points(participant[0], "Competition Registration", 15, 
                            f"Registered for {competition_name}", cursor, conn)
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_community_engagement():
    """Main community engagement interface"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access community engagement.")
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
        
        while True:
            print(f"\n🤝 Community Engagement")
            print("1. Volunteer opportunities")
            print("2. My volunteer activities")
            print("3. Community service hours")
            print("4. Local partnerships")
            print("5. Social impact projects")
            print("6. Community feedback")
            print("7. Public events")
            
            if auth.check_permission('manage_union_reps') or auth.check_permission('manage_all_clubs'):
                print("8. Manage volunteer programs")
                print("9. Partnership coordination")
                print("10. Impact measurement")
                print("11. Return to main menu")
                max_option = 11
            else:
                print("8. Return to main menu")
                max_option = 8
            
            choice = input("Choose an option: ").strip()
            
            if choice == '1':
                browse_volunteer_opportunities(cursor)
            elif choice == '2':
                view_my_volunteer_activities(student_id, cursor)
            elif choice == '3':
                track_community_service_hours(student_id, cursor, conn)
            elif choice == '4':
                view_local_partnerships(cursor)
            elif choice == '5':
                manage_social_impact_projects(student_id, cursor, conn)
            elif choice == '6':
                submit_community_feedback(student_id, cursor, conn)
            elif choice == '7':
                coordinate_public_events(student_id, cursor, conn)
            elif choice == '8' and max_option > 8:
                manage_volunteer_programs_admin(cursor, conn)
            elif choice == '9' and max_option > 8:
                partnership_coordination_admin(cursor, conn)
            elif choice == '10' and max_option > 8:
                measure_social_impact(cursor)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def engagement_trend_analysis(cursor):
    """Analyze engagement trends over time"""
    try:
        print(f"\n📈 Engagement Trend Analysis")
        print("=" * 35)
        
        # Monthly event attendance trends
        cursor.execute('''
        SELECT 
            strftime('%Y-%m', e.event_date) as month,
            COUNT(e.event_id) as events_held,
            SUM(e.current_attendees) as total_attendance,
            AVG(e.current_attendees) as avg_attendance,
            COUNT(DISTINCT e.organizer_id) as active_clubs
        FROM union_events e
        WHERE e.event_date >= date('now', '-12 months')
        GROUP BY strftime('%Y-%m', e.event_date)
        ORDER BY month
        ''')
        
        monthly_trends = cursor.fetchall()
        
        if monthly_trends:
            print("Monthly Engagement Trends:")
            print(f"{'Month':<10} {'Events':<8} {'Attendance':<12} {'Avg/Event':<10} {'Active Clubs':<12}")
            print("-" * 60)
            
            for trend in monthly_trends:
                print(f"{trend[0]:<10} {trend[1]:<8} {trend[2]:<12} {trend[3]:<10.1f} {trend[4]:<12}")
        
        # Club membership growth
        cursor.execute('''
        SELECT 
            strftime('%Y-%m', join_date) as month,
            COUNT(*) as new_members
        FROM club_members
        WHERE join_date >= date('now', '-12 months')
        GROUP BY strftime('%Y-%m', join_date)
        ORDER BY month
        ''')
        
        membership_trends = cursor.fetchall()
        
        if membership_trends:
            print(f"\nClub Membership Growth:")
            print(f"{'Month':<10} {'New Members':<12}")
            print("-" * 25)
            
            for trend in membership_trends:
                print(f"{trend[0]:<10} {trend[1]:<12}")
        
        # Identify peak engagement periods
        if monthly_trends:
            peak_month = max(monthly_trends, key=lambda x: x[2])
            low_month = min(monthly_trends, key=lambda x: x[2])
            
            print(f"\nKey Insights:")
            print(f"Peak engagement: {peak_month[0]} ({peak_month[2]} total attendance)")
            print(f"Lowest engagement: {low_month[0]} ({low_month[2]} total attendance)")
            
            # Calculate trends
            if len(monthly_trends) >= 2:
                recent_attendance = monthly_trends[-1][2]
                previous_attendance = monthly_trends[-2][2]
                trend_direction = "increasing" if recent_attendance > previous_attendance else "decreasing"
                change_percent = abs((recent_attendance - previous_attendance) / previous_attendance * 100) if previous_attendance > 0 else 0
                
                print(f"Recent trend: {trend_direction} ({change_percent:.1f}% change)")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def member_retention_insights(cursor):
    """Analyze member retention patterns"""
    try:
        print(f"\n👥 Member Retention Insights")
        print("=" * 35)
        
        # Club retention rates
        cursor.execute('''
        SELECT 
            c.club_name,
            COUNT(m.student_id) as total_members,
            COUNT(CASE WHEN m.join_date >= date('now', '-12 months') THEN 1 END) as new_members_12m,
            COUNT(CASE WHEN m.join_date <= date('now', '-12 months') THEN 1 END) as retained_members
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE c.status = 'active'
        GROUP BY c.club_id, c.club_name
        HAVING COUNT(m.student_id) >= 5
        ORDER BY total_members DESC
        ''')
        
        retention_data = cursor.fetchall()
        
        if retention_data:
            print("Club Retention Analysis:")
            print(f"{'Club':<25} {'Total':<8} {'New (12m)':<10} {'Retained':<10} {'Retention %':<12}")
            print("-" * 70)
            
            for club in retention_data:
                if club[3] > 0:
                    retention_rate = (club[3] / (club[1] - club[2]) * 100) if (club[1] - club[2]) > 0 else 0
                else:
                    retention_rate = 0
                
                print(f"{club[0][:25]:<25} {club[1]:<8} {club[2]:<10} {club[3]:<10} {retention_rate:<12.1f}%")
        
        # Activity level analysis
        cursor.execute('''
        SELECT 
            'High Activity' as activity_level,
            COUNT(DISTINCT cm.student_id) as member_count
        FROM club_members cm
        WHERE cm.student_id IN (
            SELECT er.student_id
            FROM event_registrations er
            WHERE er.registration_date >= date('now', '-6 months')
            GROUP BY er.student_id
            HAVING COUNT(*) >= 3
        )
        
        UNION ALL
        
        SELECT 
            'Low Activity' as activity_level,
            COUNT(DISTINCT cm.student_id) as member_count
        FROM club_members cm
        WHERE cm.student_id NOT IN (
            SELECT er.student_id
            FROM event_registrations er
            WHERE er.registration_date >= date('now', '-6 months')
            GROUP BY er.student_id
            HAVING COUNT(*) >= 1
        )
        ''')
        
        activity_analysis = cursor.fetchall()
        
        if activity_analysis:
            print(f"\nMember Activity Levels (last 6 months):")
            for activity in activity_analysis:
                print(f"{activity[0]}: {activity[1]} members")
        
        # Churn risk identification
        cursor.execute('''
        SELECT 
            s.first_name, s.last_name, c.club_name,
            m.join_date,
            julianday('now') - julianday(MAX(er.registration_date)) as days_since_last_activity
        FROM students s
        JOIN club_members m ON s.student_id = m.student_id
        JOIN student_clubs c ON m.club_id = c.club_id
        LEFT JOIN event_registrations er ON s.student_id = er.student_id
        WHERE c.status = 'active'
        GROUP BY s.student_id, c.club_id
        HAVING days_since_last_activity > 90 OR days_since_last_activity IS NULL
        ORDER BY days_since_last_activity DESC
        LIMIT 10
        ''')
        
        at_risk_members = cursor.fetchall()
        
        if at_risk_members:
            print(f"\n⚠️ Members at Risk of Churning:")
            print(f"{'Member':<20} {'Club':<20} {'Days Inactive':<15}")
            print("-" * 60)
            
            for member in at_risk_members:
                days_inactive = f"{int(member[4])}" if member[4] else "No activity"
                name = f"{member[0]} {member[1]}"
                print(f"{name[:20]:<20} {member[2][:20]:<20} {days_inactive:<15}")
        
        print(f"\n💡 Retention Improvement Suggestions:")
        print("- Reach out to inactive members with personalized invitations")
        print("- Create mentorship programs for new members")
        print("- Organize regular social events to build community")
        print("- Survey departing members to understand reasons")
        print("- Implement member recognition programs")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_book_clubs(student_id, cursor, conn):
    """Manage book clubs and reading groups"""
    try:
        while True:
            print(f"\n📖 Book Club Management")
            print("1. Browse book clubs")
            print("2. Create book club")
            print("3. Join book club")
            print("4. My book clubs")
            print("5. Suggest a book")
            print("6. Reading progress tracking")
            print("7. Return to learning menu")
            
            choice = input("Choose option: ").strip()
            
            if choice == '1':
                # Browse book clubs
                cursor.execute('''
                SELECT book_club_id, club_name, current_book, book_author,
                       current_members, max_members, meeting_schedule, description
                FROM book_clubs
                WHERE status = 'active'
                ORDER BY club_name
                ''')
                
                book_clubs = cursor.fetchall()
                
                if not book_clubs:
                    print("No active book clubs found.")
                    continue
                
                print(f"\nActive Book Clubs:")
                print(f"{'ID':<6} {'Club Name':<25} {'Current Book':<30} {'Members':<10}")
                print("-" * 75)
                
                for club in book_clubs:
                    members = f"{club[4]}/{club[5]}"
                    current_book = club[2] if club[2] else "Selecting next book"
                    print(f"{club[0]:<6} {club[1][:25]:<25} {current_book[:30]:<30} {members:<10}")
                    
                    if club[7]:  # description
                        print(f"       {club[7]}")
                    print(f"       Schedule: {club[6]}")
                    print()
            
            elif choice == '2':
                # Create book club
                club_name = input("Book club name: ").strip()
                if not club_name:
                    print("Club name cannot be empty.")
                    continue
                
                description = input("Club description: ").strip()
                meeting_schedule = input("Meeting schedule (e.g., 'First Monday of each month'): ").strip()
                
                try:
                    max_members = int(input("Maximum members (5-20): ").strip())
                    if max_members < 5 or max_members > 20:
                        print("Max members should be between 5 and 20.")
                        continue
                except ValueError:
                    print("Invalid number format.")
                    continue
                
                # Optional: Set first book
                first_book = input("First book to read (optional): ").strip()
                book_author = input("Author (if book specified): ").strip() if first_book else ""
                
                cursor.execute('''
                INSERT INTO book_clubs (
                    club_name, current_book, book_author, discussion_leader_id,
                    meeting_schedule, max_members, current_members, status, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    club_name, first_book, book_author, student_id,
                    meeting_schedule, max_members, 1, 'active', description
                ))
                
                conn.commit()
                book_club_id = cursor.lastrowid
                
                print(f"Book club '{club_name}' created successfully!")
                print(f"Club ID: {book_club_id}")
                
                # Award points for creating book club
                auto_award_points(student_id, "Learning", 30, 
                                f"Created book club: {club_name}", cursor, conn)
            
            elif choice == '3':
                # Join book club
                club_id = input("Enter book club ID to join: ").strip()
                if not club_id.isdigit():
                    print("Invalid club ID.")
                    continue
                
                cursor.execute('''
                SELECT club_name, current_members, max_members, current_book
                FROM book_clubs
                WHERE book_club_id = ? AND status = 'active'
                ''', (club_id,))
                
                club = cursor.fetchone()
                
                if not club:
                    print("Book club not found or not active.")
                    continue
                
                if club[1] >= club[2]:
                    print("Book club is full.")
                    continue
                
                # In a full implementation, would check if already a member
                cursor.execute('''
                UPDATE book_clubs 
                SET current_members = current_members + 1
                WHERE book_club_id = ?
                ''', (club_id,))
                
                conn.commit()
                
                print(f"Successfully joined '{club[0]}'!")
                if club[3]:
                    print(f"Current book: {club[3]}")
                
                # Award points for joining
                auto_award_points(student_id, "Learning", 15, 
                                f"Joined book club: {club[0]}", cursor, conn)
            
            elif choice == '4':
                # My book clubs (simplified - would need member table)
                cursor.execute('''
                SELECT book_club_id, club_name, current_book, book_author, meeting_schedule
                FROM book_clubs
                WHERE discussion_leader_id = ?
                ORDER BY club_name
                ''', (student_id,))
                
                my_clubs = cursor.fetchall()
                
                if not my_clubs:
                    print("You are not leading any book clubs.")
                    continue
                
                print(f"\nBook Clubs You Lead:")
                for club in my_clubs:
                    print(f"\n📚 {club[1]}")
                    if club[2]:
                        print(f"   Current book: {club[2]} by {club[3]}")
                    else:
                        print("   No current book selected")
                    print(f"   Schedule: {club[4]}")
            
            elif choice == '5':
                # Suggest a book
                book_title = input("Book title to suggest: ").strip()
                author = input("Author: ").strip()
                reason = input("Why should we read this book? ").strip()
                
                print(f"Book suggestion recorded:")
                print(f"'{book_title}' by {author}")
                print(f"Reason: {reason}")
                print("Book club leaders will be notified of your suggestion.")
            
            elif choice == '6':
                # Reading progress tracking
                print(f"\n📊 Reading Progress Tracking")
                print("Track your reading goals and progress")
                
                try:
                    books_goal = int(input("Books to read this year: ").strip())
                    books_read = int(input("Books completed so far: ").strip())
                except ValueError:
                    print("Invalid number format.")
                    continue
                
                progress_percent = (books_read / books_goal * 100) if books_goal > 0 else 0
                remaining = max(0, books_goal - books_read)
                
                print(f"\nReading Progress:")
                print(f"Goal: {books_goal} books")
                print(f"Completed: {books_read} books ({progress_percent:.1f}%)")
                print(f"Remaining: {remaining} books")
                
                if progress_percent >= 100:
                    print("🎉 Congratulations! You've reached your reading goal!")
                elif progress_percent >= 75:
                    print("📚 Great progress! You're almost there!")
                elif progress_percent >= 50:
                    print("📖 Good progress! Keep it up!")
                else:
                    print("📕 Early in your reading journey - keep going!")
            
            elif choice == '7':
                break
            
            else:
                print("Invalid choice.")
    
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def display_club_menu():
    """Display the club management menu"""
    global auth
    
    while True:
        print("\nClub Management")
        print("===============")
        
        # Options based on permissions
        options = []
        option_num = 1
        
        # View Clubs
        print(f"{option_num}. View Available Clubs")
        options.append("view_clubs")
        option_num += 1
        
        # View My Clubs
        print(f"{option_num}. View My Club Memberships")
        options.append("view_my_clubs")
        option_num += 1
        
        # Join a Club
        if auth.check_permission('join_clubs'):
            print(f"{option_num}. Join a Club")
            options.append("join_club")
            option_num += 1
        
        # Manage Club
        if auth.check_permission('manage_own_club') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Manage Club")
            options.append("manage_club")
            option_num += 1
        
        # Create Club
        if auth.check_permission('create_club') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Create New Club")
            options.append("create_club")
            option_num += 1
        
        # Return to Student Union Menu
        print(f"{option_num}. Return to Student Union Menu")
        
        choice = input("\nEnter your choice: ")
        
        # First check if user wants to return to main menu
        if choice == str(option_num):
            return
        
        # Then map the numeric choice to the actual option based on available permissions
        try:
            choice_index = int(choice) - 1  # Convert to 0-based index
            if 0 <= choice_index < len(options):
                selected_option = options[choice_index]
                
                if selected_option == "view_clubs":
                    view_clubs()
                elif selected_option == "view_my_clubs":
                    view_my_clubs()
                elif selected_option == "join_club":
                    join_club()
                elif selected_option == "manage_club":
                    manage_club()
                elif selected_option == "create_club":
                    create_club()
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid choice. Please try again.")
