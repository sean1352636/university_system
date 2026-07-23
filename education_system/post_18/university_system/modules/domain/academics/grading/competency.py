from __future__ import annotations

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.academics.grading.utils import select_student

def manage_competencies():
    """Manage competencies - add, edit, delete"""
    print("\nManage Competencies")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        while True:
            print("\nCompetencies Menu:")
            print("1. View All Competencies")
            print("2. Add New Competency")
            print("3. Edit Competency")
            print("4. Delete Competency")
            print("5. Return to Previous Menu")

            choice = input("Enter your choice (1-5): ")

            if choice == '1':
                # View all competencies
                cursor.execute('''
                SELECT competency_id, name, description, category
                FROM competencies
                ORDER BY category, name
                ''')

                competencies = cursor.fetchall()

                if not competencies:
                    print("No competencies found in the database.")
                    continue

                print("\nCompetencies:")
                print("-" * 100)
                print(f"{'ID':<5} {'Category':<20} {'Name':<30} {'Description'}")
                print("-" * 100)

                for competency in competencies:
                    id, name, description, category = competency
                    # Truncate long descriptions for display
                    short_desc = description[:40] + "..." if len(description) > 40 else description
                    print(f"{id:<5} {category:<20} {name:<30} {short_desc}")

            elif choice == '2':
                # Add new competency
                name = input("Competency Name: ").strip()
                description = input("Description: ").strip()
                category = input("Category (e.g., Technical, Soft Skills): ").strip()

                # Insert the new competency
                cursor.execute('''
                INSERT INTO competencies
                (name, description, category)
                VALUES (?, ?, ?)
                ''', (name, description, category))

                conn.commit()
                competency_id = cursor.lastrowid

                print(f"Competency added successfully with ID {competency_id}.")

                # Ask if user wants to add levels for this competency
                add_levels = input("Do you want to add levels for this competency now? (y/n): ").strip().lower()

                if add_levels == 'y':
                    # Late import to avoid circular dependency:
                    from education_system.post_18.university_system.modules.domain.academics.grading.competency_assessment import add_competency_levels as _add_levels
                    _add_levels(cursor, competency_id, name)

            elif choice == '3':
                # Edit existing competency
                competency_id = input("Enter ID of competency to edit: ").strip()

                try:
                    competency_id = int(competency_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if competency exists
                cursor.execute('''
                SELECT competency_id, name, description, category
                FROM competencies
                WHERE competency_id = ?
                ''', (competency_id,))

                competency = cursor.fetchone()

                if not competency:
                    print(f"No competency found with ID {competency_id}.")
                    continue

                # Display current values
                print("\nCurrent values:")
                print(f"Name: {competency[1]}")
                print(f"Description: {competency[2]}")
                print(f"Category: {competency[3]}")

                # Get new values (leave blank to keep current)
                print("\nEnter new values (leave blank to keep current):")
                new_name = input(f"Name [{competency[1]}]: ").strip()
                new_description = input(f"Description [{competency[2]}]: ").strip()
                new_category = input(f"Category [{competency[3]}]: ").strip()

                # Use current values if new ones are blank
                name = new_name if new_name else competency[1]
                description = new_description if new_description else competency[2]
                category = new_category if new_category else competency[3]

                # Update the competency
                cursor.execute('''
                UPDATE competencies
                SET name = ?, description = ?, category = ?
                WHERE competency_id = ?
                ''', (name, description, category, competency_id))

                conn.commit()
                print("Competency updated successfully.")

            elif choice == '4':
                # Delete competency
                competency_id = input("Enter ID of competency to delete: ").strip()

                try:
                    competency_id = int(competency_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if competency exists
                cursor.execute('''
                SELECT name
                FROM competencies
                WHERE competency_id = ?
                ''', (competency_id,))

                competency = cursor.fetchone()

                if not competency:
                    print(f"No competency found with ID {competency_id}.")
                    continue

                # Check if competency has levels
                cursor.execute('''
                SELECT COUNT(*)
                FROM competency_levels
                WHERE competency_id = ?
                ''', (competency_id,))

                level_count = cursor.fetchone()[0]

                if level_count > 0:
                    print(f"Warning: This competency has {level_count} levels defined.")
                    print("Deleting it will also remove these levels.")

                # Check if competency is mapped to assessments
                cursor.execute('''
                SELECT COUNT(*)
                FROM assessment_competencies
                WHERE competency_id = ?
                ''', (competency_id,))

                mapping_count = cursor.fetchone()[0]

                if mapping_count > 0:
                    print(f"Warning: This competency is mapped to {mapping_count} assessments.")
                    print("Deleting it will also remove these mappings.")

                # Check if competency has been assessed for students
                cursor.execute('''
                SELECT COUNT(*)
                FROM student_competencies
                WHERE competency_id = ?
                ''', (competency_id,))

                result_count = cursor.fetchone()[0]

                if result_count > 0:
                    print(f"Warning: This competency has {result_count} student assessments.")
                    print("Deleting it will also remove these records.")

                confirm = input(f"Are you sure you want to delete competency '{competency[0]}'? (y/n): ").strip().lower()

                if confirm == 'y':
                    # Delete related records first
                    cursor.execute('''
                    DELETE FROM competency_levels
                    WHERE competency_id = ?
                    ''', (competency_id,))

                    cursor.execute('''
                    DELETE FROM assessment_competencies
                    WHERE competency_id = ?
                    ''', (competency_id,))

                    cursor.execute('''
                    DELETE FROM student_competencies
                    WHERE competency_id = ?
                    ''', (competency_id,))

                    # Now delete the competency itself
                    cursor.execute('''
                    DELETE FROM competencies
                    WHERE competency_id = ?
                    ''', (competency_id,))

                    conn.commit()
                    print("Competency and related records deleted successfully.")

            elif choice == '5':
                # Return to previous menu
                break

            else:
                print("Invalid choice. Please try again.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def record_student_competencies():
    """Record student achievement of competencies"""
    print("\nRecord Student Competencies")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Select student
        student_id = select_student(cursor)
        if not student_id:
            conn.close()
            return

        # Get student details
        cursor.execute('''
        SELECT first_name, last_name
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()
        if not student:
            print("Student not found.")
            conn.close()
            return

        first_name, last_name = student

        print(f"\nRecording Competencies for: {first_name} {last_name}")

        # Get available competencies
        cursor.execute('''
        SELECT competency_id, name, category
        FROM competencies
        ORDER BY category, name
        ''')

        competencies = cursor.fetchall()

        if not competencies:
            print("No competencies defined in the system. Please add competencies first.")
            conn.close()
            return

        # Get current competency assessments
        cursor.execute('''
        SELECT sc.id, c.competency_id, c.name, c.category,
               cl.level_id, cl.level_name, sc.assessment_date
        FROM student_competencies sc
        JOIN competencies c ON sc.competency_id = c.competency_id
        JOIN competency_levels cl ON sc.level_id = cl.level_id
        WHERE sc.student_id = ?
        ORDER BY sc.assessment_date DESC
        ''', (student_id,))

        assessments = cursor.fetchall()

        if assessments:
            print("\nCurrent Competency Assessments:")
            print("-" * 110)
            print(f"{'ID':<5} {'Competency':<30} {'Category':<15} {'Level':<15} {'Date':<15}")
            print("-" * 110)

            for assessment in assessments:
                id, comp_id, name, category, level_id, level_name, date = assessment
                # Truncate long names for display
                short_name = name[:30] if len(name) > 30 else name
                print(f"{id:<5} {short_name:<30} {category[:15]:<15} {level_name:<15} {date:<15}")
        else:
            print("\nNo competency assessments recorded for this student yet.")

        # Display competencies for selection
        print("\nAvailable Competencies:")
        print("-" * 80)
        print(f"{'ID':<5} {'Name':<40} {'Category':<15}")
        print("-" * 80)

        for competency in competencies:
            id, name, category = competency
            # Truncate long names for display
            short_name = name[:40] if len(name) > 40 else name
            print(f"{id:<5} {short_name:<40} {category[:15]:<15}")

        # Select competency to assess
        competency_id = input("\nEnter Competency ID to assess: ").strip()

        try:
            competency_id = int(competency_id)
        except ValueError:
            print("Invalid ID. Please enter a number.")
            conn.close()
            return

        # Check if competency exists
        cursor.execute('''
        SELECT name
        FROM competencies
        WHERE competency_id = ?
        ''', (competency_id,))

        competency = cursor.fetchone()

        if not competency:
            print(f"No competency found with ID {competency_id}.")
            conn.close()
            return

        # Get levels for this competency
        cursor.execute('''
        SELECT level_id, level_name, level_value, description
        FROM competency_levels
        WHERE competency_id = ?
        ORDER BY level_value
        ''', (competency_id,))

        levels = cursor.fetchall()

        if not levels:
            print("No levels defined for this competency. Please add levels first.")
            conn.close()
            return

        print(f"\nAssessing competency: {competency[0]}")
        print("\nAvailable Levels:")
        print("-" * 100)
        print(f"{'ID':<5} {'Level':<15} {'Value':<8} {'Description'}")
        print("-" * 100)

        for level in levels:
            level_id, level_name, level_value, description = level
            # Truncate long descriptions for display
            short_desc = description[:70] + "..." if len(description) > 70 else description
            print(f"{level_id:<5} {level_name:<15} {level_value:<8} {short_desc}")

        # Select level
        level_id = input("\nEnter Level ID to assign: ").strip()

        try:
            level_id = int(level_id)
        except ValueError:
            print("Invalid ID. Please enter a number.")
            conn.close()
            return

        # Check if level exists and belongs to the selected competency
        cursor.execute('''
        SELECT level_id
        FROM competency_levels
        WHERE level_id = ? AND competency_id = ?
        ''', (level_id, competency_id))

        level = cursor.fetchone()

        if not level:
            print(f"No level found with ID {level_id} for this competency.")
            conn.close()
            return

        # Get evidence/notes
        evidence = input("Evidence or notes (optional): ").strip()

        # Get assessment date (default to today)
        today = datetime.now().strftime('%Y-%m-%d')
        date_input = input(f"Assessment date [{today}] (YYYY-MM-DD, leave blank for today): ").strip()
        assessment_date = date_input if date_input else today

        # Check if there's an existing assessment for this student and competency
        cursor.execute('''
        SELECT id
        FROM student_competencies
        WHERE student_id = ? AND competency_id = ?
        ''', (student_id, competency_id))

        existing = cursor.fetchone()

        if existing:
            # Update existing assessment
            cursor.execute('''
            UPDATE student_competencies
            SET level_id = ?, evidence = ?, assessment_date = ?
            WHERE id = ?
            ''', (level_id, evidence, assessment_date, existing[0]))

            conn.commit()
            print("Competency assessment updated successfully.")
        else:
            # Create new assessment
            cursor.execute('''
            INSERT INTO student_competencies
            (student_id, competency_id, level_id, evidence, assessment_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (student_id, competency_id, level_id, evidence, assessment_date))

            conn.commit()
            print("Competency assessment recorded successfully.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
