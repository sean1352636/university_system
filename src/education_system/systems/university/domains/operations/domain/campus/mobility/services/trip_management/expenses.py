from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import _common
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import sqlite3, get_text, logging, datetime, log_create
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.database import safe_db_operation

logger = logging.getLogger(__name__)

EXPENSE_CATEGORIES = (
    'Transportation', 'Accommodation', 'Food', 'Activities',
    'Equipment', 'Insurance', 'Miscellaneous',
)


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


# ---------------------------------------------------------------------------
# Domain API
#
# ``manage_trip_expenses`` covers the trips a user created or leads; anyone
# with ``manage_trips`` (admin) covers every trip. Every write is scoped by
# both expense id and trip id, so an id from another trip never matches.
# ---------------------------------------------------------------------------

def can_manage_expenses(auth, trip_id, conn=None, who=None):
    if not auth or not getattr(auth, 'current_user', None):
        return False
    if auth.check_permission('manage_trips'):
        return True
    return (auth.check_permission('manage_trip_expenses')
            and _trips().can_manage_trip(auth, trip_id, conn=conn, who=who))


def _require_expenses(auth, trip_id, conn, who):
    trip = _trips().get_trip(trip_id, conn=conn)
    if not trip:
        raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
    if not can_manage_expenses(auth, trip, conn=conn, who=who):
        raise PermissionError(get_text("mobility.trip_management.auth.no_permission_expenses",
                                       "You don't have permission to manage trip expenses."))
    return trip


def _clean_expense(category=None, description=None, amount=None, date=None, *, partial=False):
    out = {}
    if category is not None or not partial:
        if category not in EXPENSE_CATEGORIES:
            raise ValueError(f"category must be one of {', '.join(EXPENSE_CATEGORIES)}")
        out['category'] = category
    if description is not None or not partial:
        description = (description or '').strip()
        if not description:
            raise ValueError(get_text("mobility.trip_management.expenses.description_required",
                                      "Description is required."))
        out['description'] = description
    if amount is not None or not partial:
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            raise ValueError(get_text("mobility.trip_management.validation.enter_valid_amount",
                                      "Please enter a valid amount.")) from None
        if amount < 0:
            raise ValueError(get_text("mobility.trip_management.validation.amount_non_negative",
                                      "Amount cannot be negative."))
        out['amount'] = amount
    if date is not None or not partial:
        date = (date or '').strip() or datetime.now().strftime('%Y-%m-%d')
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise ValueError(get_text("mobility.trip_management.validation.invalid_date_format",
                                      "Invalid date format. Please use YYYY-MM-DD.")) from None
        out['date'] = date
    return out


def list_expenses(auth, trip_id, conn=None):
    """The trip's expenses, newest first."""
    who = _trips().actor(auth)
    with _db().read_connection(conn) as c:
        _require_expenses(auth, trip_id, c, who)
        cur = c.execute('''
        SELECT te.id, te.category, te.description, te.amount, te.date,
               u.first_name || ' ' || u.last_name as recorded_by
        FROM trip_expenses te
        LEFT JOIN users u ON te.recorded_by = u.id
        WHERE te.trip_id = ?
        ORDER BY te.date DESC, te.id DESC
        ''', (trip_id,))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def record_expense(auth, trip_id, category, description, amount, date=None, *, conn=None,
                   pending=None):
    """Add an expense to a trip. Returns the new expense id."""
    trips = _trips()
    who = trips.actor(auth)
    row = _clean_expense(category, description, amount, date)

    def work(c, p):
        _require_expenses(auth, trip_id, c, who)
        expense_id = c.execute(
            "INSERT INTO trip_expenses (trip_id, category, description, amount, date, recorded_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, row['category'], row['description'], row['amount'], row['date'],
             who['user_id'])).lastrowid
        trips._publish_after(p, "trip.expense.changed", trip_id=trip_id, expense_id=expense_id,
                             action="added", amount=row['amount'])
        return expense_id
    return trips._in_transaction(conn, pending, work)


