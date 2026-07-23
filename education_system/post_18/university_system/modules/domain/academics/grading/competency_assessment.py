from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DatabaseManager
import os
import csv
import numpy as np
import math
from scipy import stats
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import matplotlib
from education_system.post_18.university_system.infrastructure.database.db import get_connection
matplotlib.use('Agg')
from education_system.post_18.university_system.modules.domain.academics.grading.utils import select_student
from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation import calculate_student_gpa
from education_system.post_18.university_system.core.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError
)

def add_competency_levels(cursor, competency_id, competency_name):
    """Add levels for a specific competency"""
    print(f"\nAdding levels for competency: {competency_name}")

    # Ask how many levels to add
    while True:
        try:
            num_levels = int(input("How many levels do you want to define (e.g., 1-5)? "))
            if num_levels < 1:
                print("Please enter a positive number.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")

    # Add each level
    for i in range(1, num_levels + 1):
        print(f"\nDefining Level {i}:")
        level_name = input(f"Level {i} Name (e.g., Beginner, Intermediate): ").strip()
        description = input(f"Description for {level_name}: ").strip()

        # Insert the level
        cursor.execute('''
        INSERT INTO competency_levels
        (competency_id, level_name, level_value, description)
        VALUES (?, ?, ?, ?)
        ''', (competency_id, level_name, i, description))

    # Commit the changes
    cursor.connection.commit()
    print(f"Successfully added {num_levels} levels to competency '{competency_name}'.")

