from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection


def manage_learning_outcomes():
    """Manage learning outcomes - add, edit, delete"""
    print("\nManage Learning Outcomes")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        while True:
            print("\nLearning Outcomes Menu:")
            print("1. View All Learning Outcomes")
            print("2. Add New Learning Outcome")
            print("3. Edit Learning Outcome")
            print("4. Delete Learning Outcome")
            print("5. Return to Previous Menu")

            choice = input("Enter your choice (1-5): ")

            if choice == '1':
                # View all outcomes
                # course/importance columns may not exist if table was created by another subsystem
                try:
                    cursor.execute('''
                    SELECT outcome_id, course, outcome_code, description, category, importance
                    FROM learning_outcomes
                    ORDER BY course, outcome_code
                    ''')
                except sqlite3.OperationalError:
                    cursor.execute('''
                    SELECT outcome_id, NULL as course, outcome_code, description, category,
                           COALESCE(level, 0) as importance
                    FROM learning_outcomes
                    ORDER BY outcome_code
                    ''')

                outcomes = cursor.fetchall()

                if not outcomes:
                    print("No learning outcomes found in the database.")
                    continue

                print("\nLearning Outcomes:")
                print("-" * 100)
                print(f"{'ID':<5} {'Course':<10} {'Code':<15} {'Category':<15} {'Importance':<10} {'Description'}")
                print("-" * 100)

                for outcome in outcomes:
                    id, course, code, description, category, importance = outcome
                    # Truncate long descriptions for display
                    short_desc = description[:50] + "..." if len(description) > 50 else description
                    print(f"{id:<5} {course:<10} {code:<15} {category:<15} {importance:<10} {short_desc}")

            elif choice == '2':
                # Add new outcome
                course = input("Course (e.g., CS, DS): ").strip().upper()
                outcome_code = input("Outcome Code (e.g., LO1, CS-LO2): ").strip()
                description = input("Description: ").strip()
                category = input("Category (e.g., Knowledge, Skills, Attitudes): ").strip()

                while True:
                    try:
                        importance = int(input("Importance (1-5, where 5 is highest): ").strip())
                        if 1 <= importance <= 5:
                            break
                        else:
                            print("Importance must be between 1 and 5.")
                    except ValueError:
                        print("Please enter a valid number.")

                # Insert the new outcome
                # Try with course/importance first, fall back if columns don't exist
                try:
                    cursor.execute('''
                    INSERT INTO learning_outcomes
                    (course, outcome_code, description, category, importance)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (course, outcome_code, description, category, importance))
                except sqlite3.OperationalError:
                    cursor.execute('''
                    INSERT INTO learning_outcomes
                    (outcome_code, description, category, level)
                    VALUES (?, ?, ?, ?)
                    ''', (outcome_code, description, category, importance))

                conn.commit()
                print("Learning outcome added successfully.")

            elif choice == '3':
                # Edit existing outcome
                outcome_id = input("Enter ID of outcome to edit: ").strip()

                try:
                    outcome_id = int(outcome_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if outcome exists
                try:
                    cursor.execute('''
                    SELECT outcome_id, course, outcome_code, description, category, importance
                    FROM learning_outcomes
                    WHERE outcome_id = ?
                    ''', (outcome_id,))
                except sqlite3.OperationalError:
                    cursor.execute('''
                    SELECT outcome_id, NULL as course, outcome_code, description, category,
                           COALESCE(level, 0) as importance
                    FROM learning_outcomes
                    WHERE outcome_id = ?
                    ''', (outcome_id,))

                outcome = cursor.fetchone()

                if not outcome:
                    print(f"No outcome found with ID {outcome_id}.")
                    continue

                # Display current values
                print("\nCurrent values:")
                print(f"Course: {outcome[1]}")
                print(f"Outcome Code: {outcome[2]}")
                print(f"Description: {outcome[3]}")
                print(f"Category: {outcome[4]}")
                print(f"Importance: {outcome[5]}")

                # Get new values (leave blank to keep current)
                print("\nEnter new values (leave blank to keep current):")
                new_course = input(f"Course [{outcome[1]}]: ").strip().upper()
                new_code = input(f"Outcome Code [{outcome[2]}]: ").strip()
                new_description = input(f"Description [{outcome[3]}]: ").strip()
                new_category = input(f"Category [{outcome[4]}]: ").strip()
                new_importance = input(f"Importance [{outcome[5]}]: ").strip()

                # Use current values if new ones are blank
                course = new_course if new_course else outcome[1]
                code = new_code if new_code else outcome[2]
                description = new_description if new_description else outcome[3]
                category = new_category if new_category else outcome[4]

                if new_importance:
                    try:
                        importance = int(new_importance)
                        if not (1 <= importance <= 5):
                            print("Importance must be between 1 and 5. Using current value.")
                            importance = outcome[5]
                    except ValueError:
                        print("Invalid importance. Using current value.")
                        importance = outcome[5]
                else:
                    importance = outcome[5]

                # Update the outcome
                try:
                    cursor.execute('''
                    UPDATE learning_outcomes
                    SET course = ?, outcome_code = ?, description = ?, category = ?, importance = ?
                    WHERE outcome_id = ?
                    ''', (course, code, description, category, importance, outcome_id))
                except sqlite3.OperationalError:
                    cursor.execute('''
                    UPDATE learning_outcomes
                    SET outcome_code = ?, description = ?, category = ?, level = ?
                    WHERE outcome_id = ?
                    ''', (code, description, category, importance, outcome_id))

                conn.commit()
                print("Learning outcome updated successfully.")

            elif choice == '4':
                # Delete outcome
                outcome_id = input("Enter ID of outcome to delete: ").strip()

                try:
                    outcome_id = int(outcome_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if outcome exists
                cursor.execute('''
                SELECT outcome_code, description
                FROM learning_outcomes
                WHERE outcome_id = ?
                ''', (outcome_id,))

                outcome = cursor.fetchone()

                if not outcome:
                    print(f"No outcome found with ID {outcome_id}.")
                    continue

                # Check if outcome is mapped to assessments
                cursor.execute('''
                SELECT COUNT(*)
                FROM assessment_outcomes
                WHERE outcome_id = ?
                ''', (outcome_id,))

                mapping_count = cursor.fetchone()[0]

                if mapping_count > 0:
                    print(f"Warning: This outcome is mapped to {mapping_count} assessments.")
                    print("Deleting it will also remove these mappings.")

                # Check if outcome has achievement records
                cursor.execute('''
                SELECT COUNT(*)
                FROM outcome_results
                WHERE outcome_id = ?
                ''', (outcome_id,))

                result_count = cursor.fetchone()[0]

                if result_count > 0:
                    print(f"Warning: This outcome has {result_count} achievement records.")
                    print("Deleting it will also remove these records.")

                confirm = input(f"Are you sure you want to delete outcome '{outcome[0]}'? (y/n): ").strip().lower()

                if confirm == 'y':
                    # Delete related records first
                    cursor.execute('''
                    DELETE FROM assessment_outcomes
                    WHERE outcome_id = ?
                    ''', (outcome_id,))

                    cursor.execute('''
                    DELETE FROM outcome_results
                    WHERE outcome_id = ?
                    ''', (outcome_id,))

                    # Now delete the outcome
                    cursor.execute('''
                    DELETE FROM learning_outcomes
                    WHERE outcome_id = ?
                    ''', (outcome_id,))

                    conn.commit()
                    print("Learning outcome and related records deleted successfully.")
                else:
                    print("Deletion cancelled.")

            elif choice == '5':
                # Return to previous menu
                break

            else:
                print("Invalid choice. Please try again.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
