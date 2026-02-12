from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import os
import csv
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import matplotlib
from university_system.infrastructure.database.db import get_connection
matplotlib.use('Agg')
from university_system.modules.domain.academics.grading.utils import select_student



def learning_outcome_menu():
    """Display the learning outcome tracking menu and handle user choices"""
    while True:
        print("\nLearning Outcome Tracking:")
        print("1. Manage Learning Outcomes")
        print("2. Map Assessments to Outcomes")
        print("3. Record Outcome Achievement")
        print("4. View Student Outcome Achievement")
        print("5. Generate Outcome Report")
        print("6. Return to Grade Menu")
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            manage_learning_outcomes()
        elif choice == '2':
            map_assessments_to_outcomes()
        elif choice == '3':
            record_outcome_achievement()
        elif choice == '4':
            view_student_outcome_achievement()
        elif choice == '5':
            generate_outcome_report()
        elif choice == '6':
            print("Returning to grade menu...")
            break
        else:
            print("Invalid choice. Please try again.")

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
                cursor.execute('''
                SELECT outcome_id, course, outcome_code, description, category, importance
                FROM learning_outcomes
                ORDER BY course, outcome_code
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
                cursor.execute('''
                INSERT INTO learning_outcomes
                (course, outcome_code, description, category, importance)
                VALUES (?, ?, ?, ?, ?)
                ''', (course, outcome_code, description, category, importance))
                
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
                cursor.execute('''
                SELECT outcome_id, course, outcome_code, description, category, importance
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
                cursor.execute('''
                UPDATE learning_outcomes
                SET course = ?, outcome_code = ?, description = ?, category = ?, importance = ?
                WHERE outcome_id = ?
                ''', (course, code, description, category, importance, outcome_id))
                
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

def generate_outcome_report():
    """Generate a comprehensive report of learning outcome achievement"""
    print("\nGenerate Learning Outcome Report")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ask what type of report to generate
        print("\nReport Options:")
        print("1. Individual Student Outcome Report")
        print("2. Course Outcome Achievement Summary")
        print("3. Module-Based Outcome Report")
        
        report_type = input("Select report type (1-3): ")
        
        if report_type == '1':
            # Individual student report
            student_id = select_student(cursor)
            if not student_id:
                conn.close()
                return
            
            generate_student_outcome_report(cursor, student_id)
            
        elif report_type == '2':
            # Course outcome summary
            cursor.execute("SELECT DISTINCT course FROM students ORDER BY course")
            courses = cursor.fetchall()
            
            if not courses:
                print("No courses found in the database.")
                conn.close()
                return
            
            print("\nAvailable Courses:")
            for i, (course,) in enumerate(courses):
                print(f"{i+1}. {course}")
            
            course_idx = input("Select course number (or 0 for all courses): ")
            
            try:
                idx = int(course_idx)
                if idx == 0:
                    generate_all_courses_outcome_report(cursor)
                elif 1 <= idx <= len(courses):
                    generate_course_outcome_report(cursor, courses[idx-1][0])
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            
        elif report_type == '3':
            # Module-based outcome report
            cursor.execute("SELECT DISTINCT module_code, module_name FROM modules ORDER BY module_name")
            modules = cursor.fetchall()
            
            if not modules:
                print("No modules found in the database.")
                conn.close()
                return
            
            print("\nAvailable Modules:")
            for i, (code, name) in enumerate(modules):
                print(f"{i+1}. {code} - {name}")
            
            module_idx = input("Select module number: ")
            
            try:
                idx = int(module_idx)
                if 1 <= idx <= len(modules):
                    generate_module_outcome_report(cursor, modules[idx-1][0])
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            
        else:
            print("Invalid report type.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_student_outcome_report(cursor, student_id):
    """Generate a detailed outcome report for a specific student"""
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
            return
        
        # Create the reports directory if it doesn't exist
        reports_dir = 'outcome_reports'
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{reports_dir}/outcome_report_{student_id}_{timestamp}.pdf"
        
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
        elements.append(Paragraph(f"Learning Outcome Achievement Report", title_style))
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
        
        # Group outcomes by category
        outcomes_by_category = {}
        for outcome in outcomes:
            category = outcome[3]
            if category not in outcomes_by_category:
                outcomes_by_category[category] = []
            outcomes_by_category[category].append(outcome)
        
        # Add category sections
        for category, category_outcomes in outcomes_by_category.items():
            elements.append(Paragraph(f"{category} Outcomes", styles['Heading2']))
            
            outcome_data = [
                ['Code', 'Achievement', 'Date', 'Importance', 'Description']
            ]
            
            for outcome in category_outcomes:
                _, code, description, _, importance, level, date, _ = outcome
                
                if level is not None:
                    level_display = f"{level:.1f}/5.0"
                    date_display = date
                else:
                    level_display = "Not assessed"
                    date_display = "N/A"
                
                outcome_data.append([
                    code,
                    level_display,
                    date_display,
                    str(importance),
                    description
                ])
            
            outcome_table = Table(outcome_data, colWidths=[60, 80, 80, 70, 230])
            outcome_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (3, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(outcome_table)
            elements.append(Spacer(1, 12))
        
        # Calculate and add summary statistics
        assessed_outcomes = [o for o in outcomes if o[5] is not None]
        
        if assessed_outcomes:
            elements.append(Paragraph("Achievement Summary", styles['Heading2']))
            
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
            
            stats_info = [
                ['Total Learning Outcomes:', str(total_outcomes)],
                ['Assessed Outcomes:', f"{assessed_count} ({assessment_rate:.1f}%)"],
                ['Average Achievement Level:', f"{avg_achievement:.2f}/5.0"],
                ['Weighted Average (by importance):', f"{weighted_avg:.2f}/5.0"],
                ['High Achievement (≥4.0):', f"{high_achievement} outcomes"],
                ['Medium Achievement (2.5-3.9):', f"{medium_achievement} outcomes"],
                ['Low Achievement (<2.5):', f"{low_achievement} outcomes"]
            ]
            
            stats_table = Table(stats_info, colWidths=[200, 300])
            stats_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (1, -1), 6),
            ]))
            
            elements.append(stats_table)
            elements.append(Spacer(1, 12))
            
            # Add visualization if there are enough outcomes
            if assessed_count >= 3:
                # Create a simple bar chart of achievement levels
                plt.figure(figsize=(10, 6))
                
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
                plt.bar(codes, levels, color=bar_colors)
                plt.axhline(y=4.0, color='g', linestyle='--', label='High Achievement')
                plt.axhline(y=2.5, color='r', linestyle='--', label='Low Achievement')
                
                plt.ylim(0, 5.5)
                plt.title(f'Learning Outcome Achievement Levels')
                plt.xlabel('Learning Outcome Code')
                plt.ylabel('Achievement Level (0-5)')
                plt.xticks(rotation=45, ha='right')
                
                # Add a legend for categories
                category_patches = [plt.Rectangle((0,0),1,1, color=color_map[cat]) for cat in unique_categories]
                plt.legend(category_patches, unique_categories, loc='upper right')
                
                plt.tight_layout()
                
                # Save the figure to a temporary file
                chart_filename = f"{reports_dir}/temp_chart_{timestamp}.png"
                plt.savefig(chart_filename)
                plt.close()
                
                # Add the chart to the PDF
                elements.append(Paragraph("Achievement Visualization", styles['Heading2']))
                img = Image(chart_filename, width=7*inch, height=4*inch)
                elements.append(img)
                elements.append(Spacer(1, 12))
                
                # Clean up the temporary file after building the PDF
                # We'll do this later to ensure the file exists during PDF generation
            
            # Add evidence/comments section
            elements.append(Paragraph("Evidence and Comments", styles['Heading2']))
            
            evidence_data = [
                ['Code', 'Achievement', 'Date', 'Evidence/Comments']
            ]
            
            for outcome in assessed_outcomes:
                _, code, _, _, _, level, date, evidence = outcome
                if evidence:
                    evidence_data.append([
                        code,
                        f"{level:.1f}/5.0",
                        date,
                        evidence
                    ])
                else:
                    evidence_data.append([
                        code,
                        f"{level:.1f}/5.0",
                        date,
                        "No evidence recorded"
                    ])
            
            evidence_table = Table(evidence_data, colWidths=[60, 80, 80, 300])
            evidence_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (2, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(evidence_table)
            
            # Add recommendations based on achievement levels
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Recommendations", styles['Heading2']))
            
            if low_achievement > 0:
                elements.append(Paragraph(
                    f"• Focus on improving outcomes with low achievement levels (<2.5), especially those with high importance ratings.",
                    styles['Normal']))
            
            if high_achievement < assessed_count * 0.5:  # Less than 50% are high achievement
                elements.append(Paragraph(
                    f"• Work towards moving medium achievement outcomes (2.5-3.9) into the high achievement range (≥4.0).",
                    styles['Normal']))
            
            if assessment_rate < 80:
                elements.append(Paragraph(
                    f"• Increase the assessment coverage of learning outcomes (currently at {assessment_rate:.1f}%).",
                    styles['Normal']))
            
            elements.append(Paragraph(
                f"• Continue to gather evidence for achievement of learning outcomes, especially for those that currently lack detailed evidence.",
                styles['Normal']))
            
            if weighted_avg < 3.5:
                elements.append(Paragraph(
                    f"• Prioritize improvement in high-importance outcomes to raise the weighted average achievement level.",
                    styles['Normal']))
        else:
            elements.append(Paragraph("No outcomes have been assessed yet for this student.", styles['Normal']))
        
        # Build the PDF
        doc.build(elements)
        
        # Clean up temporary files
        if assessed_count >= 3:
            try:
                os.remove(chart_filename)
            except Exception:
                pass  # Ignore errors during cleanup
        
        print(f"\nLearning outcome report generated: {report_filename}")
        
    except Exception as e:
        print(f"Error generating report: {e}")

def generate_course_outcome_report(cursor, course):
    """Generate a report of learning outcome achievement for a course"""
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
        
        # Get all learning outcomes for this course
        cursor.execute('''
        SELECT outcome_id, outcome_code, description, category, importance
        FROM learning_outcomes
        WHERE course = ? OR course = 'ALL'
        ORDER BY category, outcome_code
        ''', (course,))
        
        outcomes = cursor.fetchall()
        
        if not outcomes:
            print(f"No learning outcomes defined for course {course}.")
            return
        
        # Get achievement data for all students
        outcome_achievement = {}
        
        for outcome in outcomes:
            outcome_id = outcome[0]
            
            ids = [s[0] for s in students]
            
            if ids:  # Only execute query if there are students
                placeholders = ",".join("?" for _ in ids)
                cursor.execute('''
                    SELECT o.student_id, o.achievement_level
                    FROM outcome_results AS o
                    WHERE o.outcome_id = ?
                      AND o.student_id IN (''' + placeholders + ''')
                ''', [outcome_id] + ids)

                results = cursor.fetchall()
                outcome_achievement[outcome_id] = {r[0]: r[1] for r in results}
            else:
                # No students, so no achievement data
                outcome_achievement[outcome_id] = {}
        
        # Create the reports directory if it doesn't exist
        reports_dir = 'outcome_reports'
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{reports_dir}/course_outcome_report_{course}_{timestamp}.pdf"
        
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
        elements.append(Paragraph(f"Course Learning Outcome Report", title_style))
        elements.append(Paragraph(f"{course} Course", styles['Heading2']))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))
        
        # Add course information
        elements.append(Paragraph("Course Information", styles['Heading2']))
        
        course_info = [
            ['Course:', course],
            ['Total Students:', str(len(students))],
            ['Total Learning Outcomes:', str(len(outcomes))]
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
        
        # Group outcomes by category
        outcomes_by_category = {}
        for outcome in outcomes:
            category = outcome[3]
            if category not in outcomes_by_category:
                outcomes_by_category[category] = []
            outcomes_by_category[category].append(outcome)
        
        # Prepare data for visualizations
        outcome_stats = {}
        
        for outcome in outcomes:
            outcome_id, outcome_code = outcome[0], outcome[1]
            achievements = list(outcome_achievement[outcome_id].values())
            
            if achievements:
                avg_achievement = sum(achievements) / len(achievements)
                coverage = (len(achievements) / len(students)) * 100
                high_count = sum(1 for a in achievements if a >= 4.0)
                medium_count = sum(1 for a in achievements if 2.5 <= a < 4.0)
                low_count = sum(1 for a in achievements if a < 2.5)
                high_pct = (high_count / len(achievements)) * 100 if achievements else 0
            else:
                avg_achievement = 0
                coverage = 0
                high_count = medium_count = low_count = 0
                high_pct = 0
            
            outcome_stats[outcome_id] = {
                'code': outcome_code,
                'avg': avg_achievement,
                'coverage': coverage,
                'high': high_count,
                'medium': medium_count,
                'low': low_count,
                'high_pct': high_pct
            }
        
        # Add category sections with statistics
        for category, category_outcomes in outcomes_by_category.items():
            elements.append(Paragraph(f"{category} Outcomes", styles['Heading2']))
            
            outcome_data = [
                ['Code', 'Description', 'Importance', 'Average', 'Coverage', 'High %']
            ]
            
            for outcome in category_outcomes:
                outcome_id, code, description, _, importance = outcome
                stats = outcome_stats[outcome_id]
                
                outcome_data.append([
                    code,
                    description,
                    str(importance),
                    f"{stats['avg']:.2f}/5.0" if stats['avg'] > 0 else "N/A",
                    f"{stats['coverage']:.1f}%" if stats['coverage'] > 0 else "0%",
                    f"{stats['high_pct']:.1f}%" if stats['high_pct'] > 0 else "0%"
                ])
            
            outcome_table = Table(outcome_data, colWidths=[60, 230, 60, 60, 60, 50])
            outcome_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(outcome_table)
            elements.append(Spacer(1, 12))
        
        # Calculate overall statistics
        outcomes_with_achievements = [oid for oid, data in outcome_stats.items() if data['avg'] > 0]
        
        if outcomes_with_achievements:
            avg_achievement_overall = sum(outcome_stats[oid]['avg'] for oid in outcomes_with_achievements) / len(outcomes_with_achievements)
            avg_coverage_overall = sum(outcome_stats[oid]['coverage'] for oid in outcomes_with_achievements) / len(outcomes_with_achievements)
            high_pct_overall = sum(outcome_stats[oid]['high_pct'] for oid in outcomes_with_achievements) / len(outcomes_with_achievements)
            
            elements.append(Paragraph("Overall Statistics", styles['Heading2']))
            
            overall_stats = [
                ['Average Achievement Level:', f"{avg_achievement_overall:.2f}/5.0"],
                ['Average Outcome Coverage:', f"{avg_coverage_overall:.1f}%"],
                ['Average High Achievement Rate:', f"{high_pct_overall:.1f}%"],
                ['Outcomes with Achievement Data:', f"{len(outcomes_with_achievements)}/{len(outcomes)} ({len(outcomes_with_achievements)/len(outcomes)*100:.1f}%)"]
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
            
            # 1. Top and bottom outcomes by achievement
            if len(outcomes_with_achievements) >= 5:
                # Create a figure
                plt.figure(figsize=(10, 6))
                
                # Sort outcomes by average achievement
                sorted_outcomes = sorted(
                    [(oid, outcome_stats[oid]['code'], outcome_stats[oid]['avg']) 
                     for oid in outcomes_with_achievements],
                    key=lambda x: x[2], reverse=True
                )
                
                # Get top 5 and bottom 5
                top_outcomes = sorted_outcomes[:5]
                bottom_outcomes = sorted_outcomes[-5:]
                
                # Combine into one chart
                all_outcomes = top_outcomes + bottom_outcomes
                outcome_codes = [o[1] for o in all_outcomes]
                avg_achievements = [o[2] for o in all_outcomes]
                
                # Create bar chart
                y_pos = np.arange(len(all_outcomes))
                bars = plt.barh(y_pos, avg_achievements, color=['green'] * 5 + ['red'] * 5)
                plt.yticks(y_pos, outcome_codes)
                plt.xlabel('Average Achievement Level (0-5)')
                plt.title('Top and Bottom Outcomes by Achievement Level')
                
                # Add value labels
                for i, bar in enumerate(bars):
                    width = bar.get_width()
                    plt.text(width + 0.1, bar.get_y() + bar.get_height()/2, 
                            f'{width:.2f}', ha='left', va='center')
                
                plt.tight_layout()
                
                # Save the figure to a temporary file
                chart1_filename = f"{reports_dir}/temp_chart1_{timestamp}.png"
                plt.savefig(chart1_filename)
                plt.close()
                
                # Add the chart to the PDF
                elements.append(Paragraph("Achievement Analysis", styles['Heading2']))
                img1 = Image(chart1_filename, width=7*inch, height=4*inch)
                elements.append(img1)
                elements.append(Spacer(1, 12))
            
            # 2. Coverage by outcome
            if outcomes_with_achievements:
                # Create a figure
                plt.figure(figsize=(10, 6))
                
                # Sort outcomes by coverage
                sorted_by_coverage = sorted(
                    [(oid, outcome_stats[oid]['code'], outcome_stats[oid]['coverage']) 
                     for oid in outcomes_with_achievements],
                    key=lambda x: x[2], reverse=True
                )
                
                outcome_codes = [o[1] for o in sorted_by_coverage]
                coverages = [o[2] for o in sorted_by_coverage]
                
                if len(outcome_codes) > 10:
                    outcome_codes = outcome_codes[:10]  # Limit to top 10 for readability
                    coverages = coverages[:10]
                
                # Create bar chart
                plt.bar(outcome_codes, coverages, color='skyblue')
                plt.axhline(y=80, color='g', linestyle='--', label='Target Coverage (80%)')
                plt.axhline(y=50, color='r', linestyle='--', label='Minimum Coverage (50%)')
                
                plt.xlabel('Learning Outcome Code')
                plt.ylabel('Coverage (%)')
                plt.title('Learning Outcome Coverage (% of students assessed)')
                plt.xticks(rotation=45, ha='right')
                plt.legend()
                
                plt.tight_layout()
                
                # Save the figure to a temporary file
                chart2_filename = f"{reports_dir}/temp_chart2_{timestamp}.png"
                plt.savefig(chart2_filename)
                plt.close()
                
                # Add the chart to the PDF
                elements.append(Paragraph("Coverage Analysis", styles['Heading2']))
                img2 = Image(chart2_filename, width=7*inch, height=4*inch)
                elements.append(img2)
                elements.append(Spacer(1, 12))
            
            # Add recommendations
            elements.append(Paragraph("Recommendations", styles['Heading2']))
            
            # Identify improvement areas
            low_achievement_outcomes = [oid for oid in outcomes_with_achievements if outcome_stats[oid]['avg'] < 3.0]
            low_coverage_outcomes = [oid for oid in outcomes_with_achievements if outcome_stats[oid]['coverage'] < 50]
            no_data_outcomes = [o[0] for o in outcomes if o[0] not in outcomes_with_achievements]
            
            if low_achievement_outcomes:
                elements.append(Paragraph(
                    f"• Focus on improving student achievement in the following outcomes with low average levels:",
                    styles['Normal']))
                
                for oid in low_achievement_outcomes:
                    for o in outcomes:
                        if o[0] == oid:
                            elements.append(Paragraph(
                                f"   - {o[1]}: {o[2]} (current avg: {outcome_stats[oid]['avg']:.2f}/5.0)",
                                styles['Normal']))
                            break
            
            if low_coverage_outcomes:
                elements.append(Paragraph(
                    f"• Increase assessment coverage for these outcomes with less than 50% student coverage:",
                    styles['Normal']))
                
                for oid in low_coverage_outcomes:
                    for o in outcomes:
                        if o[0] == oid:
                            elements.append(Paragraph(
                                f"   - {o[1]}: {o[2]} (current coverage: {outcome_stats[oid]['coverage']:.1f}%)",
                                styles['Normal']))
                            break
            
            if no_data_outcomes:
                elements.append(Paragraph(
                    f"• Begin assessing the following outcomes that currently have no achievement data:",
                    styles['Normal']))
                
                for oid in no_data_outcomes[:5]:  # Limit to first 5 to avoid very long lists
                    for o in outcomes:
                        if o[0] == oid:
                            elements.append(Paragraph(
                                f"   - {o[1]}: {o[2]}",
                                styles['Normal']))
                            break
                
                if len(no_data_outcomes) > 5:
                    elements.append(Paragraph(
                        f"   - Plus {len(no_data_outcomes) - 5} more outcomes without achievement data",
                        styles['Normal']))
            
            if avg_coverage_overall < 80:
                elements.append(Paragraph(
                    f"• Implement more consistent assessment of learning outcomes across all students (current average coverage: {avg_coverage_overall:.1f}%).",
                    styles['Normal']))
            
            if avg_achievement_overall < 3.5:
                elements.append(Paragraph(
                    f"• Develop strategies to raise overall achievement levels (current average: {avg_achievement_overall:.2f}/5.0).",
                    styles['Normal']))
            
            elements.append(Paragraph(
                f"• Document best practices from outcomes with high achievement levels to apply to other areas.",
                styles['Normal']))
        else:
            elements.append(Paragraph("No achievement data has been recorded for any outcomes in this course.", styles['Normal']))
        
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
        
        print(f"\nCourse outcome report generated: {report_filename}")
        
    except Exception as e:
        print(f"Error generating report: {e}")

def generate_all_courses_outcome_report(cursor):
    """Generate a comparative report of learning outcome achievement across all courses"""
    try:
        # Get all courses
        cursor.execute("SELECT DISTINCT course FROM students ORDER BY course")
        courses = [c[0] for c in cursor.fetchall()]
        
        if not courses:
            print("No courses found in the database.")
            return
        
        # Get outcome data for each course
        course_data = {}
        
        for course in courses:
            # Get student IDs for this course
            cursor.execute("SELECT student_id FROM students WHERE course = ?", (course,))
            student_ids = [s[0] for s in cursor.fetchall()]
            
            if not student_ids:
                continue
            
            # Get outcomes for this course
            cursor.execute('''
            SELECT outcome_id, outcome_code, category
            FROM learning_outcomes
            WHERE course = ? OR course = 'ALL'
            ''', (course,))
            
            outcomes = cursor.fetchall()
            
            if not outcomes:
                continue
            
            # Get achievement data
            outcome_data = {}
            
            for outcome_id, outcome_code, category in outcomes:
                if len(student_ids) > 0:
                    # Get achievement levels for this outcome
                    placeholders = ','.join(['?'] * len(student_ids))
                    cursor.execute('''
                    SELECT achievement_level
                    FROM outcome_results
                    WHERE outcome_id = ? AND student_id IN (''' + placeholders + ''')
                    ''', [outcome_id] + student_ids)
                    
                    achievement_levels = [r[0] for r in cursor.fetchall()]
                    
                    if achievement_levels:
                        avg_achievement = sum(achievement_levels) / len(achievement_levels)
                        coverage = (len(achievement_levels) / len(student_ids)) * 100
                    else:
                        avg_achievement = 0
                        coverage = 0
                else:
                    avg_achievement = 0
                    coverage = 0
                
                outcome_data[outcome_code] = {
                    'category': category,
                    'avg_achievement': avg_achievement,
                    'coverage': coverage
                }
            
            # Calculate course-level statistics
            outcomes_with_data = [data for code, data in outcome_data.items() if data['avg_achievement'] > 0]
            
            if outcomes_with_data:
                avg_course_achievement = sum(data['avg_achievement'] for data in outcomes_with_data) / len(outcomes_with_data)
                avg_course_coverage = sum(data['coverage'] for data in outcomes_with_data) / len(outcomes_with_data)
                outcome_count = len(outcomes)
                assessed_count = len(outcomes_with_data)
            else:
                avg_course_achievement = 0
                avg_course_coverage = 0
                outcome_count = len(outcomes)
                assessed_count = 0
            
            course_data[course] = {
                'outcomes': outcome_data,
                'avg_achievement': avg_course_achievement,
                'avg_coverage': avg_course_coverage,
                'outcome_count': outcome_count,
                'assessed_count': assessed_count,
                'student_count': len(student_ids)
            }
        
        # Filter out courses with no data
        course_data = {course: data for course, data in course_data.items() if data['student_count'] > 0}
        
        if not course_data:
            print("No courses with student and outcome data found.")
            return
        
        # Create the reports directory if it doesn't exist
        reports_dir = 'outcome_reports'
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{reports_dir}/all_courses_outcome_report_{timestamp}.pdf"
        
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
        elements.append(Paragraph(f"Cross-Course Learning Outcome Report", title_style))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))
        
        # Add summary table
        elements.append(Paragraph("Course Summary", styles['Heading2']))
        
        summary_data = [
            ['Course', 'Students', 'Outcomes', 'Assessed', 'Avg Achievement', 'Avg Coverage']
        ]
        
        for course, data in course_data.items():
            summary_data.append([
                course,
                str(data['student_count']),
                str(data['outcome_count']),
                f"{data['assessed_count']} ({data['assessed_count']/data['outcome_count']*100:.1f}%)" if data['outcome_count'] > 0 else "0",
                f"{data['avg_achievement']:.2f}/5.0" if data['avg_achievement'] > 0 else "N/A",
                f"{data['avg_coverage']:.1f}%" if data['avg_coverage'] > 0 else "0%"
            ])
        
        summary_table = Table(summary_data, colWidths=[80, 70, 70, 80, 100, 100])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 12))
        
        # Create visualizations
        
        # 1. Average achievement by course
        plt.figure(figsize=(10, 6))
        
        courses_list = list(course_data.keys())
        avg_achievements = [data['avg_achievement'] for data in course_data.values()]
        
        # Sort by achievement
        sorted_indices = np.argsort(avg_achievements)[::-1]  # Descending order
        sorted_courses = [courses_list[i] for i in sorted_indices]
        sorted_achievements = [avg_achievements[i] for i in sorted_indices]
        
        bars = plt.bar(sorted_courses, sorted_achievements, color='skyblue')
        plt.axhline(y=4.0, color='g', linestyle='--', label='High Achievement')
        plt.axhline(y=2.5, color='r', linestyle='--', label='Low Achievement')
        
        plt.xlabel('Course')
        plt.ylabel('Average Achievement Level (0-5)')
        plt.title('Average Learning Outcome Achievement by Course')
        plt.ylim(0, 5.5)
        plt.legend()
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{height:.2f}', ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save the figure to a temporary file
        chart1_filename = f"{reports_dir}/temp_chart1_{timestamp}.png"
        plt.savefig(chart1_filename)
        plt.close()
        
        # Add the chart to the PDF
        elements.append(Paragraph("Achievement Comparison", styles['Heading2']))
        img1 = Image(chart1_filename, width=7*inch, height=4*inch)
        elements.append(img1)
        elements.append(Spacer(1, 12))
        
        # 2. Coverage comparison
        plt.figure(figsize=(10, 6))
        
        avg_coverages = [data['avg_coverage'] for data in course_data.values()]
        
        # Sort by coverage
        sorted_indices = np.argsort(avg_coverages)[::-1]  # Descending order
        sorted_courses = [courses_list[i] for i in sorted_indices]
        sorted_coverages = [avg_coverages[i] for i in sorted_indices]
        
        bars = plt.bar(sorted_courses, sorted_coverages, color='lightgreen')
        plt.axhline(y=80, color='g', linestyle='--', label='Target Coverage (80%)')
        plt.axhline(y=50, color='r', linestyle='--', label='Minimum Coverage (50%)')
        
        plt.xlabel('Course')
        plt.ylabel('Average Coverage (%)')
        plt.title('Average Learning Outcome Coverage by Course')
        plt.ylim(0, 105)
        plt.legend()
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{height:.1f}%', ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save the figure to a temporary file
        chart2_filename = f"{reports_dir}/temp_chart2_{timestamp}.png"
        plt.savefig(chart2_filename)
        plt.close()
        
        # Add the chart to the PDF
        elements.append(Paragraph("Coverage Comparison", styles['Heading2']))
        img2 = Image(chart2_filename, width=7*inch, height=4*inch)
        elements.append(img2)
        elements.append(Spacer(1, 12))
        
        # 3. Assessment rate comparison
        plt.figure(figsize=(10, 6))
        
        assessment_rates = [data['assessed_count']/data['outcome_count']*100 if data['outcome_count'] > 0 else 0 
                           for data in course_data.values()]
        
        # Sort by assessment rate
        sorted_indices = np.argsort(assessment_rates)[::-1]  # Descending order
        sorted_courses = [courses_list[i] for i in sorted_indices]
        sorted_rates = [assessment_rates[i] for i in sorted_indices]
        
        bars = plt.bar(sorted_courses, sorted_rates, color='salmon')
        plt.axhline(y=80, color='g', linestyle='--', label='Target (80%)')
        
        plt.xlabel('Course')
        plt.ylabel('Outcomes Assessed (%)')
        plt.title('Percentage of Learning Outcomes with Assessment Data')
        plt.ylim(0, 105)
        plt.legend()
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{height:.1f}%', ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save the figure to a temporary file
        chart3_filename = f"{reports_dir}/temp_chart3_{timestamp}.png"
        plt.savefig(chart3_filename)
        plt.close()
        
        # Add the chart to the PDF
        elements.append(Paragraph("Assessment Rate Comparison", styles['Heading2']))
        img3 = Image(chart3_filename, width=7*inch, height=4*inch)
        elements.append(img3)
        elements.append(Spacer(1, 12))
        
        # Add cross-course analysis for shared outcomes
        elements.append(Paragraph("Shared Outcome Analysis", styles['Heading2']))
        
        # Find outcomes that exist across multiple courses
        all_outcome_codes = set()
        for course, data in course_data.items():
            all_outcome_codes.update(data['outcomes'].keys())
        
        shared_outcomes = {}
        for code in all_outcome_codes:
            courses_with_outcome = []
            for course, data in course_data.items():
                if code in data['outcomes'] and data['outcomes'][code]['avg_achievement'] > 0:
                    courses_with_outcome.append((
                        course, 
                        data['outcomes'][code]['avg_achievement'],
                        data['outcomes'][code]['coverage']
                    ))
            
            if len(courses_with_outcome) > 1:  # Only include if shared across courses
                shared_outcomes[code] = courses_with_outcome
        
        if shared_outcomes:
            shared_data = [
                ['Outcome', 'Courses', 'Avg Achievement', 'Avg Coverage', 'Variation']
            ]
            
            for code, courses_data in shared_outcomes.items():
                courses_list = [c[0] for c in courses_data]
                achievements = [c[1] for c in courses_data]
                coverages = [c[2] for c in courses_data]
                
                avg_achievement = sum(achievements) / len(achievements)
                avg_coverage = sum(coverages) / len(coverages)
                
                # Calculate variation in achievement across courses
                achievement_range = max(achievements) - min(achievements)
                
                shared_data.append([
                    code,
                    ", ".join(courses_list),
                    f"{avg_achievement:.2f}/5.0",
                    f"{avg_coverage:.1f}%",
                    f"{achievement_range:.2f}"
                ])
            
            shared_table = Table(shared_data, colWidths=[60, 200, 90, 90, 60])
            shared_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(shared_table)
            
            # Create visualization for a few selected shared outcomes
            if len(shared_outcomes) >= 3:
                # Select outcomes with the most courses or highest variation
                selected_outcomes = sorted(shared_outcomes.items(), 
                                          key=lambda x: (len(x[1]), max(c[1] for c in x[1]) - min(c[1] for c in x[1])), 
                                          reverse=True)[:5]
                
                plt.figure(figsize=(12, 8))
                
                # Create a grouped bar chart
                num_outcomes = len(selected_outcomes)
                num_courses_max = max(len(data) for _, data in selected_outcomes)
                bar_width = 0.8 / num_courses_max
                
                for i, (code, courses_data) in enumerate(selected_outcomes):
                    for j, (course, achievement, _) in enumerate(courses_data):
                        x_pos = i + j * bar_width
                        plt.bar(x_pos, achievement, width=bar_width, 
                               label=course if i == 0 else "_nolegend_")
                
                plt.xlabel('Learning Outcome')
                plt.ylabel('Achievement Level (0-5)')
                plt.title('Cross-Course Comparison of Shared Learning Outcomes')
                plt.xticks([i + (num_courses_max-1) * bar_width / 2 for i in range(num_outcomes)], 
                          [code for code, _ in selected_outcomes])
                plt.ylim(0, 5.5)
                plt.legend()
                
                plt.tight_layout()
                
                # Save the figure to a temporary file
                chart4_filename = f"{reports_dir}/temp_chart4_{timestamp}.png"
                plt.savefig(chart4_filename)
                plt.close()
                
                # Add the chart to the PDF
                elements.append(Spacer(1, 12))
                img4 = Image(chart4_filename, width=7*inch, height=5*inch)
                elements.append(img4)
        else:
            elements.append(Paragraph("No shared outcomes with achievement data found across courses.", styles['Normal']))
        
        # Add recommendations
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Recommendations", styles['Heading2']))
        
        # Calculate some statistics for recommendations
        avg_achievement_all = sum(data['avg_achievement'] for data in course_data.values() if data['avg_achievement'] > 0)
        avg_achievement_all /= sum(1 for data in course_data.values() if data['avg_achievement'] > 0)
        
        avg_coverage_all = sum(data['avg_coverage'] for data in course_data.values() if data['avg_coverage'] > 0)
        avg_coverage_all /= sum(1 for data in course_data.values() if data['avg_coverage'] > 0)
        
        low_achievement_courses = [course for course, data in course_data.items() 
                                 if data['avg_achievement'] > 0 and data['avg_achievement'] < 3.0]
        
        low_coverage_courses = [course for course, data in course_data.items() 
                              if data['avg_coverage'] > 0 and data['avg_coverage'] < 50]
        
        # Add recommendations based on analysis
        if low_achievement_courses:
            elements.append(Paragraph(
                f"• Focus on improving learning outcome achievement in the following courses with below-average levels:",
                styles['Normal']))
            
            for course in low_achievement_courses:
                elements.append(Paragraph(
                    f"   - {course} (current avg: {course_data[course]['avg_achievement']:.2f}/5.0)",
                    styles['Normal']))
        
        if low_coverage_courses:
            elements.append(Paragraph(
                f"• Increase assessment coverage in these courses with less than 50% coverage:",
                styles['Normal']))
            
            for course in low_coverage_courses:
                elements.append(Paragraph(
                    f"   - {course} (current coverage: {course_data[course]['avg_coverage']:.1f}%)",
                    styles['Normal']))
        
        if shared_outcomes:
            high_variation_outcomes = [code for code, courses_data in shared_outcomes.items() 
                                     if max(c[1] for c in courses_data) - min(c[1] for c in courses_data) > 1.0]
            
            if high_variation_outcomes:
                elements.append(Paragraph(
                    f"• Address inconsistencies in the following shared outcomes that have high variation across courses:",
                    styles['Normal']))
                
                for code in high_variation_outcomes[:5]:  # Limit to top 5
                    elements.append(Paragraph(
                        f"   - {code}",
                        styles['Normal']))
                
                if len(high_variation_outcomes) > 5:
                    elements.append(Paragraph(
                        f"   - Plus {len(high_variation_outcomes) - 5} more outcomes with high variation",
                        styles['Normal']))
        
        if avg_coverage_all < 70:
            elements.append(Paragraph(
                f"• Develop a systematic approach to outcome assessment across all courses (current average coverage: {avg_coverage_all:.1f}%).",
                styles['Normal']))
        
        # Add general recommendations
        elements.append(Paragraph(
            f"• Share best practices from high-performing courses to improve outcomes in lower-performing areas.",
            styles['Normal']))
        
        elements.append(Paragraph(
            f"• Standardize outcome assessment methods across courses to ensure consistent evaluation.",
            styles['Normal']))
        
        elements.append(Paragraph(
            f"• Regularly review and update learning outcomes based on achievement data and curriculum changes.",
            styles['Normal']))
        
        # Build the PDF
        doc.build(elements)
        
        # Clean up temporary files
        try:
            for filename in [chart1_filename, chart2_filename, chart3_filename]:
                if 'filename' in locals() and os.path.exists(filename):
                    os.remove(filename)
            if 'chart4_filename' in locals() and os.path.exists(chart4_filename):
                os.remove(chart4_filename)
        except Exception:
            pass  # Ignore errors during cleanup
        
        print(f"\nCross-course outcome report generated: {report_filename}")
        
    except Exception as e:
        print(f"Error generating report: {e}")