def manage_competency_levels():
    """Manage competency levels - view, add, edit, delete"""
    print("\nManage Competency Levels")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # First, select a competency
        cursor.execute('''
        SELECT competency_id, name, category
        FROM competencies
        ORDER BY category, name
        ''')

        competencies = cursor.fetchall()

        if not competencies:
            print("No competencies found in the database. Please add competencies first.")
            conn.close()
            return

        print("\nAvailable Competencies:")
        print("-" * 70)
        print(f"{'ID':<5} {'Category':<20} {'Name':<30}")
        print("-" * 70)

        for competency in competencies:
            id, name, category = competency
            print(f"{id:<5} {category:<20} {name:<30}")

        competency_id = input("\nEnter competency ID to manage levels: ").strip()

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

        competency_name = competency[0]
        print(f"\nManaging levels for competency: {competency_name}")

        while True:
            # Get current levels
            cursor.execute('''
            SELECT level_id, level_name, level_value, description
            FROM competency_levels
            WHERE competency_id = ?
            ORDER BY level_value
            ''', (competency_id,))

            levels = cursor.fetchall()

            print("\nCurrent Competency Levels:")
            if not levels:
                print("No levels defined for this competency.")
            else:
                print("-" * 100)
                print(f"{'ID':<5} {'Level':<15} {'Value':<8} {'Description'}")
                print("-" * 100)

                for level in levels:
                    level_id, level_name, level_value, description = level
                    # Truncate long descriptions for display
                    short_desc = description[:70] + "..." if len(description) > 70 else description
                    print(f"{level_id:<5} {level_name:<15} {level_value:<8} {short_desc}")

            print("\nLevel Management Options:")
            print("1. Add New Level")
            print("2. Edit Level")
            print("3. Delete Level")
            print("4. Return to Previous Menu")

            choice = input("Enter your choice (1-4): ")

            if choice == '1':
                # Add new level
                level_name = input("Level Name (e.g., Beginner, Intermediate): ").strip()

                # Find the next level value
                next_value = 1
                if levels:
                    next_value = max(level[2] for level in levels) + 1

                # Allow overriding the level value
                override_value = input(f"Level Value [{next_value}] (leave blank for default): ").strip()
                if override_value:
                    try:
                        level_value = int(override_value)
                    except ValueError:
                        print("Invalid value. Using default.")
                        level_value = next_value
                else:
                    level_value = next_value

                description = input("Description: ").strip()

                # Insert the level
                cursor.execute('''
                INSERT INTO competency_levels
                (competency_id, level_name, level_value, description)
                VALUES (?, ?, ?, ?)
                ''', (competency_id, level_name, level_value, description))

                conn.commit()
                print("Level added successfully.")

            elif choice == '2':
                # Edit existing level
                if not levels:
                    print("No levels to edit. Please add levels first.")
                    continue

                level_id = input("Enter Level ID to edit: ").strip()

                try:
                    level_id = int(level_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if level exists
                cursor.execute('''
                SELECT level_id, level_name, level_value, description
                FROM competency_levels
                WHERE level_id = ? AND competency_id = ?
                ''', (level_id, competency_id))

                level = cursor.fetchone()

                if not level:
                    print(f"No level found with ID {level_id} for this competency.")
                    continue

                # Display current values
                print("\nCurrent values:")
                print(f"Level Name: {level[1]}")
                print(f"Level Value: {level[2]}")
                print(f"Description: {level[3]}")

                # Get new values (leave blank to keep current)
                print("\nEnter new values (leave blank to keep current):")
                new_name = input(f"Level Name [{level[1]}]: ").strip()
                new_value = input(f"Level Value [{level[2]}]: ").strip()
                new_description = input(f"Description [{level[3]}]: ").strip()

                # Use current values if new ones are blank
                level_name = new_name if new_name else level[1]
                level_value = level[2]
                if new_value:
                    try:
                        level_value = int(new_value)
                    except ValueError:
                        print("Invalid value. Using current value.")

                description = new_description if new_description else level[3]

                # Update the level
                cursor.execute('''
                UPDATE competency_levels
                SET level_name = ?, level_value = ?, description = ?
                WHERE level_id = ?
                ''', (level_name, level_value, description, level_id))

                conn.commit()
                print("Level updated successfully.")

            elif choice == '3':
                # Delete level
                if not levels:
                    print("No levels to delete. Please add levels first.")
                    continue

                level_id = input("Enter Level ID to delete: ").strip()

                try:
                    level_id = int(level_id)
                except ValueError:
                    print("Invalid ID. Please enter a number.")
                    continue

                # Check if level exists
                cursor.execute('''
                SELECT level_name
                FROM competency_levels
                WHERE level_id = ? AND competency_id = ?
                ''', (level_id, competency_id))

                level = cursor.fetchone()

                if not level:
                    print(f"No level found with ID {level_id} for this competency.")
                    continue

                # Check if level is used in student competencies
                cursor.execute('''
                SELECT COUNT(*)
                FROM student_competencies
                WHERE level_id = ?
                ''', (level_id,))

                usage_count = cursor.fetchone()[0]

                if usage_count > 0:
                    print(f"Warning: This level is used in {usage_count} student competency records.")
                    print("Deleting it will affect these records.")

                confirm = input(f"Are you sure you want to delete level '{level[0]}'? (y/n): ").strip().lower()

                if confirm == 'y':
                    # Delete the level
                    cursor.execute('''
                    DELETE FROM competency_levels
                    WHERE level_id = ?
                    ''', (level_id,))

                    conn.commit()
                    print("Level deleted successfully.")

            elif choice == '4':
                # Return to previous menu
                break

            else:
                print("Invalid choice. Please try again.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_student_competency_profile():
    """View a student's competency profile"""
    import matplotlib.pyplot as plt
    print("\nView Student Competency Profile")

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

        print(f"\nCompetency Profile for: {first_name} {last_name}")

        # Get all competency assessments for this student
        cursor.execute('''
        SELECT c.competency_id, c.name, c.category, c.description,
               cl.level_id, cl.level_name, cl.level_value, cl.description,
               sc.assessment_date, sc.evidence
        FROM student_competencies sc
        JOIN competencies c ON sc.competency_id = c.competency_id
        JOIN competency_levels cl ON sc.level_id = cl.level_id
        WHERE sc.student_id = ?
        ORDER BY c.category, c.name
        ''', (student_id,))

        assessments = cursor.fetchall()

        if not assessments:
            print("No competency assessments recorded for this student.")
            conn.close()
            return

        # Group assessments by category
        assessments_by_category = {}
        for assessment in assessments:
            category = assessment[2]
            if category not in assessments_by_category:
                assessments_by_category[category] = []
            assessments_by_category[category].append(assessment)

        # Display profile by category
        for category, category_assessments in assessments_by_category.items():
            print(f"\n{category} Competencies:")
            print("-" * 110)
            print(f"{'Competency':<30} {'Level':<15} {'Value':<8} {'Date':<12} {'Evidence'}")
            print("-" * 110)

            for assessment in category_assessments:
                comp_name = assessment[1]
                level_name = assessment[5]
                level_value = assessment[6]
                date = assessment[8]
                evidence = assessment[9] if assessment[9] else "N/A"

                # Truncate long names and evidence for display
                short_name = comp_name[:30] if len(comp_name) > 30 else comp_name
                short_evidence = evidence[:40] + "..." if len(evidence) > 40 else evidence

                print(f"{short_name:<30} {level_name:<15} {level_value:<8} {date:<12} {short_evidence}")

        # Calculate and display competency statistics
        total_competencies = len(assessments)
        level_values = [a[6] for a in assessments]
        avg_level = sum(level_values) / total_competencies

        # Count levels by range
        beginner_count = sum(1 for v in level_values if v == 1)
        intermediate_count = sum(1 for v in level_values if v == 2 or v == 3)
        advanced_count = sum(1 for v in level_values if v >= 4)

        print("\nCompetency Statistics:")
        print(f"Total Assessed Competencies: {total_competencies}")
        print(f"Average Level: {avg_level:.2f}")
        print(f"Beginner Level (1): {beginner_count} competencies ({beginner_count/total_competencies*100:.1f}%)")
        print(f"Intermediate Level (2-3): {intermediate_count} competencies ({intermediate_count/total_competencies*100:.1f}%)")
        print(f"Advanced Level (4+): {advanced_count} competencies ({advanced_count/total_competencies*100:.1f}%)")

        # Option to view detailed evidence
        view_evidence = input("\nView detailed evidence/notes? (y/n): ").strip().lower()
        if view_evidence == 'y':
            print("\nDetailed Evidence/Notes:")
            print("-" * 100)
            print(f"{'Competency':<30} {'Level':<15} {'Date':<12} {'Evidence/Notes'}")
            print("-" * 100)

            for assessment in assessments:
                comp_name = assessment[1]
                level_name = assessment[5]
                date = assessment[8]
                evidence = assessment[9] if assessment[9] else "N/A"

                # Truncate long names for display
                short_name = comp_name[:30] if len(comp_name) > 30 else comp_name

                print(f"{short_name:<30} {level_name:<15} {date:<12} {evidence}")

        # Option to visualize competency profile
        visualize = input("\nVisualize competency profile? (y/n): ").strip().lower()
        if visualize == 'y':
            # Create the visualization directory if it doesn't exist
            viz_dir = 'competency_visualizations'
            if not os.path.exists(viz_dir):
                os.makedirs(viz_dir)

            # Create a radar chart of competencies
            plt.figure(figsize=(10, 8))

            # Prepare data for radar chart
            categories = list(assessments_by_category.keys())
            num_categories = len(categories)

            # Calculate average level value per category
            category_avgs = []
            for category in categories:
                category_assessments = assessments_by_category[category]
                avg = sum(a[6] for a in category_assessments) / len(category_assessments)
                category_avgs.append(avg)

            # Set up radar chart
            angles = np.linspace(0, 2*np.pi, num_categories, endpoint=False).tolist()

            # Make the plot circular by appending the first values
            category_avgs.append(category_avgs[0])
            angles.append(angles[0])
            categories.append(categories[0])

            # Plot the radar chart
            ax = plt.subplot(111, polar=True)
            ax.plot(angles, category_avgs, 'o-', linewidth=2)
            ax.fill(angles, category_avgs, alpha=0.25)

            # Set the labels
            ax.set_thetagrids(np.degrees(angles[:-1]), categories[:-1])

            # Set y-axis limits
            ax.set_ylim(0, 5)

            # Add grid lines and labels
            ax.set_rticks([1, 2, 3, 4, 5])
            ax.set_rlabel_position(0)
            ax.grid(True)

            plt.title(f"Competency Profile: {first_name} {last_name}")

            # Save the visualization
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            viz_filename = f"{viz_dir}/competency_profile_{student_id}_{timestamp}.png"
            plt.savefig(viz_filename)
            plt.close()

            print(f"\nVisualization saved to {viz_filename}")

            # Create a bar chart of competency levels
            plt.figure(figsize=(12, 8))

            # Prepare data for bar chart
            competency_names = [a[1] for a in assessments]
            level_values = [a[6] for a in assessments]

            # Sort by level value
            sorted_indices = np.argsort(level_values)
            sorted_names = [competency_names[i] for i in sorted_indices]
            sorted_values = [level_values[i] for i in sorted_indices]

            # Truncate long names
            sorted_names = [name[:20] + "..." if len(name) > 20 else name for name in sorted_names]

            # Create a color map
            palette = plt.cm.viridis(np.array(sorted_values) / 5.0)

            # Create the bar chart
            bars = plt.barh(sorted_names, sorted_values, color=palette)

            plt.xlabel('Competency Level')
            plt.ylabel('Competency')
            plt.title(f"Competency Levels: {first_name} {last_name}")
            plt.xlim(0, 5.5)

            # Add value labels
            for i, bar in enumerate(bars):
                width = bar.get_width()
                plt.text(width + 0.1, bar.get_y() + bar.get_height()/2,
                        f'{width:.1f}', ha='left', va='center')

            plt.tight_layout()

            # Save the visualization
            bar_filename = f"{viz_dir}/competency_levels_{student_id}_{timestamp}.png"
            plt.savefig(bar_filename)
            plt.close()

            print(f"Bar chart saved to {bar_filename}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_competency_report():
    """Generate a comprehensive competency report"""
    print("\nGenerate Competency Report")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Ask what type of report to generate
        print("\nReport Options:")
        print("1. Individual Student Competency Report")
        print("2. Course Competency Summary")
        print("3. Return to Previous Menu")

        report_type = input("Select report type (1-3): ")

        if report_type == '1':
            # Individual student report
            student_id = select_student(cursor)
            if not student_id:
                conn.close()
                return

            generate_student_competency_report(cursor, student_id)

        elif report_type == '2':
            # Course competency summary
            cursor.execute("SELECT DISTINCT course FROM students ORDER BY course")
            courses = cursor.fetchall()

            if not courses:
                print("No courses found in the database.")
                conn.close()
                return

            print("\nAvailable Courses:")
            for i, (course,) in enumerate(courses):
                print(f"{i+1}. {course}")

            course_idx = input("Select course number: ")

            try:
                idx = int(course_idx)
                if 1 <= idx <= len(courses):
                    generate_course_competency_report(cursor, courses[idx-1][0])
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif report_type == '3':
            # Return to previous menu
            pass

        else:
            print("Invalid report type.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_student_competency_report(cursor, student_id):
    """Generate a detailed competency report for a specific student"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image
    from reportlab.platypus import Paragraph
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.platypus import Spacer
    from reportlab.platypus import Table
    from reportlab.platypus import TableStyle
    import matplotlib.pyplot as plt
    try:
        # Get student details
        cursor.execute('''
        SELECT first_name, last_name, course
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()
        if not student:
            print("Student not found.")
            return

        first_name, last_name, course = student

        # Get all competency assessments for this student
        cursor.execute('''
        SELECT c.competency_id, c.name, c.category, c.description,
               cl.level_id, cl.level_name, cl.level_value, cl.description,
               sc.assessment_date, sc.evidence
        FROM student_competencies sc
        JOIN competencies c ON sc.competency_id = c.competency_id
        JOIN competency_levels cl ON sc.level_id = cl.level_id
        WHERE sc.student_id = ?
        ORDER BY c.category, c.name
        ''', (student_id,))

        assessments = cursor.fetchall()

        if not assessments:
            print("No competency assessments recorded for this student.")
            return

        # Create the reports directory if it doesn't exist
        reports_dir = 'competency_reports'
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)

        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{reports_dir}/student_competency_{student_id}_{timestamp}.pdf"

        # Create the PDF document
        doc = SimpleDocTemplate(report_filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            alignment=1,  # Center alignment
            spaceAfter=12
        )
        elements.append(Paragraph("Student Competency Report", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Add student information
        elements.append(Paragraph("Student Information", styles['Heading2']))

        student_info = [
            ['Name:', f"{first_name} {last_name}"],
            ['Student ID:', student_id],
            ['Course:', course]
        ]

        student_table = Table(student_info, colWidths=[100, 400])
        student_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))

        elements.append(student_table)
        elements.append(Spacer(1, 12))

        # Group assessments by category
        assessments_by_category = {}
        for assessment in assessments:
            category = assessment[2]
            if category not in assessments_by_category:
                assessments_by_category[category] = []
            assessments_by_category[category].append(assessment)

        # Add category sections
        for category, category_assessments in assessments_by_category.items():
            elements.append(Paragraph(f"{category} Competencies", styles['Heading2']))

            assessment_data = [
                ['Competency', 'Level', 'Value', 'Date', 'Evidence']
            ]

            for assessment in category_assessments:
                comp_name = assessment[1]
                level_name = assessment[5]
                level_value = assessment[6]
                date = assessment[8]
                evidence = assessment[9] if assessment[9] else "N/A"

                assessment_data.append([
                    comp_name,
                    level_name,
                    str(level_value),
                    date,
                    evidence
                ])

            assessment_table = Table(assessment_data, colWidths=[120, 80, 40, 80, 180])
            assessment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (1, 1), (3, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            elements.append(assessment_table)
            elements.append(Spacer(1, 12))

        # Calculate and add summary statistics
        total_competencies = len(assessments)
        level_values = [a[6] for a in assessments]
        avg_level = sum(level_values) / total_competencies

        # Count levels by range
        beginner_count = sum(1 for v in level_values if v == 1)
        intermediate_count = sum(1 for v in level_values if v == 2 or v == 3)
        advanced_count = sum(1 for v in level_values if v >= 4)

        elements.append(Paragraph("Competency Summary", styles['Heading2']))

        summary_info = [
            ['Total Assessed Competencies:', str(total_competencies)],
            ['Average Level:', f"{avg_level:.2f}"],
            ['Beginner Level (1):', f"{beginner_count} ({beginner_count/total_competencies*100:.1f}%)"],
            ['Intermediate Level (2-3):', f"{intermediate_count} ({intermediate_count/total_competencies*100:.1f}%)"],
            ['Advanced Level (4+):', f"{advanced_count} ({advanced_count/total_competencies*100:.1f}%)"]
        ]

        summary_table = Table(summary_info, colWidths=[200, 300])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 12))

        # Add visualization
        # Create a bar chart of competency levels
        plt.figure(figsize=(10, 6))

        # Prepare data for bar chart
        competency_names = [a[1] for a in assessments]

        # Sort by level value
        sorted_indices = np.argsort(level_values)
        sorted_names = [competency_names[i] for i in sorted_indices]
        sorted_values = [level_values[i] for i in sorted_indices]

        # Truncate long names
        sorted_names = [name[:30] + "..." if len(name) > 30 else name for name in sorted_names]

        # Create a color map
        palette = plt.cm.viridis(np.array(sorted_values) / 5.0)

        # Create the bar chart
        plt.barh(sorted_names, sorted_values, color=palette)

        plt.xlabel('Competency Level')
        plt.ylabel('Competency')
        plt.title("Competency Levels")
        plt.xlim(0, 5.5)

        plt.tight_layout()

        # Save the visualization to a temporary file
        chart_filename = f"{reports_dir}/temp_chart_{timestamp}.png"
        plt.savefig(chart_filename)
        plt.close()

        # Add the chart to the PDF
        elements.append(Paragraph("Competency Visualization", styles['Heading2']))
        img = Image(chart_filename, width=7*inch, height=5*inch)
        elements.append(img)
        elements.append(Spacer(1, 12))

        # Add recommendations section
        elements.append(Paragraph("Development Recommendations", styles['Heading2']))

        # Identify focus areas (competencies with low levels)
        low_competencies = [(a[1], a[6]) for a in assessments if a[6] < 2]

        if low_competencies:
            elements.append(Paragraph("Focus Areas for Improvement:", styles['Normal']))
            for comp_name, level in low_competencies:
                elements.append(Paragraph(f"• {comp_name} (current level: {level})", styles['Normal']))
        else:
            elements.append(Paragraph("No specific focus areas identified - all competencies are at level 2 or higher.", styles['Normal']))

        elements.append(Spacer(1, 6))

        # General recommendations based on profile
        if avg_level < 2:
            elements.append(Paragraph("Overall Recommendation: Focus on building fundamental competencies to reach intermediate levels.", styles['Normal']))
        elif avg_level < 3.5:
            elements.append(Paragraph("Overall Recommendation: Continue developing intermediate competencies while beginning to master advanced skills.", styles['Normal']))
        else:
            elements.append(Paragraph("Overall Recommendation: Focus on maintaining and refining advanced competencies.", styles['Normal']))

        # Build the PDF
        doc.build(elements)

        # Clean up temporary files
        try:
            os.remove(chart_filename)
        except Exception:
            pass  # Ignore errors during cleanup

        print(f"\nStudent competency report generated: {report_filename}")

    except Exception as e:
        print(f"Error generating report: {e}")

def generate_course_competency_report(cursor, course):
    """Generate a competency report for a course"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image
    from reportlab.platypus import Paragraph
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.platypus import Spacer
    from reportlab.platypus import Table
    from reportlab.platypus import TableStyle
    import matplotlib.pyplot as plt
    try:
        # Get all students in this course
        cursor.execute('''
        SELECT student_id, first_name, last_name
        FROM students
        WHERE course = ?
        ''', (course,))

        students = cursor.fetchall()

        if not students:
            print(f"No students found for course {course}.")
            return

        # Get all competencies that have been assessed for these students
        # SECURITY FIX: Use parameterized query instead of string interpolation for IN clause
        student_id_values = [s[0] for s in students]
        placeholders = ','.join(['?' for _ in student_id_values])

        cursor.execute('''
        SELECT DISTINCT c.competency_id, c.name, c.category
        FROM competencies c
        JOIN student_competencies sc ON c.competency_id = sc.competency_id
        WHERE sc.student_id IN (''' + placeholders + ''')
        ORDER BY c.category, c.name
        ''', student_id_values)

        competencies = cursor.fetchall()

        if not competencies:
            print(f"No competency assessments found for students in course {course}.")
            return

        # Get assessment data for each competency
        competency_data = {}

        for comp_id, comp_name, category in competencies:
            # SECURITY FIX: Use parameterized query for IN clause
            cursor.execute('''
            SELECT sc.student_id, cl.level_value
            FROM student_competencies sc
            JOIN competency_levels cl ON sc.level_id = cl.level_id
            WHERE sc.competency_id = ? AND sc.student_id IN (''' + placeholders + ''')
            ''', [comp_id] + student_id_values)

            assessments = cursor.fetchall()

            if assessments:
                # Calculate statistics
                level_values = [a[1] for a in assessments]
                avg_level = sum(level_values) / len(level_values)
                coverage = (len(assessments) / len(students)) * 100
                beginner_pct = sum(1 for v in level_values if v == 1) / len(level_values) * 100
                intermediate_pct = sum(1 for v in level_values if v == 2 or v == 3) / len(level_values) * 100
                advanced_pct = sum(1 for v in level_values if v >= 4) / len(level_values) * 100
            else:
                avg_level = 0
                coverage = 0
                beginner_pct = intermediate_pct = advanced_pct = 0

            competency_data[comp_id] = {
                'name': comp_name,
                'category': category,
                'avg_level': avg_level,
                'coverage': coverage,
                'beginner_pct': beginner_pct,
                'intermediate_pct': intermediate_pct,
                'advanced_pct': advanced_pct
            }

        # Create the reports directory if it doesn't exist
        reports_dir = 'competency_reports'
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)

        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{reports_dir}/course_competency_{course}_{timestamp}.pdf"

        # Create the PDF document
        doc = SimpleDocTemplate(report_filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            alignment=1,  # Center alignment
            spaceAfter=12
        )
        elements.append(Paragraph(f"Course Competency Report: {course}", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Add course information
        elements.append(Paragraph("Course Information", styles['Heading2']))

        course_info = [
            ['Course:', course],
            ['Total Students:', str(len(students))],
            ['Total Competencies Assessed:', str(len(competencies))]
        ]

        course_table = Table(course_info, colWidths=[150, 350])
        course_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))

        elements.append(course_table)
        elements.append(Spacer(1, 12))

        # Group competencies by category
        competencies_by_category = {}
        for comp_id, _, category in competencies:
            if category not in competencies_by_category:
                competencies_by_category[category] = []
            competencies_by_category[category].append(comp_id)

        # Add category sections
        for category, category_competencies in competencies_by_category.items():
            elements.append(Paragraph(f"{category} Competencies", styles['Heading2']))

            competency_table_data = [
                ['Competency', 'Avg Level', 'Coverage', 'Beginner %', 'Intermediate %', 'Advanced %']
            ]

            for comp_id in category_competencies:
                data = competency_data[comp_id]

                competency_table_data.append([
                    data['name'],
                    f"{data['avg_level']:.2f}",
                    f"{data['coverage']:.1f}%",
                    f"{data['beginner_pct']:.1f}%",
                    f"{data['intermediate_pct']:.1f}%",
                    f"{data['advanced_pct']:.1f}%"
                ])

            competency_table = Table(competency_table_data, colWidths=[150, 70, 70, 70, 70, 70])
            competency_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            elements.append(competency_table)
            elements.append(Spacer(1, 12))

        # Calculate overall statistics
        competencies_with_data = [data for comp_id, data in competency_data.items() if data['avg_level'] > 0]

        if competencies_with_data:
            avg_level_overall = sum(data['avg_level'] for data in competencies_with_data) / len(competencies_with_data)
            avg_coverage_overall = sum(data['coverage'] for data in competencies_with_data) / len(competencies_with_data)

            elements.append(Paragraph("Overall Statistics", styles['Heading2']))

            overall_stats = [
                ['Average Competency Level:', f"{avg_level_overall:.2f}"],
                ['Average Coverage:', f"{avg_coverage_overall:.1f}%"]
            ]

            overall_table = Table(overall_stats, colWidths=[200, 300])
            overall_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (1, -1), 6),
            ]))

            elements.append(overall_table)
            elements.append(Spacer(1, 12))

            # Create visualizations

            # 1. Average level by competency
            plt.figure(figsize=(10, 6))

            # Sort competencies by average level
            sorted_competencies = sorted(
                [(comp_id, data['name'], data['avg_level'])
                 for comp_id, data in competency_data.items()],
                key=lambda x: x[2], reverse=True
            )

            # Limit to top 15 for readability
            if len(sorted_competencies) > 15:
                sorted_competencies = sorted_competencies[:15]

            comp_names = [c[1][:25] + "..." if len(c[1]) > 25 else c[1] for c in sorted_competencies]
            avg_levels = [c[2] for c in sorted_competencies]

            # Create a color map
            palette = plt.cm.viridis(np.array(avg_levels) / 5.0)

            # Create the bar chart
            bars = plt.barh(comp_names, avg_levels, color=palette)

            plt.xlabel('Average Competency Level')
            plt.ylabel('Competency')
            plt.title("Average Competency Levels")
            plt.xlim(0, 5.5)

            # Add value labels
            for bar in bars:
                width = bar.get_width()
                plt.text(width + 0.1, bar.get_y() + bar.get_height()/2,
                        f'{width:.2f}', ha='left', va='center')

            plt.tight_layout()

            # Save the visualization to a temporary file
            chart1_filename = f"{reports_dir}/temp_chart1_{timestamp}.png"
            plt.savefig(chart1_filename)
            plt.close()

            # Add the chart to the PDF
            elements.append(Paragraph("Competency Level Visualization", styles['Heading2']))
            img1 = Image(chart1_filename, width=7*inch, height=4*inch)
            elements.append(img1)
            elements.append(Spacer(1, 12))

            # 2. Coverage by competency
            plt.figure(figsize=(10, 6))

            # Sort competencies by coverage
            sorted_by_coverage = sorted(
                [(comp_id, data['name'], data['coverage'])
                 for comp_id, data in competency_data.items()],
                key=lambda x: x[2]
            )

            # Limit to lowest 15 for readability
            if len(sorted_by_coverage) > 15:
                sorted_by_coverage = sorted_by_coverage[:15]

            comp_names = [c[1][:25] + "..." if len(c[1]) > 25 else c[1] for c in sorted_by_coverage]
            coverages = [c[2] for c in sorted_by_coverage]

            # Create the bar chart
            bars = plt.barh(comp_names, coverages, color='skyblue')

            plt.xlabel('Coverage (%)')
            plt.ylabel('Competency')
            plt.title("Lowest Competency Coverage")
            plt.xlim(0, 105)

            # Add value labels
            for bar in bars:
                width = bar.get_width()
                plt.text(width + 1, bar.get_y() + bar.get_height()/2,
                        f'{width:.1f}%', ha='left', va='center')

            plt.tight_layout()

            # Save the visualization to a temporary file
            chart2_filename = f"{reports_dir}/temp_chart2_{timestamp}.png"
            plt.savefig(chart2_filename)
            plt.close()

            # Add the chart to the PDF
            elements.append(Paragraph("Competency Coverage Visualization", styles['Heading2']))
            img2 = Image(chart2_filename, width=7*inch, height=4*inch)
            elements.append(img2)
            elements.append(Spacer(1, 12))

            # Add recommendations
            elements.append(Paragraph("Recommendations", styles['Heading2']))

            # Identify improvement areas
            low_level_competencies = [(comp_id, data['name'])
                                    for comp_id, data in competency_data.items()
                                    if data['avg_level'] < 2.5 and data['coverage'] > 30]

            low_coverage_competencies = [(comp_id, data['name'])
                                       for comp_id, data in competency_data.items()
                                       if data['coverage'] < 50]

            if low_level_competencies:
                elements.append(Paragraph(
                    "• Focus on improving overall proficiency in these competencies:",
                    styles['Normal']))

                for _, name in low_level_competencies[:5]:  # Limit to first 5
                    elements.append(Paragraph(f"   - {name}", styles['Normal']))

                if len(low_level_competencies) > 5:
                    elements.append(Paragraph(
                        f"   - Plus {len(low_level_competencies) - 5} more competencies with low average levels",
                        styles['Normal']))

            if low_coverage_competencies:
                elements.append(Paragraph(
                    "• Increase assessment coverage for these competencies:",
                    styles['Normal']))

                for _, name in low_coverage_competencies[:5]:  # Limit to first 5
                    elements.append(Paragraph(f"   - {name}", styles['Normal']))

                if len(low_coverage_competencies) > 5:
                    elements.append(Paragraph(
                        f"   - Plus {len(low_coverage_competencies) - 5} more competencies with low coverage",
                        styles['Normal']))

            # General recommendations
            if avg_coverage_overall < 80:
                elements.append(Paragraph(
                    f"• Implement more consistent competency assessment across all students (current average coverage: {avg_coverage_overall:.1f}%).",
                    styles['Normal']))

            if avg_level_overall < 3:
                elements.append(Paragraph(
                    f"• Develop strategies to raise overall competency levels (current average: {avg_level_overall:.2f}).",
                    styles['Normal']))

            elements.append(Paragraph(
                "• Document best practices from competencies with high achievement levels to apply to other areas.",
                styles['Normal']))
        else:
            elements.append(Paragraph("No competency assessment data available for analysis.", styles['Normal']))

        # Build the PDF
        doc.build(elements)

        # Clean up temporary files
        try:
            if 'chart1_filename' in locals() and os.path.exists(chart1_filename):
                os.remove(chart1_filename)
            if 'chart2_filename' in locals() and os.path.exists(chart2_filename):
                os.remove(chart2_filename)
        except Exception:
            pass  # Ignore errors during cleanup

        print(f"\nCourse competency report generated: {report_filename}")

    except Exception as e:
        print(f"Error generating report: {e}")

