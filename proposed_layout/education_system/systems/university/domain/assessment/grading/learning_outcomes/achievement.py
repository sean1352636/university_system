import os
import numpy as np
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.assessment.grading.utils import select_student
import matplotlib
matplotlib.use('Agg')


def record_outcome_achievement():
    """Record student achievement of learning outcomes"""
    print("\nRecord Learning Outcome Achievement")

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
        SELECT first_name, last_name, course
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()
        if not student:
            print("Student not found.")
            conn.close()
            return

        first_name, last_name, course = student

        print(f"\nRecording Learning Outcome Achievement for: {first_name} {last_name} ({course})")

        # Get learning outcomes for this student's course
        cursor.execute('''
        SELECT outcome_id, outcome_code, description, category
        FROM learning_outcomes
        WHERE course = ? OR course = 'ALL'
        ORDER BY outcome_code
        ''', (course,))

        outcomes = cursor.fetchall()

        if not outcomes:
            print(f"No learning outcomes defined for course {course}.")
            conn.close()
            return

        # Get current achievement levels
        cursor.execute('''
        SELECT outcome_id, achievement_level, date_assessed
        FROM outcome_results
        WHERE student_id = ?
        ''', (student_id,))

        achievements = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        print("\nLearning Outcomes:")
        print("-" * 100)
        print(f"{'ID':<5} {'Code':<15} {'Category':<15} {'Current Level':<15} {'Date Assessed':<20} {'Description'}")
        print("-" * 100)

        for outcome in outcomes:
            id, code, description, category = outcome
            # Get current achievement if any
            if id in achievements:
                level, date = achievements[id]
                level_display = f"{level:.1f}/5.0"
                date_display = date
            else:
                level_display = "Not assessed"
                date_display = "N/A"

            # Truncate long descriptions for display
            short_desc = description[:40] + "..." if len(description) > 40 else description
            print(f"{id:<5} {code:<15} {category:<15} {level_display:<15} {date_display:<20} {short_desc}")

        # Record achievement
        outcome_id = input("\nEnter Outcome ID to record achievement for: ").strip()

        try:
            outcome_id = int(outcome_id)
        except ValueError:
            print("Invalid ID. Please enter a number.")
            conn.close()
            return

        # Check if outcome exists and is applicable for this student
        cursor.execute('''
        SELECT outcome_id, outcome_code, description
        FROM learning_outcomes
        WHERE outcome_id = ? AND (course = ? OR course = 'ALL')
        ''', (outcome_id, course))

        outcome = cursor.fetchone()

        if not outcome:
            print(f"No applicable outcome found with ID {outcome_id} for this student's course.")
            conn.close()
            return

        # Get achievement level
        print(f"\nRecording achievement for outcome: {outcome[1]} - {outcome[2]}")

        if outcome_id in achievements:
            current_level, current_date = achievements[outcome_id]
            print(f"Current achievement level: {current_level}/5.0 (recorded on {current_date})")

        while True:
            try:
                level = float(input("Enter achievement level (0-5, where 5 is highest): ").strip())
                if 0 <= level <= 5:
                    break
                else:
                    print("Achievement level must be between 0 and 5.")
            except ValueError:
                print("Please enter a valid number.")

        # Get evidence/comments
        evidence = input("Evidence or comments (optional): ").strip()

        # Record date
        date_assessed = datetime.now().strftime('%Y-%m-%d')

        # Check if there's an existing record to update
        if outcome_id in achievements:
            cursor.execute('''
            UPDATE outcome_results
            SET achievement_level = ?, evidence = ?, date_assessed = ?
            WHERE student_id = ? AND outcome_id = ?
            ''', (level, evidence, date_assessed, student_id, outcome_id))

            message = "updated"
        else:
            cursor.execute('''
            INSERT INTO outcome_results
            (student_id, outcome_id, achievement_level, evidence, date_assessed)
            VALUES (?, ?, ?, ?, ?)
            ''', (student_id, outcome_id, level, evidence, date_assessed))

            message = "recorded"

        conn.commit()
        print(f"Achievement level {message} successfully.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_student_outcome_achievement():
    """View achievement of learning outcomes for a student"""
    import matplotlib.pyplot as plt
    print("\nView Student Learning Outcome Achievement")

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
        SELECT first_name, last_name, course
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()
        if not student:
            print("Student not found.")
            conn.close()
            return

        first_name, last_name, course = student

        print(f"\nLearning Outcome Achievement for: {first_name} {last_name} ({course})")

        # Get all learning outcomes for this student's course with achievement levels
        cursor.execute('''
        SELECT lo.outcome_id, lo.outcome_code, lo.description, lo.category, lo.importance,
               or_.achievement_level, or_.date_assessed, or_.evidence
        FROM learning_outcomes lo
        LEFT JOIN outcome_results AS or_ ON lo.outcome_id = or_.outcome_id AND or_.student_id = ?
        WHERE lo.course = ? OR lo.course = 'ALL'
        ORDER BY lo.category, lo.outcome_code
        ''', (student_id, course))

        outcomes = cursor.fetchall()

        if not outcomes:
            print(f"No learning outcomes defined for course {course}.")
            conn.close()
            return

        # Group outcomes by category
        outcomes_by_category = {}
        for outcome in outcomes:
            category = outcome[3]
            if category not in outcomes_by_category:
                outcomes_by_category[category] = []
            outcomes_by_category[category].append(outcome)

        # Display outcomes by category
        for category, category_outcomes in outcomes_by_category.items():
            print(f"\n{category} Outcomes:")
            print("-" * 100)
            print(f"{'Code':<15} {'Importance':<10} {'Achievement':<15} {'Date Assessed':<15} {'Description'}")
            print("-" * 100)

            for outcome in category_outcomes:
                _, code, description, _, importance, level, date, _ = outcome

                if level is not None:
                    level_display = f"{level:.1f}/5.0"
                    date_display = date
                else:
                    level_display = "Not assessed"
                    date_display = "N/A"

                # Truncate long descriptions for display
                short_desc = description[:50] + "..." if len(description) > 50 else description
                print(f"{code:<15} {importance:<10} {level_display:<15} {date_display:<15} {short_desc}")

        # Calculate and display overall achievement statistics
        assessed_outcomes = [o for o in outcomes if o[5] is not None]

        if assessed_outcomes:
            total_outcomes = len(outcomes)
            assessed_count = len(assessed_outcomes)
            assessment_rate = (assessed_count / total_outcomes) * 100

            avg_achievement = sum(o[5] for o in assessed_outcomes) / assessed_count

            # Count outcomes at different achievement levels
            high_achievement = sum(1 for o in assessed_outcomes if o[5] >= 4.0)
            medium_achievement = sum(1 for o in assessed_outcomes if 2.5 <= o[5] < 4.0)
            low_achievement = sum(1 for o in assessed_outcomes if o[5] < 2.5)

            # Calculate weighted average based on importance
            weighted_sum = sum(o[5] * o[4] for o in assessed_outcomes)
            total_importance = sum(o[4] for o in assessed_outcomes)
            weighted_avg = weighted_sum / total_importance if total_importance > 0 else 0

            print("\nSummary Statistics:")
            print(f"Total Learning Outcomes: {total_outcomes}")
            print(f"Assessed Outcomes: {assessed_count} ({assessment_rate:.1f}%)")
            print(f"Average Achievement Level: {avg_achievement:.2f}/5.0")
            print(f"Weighted Average (by importance): {weighted_avg:.2f}/5.0")
            print(f"High Achievement (≥4.0): {high_achievement} outcomes")
            print(f"Medium Achievement (2.5-3.9): {medium_achievement} outcomes")
            print(f"Low Achievement (<2.5): {low_achievement} outcomes")

            # Visualize achievement if there are enough outcomes
            if assessed_count >= 3:
                visualize = input("\nWould you like to visualize the achievement levels? (y/n): ").strip().lower()

                if visualize == 'y':
                    # Create the plots directory if it doesn't exist
                    plots_dir = 'outcome_plots'
                    if not os.path.exists(plots_dir):
                        os.makedirs(plots_dir)

                    # Generate a simple bar chart of achievement levels
                    plt.figure(figsize=(12, 8))

                    # Sort outcomes by achievement level
                    sorted_outcomes = sorted(assessed_outcomes, key=lambda x: x[5], reverse=True)
                    codes = [o[1] for o in sorted_outcomes]
                    levels = [o[5] for o in sorted_outcomes]
                    categories = [o[3] for o in sorted_outcomes]

                    # Create a color map based on categories
                    unique_categories = list(set(categories))
                    palette = plt.cm.tab10(np.linspace(0, 1, len(unique_categories)))
                    color_map = {cat: palette[i] for i, cat in enumerate(unique_categories)}
                    bar_colors = [color_map[cat] for cat in categories]

                    # Create bar chart
                    bars = plt.bar(codes, levels, color=bar_colors)
                    plt.axhline(y=4.0, color='g', linestyle='--', label='High Achievement')
                    plt.axhline(y=2.5, color='r', linestyle='--', label='Low Achievement')

                    plt.ylim(0, 5.5)
                    plt.title(f'Learning Outcome Achievement Levels for {first_name} {last_name}')
                    plt.xlabel('Learning Outcome Code')
                    plt.ylabel('Achievement Level (0-5)')
                    plt.xticks(rotation=45, ha='right')

                    # Add a legend for categories
                    category_patches = [plt.Rectangle((0,0),1,1, color=color_map[cat]) for cat in unique_categories]
                    plt.legend(category_patches, unique_categories, loc='upper right')

                    plt.tight_layout()

                    # Save the figure
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    plot_filename = f"{plots_dir}/outcome_achievement_{student_id}_{timestamp}.png"
                    plt.savefig(plot_filename)
                    plt.close()

                    print(f"\nVisualization saved to {plot_filename}")
        else:
            print("\nNo outcomes have been assessed yet for this student.")

        # Ask if user wants to see outcome evidence details
        if assessed_outcomes:
            show_evidence = input("\nWould you like to see evidence/comments for assessed outcomes? (y/n): ").strip().lower()

            if show_evidence == 'y':
                print("\nOutcome Evidence/Comments:")
                print("-" * 100)
                print(f"{'Code':<15} {'Achievement':<15} {'Date':<15} {'Evidence/Comments'}")
                print("-" * 100)

                for outcome in assessed_outcomes:
                    _, code, _, _, _, level, date, evidence = outcome
                    if evidence:
                        print(f"{code:<15} {level:.1f}/5.0{' ':<9} {date:<15} {evidence}")
                    else:
                        print(f"{code:<15} {level:.1f}/5.0{' ':<9} {date:<15} No evidence recorded")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