def generate_module_outcome_report(cursor, module_code):
    """Generate a report of learning outcome achievement for a specific module"""
    try:
        # Get module details
        cursor.execute('''
        SELECT module_name, module_type
        FROM modules
        WHERE module_code = ?
        ''', (module_code,))
        
        module = cursor.fetchone()
        if not module:
            print(f"Module {module_code} not found.")
            return
        
        module_name, module_type = module
        
        # Get assessments for this module
        cursor.execute('''
        SELECT assessment_id, assessment_name, assessment_type, weight
        FROM assessments
        WHERE module_code = ?
        ''', (module_code,))
        
        assessments = cursor.fetchall()
        
        if not assessments:
            print(f"No assessments found for module {module_code}.")
            return
        
        # Get outcome mappings for each assessment
        assessment_outcomes = {}
        
        for assessment_id, _, _, _ in assessments:
            cursor.execute('''
            SELECT ao.outcome_id, lo.outcome_code, lo.description, lo.category, ao.weight
            FROM assessment_outcomes ao
            JOIN learning_outcomes lo ON ao.outcome_id = lo.outcome_id
            WHERE ao.assessment_id = ?
            ''', (assessment_id,))
            
            outcomes = cursor.fetchall()
            assessment_outcomes[assessment_id] = outcomes
        
        # Get all students enrolled in this module
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ?
        ''', (module_code,))
        
        students = cursor.fetchall()
        
        if not students:
            print(f"No students found enrolled in module {module_code}.")
            return
        
        # Create a map of outcomes to assessments
        outcome_assessments = {}
        
        for assessment_id, outcomes in assessment_outcomes.items():
            for outcome_id, code, desc, category, weight in outcomes:
                if outcome_id not in outcome_assessments:
                    outcome_assessments[outcome_id] = {
                        'code': code,
                        'description': desc,
                        'category': category,
                        'assessments': []
                    }
                
                # Find assessment details
                for a_id, a_name, a_type, a_weight in assessments:
                    if a_id == assessment_id:
                        outcome_assessments[outcome_id]['assessments'].append({
                            'id': assessment_id,
                            'name': a_name,
                            'type': a_type,
                            'weight': a_weight,
                            'outcome_weight': weight
                        })
                        break
        
        # If no outcomes are mapped, exit
        if not outcome_assessments:
            print(f"No learning outcomes are mapped to assessments for module {module_code}.")
            return
        
        # Get outcome achievement data
        outcome_achievement = {}
        
        for outcome_id in outcome_assessments.keys():
            ids = [s[0] for s in students]
            
            if ids:  # Only execute query if there are students
                placeholders = ",".join("?" for _ in ids)
                cursor.execute('''
                    SELECT o.student_id, o.achievement_level
                    FROM outcome_results AS o
                    WHERE o.outcome_id = ?
                      AND o.student_id IN (''' + placeholders + ''')
                ''', [outcome_id] + ids)

                direct_results = {r[0]: r[1] for r in cursor.fetchall()}
            else:
                # No students, so no direct results
                direct_results = {}
            
            # Calculate achievement levels from assessment grades
            assessment_results = {}
            
            for student_id, _, _ in students:
                # Skip students with direct measurement
                if student_id in direct_results:
                    continue
                
                # Get grades for assessments that map to this outcome
                assessment_ids = [a['id'] for a in outcome_assessments[outcome_id]['assessments']]
                
                if not assessment_ids:
                    continue
                
                student_grades = []
                
                for assessment_id in assessment_ids:
                    cursor.execute('''
                    SELECT g.score, a.max_points, ao.weight
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    JOIN assessment_outcomes ao ON a.assessment_id = ao.assessment_id AND ao.outcome_id = ?
                    WHERE g.student_id = ? AND g.assessment_id = ?
                    ''', (outcome_id, student_id, assessment_id))
                    
                    grade = cursor.fetchone()
                    
                    if grade:
                        score, max_points, outcome_weight = grade
                        if max_points > 0:  # Avoid division by zero
                            percentage = (score / max_points) * 100
                            student_grades.append((percentage, outcome_weight))
                
                if student_grades:
                    # Calculate weighted average achievement
                    weighted_sum = sum(percentage * weight for percentage, weight in student_grades)
                    total_weight = sum(weight for _, weight in student_grades)
                    
                    if total_weight > 0:
                        avg_percentage = weighted_sum / total_weight
                        
                        # Convert to 0-5 scale
                        assessment_results[student_id] = avg_percentage / 20  # 100% = 5.0
            
            # Combine direct and calculated results
            combined_results = {**assessment_results, **direct_results}
            
            outcome_achievement[outcome_id] = combined_results
        
        # Create the reports directory if it doesn't exist
        reports_dir = 'outcome_reports'
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{reports_dir}/module_outcome_report_{module_code}_{timestamp}.pdf"
        
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
        elements.append(Paragraph(f"Module Learning Outcome Report", title_style))
        elements.append(Paragraph(f"{module_code} - {module_name}", styles['Heading2']))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 12))
        
        # Add module information
        elements.append(Paragraph("Module Information", styles['Heading2']))
        
        module_info = [
            ['Module Code:', module_code],
            ['Module Name:', module_name],
            ['Module Type:', module_type],
            ['Total Students:', str(len(students))],
            ['Total Assessments:', str(len(assessments))],
            ['Total Outcomes:', str(len(outcome_assessments))]
        ]
        
        module_table = Table(module_info, colWidths=[150, 350])
        module_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (1, -1), 6),
        ]))
        
        elements.append(module_table)
        elements.append(Spacer(1, 12))
        
        # Add assessment information
        elements.append(Paragraph("Assessment Information", styles['Heading2']))
        
        assessment_data = [
            ['Assessment Name', 'Type', 'Weight', 'Mapped Outcomes']
        ]
        
        for assessment_id, name, type, weight in assessments:
            outcomes = assessment_outcomes.get(assessment_id, [])
            outcome_codes = [o[1] for o in outcomes]
            
            assessment_data.append([
                name,
                type,
                f"{weight}%",
                ", ".join(outcome_codes) if outcome_codes else "None"
            ])
        
        assessment_table = Table(assessment_data, colWidths=[200, 100, 60, 140])
        assessment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(assessment_table)
        elements.append(Spacer(1, 12))
        
        # Group outcomes by category
        outcomes_by_category = {}
        
        for outcome_id, data in outcome_assessments.items():
            category = data['category']
            if category not in outcomes_by_category:
                outcomes_by_category[category] = []
            outcomes_by_category[category].append((outcome_id, data))
        
        # Calculate outcome statistics
        outcome_stats = {}
        
        for outcome_id, data in outcome_assessments.items():
            achievements = list(outcome_achievement.get(outcome_id, {}).values())
            
            if achievements:
                avg_achievement = sum(achievements) / len(achievements)
                coverage = (len(achievements) / len(students)) * 100
                high_count = sum(1 for a in achievements if a >= 4.0)
                medium_count = sum(1 for a in achievements if 2.5 <= a < 4.0)
                low_count = sum(1 for a in achievements if a < 2.5)
                high_pct = (high_count / len(achievements)) * 100 if achievements else 0
            else:
                avg_achievement = 0
                coverage = 0
                high_count = medium_count = low_count = 0
                high_pct = 0
            
            outcome_stats[outcome_id] = {
                'avg': avg_achievement,
                'coverage': coverage,
                'high': high_count,
                'medium': medium_count,
                'low': low_count,
                'high_pct': high_pct
            }
        
        # Add outcome sections by category
        for category, category_outcomes in outcomes_by_category.items():
            elements.append(Paragraph(f"{category} Outcomes", styles['Heading2']))
            
            outcome_data = [
                ['Code', 'Description', 'Average', 'Coverage', 'Assessments']
            ]
            
            for outcome_id, data in category_outcomes:
                code = data['code']
                description = data['description']
                stats = outcome_stats[outcome_id]
                assessment_names = [a['name'] for a in data['assessments']]
                
                outcome_data.append([
                    code,
                    description,
                    f"{stats['avg']:.2f}/5.0" if stats['avg'] > 0 else "N/A",
                    f"{stats['coverage']:.1f}%" if stats['coverage'] > 0 else "0%",
                    ", ".join(assessment_names)
                ])
            
            outcome_table = Table(outcome_data, colWidths=[60, 170, 60, 60, 150])
            outcome_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (3, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(outcome_table)
            elements.append(Spacer(1, 12))
        
        # Calculate overall statistics
        outcomes_with_achievements = [oid for oid, stats in outcome_stats.items() if stats['avg'] > 0]
        
        if outcomes_with_achievements:
            avg_achievement_overall = sum(outcome_stats[oid]['avg'] for oid in outcomes_with_achievements) / len(outcomes_with_achievements)
            avg_coverage_overall = sum(outcome_stats[oid]['coverage'] for oid in outcomes_with_achievements) / len(outcomes_with_achievements)
            
            elements.append(Paragraph("Overall Statistics", styles['Heading2']))
            
            overall_stats = [
                ['Average Achievement Level:', f"{avg_achievement_overall:.2f}/5.0"],
                ['Average Outcome Coverage:', f"{avg_coverage_overall:.1f}%"],
                ['Outcomes with Achievement Data:', f"{len(outcomes_with_achievements)}/{len(outcome_assessments)} ({len(outcomes_with_achievements)/len(outcome_assessments)*100:.1f}%)"]
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
            
            # 1. Achievement levels by outcome
            if outcomes_with_achievements:
                # Create a figure
                plt.figure(figsize=(10, 6))
                
                # Sort outcomes by achievement level
                sorted_outcomes = sorted(
                    [(oid, outcome_assessments[oid]['code'], outcome_stats[oid]['avg']) 
                     for oid in outcomes_with_achievements],
                    key=lambda x: x[2], reverse=True
                )
                
                outcome_codes = [o[1] for o in sorted_outcomes]
                achievements = [o[2] for o in sorted_outcomes]
                
                # Create bar chart
                plt.bar(outcome_codes, achievements, color='skyblue')
                plt.axhline(y=4.0, color='g', linestyle='--', label='High Achievement')
                plt.axhline(y=2.5, color='r', linestyle='--', label='Low Achievement')
                
                plt.xlabel('Learning Outcome Code')
                plt.ylabel('Average Achievement Level (0-5)')
                plt.title('Learning Outcome Achievement Levels')
                plt.ylim(0, 5.5)
                plt.xticks(rotation=45, ha='right')
                plt.legend()
                
                plt.tight_layout()
                
                # Save the figure to a temporary file
                chart1_filename = f"{reports_dir}/temp_chart1_{timestamp}.png"
                plt.savefig(chart1_filename)
                plt.close()
                
                # Add the chart to the PDF
                elements.append(Paragraph("Achievement Visualization", styles['Heading2']))
                img1 = Image(chart1_filename, width=7*inch, height=4*inch)
                elements.append(img1)
                elements.append(Spacer(1, 12))
            
            # Add outcome-assessment mapping visualization
            if assessments and outcome_assessments:
                plt.figure(figsize=(12, 8))
                
                # Create a matrix for the heatmap
                assessment_names = [a[1] for a in assessments]
                outcome_codes = [outcome_assessments[oid]['code'] for oid in outcome_assessments.keys()]
                
                matrix = np.zeros((len(outcome_codes), len(assessment_names)))
                
                # Fill the matrix with weights
                for i, outcome_id in enumerate(outcome_assessments.keys()):
                    for j, (assessment_id, _, _, _) in enumerate(assessments):
                        for assessment in outcome_assessments[outcome_id]['assessments']:
                            if assessment['id'] == assessment_id:
                                matrix[i, j] = assessment['outcome_weight']
                
                # Create the heatmap
                plt.imshow(matrix, cmap='YlGnBu')
                
                # Add labels
                plt.yticks(range(len(outcome_codes)), outcome_codes)
                plt.xticks(range(len(assessment_names)), assessment_names, rotation=45, ha='right')
                
                plt.colorbar(label='Outcome Weight in Assessment')
                plt.title('Outcome-Assessment Mapping')
                plt.xlabel('Assessments')
                plt.ylabel('Learning Outcomes')
                
                plt.tight_layout()
                
                # Save the figure to a temporary file
                chart2_filename = f"{reports_dir}/temp_chart2_{timestamp}.png"
                plt.savefig(chart2_filename)
                plt.close()
                
                # Add the chart to the PDF
                elements.append(Paragraph("Outcome-Assessment Mapping", styles['Heading2']))
                img2 = Image(chart2_filename, width=7*inch, height=5*inch)
                elements.append(img2)
                elements.append(Spacer(1, 12))
            
            # Add recommendations
            elements.append(Paragraph("Recommendations", styles['Heading2']))
            
            # Identify improvement areas
            low_achievement_outcomes = [(oid, outcome_assessments[oid]['code']) 
                                      for oid in outcomes_with_achievements 
                                      if outcome_stats[oid]['avg'] < 3.0]
            
            low_coverage_outcomes = [(oid, outcome_assessments[oid]['code']) 
                                   for oid in outcomes_with_achievements 
                                   if outcome_stats[oid]['coverage'] < 50]
            
            no_data_outcomes = [(oid, outcome_assessments[oid]['code']) 
                              for oid in outcome_assessments.keys() 
                              if oid not in outcomes_with_achievements]
            
            if low_achievement_outcomes:
                elements.append(Paragraph(
                    f"• Focus on improving achievement in these outcomes with low average levels:",
                    styles['Normal']))
                
                for _, code in low_achievement_outcomes:
                    for oid, data in outcome_assessments.items():
                        if data['code'] == code:
                            elements.append(Paragraph(
                                f"   - {code}: {data['description']} (current avg: {outcome_stats[oid]['avg']:.2f}/5.0)",
                                styles['Normal']))
                            break
            
            if low_coverage_outcomes:
                elements.append(Paragraph(
                    f"• Increase assessment coverage for these outcomes:",
                    styles['Normal']))
                
                for _, code in low_coverage_outcomes:
                    for oid, data in outcome_assessments.items():
                        if data['code'] == code:
                            elements.append(Paragraph(
                                f"   - {code}: {data['description']} (current coverage: {outcome_stats[oid]['coverage']:.1f}%)",
                                styles['Normal']))
                            break
            
            if no_data_outcomes:
                elements.append(Paragraph(
                    f"• Begin assessing these outcomes that currently have no achievement data:",
                    styles['Normal']))
                
                for _, code in no_data_outcomes[:5]:  # Limit to first 5 to avoid very long lists
                    for oid, data in outcome_assessments.items():
                        if data['code'] == code:
                            elements.append(Paragraph(
                                f"   - {code}: {data['description']}",
                                styles['Normal']))
                            break
                
                if len(no_data_outcomes) > 5:
                    elements.append(Paragraph(
                        f"   - Plus {len(no_data_outcomes) - 5} more outcomes without achievement data",
                        styles['Normal']))
            
            # Check assessment-outcome mappings
            unmapped_assessments = [a for a in assessments if a[0] not in assessment_outcomes or not assessment_outcomes[a[0]]]
            
            if unmapped_assessments:
                elements.append(Paragraph(
                    f"• Map learning outcomes to these assessments that currently have no outcome mappings:",
                    styles['Normal']))
                
                for a_id, a_name, a_type, a_weight in unmapped_assessments:
                    elements.append(Paragraph(
                        f"   - {a_name} ({a_type}, {a_weight}%)",
                        styles['Normal']))
            
            # General recommendations
            if avg_coverage_overall < 80:
                elements.append(Paragraph(
                    f"• Implement more consistent assessment of learning outcomes across all students (current average coverage: {avg_coverage_overall:.1f}%).",
                    styles['Normal']))
            
            if avg_achievement_overall < 3.5:
                elements.append(Paragraph(
                    f"• Develop strategies to raise overall achievement levels (current average: {avg_achievement_overall:.2f}/5.0).",
                    styles['Normal']))
            
            elements.append(Paragraph(
                f"• Ensure that assessment tasks are aligned with learning outcomes and appropriately weighted.",
                styles['Normal']))
            
            elements.append(Paragraph(
                f"• Consider direct assessment methods for outcomes that are currently only measured indirectly through assessments.",
                styles['Normal']))
        else:
            elements.append(Paragraph("No achievement data has been recorded for any outcomes in this module.", styles['Normal']))
        
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
        
        print(f"\nModule outcome report generated: {report_filename}")
        
    except Exception as e:
        print(f"Error generating report: {e}")