def assess_student_risk(cursor, student_id, first_name, last_name, course):
    """Assess risk for a specific student"""
    risk_score = 0
    risk_factors = []

    # Factor 1: Current GPA
    gpa, credits, _ = calculate_student_gpa(cursor, student_id)
    if gpa:
        if gpa < 2.0:
            risk_score += 40
            risk_factors.append(f"Very Low GPA ({gpa:.2f})")
        elif gpa < 2.5:
            risk_score += 25
            risk_factors.append(f"Low GPA ({gpa:.2f})")
        elif gpa < 3.0:
            risk_score += 10
            risk_factors.append(f"Below Average GPA ({gpa:.2f})")

    # Factor 2: Failed assessments
    cursor.execute('''
    SELECT COUNT(*) FROM grades
    WHERE student_id = ? AND letter_grade = 'F'
    ''', (student_id,))

    failed_count = cursor.fetchone()[0]
    if failed_count > 0:
        risk_score += failed_count * 8
        risk_factors.append(f"Failed Assessments ({failed_count})")

    # Factor 3: Attendance/Submission rate
    cursor.execute('''
    SELECT COUNT(DISTINCT a.assessment_id) as total_assessments,
           COUNT(g.grade_id) as submitted_assessments
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))

    result = cursor.fetchone()
    if result and result[0] > 0:
        submission_rate = result[1] / result[0]
        if submission_rate < 0.7:
            risk_score += 20
            risk_factors.append(f"Low Submission Rate ({submission_rate*100:.1f}%)")
        elif submission_rate < 0.85:
            risk_score += 10
            risk_factors.append(f"Moderate Submission Rate ({submission_rate*100:.1f}%)")

    # Factor 4: Performance trend
    cursor.execute('''
    SELECT g.score / a.max_points * 100, g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date
    ''', (student_id,))

    grade_trend = cursor.fetchall()
    if len(grade_trend) >= 4:
        recent_scores = [g[0] for g in grade_trend[-3:]]
        early_scores = [g[0] for g in grade_trend[:3]]

        recent_avg = np.mean(recent_scores)
        early_avg = np.mean(early_scores)

        if recent_avg < early_avg - 15:
            risk_score += 15
            risk_factors.append("Declining Performance")
        elif recent_avg < early_avg - 5:
            risk_score += 8
            risk_factors.append("Slight Decline")

    # Determine risk level
    if risk_score >= 50:
        risk_level = "High"
    elif risk_score >= 25:
        risk_level = "Medium"
    elif risk_score >= 10:
        risk_level = "Low"
    else:
        risk_level = "Minimal"

    return {
        'student_id': student_id,
        'name': f"{first_name} {last_name}",
        'course': course,
        'risk_score': risk_score,
        'risk_level': risk_level,
        'risk_factors': risk_factors,
        'gpa': gpa
    }

def assess_comprehensive_student_risk(cursor, student_id, first_name, last_name, course, email):
    """Assess comprehensive risk for a student"""
    risk_factors = {}
    total_risk_score = 0

    # 1. Academic Performance Risk
    gpa, _, _ = calculate_student_gpa(cursor, student_id)
    if gpa:
        if gpa < 2.0:
            academic_risk = 40
            risk_factors['Academic Performance'] = f"Very Low GPA ({gpa:.2f})"
        elif gpa < 2.5:
            academic_risk = 25
            risk_factors['Academic Performance'] = f"Low GPA ({gpa:.2f})"
        elif gpa < 3.0:
            academic_risk = 10
            risk_factors['Academic Performance'] = f"Below Average GPA ({gpa:.2f})"
        else:
            academic_risk = 0
        total_risk_score += academic_risk

    # 2. Assessment Submission Risk
    cursor.execute('''
    SELECT COUNT(DISTINCT a.assessment_id) as total,
           COUNT(g.grade_id) as submitted
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))

    result = cursor.fetchone()
    submission_risk = 0
    if result and result[0] > 0:
        submission_rate = result[1] / result[0]
        if submission_rate < 0.6:
            submission_risk = 20
            risk_factors['Submission Rate'] = f"Very Low ({submission_rate*100:.1f}%)"
        elif submission_rate < 0.8:
            submission_risk = 12
            risk_factors['Submission Rate'] = f"Low ({submission_rate*100:.1f}%)"
        total_risk_score += submission_risk

    # 3. Failed Assessments Risk
    cursor.execute('''
    SELECT COUNT(*) FROM grades
    WHERE student_id = ? AND letter_grade = 'F'
    ''', (student_id,))

    failed_count = cursor.fetchone()[0]
    failed_risk = 0
    if failed_count > 0:
        failed_risk = min(failed_count * 8, 20)
        risk_factors['Failed Assessments'] = f"{failed_count} failures"
        total_risk_score += failed_risk

    # 4. Performance Trend Risk
    cursor.execute('''
    SELECT g.score / a.max_points * 100, g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date
    ''', (student_id,))

    grades_history = cursor.fetchall()
    trend_risk = 0
    if len(grades_history) >= 4:
        recent_scores = [g[0] for g in grades_history[-3:]]
        early_scores = [g[0] for g in grades_history[:3]]

        recent_avg = np.mean(recent_scores)
        early_avg = np.mean(early_scores)
        decline = early_avg - recent_avg

        if decline > 15:
            trend_risk = 15
            risk_factors['Performance Trend'] = f"Significant decline ({decline:.1f}%)"
        elif decline > 5:
            trend_risk = 8
            risk_factors['Performance Trend'] = f"Moderate decline ({decline:.1f}%)"
        total_risk_score += trend_risk

    # Determine risk level
    if total_risk_score >= 50:
        risk_level = "High"
    elif total_risk_score >= 25:
        risk_level = "Medium"
    elif total_risk_score >= 10:
        risk_level = "Low"
    else:
        risk_level = "Minimal"

    return {
        'student_id': student_id,
        'name': f"{first_name} {last_name}",
        'course': course,
        'email': email,
        'risk_score': total_risk_score,
        'risk_level': risk_level,
        'risk_factors': risk_factors,
        'gpa': gpa
    }