def update_expense(auth, trip_id, expense_id, *, conn=None, pending=None, **fields):
    """Change an expense's category / description / amount / date."""
    trips = _trips()
    who = trips.actor(auth)
    unknown = set(fields) - {'category', 'description', 'amount', 'date'}
    if unknown:
        raise ValueError(f"unknown expense field(s): {', '.join(sorted(unknown))}")
    changes = _clean_expense(partial=True, **fields)
    if not changes:
        return False

    def work(c, p):
        _require_expenses(auth, trip_id, c, who)
        cur = c.execute(
            f"UPDATE trip_expenses SET {', '.join(k + ' = ?' for k in changes)} "
            "WHERE id = ? AND trip_id = ?", [*changes.values(), expense_id, trip_id])
        if cur.rowcount == 0:
            raise ValueError(get_text("mobility.trip_management.expenses.expense_not_found",
                                      "Expense not found."))
        trips._publish_after(p, "trip.expense.changed", trip_id=trip_id, expense_id=expense_id,
                             action="updated")
        return True
    return trips._in_transaction(conn, pending, work)


def remove_expense(auth, trip_id, expense_id, *, conn=None, pending=None):
    """Delete an expense recorded against this trip."""
    trips = _trips()
    who = trips.actor(auth)

    def work(c, p):
        _require_expenses(auth, trip_id, c, who)
        cur = c.execute("DELETE FROM trip_expenses WHERE id = ? AND trip_id = ?",
                        (expense_id, trip_id))
        if cur.rowcount == 0:
            raise ValueError(get_text("mobility.trip_management.expenses.expense_not_found",
                                      "Expense not found."))
        trips._publish_after(p, "trip.expense.changed", trip_id=trip_id, expense_id=expense_id,
                             action="deleted")
        return True
    return trips._in_transaction(conn, pending, work)


# ---------------------------------------------------------------------------
# CLI — no connection is held while the user types.
# ---------------------------------------------------------------------------

def _expense_trips(auth):
    who = _trips().actor(auth)
    with _db().read_connection() as conn:
        sql = '''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.status,
               COALESCE((SELECT SUM(te.amount) FROM trip_expenses te WHERE te.trip_id = t.id), 0)
        FROM trips t
        WHERE t.status <> 'archived'
        '''
        params = []
        if not auth.check_permission('manage_trips'):
            sql += (" AND (t.created_by = ? OR t.id IN (SELECT trip_id FROM trip_staff "
                    "WHERE staff_user_id = ? AND role IN ('coordinator', 'supervisor')))")
            params = [who['user_id'], who['user_id']]
        sql += " ORDER BY t.start_date DESC"
        return [tuple(r) for r in conn.execute(sql, params).fetchall()]


