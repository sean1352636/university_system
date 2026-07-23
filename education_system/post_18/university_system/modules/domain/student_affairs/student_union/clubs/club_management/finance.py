from education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state


def view_club_financial_reports():
    """View financial reports for clubs"""
    auth = _state.auth

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
            print("\nRecent Expenses (Last 10):")
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

        print("\nSummary Statistics:")
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
    auth = _state.auth

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
