from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.assessment.grading.grade_calculation.utils import select_assessment


def map_assessments_to_outcomes():
    """Map assessments to learning outcomes with weights"""
    print("\nMap Assessments to Learning Outcomes")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Select an assessment
        assessment_id = select_assessment(cursor)
        if not assessment_id:
            conn.close()
            return

        # Get assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, assessment_type
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))

        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            conn.close()
            return

        assessment_name, module_code, assessment_type = assessment

        # Get current outcome mappings
        cursor.execute('''
        SELECT ao.id, lo.outcome_id, lo.outcome_code, lo.description, ao.weight
        FROM assessment_outcomes ao
        JOIN learning_outcomes lo ON ao.outcome_id = lo.outcome_id
        WHERE ao.assessment_id = ?
        ORDER BY ao.weight DESC
        ''', (assessment_id,))

        mappings = cursor.fetchall()

        print(f"\nAssessment: {assessment_name} [{module_code}] ({assessment_type})")

        if mappings:
            print("\nCurrent Learning Outcome Mappings:")
            print("-" * 80)
            print(f"{'Mapping ID':<12} {'Outcome ID':<12} {'Code':<15} {'Weight':<10} {'Description'}")
            print("-" * 80)

            for mapping in mappings:
                mapping_id, outcome_id, outcome_code, description, weight = mapping
                # Truncate long descriptions for display
                short_desc = description[:40] + "..." if len(description) > 40 else description
                print(f"{mapping_id:<12} {outcome_id:<12} {outcome_code:<15} {weight:<10.1f} {short_desc}")
        else:
            print("\nNo learning outcomes are currently mapped to this assessment.")

        # Get the module's course (course column may not exist)
        course = None
        try:
            cursor.execute('''
            SELECT course
            FROM modules
            WHERE module_code = ?
            ''', (module_code,))
            course_result = cursor.fetchone()
            course = course_result[0] if course_result else None
        except Exception:
            pass

        # Get available learning outcomes for this course
        # importance column may not exist (may be called 'level')
        try:
            if course:
                cursor.execute('''
                SELECT outcome_id, outcome_code, description, category,
                       COALESCE(importance, level, 0) as importance
                FROM learning_outcomes
                WHERE course = ? OR course = 'ALL' OR course IS NULL
                ORDER BY importance DESC, outcome_code
                ''', (course,))
            else:
                cursor.execute('''
                SELECT outcome_id, outcome_code, description, category,
                       COALESCE(importance, level, 0) as importance
                FROM learning_outcomes
                ORDER BY importance DESC, outcome_code
                ''')
        except Exception:
            # Fallback if COALESCE with importance/level fails
            cursor.execute('''
            SELECT outcome_id, outcome_code, description, category, 0 as importance
            FROM learning_outcomes
            ORDER BY outcome_code
            ''')

        outcomes = cursor.fetchall()

        if not outcomes:
            print("\nNo learning outcomes available for mapping.")
            conn.close()
            return

        print("\nAvailable Learning Outcomes:")
        print("-" * 80)
        print(f"{'ID':<5} {'Code':<15} {'Category':<15} {'Importance':<10} {'Description'}")
        print("-" * 80)

        for outcome in outcomes:
            id, code, description, category, importance = outcome
            category = category or ""
            # Truncate long descriptions for display
            short_desc = description[:40] + "..." if len(description) > 40 else description
            print(f"{id:<5} {code:<15} {category:<15} {importance:<10} {short_desc}")

        # Mapping operations
        while True:
            print("\nMapping Operations:")
            print("1. Add new outcome mapping")
            print("2. Update existing mapping")
            print("3. Delete mapping")
            print("4. Return to previous menu")

            op_choice = input("Enter your choice (1-4): ")

            if op_choice == '1':
                # Add new mapping
                outcome_id = input("\nEnter Outcome ID to map to this assessment: ").strip()

                try:
                    outcome_id = int(outcome_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if outcome exists
                cursor.execute('''
                SELECT outcome_id, outcome_code, description
                FROM learning_outcomes
                WHERE outcome_id = ?
                ''', (outcome_id,))

                outcome = cursor.fetchone()

                if not outcome:
                    print(f"No outcome found with ID {outcome_id}.")
                    continue

                # Check if mapping already exists
                cursor.execute('''
                SELECT id
                FROM assessment_outcomes
                WHERE assessment_id = ? AND outcome_id = ?
                ''', (assessment_id, outcome_id))

                existing = cursor.fetchone()

                if existing:
                    print(f"This outcome is already mapped to this assessment (Mapping ID: {existing[0]}).")
                    print("Use the update option to change the weight.")
                    continue

                # Get weight
                while True:
                    try:
                        weight = float(input("Enter weight for this outcome (0-100): ").strip())
                        if 0 <= weight <= 100:
                            break
                        else:
                            print("Weight must be between 0 and 100.")
                    except ValueError:
                        print("Please enter a valid number.")

                # Add the mapping
                cursor.execute('''
                INSERT INTO assessment_outcomes
                (assessment_id, outcome_id, weight)
                VALUES (?, ?, ?)
                ''', (assessment_id, outcome_id, weight))

                conn.commit()
                print(f"Learning outcome '{outcome[1]}' successfully mapped to assessment.")

            elif op_choice == '2':
                # Update existing mapping
                mapping_id = input("\nEnter Mapping ID to update: ").strip()

                try:
                    mapping_id = int(mapping_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if mapping exists
                cursor.execute('''
                SELECT ao.id, lo.outcome_code, ao.weight
                FROM assessment_outcomes ao
                JOIN learning_outcomes lo ON ao.outcome_id = lo.outcome_id
                WHERE ao.id = ? AND ao.assessment_id = ?
                ''', (mapping_id, assessment_id))

                mapping = cursor.fetchone()

                if not mapping:
                    print(f"No mapping found with ID {mapping_id} for this assessment.")
                    continue

                # Get new weight
                print(f"Current weight for outcome '{mapping[1]}': {mapping[2]}")

                while True:
                    try:
                        weight = float(input("Enter new weight (0-100): ").strip())
                        if 0 <= weight <= 100:
                            break
                        else:
                            print("Weight must be between 0 and 100.")
                    except ValueError:
                        print("Please enter a valid number.")

                # Update the mapping
                cursor.execute('''
                UPDATE assessment_outcomes
                SET weight = ?
                WHERE id = ?
                ''', (weight, mapping_id))

                conn.commit()
                print(f"Weight for outcome '{mapping[1]}' updated successfully.")

            elif op_choice == '3':
                # Delete mapping
                mapping_id = input("\nEnter Mapping ID to delete: ").strip()

                try:
                    mapping_id = int(mapping_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if mapping exists
                cursor.execute('''
                SELECT ao.id, lo.outcome_code
                FROM assessment_outcomes ao
                JOIN learning_outcomes lo ON ao.outcome_id = lo.outcome_id
                WHERE ao.id = ? AND ao.assessment_id = ?
                ''', (mapping_id, assessment_id))

                mapping = cursor.fetchone()

                if not mapping:
                    print(f"No mapping found with ID {mapping_id} for this assessment.")
                    continue

                confirm = input(f"Are you sure you want to delete mapping for outcome '{mapping[1]}'? (y/n): ").strip().lower()

                if confirm == 'y':
                    cursor.execute('''
                    DELETE FROM assessment_outcomes
                    WHERE id = ?
                    ''', (mapping_id,))

                    conn.commit()
                    print(f"Mapping for outcome '{mapping[1]}' deleted successfully.")
                else:
                    print("Deletion cancelled.")

            elif op_choice == '4':
                # Return to previous menu
                break

            else:
                print("Invalid choice. Please try again.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")


def map_assessments_to_competencies():
    """Map assessments to competencies with weights"""
    print("\nMap Assessments to Competencies")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Select an assessment
        assessment_id = select_assessment(cursor)
        if not assessment_id:
            conn.close()
            return

        # Get assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, assessment_type
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))

        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            conn.close()
            return

        assessment_name, module_code, assessment_type = assessment

        # Get current competency mappings
        cursor.execute('''
        SELECT ac.id, c.competency_id, c.name, c.category, ac.weight
        FROM assessment_competencies ac
        JOIN competencies c ON ac.competency_id = c.competency_id
        WHERE ac.assessment_id = ?
        ORDER BY ac.weight DESC
        ''', (assessment_id,))

        mappings = cursor.fetchall()

        print(f"\nAssessment: {assessment_name} [{module_code}] ({assessment_type})")

        if mappings:
            print("\nCurrent Competency Mappings:")
            print("-" * 80)
            print(f"{'Mapping ID':<12} {'Comp ID':<12} {'Name':<25} {'Category':<15} {'Weight':<10}")
            print("-" * 80)

            for mapping in mappings:
                mapping_id, competency_id, name, category, weight = mapping
                print(f"{mapping_id:<12} {competency_id:<12} {name[:25]:<25} {category[:15]:<15} {weight:<10.1f}")
        else:
            print("\nNo competencies are currently mapped to this assessment.")

        # Get available competencies
        cursor.execute('''
        SELECT competency_id, name, category, description
        FROM competencies
        ORDER BY category, name
        ''')

        competencies = cursor.fetchall()

        if not competencies:
            print("\nNo competencies available for mapping. Please add competencies first.")
            conn.close()
            return

        print("\nAvailable Competencies:")
        print("-" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Category':<15} {'Description'}")
        print("-" * 80)

        for competency in competencies:
            id, name, category, description = competency
            # Truncate long descriptions and names for display
            short_name = name[:25] if len(name) > 25 else name
            short_desc = description[:35] + "..." if len(description) > 35 else description
            print(f"{id:<5} {short_name:<25} {category[:15]:<15} {short_desc}")

        # Mapping operations
        while True:
            print("\nMapping Operations:")
            print("1. Add new competency mapping")
            print("2. Update existing mapping")
            print("3. Delete mapping")
            print("4. Return to previous menu")

            op_choice = input("Enter your choice (1-4): ")

            if op_choice == '1':
                # Add new mapping
                competency_id = input("\nEnter Competency ID to map to this assessment: ").strip()

                try:
                    competency_id = int(competency_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if competency exists
                cursor.execute('''
                SELECT competency_id, name
                FROM competencies
                WHERE competency_id = ?
                ''', (competency_id,))

                competency = cursor.fetchone()

                if not competency:
                    print(f"No competency found with ID {competency_id}.")
                    continue

                # Check if mapping already exists
                cursor.execute('''
                SELECT id
                FROM assessment_competencies
                WHERE assessment_id = ? AND competency_id = ?
                ''', (assessment_id, competency_id))

                existing = cursor.fetchone()

                if existing:
                    print(f"This competency is already mapped to this assessment (Mapping ID: {existing[0]}).")
                    print("Use the update option to change the weight.")
                    continue

                # Get weight
                while True:
                    try:
                        weight = float(input("Enter weight for this competency (0-100): ").strip())
                        if 0 <= weight <= 100:
                            break
                        else:
                            print("Weight must be between 0 and 100.")
                    except ValueError:
                        print("Please enter a valid number.")

                # Add the mapping
                cursor.execute('''
                INSERT INTO assessment_competencies
                (assessment_id, competency_id, weight)
                VALUES (?, ?, ?)
                ''', (assessment_id, competency_id, weight))

                conn.commit()
                print(f"Competency '{competency[1]}' successfully mapped to assessment.")

            elif op_choice == '2':
                # Update existing mapping
                mapping_id = input("\nEnter Mapping ID to update: ").strip()

                try:
                    mapping_id = int(mapping_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if mapping exists
                cursor.execute('''
                SELECT ac.id, c.name, ac.weight
                FROM assessment_competencies ac
                JOIN competencies c ON ac.competency_id = c.competency_id
                WHERE ac.id = ? AND ac.assessment_id = ?
                ''', (mapping_id, assessment_id))

                mapping = cursor.fetchone()

                if not mapping:
                    print(f"No mapping found with ID {mapping_id} for this assessment.")
                    continue

                # Get new weight
                print(f"Current weight for competency '{mapping[1]}': {mapping[2]}")

                while True:
                    try:
                        weight = float(input("Enter new weight (0-100): ").strip())
                        if 0 <= weight <= 100:
                            break
                        else:
                            print("Weight must be between 0 and 100.")
                    except ValueError:
                        print("Please enter a valid number.")

                # Update the mapping
                cursor.execute('''
                UPDATE assessment_competencies
                SET weight = ?
                WHERE id = ?
                ''', (weight, mapping_id))

                conn.commit()
                print(f"Weight for competency '{mapping[1]}' updated successfully.")

            elif op_choice == '3':
                # Delete mapping
                mapping_id = input("\nEnter Mapping ID to delete: ").strip()

                try:
                    mapping_id = int(mapping_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if mapping exists
                cursor.execute('''
                SELECT ac.id, c.name
                FROM assessment_competencies ac
                JOIN competencies c ON ac.competency_id = c.competency_id
                WHERE ac.id = ? AND ac.assessment_id = ?
                ''', (mapping_id, assessment_id))

                mapping = cursor.fetchone()

                if not mapping:
                    print(f"No mapping found with ID {mapping_id} for this assessment.")
                    continue

                confirm = input(f"Are you sure you want to delete mapping for competency '{mapping[1]}'? (y/n): ").strip().lower()

                if confirm == 'y':
                    cursor.execute('''
                    DELETE FROM assessment_competencies
                    WHERE id = ?
                    ''', (mapping_id,))

                    conn.commit()
                    print(f"Mapping for competency '{mapping[1]}' deleted successfully.")
                else:
                    print("Deletion cancelled.")

            elif op_choice == '4':
                # Return to previous menu
                break

            else:
                print("Invalid choice. Please try again.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