@log_create(module="trips", description="Managing trip expenses")
def manage_trip_expenses():
    """Manage expenses for trips"""
    auth = _common.get_auth()

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_expenses", "You must be logged in to manage trip expenses."))
        return False

    if not (auth.check_permission('manage_trip_expenses') or auth.check_permission('manage_trips')):
        print(get_text("mobility.trip_management.auth.no_permission_expenses", "You don't have permission to manage trip expenses."))
        return False

    trips = _expense_trips(auth)
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
    except ValueError:
        print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
        return False

    trip_name = next((t[1] for t in trips if t[0] == trip_id), None)
    if trip_name is None:
        print(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        return False

    while True:
        try:
            expenses = [(e['id'], e['category'], e['description'], e['amount'], e['date'],
                         e['recorded_by']) for e in list_expenses(auth, trip_id)]
        except (ValueError, PermissionError) as e:
            print(str(e))
            return False
        except sqlite3.Error as e:
            print(get_text("mobility.trip_management.errors.managing_expenses", "Error managing expenses: {error}").format(error=e))
            logging.error(get_text("mobility.trip_management.errors.in_manage_expenses", "Error in manage_trip_expenses: {error}").format(error=e))
            return False

        print(get_text("mobility.trip_management.expenses.for_trip", "\nExpenses for '{trip_name}':").format(trip_name=trip_name))
        print("=" * 100)
        if expenses:
            print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.category', 'Category'):<15} {get_text('mobility.trip_management.headers.description', 'Description'):<25} {get_text('mobility.trip_management.headers.amount', 'Amount'):<10} {get_text('mobility.trip_management.headers.date', 'Date'):<12} {get_text('mobility.trip_management.headers.recorded_by', 'Recorded By'):<15}")
            print("-" * 100)
            total_amount = 0
            for exp_id, category, description, amount, date, recorded_by in expenses:
                total_amount += amount
                recorded_by = recorded_by if recorded_by else get_text("mobility.trip_management.common.unknown", "Unknown")
                print(f"{exp_id:<5} {category[:14]:<15} {description[:24]:<25} £{amount:<9.2f} {date:<12} {recorded_by[:14]:<15}")
            print("-" * 100)
            print(get_text("mobility.trip_management.expenses.total", "Total Expenses: £{total:.2f}").format(total=total_amount))
        else:
            print(get_text("mobility.trip_management.expenses.no_expenses", "No expenses recorded for this trip."))
        print("=" * 100)

        print("\n" + get_text("mobility.trip_management.expenses.management_options", "Expense Management Options:"))
        print(get_text("mobility.trip_management.expenses.option_add", "1. Add New Expense"))
        print(get_text("mobility.trip_management.expenses.option_edit", "2. Edit Expense"))
        print(get_text("mobility.trip_management.expenses.option_delete", "3. Delete Expense"))
        print(get_text("mobility.trip_management.expenses.option_back", "4. Back to Trip Selection"))

        choice = input(get_text("mobility.trip_management.common.enter_choice_1_4", "Enter choice (1-4): ")).strip()

        if choice == '1':
            add_expense(None, trip_id)
        elif choice == '2':
            if expenses:
                edit_expense(None, trip_id, expenses)
            else:
                print(get_text("mobility.trip_management.expenses.no_expenses_to_edit", "No expenses to edit."))
        elif choice == '3':
            if expenses:
                delete_expense(None, trip_id, expenses)
            else:
                print(get_text("mobility.trip_management.expenses.no_expenses_to_delete", "No expenses to delete."))
        elif choice == '4':
            break
        else:
            print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))

    return True


def _report_failure(key, default, error):
    print(get_text(key, default).format(error=error))
    if isinstance(error, sqlite3.Error):
        logger.error("%s: %s", default, error)


def add_expense(conn, trip_id):
    """Add a new expense to a trip (``conn`` is unused; kept for callers).

    Asks for everything first, then writes in one short transaction; a
    failure rolls back and is reported.
    """
    auth = _common.get_auth()
    print("\n" + get_text("mobility.trip_management.expenses.add_new", "Add New Expense:"))
    print(get_text("mobility.trip_management.expenses.categories", "Expense Categories:"))
    for i, category in enumerate(EXPENSE_CATEGORIES, 1):
        print(f"{i}. {category}")

    while True:
        try:
            cat_choice = int(input(get_text("mobility.trip_management.expenses.select_category", "Select category (1-7): "))) - 1
            if 0 <= cat_choice < len(EXPENSE_CATEGORIES):
                category = EXPENSE_CATEGORIES[cat_choice]
                break
            print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
        except ValueError:
            print(get_text("mobility.trip_management.validation.enter_number", "Please enter a number."))

    description = input(get_text("mobility.trip_management.expenses.description_prompt", "Description: ")).strip()
    if not description:
        print(get_text("mobility.trip_management.expenses.description_required", "Description is required."))
        return False

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

    try:
        record_expense(auth, trip_id, category, description, amount, date_str)
    except (ValueError, PermissionError, sqlite3.Error) as e:
        _report_failure("mobility.trip_management.errors.adding_expense", "Error adding expense: {error}", e)
        return False
    print(get_text("mobility.trip_management.expenses.added", "Expense added: {category} - {description} (£{amount:.2f})").format(category=category, description=description, amount=amount))
    return True


