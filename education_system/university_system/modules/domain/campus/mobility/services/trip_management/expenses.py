from education_system.university_system.modules.domain.campus.mobility.services.trip_management import _common
from education_system.university_system.modules.domain.campus.mobility.services.trip_management._common import sqlite3, get_text, logging, datetime, log_create
from education_system.university_system.modules.domain.campus.mobility.services.trip_management.database import safe_db_operation


@log_create(module="trips", description="Managing trip expenses")
def manage_trip_expenses():
    """Manage expenses for trips"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_expenses", "You must be logged in to manage trip expenses."))
        return False

    if not auth.check_permission('manage_trip_expenses'):
        print(get_text("mobility.trip_management.auth.no_permission_expenses", "You don't have permission to manage trip expenses."))
        return False

    def manage_expenses_operation(conn):
        cursor = conn.cursor()

        # Get trips that user can manage expenses for
        cursor.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.status,
               COALESCE(SUM(te.amount), 0) as total_expenses
        FROM trips t
        LEFT JOIN trip_expenses te ON t.id = te.trip_id
        GROUP BY t.id
        ORDER BY t.start_date DESC
        ''')

        trips = cursor.fetchall()

        if not trips:
            print(get_text("mobility.trip_management.trips.no_trips_found", "No trips found."))
            return False

        print("\n" + get_text("mobility.trip_management.expenses.trips_with_expenses", "Trips with Expense Information:"))
        print("=" * 80)
        print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.total_expenses', 'Total Expenses'):<15}")
        print("-" * 80)

        for trip in trips:
            trip_id, name, destination, start_date, status, total_expenses = trip
            print(f"{trip_id:<5} {name[:24]:<25} {destination[:19]:<20} {start_date:<12} £{total_expenses:<14.2f}")

        print("=" * 80)

        try:
            trip_id = int(input(get_text("mobility.trip_management.expenses.enter_trip_id", "\nEnter Trip ID to manage expenses: ")))

            # Verify trip exists
            cursor.execute('SELECT trip_name FROM trips WHERE id = ?', (trip_id,))
            trip_result = cursor.fetchone()

            if not trip_result:
                print(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
                return False

            trip_name = trip_result[0]

            while True:
                # Get existing expenses
                cursor.execute('''
                SELECT te.id, te.category, te.description, te.amount, te.date,
                       u.first_name || ' ' || u.last_name as recorded_by
                FROM trip_expenses te
                LEFT JOIN users u ON te.recorded_by = u.id
                WHERE te.trip_id = ?
                ORDER BY te.date DESC
                ''', (trip_id,))

                expenses = cursor.fetchall()

                print(get_text("mobility.trip_management.expenses.for_trip", "\nExpenses for '{trip_name}':").format(trip_name=trip_name))
                print("=" * 100)

                if expenses:
                    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.category', 'Category'):<15} {get_text('mobility.trip_management.headers.description', 'Description'):<25} {get_text('mobility.trip_management.headers.amount', 'Amount'):<10} {get_text('mobility.trip_management.headers.date', 'Date'):<12} {get_text('mobility.trip_management.headers.recorded_by', 'Recorded By'):<15}")
                    print("-" * 100)

                    total_amount = 0
                    for expense in expenses:
                        exp_id, category, description, amount, date, recorded_by = expense
                        total_amount += amount
                        recorded_by = recorded_by if recorded_by else get_text("mobility.trip_management.common.unknown", "Unknown")
                        print(f"{exp_id:<5} {category[:14]:<15} {description[:24]:<25} £{amount:<9.2f} {date:<12} {recorded_by[:14]:<15}")

                    print("-" * 100)
                    print(get_text("mobility.trip_management.expenses.total", "Total Expenses: £{total:.2f}").format(total=total_amount))
                else:
                    print(get_text("mobility.trip_management.expenses.no_expenses", "No expenses recorded for this trip."))

                print("=" * 100)

                # Expense management options
                print("\n" + get_text("mobility.trip_management.expenses.management_options", "Expense Management Options:"))
                print(get_text("mobility.trip_management.expenses.option_add", "1. Add New Expense"))
                print(get_text("mobility.trip_management.expenses.option_edit", "2. Edit Expense"))
                print(get_text("mobility.trip_management.expenses.option_delete", "3. Delete Expense"))
                print(get_text("mobility.trip_management.expenses.option_back", "4. Back to Trip Selection"))

                choice = input(get_text("mobility.trip_management.common.enter_choice_1_4", "Enter choice (1-4): ")).strip()

                if choice == '1':
                    add_expense(conn, trip_id)
                elif choice == '2':
                    if expenses:
                        edit_expense(conn, trip_id, expenses)
                    else:
                        print(get_text("mobility.trip_management.expenses.no_expenses_to_edit", "No expenses to edit."))
                elif choice == '3':
                    if expenses:
                        delete_expense(conn, trip_id, expenses)
                    else:
                        print(get_text("mobility.trip_management.expenses.no_expenses_to_delete", "No expenses to delete."))
                elif choice == '4':
                    break
                else:
                    print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))

            return True

        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
            return False
        except Exception as e:
            print(get_text("mobility.trip_management.errors.managing_expenses", "Error managing expenses: {error}").format(error=e))
            logging.error(get_text("mobility.trip_management.errors.in_manage_expenses", "Error in manage_trip_expenses: {error}").format(error=e))
            return False

    return safe_db_operation(manage_expenses_operation)

def add_expense(conn, trip_id):
    """Add a new expense to a trip"""
    auth = _common.auth
    try:
        print("\n" + get_text("mobility.trip_management.expenses.add_new", "Add New Expense:"))

        # Expense categories
        categories = [
            'Transportation', 'Accommodation', 'Food', 'Activities',
            'Equipment', 'Insurance', 'Miscellaneous'
        ]

        print(get_text("mobility.trip_management.expenses.categories", "Expense Categories:"))
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")

        while True:
            try:
                cat_choice = int(input(get_text("mobility.trip_management.expenses.select_category", "Select category (1-7): "))) - 1
                if 0 <= cat_choice < len(categories):
                    category = categories[cat_choice]
                    break
                print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
            except ValueError:
                print(get_text("mobility.trip_management.validation.enter_number", "Please enter a number."))

        description = input(get_text("mobility.trip_management.expenses.description_prompt", "Description: ")).strip()
        if not description:
            print(get_text("mobility.trip_management.expenses.description_required", "Description is required."))
            return

        while True:
            try:
                amount = float(input(get_text("mobility.trip_management.expenses.amount_prompt", "Amount (£): ")))
                if amount >= 0:
                    break
                print(get_text("mobility.trip_management.validation.amount_non_negative", "Amount cannot be negative."))
            except ValueError:
                print(get_text("mobility.trip_management.validation.enter_valid_amount", "Please enter a valid amount."))

        while True:
            date_str = input(get_text("mobility.trip_management.expenses.date_prompt", "Date (YYYY-MM-DD, or press Enter for today): ")).strip()
            if not date_str:
                date_str = datetime.now().strftime('%Y-%m-%d')
                break
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                break
            except ValueError:
                print(get_text("mobility.trip_management.validation.invalid_date_format", "Invalid date format. Please use YYYY-MM-DD."))

        # Insert expense
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO trip_expenses (trip_id, category, description, amount, date, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (trip_id, category, description, amount, date_str, auth.current_user['id']))

        print(get_text("mobility.trip_management.expenses.added", "Expense added: {category} - {description} (£{amount:.2f})").format(category=category, description=description, amount=amount))

    except Exception as e:
        print(get_text("mobility.trip_management.errors.adding_expense", "Error adding expense: {error}").format(error=e))

def edit_expense(conn, trip_id, expenses):
    """Edit an existing expense"""
    try:
        expense_id = int(input(get_text("mobility.trip_management.expenses.enter_expense_id_edit", "Enter expense ID to edit: ")))

        # Find expense
        selected_expense = None
        for expense in expenses:
            if expense[0] == expense_id:
                selected_expense = expense
                break

        if not selected_expense:
            print(get_text("mobility.trip_management.expenses.expense_not_found", "Expense not found."))
            return

        exp_id, category, description, amount, date, recorded_by = selected_expense

        print(get_text("mobility.trip_management.expenses.editing", "\nEditing expense: {category} - {description}").format(category=category, description=description))
        print(get_text("mobility.trip_management.update.leave_blank", "Leave fields blank to keep current values."))

        new_description = input(get_text("mobility.trip_management.expenses.description_current", "Description (current: {current}): ").format(current=description)).strip()

        new_amount = input(get_text("mobility.trip_management.expenses.amount_current", "Amount (current: £{current:.2f}): ").format(current=amount)).strip()
        if new_amount:
            try:
                new_amount = float(new_amount)
                if new_amount < 0:
                    print(get_text("mobility.trip_management.validation.amount_non_negative_keeping", "Amount cannot be negative. Keeping current value."))
                    new_amount = None
            except ValueError:
                print(get_text("mobility.trip_management.validation.invalid_amount_keeping", "Invalid amount. Keeping current value."))
                new_amount = None

        new_date = input(get_text("mobility.trip_management.expenses.date_current", "Date (current: {current}): ").format(current=date)).strip()
        if new_date:
            try:
                datetime.strptime(new_date, '%Y-%m-%d')
            except ValueError:
                print(get_text("mobility.trip_management.validation.invalid_date_keeping", "Invalid date format. Keeping current value."))
                new_date = None

        # Build update query
        updates = []
        values = []

        if new_description:
            updates.append("description = ?")
            values.append(new_description)
        if new_amount is not None:
            updates.append("amount = ?")
            values.append(new_amount)
        if new_date:
            updates.append("date = ?")
            values.append(new_date)

        if not updates:
            print(get_text("mobility.trip_management.update.no_changes", "No changes to update."))
            return

        values.append(expense_id)

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trip_expenses SET " + ", ".join(updates) +
            " WHERE id = ?",
            values)

        print(get_text("mobility.trip_management.expenses.updated", "Expense updated successfully."))

    except ValueError:
        print(get_text("mobility.trip_management.expenses.invalid_expense_id", "Invalid expense ID."))
    except Exception as e:
        print(get_text("mobility.trip_management.errors.editing_expense", "Error editing expense: {error}").format(error=e))

def delete_expense(conn, trip_id, expenses):
    """Delete an expense"""
    try:
        expense_id = int(input(get_text("mobility.trip_management.expenses.enter_expense_id_delete", "Enter expense ID to delete: ")))

        # Find expense
        selected_expense = None
        for expense in expenses:
            if expense[0] == expense_id:
                selected_expense = expense
                break

        if not selected_expense:
            print(get_text("mobility.trip_management.expenses.expense_not_found", "Expense not found."))
            return

        exp_id, category, description, amount, date, recorded_by = selected_expense

        print(get_text("mobility.trip_management.expenses.delete_confirm", "\nDelete expense: {category} - {description} (£{amount:.2f})").format(category=category, description=description, amount=amount))
        confirm = input(get_text("mobility.trip_management.common.are_you_sure", "Are you sure? (y/n): ")).lower()

        if confirm == 'y':
            cursor = conn.cursor()
            cursor.execute('DELETE FROM trip_expenses WHERE id = ?', (expense_id,))
            print(get_text("mobility.trip_management.expenses.deleted", "Expense deleted successfully."))
        else:
            print(get_text("mobility.trip_management.common.deletion_cancelled", "Deletion cancelled."))

    except ValueError:
        print(get_text("mobility.trip_management.expenses.invalid_expense_id", "Invalid expense ID."))
    except Exception as e:
        print(get_text("mobility.trip_management.errors.deleting_expense", "Error deleting expense: {error}").format(error=e))
