"""Conditional logic search with boolean operators (AND, OR, NOT)."""
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search.display import display_search_results
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search.system import log_search
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search.admin import audit_log


@audit_log
def conditional_logic_search():
    """Advanced search with boolean logic (AND, OR, NOT)"""
    print("\n🧠 CONDITIONAL LOGIC SEARCH")
    print("="*40)
    print("Build complex queries using AND, OR, NOT operators")
    print("Example: (age > 20 AND course = 'CS') OR (gender = 'female' AND age < 25)")

    conditions = []
    condition_params = []

    while True:
        print(f"\nCurrent conditions: {len(conditions)}")
        for i, cond in enumerate(conditions):
            print(f"{i+1}. {cond}")

        print("\nOptions:")
        print("1. Add condition")
        print("2. Remove condition")
        print("3. Execute search")
        print("4. Cancel")

        choice = input("Select option: ").strip()

        if choice == '1':
            add_condition(conditions, condition_params)
        elif choice == '2':
            remove_condition(conditions, condition_params)
        elif choice == '3':
            execute_conditional_search(conditions, condition_params)
            break
        elif choice == '4':
            break
        else:
            print("Invalid choice.")

def add_condition(conditions, condition_params):
    """Add a condition to the conditional search"""
    VALID_OPERATORS = {'>', '<', '=', '>=', '<='}

    print("\nAdd Condition:")
    print("1. Age condition")
    print("2. Course condition")
    print("3. Gender condition")
    print("4. Registration date condition")

    ctype = input("Select condition type (1-4): ").strip()

    if ctype == '1':
        operator = input("Operator (>, <, =, >=, <=): ").strip()
        if operator not in VALID_OPERATORS:
            print("Invalid operator.")
            return
        value = input("Age value: ").strip()
        try:
            int(value)  # Validate
            conditions.append(f"age {operator} ?")
            condition_params.append(int(value))
        except ValueError:
            print("Invalid age value.")

    elif ctype == '2':
        course = input("Course (CS/DS): ").strip().upper()
        if course in ['CS', 'DS']:
            conditions.append("course = ?")
            condition_params.append(course)
        else:
            print("Invalid course.")

    elif ctype == '3':
        gender = input("Gender (male/female/other): ").strip().lower()
        if gender in ['male', 'female', 'other']:
            conditions.append("gender = ?")
            condition_params.append(gender)
        else:
            print("Invalid gender.")

    elif ctype == '4':
        operator = input("Operator (>, <, =, >=, <=): ").strip()
        if operator not in VALID_OPERATORS:
            print("Invalid operator.")
            return
        date = input("Date (YYYY-MM-DD): ").strip()
        try:
            datetime.strptime(date, "%Y-%m-%d")
            conditions.append(f"DATE(registration_datetime) {operator} ?")
            condition_params.append(date)
        except ValueError:
            print("Invalid date format.")

def remove_condition(conditions, condition_params=None):
    """Remove a condition from the list"""
    if not conditions:
        print("No conditions to remove.")
        return

    try:
        index = int(input(f"Enter condition number to remove (1-{len(conditions)}): ")) - 1
        if 0 <= index < len(conditions):
            removed = conditions.pop(index)
            if condition_params is not None and index < len(condition_params):
                condition_params.pop(index)
            print(f"Removed: {removed}")
        else:
            print("Invalid condition number.")
    except ValueError:
        print("Invalid input.")

def execute_conditional_search(conditions, condition_params):
    """Execute the conditional search"""
    if not conditions:
        print("No conditions specified.")
        return

    # Get logical operators between conditions
    if len(conditions) > 1:
        print("\nCombine conditions with:")
        print("1. AND (all conditions must be true)")
        print("2. OR (any condition can be true)")

        logic = input("Select logic (1-2): ").strip()
        operator = " AND " if logic == '1' else " OR "
        where_clause = operator.join(conditions)
    else:
        where_clause = conditions[0]

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = f"SELECT * FROM students WHERE {where_clause}"
        print(f"\nExecuting query: {query}")

        cursor.execute(query, condition_params)
        results = cursor.fetchall()

        log_search("conditional_logic", {"conditions": conditions}, len(results))
        display_search_results(results)
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