def edit_expense(conn, trip_id, expenses):
    """Edit an existing expense (``conn`` is unused; kept for callers)."""
    auth = _common.get_auth()
    try:
        expense_id = int(input(get_text("mobility.trip_management.expenses.enter_expense_id_edit", "Enter expense ID to edit: ")))
    except ValueError:
        print(get_text("mobility.trip_management.expenses.invalid_expense_id", "Invalid expense ID."))
        return False

    selected_expense = next((e for e in expenses if e[0] == expense_id), None)
    if not selected_expense:
        print(get_text("mobility.trip_management.expenses.expense_not_found", "Expense not found."))
        return False

    exp_id, category, description, amount, date, recorded_by = selected_expense

    print(get_text("mobility.trip_management.expenses.editing", "\nEditing expense: {category} - {description}").format(category=category, description=description))
    print(get_text("mobility.trip_management.update.leave_blank", "Leave fields blank to keep current values."))

    changes = {}
    new_description = input(get_text("mobility.trip_management.expenses.description_current", "Description (current: {current}): ").format(current=description)).strip()
    if new_description:
        changes['description'] = new_description

    new_amount = input(get_text("mobility.trip_management.expenses.amount_current", "Amount (current: £{current:.2f}): ").format(current=amount)).strip()
    if new_amount:
        try:
            value = float(new_amount)
            if value < 0:
                print(get_text("mobility.trip_management.validation.amount_non_negative_keeping", "Amount cannot be negative. Keeping current value."))
            else:
                changes['amount'] = value
        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_amount_keeping", "Invalid amount. Keeping current value."))

    new_date = input(get_text("mobility.trip_management.expenses.date_current", "Date (current: {current}): ").format(current=date)).strip()
    if new_date:
        try:
            datetime.strptime(new_date, '%Y-%m-%d')
            changes['date'] = new_date
        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_date_keeping", "Invalid date format. Keeping current value."))

    if not changes:
        print(get_text("mobility.trip_management.update.no_changes", "No changes to update."))
        return True

    try:
        update_expense(auth, trip_id, expense_id, **changes)
    except (ValueError, PermissionError, sqlite3.Error) as e:
        _report_failure("mobility.trip_management.errors.editing_expense", "Error editing expense: {error}", e)
        return False
    print(get_text("mobility.trip_management.expenses.updated", "Expense updated successfully."))
    return True


def delete_expense(conn, trip_id, expenses):
    """Delete an expense (``conn`` is unused; kept for callers)."""
    auth = _common.get_auth()
    try:
        expense_id = int(input(get_text("mobility.trip_management.expenses.enter_expense_id_delete", "Enter expense ID to delete: ")))
    except ValueError:
        print(get_text("mobility.trip_management.expenses.invalid_expense_id", "Invalid expense ID."))
        return False

    selected_expense = next((e for e in expenses if e[0] == expense_id), None)
    if not selected_expense:
        print(get_text("mobility.trip_management.expenses.expense_not_found", "Expense not found."))
        return False

    exp_id, category, description, amount, date, recorded_by = selected_expense

    print(get_text("mobility.trip_management.expenses.delete_confirm", "\nDelete expense: {category} - {description} (£{amount:.2f})").format(category=category, description=description, amount=amount))
    confirm = input(get_text("mobility.trip_management.common.are_you_sure", "Are you sure? (y/n): ")).lower()
    if confirm != 'y':
        print(get_text("mobility.trip_management.common.deletion_cancelled", "Deletion cancelled."))
        return True

    try:
        remove_expense(auth, trip_id, expense_id)
    except (ValueError, PermissionError, sqlite3.Error) as e:
        _report_failure("mobility.trip_management.errors.deleting_expense", "Error deleting expense: {error}", e)
        return False
    print(get_text("mobility.trip_management.expenses.deleted", "Expense deleted successfully."))
    return True
