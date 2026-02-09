# Standard library imports
import os
import csv
import math
from datetime import datetime, timedelta

# Third-party imports
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
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

# Set matplotlib backend
matplotlib.use('Agg')

# Local imports - Database
from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection

# Local imports - Grade management
from university_system.modules.domain.academics.grading.grade_calculation import (
    calculate_student_gpa,
    extract_student_features,
)

def predictive_analytics_menu():
    """Display the predictive analytics menu and handle user choices"""
    while True:
        print("\nPredictive Analytics & Early Warning:")
        print("1. Student Risk Assessment")
        print("2. Performance Prediction Models")
        print("3. Early Warning System")
        print("4. Intervention Recommendations")
        print("5. Success Probability Calculator")
        print("6. Dropout Risk Analysis")
        print("7. Grade Prediction")
        print("8. Trend Forecasting")
        print("9. Generate Risk Report")
        print("10. Return to Grade Menu")
        
        choice = input("Enter your choice (1-10): ")
        
        if choice == '1':
            student_risk_assessment()
        elif choice == '2':
            performance_prediction_models()
        elif choice == '3':
            early_warning_system()
        elif choice == '4':
            intervention_recommendations()
        elif choice == '5':
            success_probability_calculator()
        elif choice == '6':
            dropout_risk_analysis()
        elif choice == '7':
            grade_prediction()
        elif choice == '8':
            trend_forecasting()
        elif choice == '9':
            generate_risk_report()
        elif choice == '10':
            print("Returning to grade menu...")
            break
        else:
            print("Invalid choice. Please try again.")

def identify_at_risk_students():
    """Identify students at risk of academic failure"""
    print("\nIdentify At-Risk Students")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Define at-risk threshold GPA
        threshold = input("Enter at-risk GPA threshold (default is 2.0): ").strip()
        try:
            threshold = float(threshold) if threshold else 2.0
        except ValueError:
            print("Invalid threshold. Using default of 2.0.")
            threshold = 2.0
            
        # Get all students with module grades
        cursor.execute('''
        SELECT DISTINCT s.student_id, s.first_name, s.middle_name, s.last_name, s.course, s.email_address
        FROM students s
        JOIN module_grades mg ON s.student_id = mg.student_id
        ORDER BY s.last_name, s.first_name
        ''')
        
        students = cursor.fetchall()
        
        if not students:
            print("No students with grades found in the database.")
            conn.close()
            return
            
        # Analyze each student
        at_risk_students = []
        
        for student in students:
            student_id, first_name, middle_name, last_name, course, email = student
            
            # Calculate GPA
            gpa, credits, module_grades = calculate_student_gpa(cursor, student_id)
            
            if gpa is not None and gpa < threshold:
                # Find problematic modules
                problematic_modules = []
                
                for module_code, module_name, grade, _ in module_grades:
                    if grade in ['D+', 'D', 'D-', 'F']:
                        problematic_modules.append((module_code, module_name, grade))
                
                # Calculate additional risk factors
                risk_factors = calculate_risk_factors(cursor, student_id)
                
                # Add to at-risk list
                middle_initial = middle_name[0] + ". " if middle_name else ""
                full_name = f"{first_name} {middle_initial}{last_name}"
                
                at_risk_students.append({
                    'id': student_id,
                    'name': full_name,
                    'course': course,
                    'email': email,
                    'gpa': gpa,
                    'problematic_modules': problematic_modules,
                    'risk_factors': risk_factors
                })
        
        # Display results
        if not at_risk_students:
            print(f"No at-risk students found with GPA below {threshold}.")
        else:
            print(f"\nFound {len(at_risk_students)} at-risk students with GPA below {threshold}:")
            
            for i, student in enumerate(at_risk_students):
                print(f"\n{i+1}. {student['name']} (ID: {student['id']})")
                print(f"   Course: {student['course']}")
                print(f"   Email: {student['email']}")
                print(f"   GPA: {student['gpa']:.2f}")
                
                if student['problematic_modules']:
                    print("   Problematic Modules:")
                    for module in student['problematic_modules']:
                        print(f"   - {module[0]} {module[1]}: {module[2]}")
                
                print(f"   Risk Score: {student['risk_factors']['total_score']:.1f}")
                print(f"   Primary Risk Factors: {', '.join(student['risk_factors']['primary_factors'])}")
            
            # Export option
            export = input("\nExport at-risk student list? (y/n): ").strip().lower()
            if export == 'y':
                export_at_risk_students(at_risk_students, threshold)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def calculate_risk_factors(cursor, student_id):
    """Calculate risk factors for a student"""
    risk_score = 0
    risk_factors = []
    
    # 1. Check for failed assessments
    cursor.execute('''
    SELECT COUNT(*) FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ? AND g.letter_grade = 'F'
    ''', (student_id,))
    
    failed_assessments = cursor.fetchone()[0]
    if failed_assessments > 0:
        risk_score += failed_assessments * 10
        risk_factors.append(f"Failed Assessments ({failed_assessments})")
    
    # 2. Check for missed submissions
    cursor.execute('''
    SELECT COUNT(*) as total_assessments,
           COUNT(g.grade_id) as submitted_assessments
    FROM assessments a
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = ?
    JOIN student_modules sm ON a.module_code = sm.module_code AND sm.student_id = ?
    ''', (student_id, student_id))
    
    result = cursor.fetchone()
    if result and result[0] > 0:
        submission_rate = result[1] / result[0]
        if submission_rate < 0.8:
            risk_score += (1 - submission_rate) * 20
            risk_factors.append(f"Low Submission Rate ({submission_rate*100:.1f}%)")
    
    # 3. Check for declining performance
    cursor.execute('''
    SELECT g.score / a.max_points * 100 as percentage, g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date
    ''', (student_id,))
    
    grades_over_time = cursor.fetchall()
    if len(grades_over_time) >= 3:
        recent_avg = np.mean([g[0] for g in grades_over_time[-3:]])
        early_avg = np.mean([g[0] for g in grades_over_time[:3]])
        
        if recent_avg < early_avg - 10:  # 10% decline
            risk_score += 15
            risk_factors.append("Declining Performance")
    
    # 4. Check GPA
    gpa, _, _ = calculate_student_gpa(cursor, student_id)
    if gpa and gpa < 2.5:
        risk_score += (2.5 - gpa) * 20
        risk_factors.append(f"Low GPA ({gpa:.2f})")
    
    return {
        'total_score': risk_score,
        'primary_factors': risk_factors[:3]  # Top 3 factors
    }

def early_warning_system():
    """Implement early warning system for at-risk students"""
    print("\nEarly Warning System")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get recent risk assessments
        cursor.execute('''
        SELECT sra.student_id, s.first_name, s.last_name, s.course, s.email_address,
               sra.risk_score, sra.risk_level, sra.assessment_date
        FROM student_risk_assessment sra
        JOIN students s ON sra.student_id = s.student_id
        WHERE sra.risk_level IN ('High', 'Medium')
        ORDER BY sra.risk_score DESC
        ''')
        
        at_risk_students = cursor.fetchall()
        
        if not at_risk_students:
            print("No students currently flagged as at-risk.")
            print("Run Student Risk Assessment first.")
            conn.close()
            return
        
        print(f"\nEarly Warning Alerts for {len(at_risk_students)} students:")
        print("="*80)
        
        alerts = []
        
        for student in at_risk_students:
            student_id, first_name, last_name, course, email, risk_score, risk_level, assess_date = student
            
            # Generate alert
            alert = generate_early_warning_alert(cursor, student_id, first_name, last_name, 
                                                course, email, risk_score, risk_level)
            alerts.append(alert)
            
            # Display alert
            print(f"\n🚨 {risk_level.upper()} RISK ALERT")
            print(f"Student: {first_name} {last_name} ({student_id})")
            print(f"Course: {course}")
            print(f"Email: {email}")
            print(f"Risk Score: {risk_score}")
            print(f"Recommended Actions:")
            for action in alert['recommended_actions']:
                print(f"  • {action}")
        
        # Export alerts
        export = input("\nExport early warning alerts? (y/n): ").strip().lower()
        if export == 'y':
            export_early_warning_alerts(alerts)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_early_warning_alert(cursor, student_id, first_name, last_name, course, email, risk_score, risk_level):
    """Generate an early warning alert for a student"""
    # Get specific risk factors
    cursor.execute('''
    SELECT rd.factor_id, rf.name, rd.factor_value
    FROM risk_details rd
    JOIN risk_factors rf ON rd.factor_id = rf.factor_id
    JOIN student_risk_assessment sra ON rd.risk_assessment_id = sra.id
    WHERE sra.student_id = ?
    ORDER BY rd.factor_contribution DESC
    ''', (student_id,))
    
    risk_details = cursor.fetchall()
    
    # Generate recommendations based on risk factors
    recommended_actions = []
    
    # Get current GPA
    gpa, _, _ = calculate_student_gpa(cursor, student_id)
    if gpa and gpa < 2.0:
        recommended_actions.append("Schedule immediate academic advising session")
        recommended_actions.append("Consider course load reduction")
    
    # Check for failed assessments
    cursor.execute('''
    SELECT COUNT(*) FROM grades
    WHERE student_id = ? AND letter_grade = 'F'
    ''', (student_id,))
    
    failed_count = cursor.fetchone()[0]
    if failed_count > 0:
        recommended_actions.append("Arrange tutoring for failed subjects")
        recommended_actions.append("Review study strategies and time management")
    
    # Check submission patterns
    cursor.execute('''
    SELECT COUNT(DISTINCT a.assessment_id) as total,
           COUNT(g.grade_id) as submitted
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))
    
    result = cursor.fetchone()
    if result and result[0] > 0:
        submission_rate = result[1] / result[0]
        if submission_rate < 0.8:
            recommended_actions.append("Follow up on missing assignments")
            recommended_actions.append("Check for personal/technical barriers")
    
    # Default recommendations
    if risk_level == 'High':
        recommended_actions.extend([
            "Contact student within 24 hours",
            "Refer to counseling services if needed",
            "Create academic recovery plan"
        ])
    else:
        recommended_actions.extend([
            "Contact student within 3 days",
            "Monitor progress weekly"
        ])
    
    return {
        'student_id': student_id,
        'name': f"{first_name} {last_name}",
        'course': course,
        'email': email,
        'risk_score': risk_score,
        'risk_level': risk_level,
        'recommended_actions': list(set(recommended_actions))  # Remove duplicates
    }

def export_at_risk_students(at_risk_students, threshold):
    """Export at-risk students list"""
    exports_dir = 'performance_reports'
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{exports_dir}/at_risk_students_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Student ID', 'Name', 'Course', 'Email', 'GPA', 'Risk Score', 'Problematic Modules'])
        
        for student in at_risk_students:
            problematic = "; ".join([f"{m[0]} {m[1]}: {m[2]}" for m in student['problematic_modules']])
            
            writer.writerow([
                student['id'],
                student['name'],
                student['course'],
                student['email'],
                f"{student['gpa']:.2f}",
                f"{student['risk_factors']['total_score']:.1f}",
                problematic
            ])
    
    print(f"At-risk student list exported to {filename}")

def export_early_warning_alerts(alerts):
    """Export early warning alerts to file"""
    exports_dir = 'alert_exports'
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{exports_dir}/early_warning_alerts_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Student ID', 'Name', 'Course', 'Email', 'Risk Score', 
                        'Risk Level', 'Recommended Actions'])
        
        for alert in alerts:
            actions = '; '.join(alert['recommended_actions'])
            writer.writerow([
                alert['student_id'],
                alert['name'],
                alert['course'],
                alert['email'],
                alert['risk_score'],
                alert['risk_level'],
                actions
            ])
    
    print(f"Early warning alerts exported to {filename}")

def export_dropout_risk_list(high_risk_students):
    """Export high dropout risk student list"""
    exports_dir = 'dropout_risk_exports'
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{exports_dir}/high_dropout_risk_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Student ID', 'Name', 'Course', 'Email', 'Risk Score'])
        
        for student in high_risk_students:
            writer.writerow([
                student['student_id'],
                student['name'],
                student['course'],
                student['email'],
                f"{student['risk_score']:.1f}"
            ])
    
    print(f"High dropout risk list exported to {filename}")

def build_at_risk_prediction_model(cursor):
    """Build a machine learning model to predict at-risk students"""
    print("\nBuilding At-Risk Student Prediction Model...")
    
    # Collect training data
    training_data = []
    
    cursor.execute('SELECT DISTINCT student_id FROM module_grades')
    students = cursor.fetchall()
    
    for (student_id,) in students:
        features = extract_comprehensive_student_features(cursor, student_id)
        if features:
            # Determine if student is at-risk (GPA < 2.0 or other criteria)
            gpa, _, _ = calculate_student_gpa(cursor, student_id)
            is_at_risk = 1 if (gpa and gpa < 2.0) else 0
            
            features['target'] = is_at_risk
            training_data.append(features)
    
    if len(training_data) < 20:
        print("Insufficient data for model training (need at least 20 students).")
        return
    
    print(f"Training model with {len(training_data)} student records...")
    
    # Prepare data for modeling
    X = []
    y = []
    
    feature_names = ['avg_score', 'submission_rate', 'failed_count', 'assessment_count', 
                    'score_trend', 'consistency_score']
    
    for record in training_data:
        features_vector = [
            record.get('avg_score', 0),
            record.get('submission_rate', 0),
            record.get('failed_count', 0),
            record.get('assessment_count', 0),
            record.get('score_trend', 0),
            record.get('consistency_score', 0)
        ]
        X.append(features_vector)
        y.append(record['target'])
    
    X = np.array(X)
    y = np.array(y)
    
    # Split data and train model
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Use Random Forest for better performance
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Make predictions and evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\nModel Performance:")
    print(f"Accuracy: {accuracy*100:.1f}%")
    print(f"Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Not At-Risk', 'At-Risk']))
    
    # Feature importance
    print(f"\nFeature Importance:")
    for i, feature in enumerate(feature_names):
        importance = model.feature_importances_[i]
        print(f"  {feature}: {importance:.3f}")
    
    return model

def analyze_dropout_risk_factors(cursor):
    """Analyze common dropout risk factors"""
    print("\nDropout Risk Factor Analysis")
    
    # Get students and their risk levels
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.course
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    ''')
    
    students = cursor.fetchall()
    
    if not students:
        print("No student data found.")
        return
    
    # Analyze risk factors
    risk_factor_analysis = {
        'low_gpa': {'count': 0, 'description': 'GPA below 2.0'},
        'failed_modules': {'count': 0, 'description': 'Failed one or more modules'},
        'low_submission': {'count': 0, 'description': 'Submission rate below 70%'},
        'declining_performance': {'count': 0, 'description': 'Performance declining over time'},
        'multiple_factors': {'count': 0, 'description': 'Multiple risk factors present'}
    }
    
    total_students = len(students)
    
    for student_id, course in students:
        student_risk_factors = []
        
        # Check GPA
        gpa, _, _ = calculate_student_gpa(cursor, student_id)
        if gpa and gpa < 2.0:
            risk_factor_analysis['low_gpa']['count'] += 1
            student_risk_factors.append('low_gpa')
        
        # Check failed modules
        cursor.execute('''
        SELECT COUNT(*) FROM module_grades
        WHERE student_id = ? AND final_grade = 'F'
        ''', (student_id,))
        
        failed_count = cursor.fetchone()[0]
        if failed_count > 0:
            risk_factor_analysis['failed_modules']['count'] += 1
            student_risk_factors.append('failed_modules')
        
        # Check submission rate
        cursor.execute('''
        SELECT COUNT(DISTINCT a.assessment_id) as total,
               COUNT(g.grade_id) as submitted
        FROM assessments a
        JOIN student_modules sm ON a.module_code = sm.module_code
        LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = sm.student_id
        WHERE sm.student_id = ?
        ''', (student_id,))
        
        result = cursor.fetchone()
        if result and result[0] > 0:
            submission_rate = result[1] / result[0]
            if submission_rate < 0.7:
                risk_factor_analysis['low_submission']['count'] += 1
                student_risk_factors.append('low_submission')
        
        # Check performance trend
        cursor.execute('''
        SELECT g.score / a.max_points * 100
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        WHERE g.student_id = ?
        ORDER BY g.submission_date
        ''', (student_id,))
        
        scores = [r[0] for r in cursor.fetchall()]
        if len(scores) >= 4:
            recent_avg = np.mean(scores[-3:])
            early_avg = np.mean(scores[:3])
            if recent_avg < early_avg - 10:  # 10% decline
                risk_factor_analysis['declining_performance']['count'] += 1
                student_risk_factors.append('declining_performance')
        
        # Check for multiple factors
        if len(student_risk_factors) >= 2:
            risk_factor_analysis['multiple_factors']['count'] += 1
    
    # Display results
    print(f"\nDropout Risk Factor Analysis ({total_students} students):")
    print("="*80)
    print(f"{'Risk Factor':<30} {'Count':<10} {'Percentage':<12} {'Description'}")
    print("-"*80)
    
    for factor, data in risk_factor_analysis.items():
        count = data['count']
        percentage = (count / total_students) * 100
        print(f"{factor.replace('_', ' ').title():<30} {count:<10} {percentage:<12.1f}% {data['description']}")
    
    # Recommendations based on analysis
    print(f"\nRecommendations:")
    
    if risk_factor_analysis['low_gpa']['count'] > total_students * 0.15:
        print("• High number of students with low GPA - review academic support services")
    
    if risk_factor_analysis['low_submission']['count'] > total_students * 0.20:
        print("• Significant submission issues - investigate barriers to assessment completion")
    
    if risk_factor_analysis['declining_performance']['count'] > total_students * 0.10:
        print("• Many students showing performance decline - implement early intervention")
    
    if risk_factor_analysis['multiple_factors']['count'] > total_students * 0.05:
        print("• Students with multiple risk factors need intensive support")

def build_dropout_prediction_model(cursor):
    """Build a predictive model for dropout risk"""
    print("\nBuilding Dropout Prediction Model...")
    
    # This would use comprehensive student data to predict dropout likelihood
    # Similar to the at-risk model but focused specifically on dropout prediction
    print("Dropout prediction model - would analyze:")
    print("• Academic performance trends")
    print("• Engagement patterns")
    print("• Historical dropout patterns")
    print("• Demographic factors")
    print("• Financial indicators (if available)")

def generate_dropout_interventions(cursor):
    """Generate specific interventions for dropout prevention"""
    print("\nDropout Prevention Interventions")
    
    # Get high dropout risk students
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course, s.email_address
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    ''')
    
    students = cursor.fetchall()
    
    high_risk_interventions = []
    
    for student_id, first_name, last_name, course, email in students:
        risk_score = calculate_dropout_risk_score(cursor, student_id)
        
        if risk_score >= 70:  # High dropout risk
            interventions = generate_dropout_intervention_plan(cursor, student_id, 
                                                             first_name, last_name, course, email)
            high_risk_interventions.append(interventions)
    
    if not high_risk_interventions:
        print("No high dropout risk students identified.")
        return
    
    # Display intervention plans
    print(f"\nDropout Prevention Plans ({len(high_risk_interventions)} students):")
    print("="*80)
    
    for intervention in high_risk_interventions:
        print(f"\nStudent: {intervention['name']} ({intervention['course']})")
        print(f"Risk Score: {intervention['risk_score']}")
        print(f"Priority Interventions:")
        
        for i, action in enumerate(intervention['interventions'], 1):
            print(f"  {i}. {action['intervention']} - {action['timeline']}")
            print(f"     Rationale: {action['rationale']}")

def generate_dropout_intervention_plan(cursor, student_id, first_name, last_name, course, email):
    """Generate a specific dropout intervention plan"""
    risk_score = calculate_dropout_risk_score(cursor, student_id)
    interventions = []
    
    # Get specific risk factors
    gpa, _, _ = calculate_student_gpa(cursor, student_id)
    
    # Academic interventions
    if gpa and gpa < 2.0:
        interventions.append({
            'intervention': 'Emergency Academic Advising',
            'timeline': 'Within 48 hours',
            'rationale': f'GPA of {gpa:.2f} indicates severe academic distress'
        })
        
        interventions.append({
            'intervention': 'Intensive Tutoring Program',
            'timeline': 'Begin immediately',
            'rationale': 'Low GPA requires immediate academic support'
        })
    
    # Engagement interventions
    cursor.execute('''
    SELECT COUNT(DISTINCT a.assessment_id) as total,
           COUNT(g.grade_id) as submitted
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))
    
    result = cursor.fetchone()
    if result and result[0] > 0:
        submission_rate = result[1] / result[0]
        if submission_rate < 0.5:
            interventions.append({
                'intervention': 'Personal Outreach and Barrier Assessment',
                'timeline': 'Within 24 hours',
                'rationale': f'Very low submission rate ({submission_rate*100:.1f}%) suggests disengagement'
            })
    
    # Financial/Personal support
    if risk_score >= 80:
        interventions.append({
            'intervention': 'Comprehensive Support Services Referral',
            'timeline': 'Within 1 week',
            'rationale': 'Extremely high risk requires holistic support approach'
        })
    
    # Default interventions for all high-risk students
    interventions.extend([
        {
            'intervention': 'Weekly Check-in Schedule',
            'timeline': 'Begin next week',
            'rationale': 'Regular monitoring prevents further deterioration'
        },
        {
            'intervention': 'Peer Mentor Assignment',
            'timeline': 'Within 1 week',
            'rationale': 'Peer support can improve engagement and retention'
        }
    ])
    
    return {
        'student_id': student_id,
        'name': f"{first_name} {last_name}",
        'course': course,
        'email': email,
        'risk_score': risk_score,
        'interventions': interventions
    }

def identify_high_dropout_risk(cursor):
    """Identify students at high risk of dropping out"""
    print("\nIdentifying High Dropout Risk Students...")
    
    # Get all active students
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course, s.email_address
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    ''')
    
    students = cursor.fetchall()
    
    if not students:
        print("No student data found.")
        return
    
    high_risk_students = []
    
    for student_id, first_name, last_name, course, email in students:
        risk_score = calculate_dropout_risk_score(cursor, student_id)
        
        if risk_score >= 70:  # High risk threshold
            high_risk_students.append({
                'student_id': student_id,
                'name': f"{first_name} {last_name}",
                'course': course,
                'email': email,
                'risk_score': risk_score
            })
    
    # Sort by risk score
    high_risk_students.sort(key=lambda x: x['risk_score'], reverse=True)
    
    print(f"\nHigh Dropout Risk Students ({len(high_risk_students)}):")
    print("="*80)
    
    if not high_risk_students:
        print("No students identified as high dropout risk.")
    else:
        print(f"{'Name':<25} {'Course':<10} {'Risk Score':<12} {'Email'}")
        print("-"*80)
        
        for student in high_risk_students:
            print(f"{student['name']:<25} {student['course']:<10} {student['risk_score']:<12.1f} {student['email']}")
        
        # Export option
        export = input("\nExport high-risk student list? (y/n): ").strip().lower()
        if export == 'y':
            export_dropout_risk_list(high_risk_students)

def calculate_dropout_risk_score(cursor, student_id):
    """Calculate dropout risk score for a student"""
    risk_score = 0
    
    # Factor 1: Low GPA (40% weight)
    gpa, _, _ = calculate_student_gpa(cursor, student_id)
    if gpa:
        if gpa < 1.5:
            risk_score += 40
        elif gpa < 2.0:
            risk_score += 30
        elif gpa < 2.5:
            risk_score += 15
    else:
        risk_score += 20  # No GPA data is also risky
    
    # Factor 2: Failed modules (25% weight)
    cursor.execute('''
    SELECT COUNT(*) FROM module_grades
    WHERE student_id = ? AND final_grade = 'F'
    ''', (student_id,))
    
    failed_modules = cursor.fetchone()[0]
    if failed_modules > 0:
        risk_score += min(failed_modules * 8, 25)
    
    # Factor 3: Low submission rate (20% weight)
    cursor.execute('''
    SELECT COUNT(DISTINCT a.assessment_id) as total,
           COUNT(g.grade_id) as submitted
    FROM assessments a
    JOIN student_modules sm ON a.module_code = sm.module_code
    LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = sm.student_id
    WHERE sm.student_id = ?
    ''', (student_id,))
    
    result = cursor.fetchone()
    if result and result[0] > 0:
        submission_rate = result[1] / result[0]
        if submission_rate < 0.5:
            risk_score += 20
        elif submission_rate < 0.7:
            risk_score += 12
        elif submission_rate < 0.85:
            risk_score += 5
    
    # Factor 4: Declining performance (15% weight)
    cursor.execute('''
    SELECT g.score / a.max_points * 100, g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date
    ''', (student_id,))
    
    grades_over_time = cursor.fetchall()
    if len(grades_over_time) >= 4:
        recent_scores = [g[0] for g in grades_over_time[-3:]]
        early_scores = [g[0] for g in grades_over_time[:3]]
        
        recent_avg = np.mean(recent_scores)
        early_avg = np.mean(early_scores)
        
        decline = early_avg - recent_avg
        if decline > 20:
            risk_score += 15
        elif decline > 10:
            risk_score += 8
        elif decline > 5:
            risk_score += 3
    
    return min(risk_score, 100)  # Cap at 100

def generate_risk_report():
    """Generate comprehensive risk assessment report"""
    print("\nGenerating Comprehensive Risk Assessment Report...")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Collect comprehensive risk data
        risk_data = collect_comprehensive_risk_data(cursor)
        
        if not risk_data:
            print("Insufficient data for risk report generation.")
            conn.close()
            return
        
        # Generate the report
        generate_comprehensive_risk_report(risk_data)
        
        print("Comprehensive risk assessment report generated successfully!")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def collect_comprehensive_risk_data(cursor):
    """Collect comprehensive risk assessment data"""
    risk_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'students': [],
        'summary_stats': {},
        'risk_factors': {},
        'recommendations': []
    }
    
    # Get all students with grades
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course, s.email_address
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    ORDER BY s.last_name, s.first_name
    ''')
    
    students = cursor.fetchall()
    
    risk_levels = {'High': 0, 'Medium': 0, 'Low': 0, 'Minimal': 0}
    
    for student_id, first_name, last_name, course, email in students:
        # Calculate comprehensive risk assessment
        student_risk = assess_comprehensive_student_risk(cursor, student_id, first_name, last_name, course, email)
        if student_risk:
            risk_data['students'].append(student_risk)
            risk_levels[student_risk['risk_level']] += 1
    
    # Calculate summary statistics
    if risk_data['students']:
        risk_scores = [s['risk_score'] for s in risk_data['students']]
        risk_data['summary_stats'] = {
            'total_students': len(risk_data['students']),
            'avg_risk_score': np.mean(risk_scores),
            'median_risk_score': np.median(risk_scores),
            'max_risk_score': max(risk_scores),
            'min_risk_score': min(risk_scores),
            'risk_distribution': risk_levels
        }
    
    # Generate system-wide recommendations
    try:
        from university_system.modules.domain.academics.grading import generate_system_recommendations
        risk_data['recommendations'] = generate_system_recommendations(risk_data)
    except Exception as e:
        risk_data['recommendations'] = [f"(recommendations unavailable: {e})"]
    
    return risk_data

def generate_comprehensive_risk_report(risk_data):
    """Generate a comprehensive risk assessment report"""

    # --- Safe defaults for summary stats to avoid KeyError when data is sparse ---
    summary_stats = (risk_data.get('summary_stats') or {})
    students = risk_data.get('students') or []
    total_students = summary_stats.get('total_students', len(students))
    avg_risk = float(summary_stats.get('avg_risk_score', 0) or 0)
    median_risk = float(summary_stats.get('median_risk_score', 0) or 0)
    max_risk = float(summary_stats.get('max_risk_score', 0) or 0)
    min_risk = float(summary_stats.get('min_risk_score', 0) or 0)
    risk_dist = summary_stats.get('risk_distribution') or {'High': 0, 'Medium': 0, 'Low': 0}

    # Compute safe percentages for risk distribution (avoid division by zero)
    high_cnt = int(risk_dist.get('High', 0) or 0)
    med_cnt = int(risk_dist.get('Medium', 0) or 0)
    low_cnt = int(risk_dist.get('Low', 0) or 0)
    denom = total_students if total_students else (high_cnt + med_cnt + low_cnt)
    pct_high = (high_cnt / denom * 100.0) if denom else 0.0
    pct_med = (med_cnt / denom * 100.0) if denom else 0.0
    pct_low = (low_cnt / denom * 100.0) if denom else 0.0
    # Normalize risk_dist keys
    for k in ('High','Medium','Low'):
        risk_dist.setdefault(k, 0)
    # Ensure recommendations list exists
    if 'recommendations' not in risk_data or risk_data['recommendations'] is None:
        risk_data['recommendations'] = []
    # Create reports directory
    reports_dir = 'risk_reports'
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Generate PDF report
    report_filename = f"{reports_dir}/comprehensive_risk_report_{timestamp}.pdf"
    
    doc = SimpleDocTemplate(report_filename, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        alignment=1,
        spaceAfter=12
    )
    elements.append(Paragraph("Comprehensive Risk Assessment Report", title_style))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Executive Summary
    elements.append(Paragraph("Executive Summary", styles['Heading2']))
    
    summary_stats = risk_data['summary_stats']
    risk_dist = risk_dist
    
    summary_data = [
        ['Total Students Assessed:', str(total_students)],
        ['Average Risk Score:', f"{avg_risk:.1f}"],
        ['High Risk Students:', f"{high_cnt} ({pct_high:.1f}%)"],
        ['Medium Risk Students:', f"{med_cnt} ({pct_med:.1f}%)"],
        ['Low Risk Students:', f"{low_cnt} ({pct_low:.1f}%)"]
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 300])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (1, -1), 6),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # High Risk Students Details
    high_risk_students = [s for s in risk_data['students'] if s['risk_level'] == 'High']
    
    if high_risk_students:
        elements.append(Paragraph("High Risk Students (Immediate Action Required)", styles['Heading2']))
        
        high_risk_data = [['Name', 'Course', 'Risk Score', 'Primary Risk Factors']]
        
        for student in high_risk_students:
            factors = ', '.join(student['risk_factors'].keys())
            high_risk_data.append([
                student['name'],
                student['course'],
                str(student['risk_score']),
                factors
            ])
        
        high_risk_table = Table(high_risk_data, colWidths=[120, 80, 80, 220])
        high_risk_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(high_risk_table)
        elements.append(Spacer(1, 20))
    
    # Recommendations
    elements.append(Paragraph("System-Wide Recommendations", styles['Heading2']))
    
    recommendations = risk_data.get('recommendations', [])
    for i, rec in enumerate(recommendations, 1):
        elements.append(Paragraph(f"{i}. {rec}", styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    # Also create CSV export
    csv_filename = f"{reports_dir}/risk_assessment_data_{timestamp}.csv"
    
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Student ID', 'Name', 'Course', 'Email', 'Risk Score', 'Risk Level', 'GPA', 'Risk Factors'])
        
        for student in risk_data['students']:
            factors = '; '.join([f"{k}: {v}" for k, v in student['risk_factors'].items()])
            writer.writerow([
                student['student_id'],
                student['name'],
                student['course'],
                student['email'],
                student['risk_score'],
                student['risk_level'],
                f"{student['gpa']:.2f}" if student['gpa'] else "N/A",
                factors
            ])
    
    print(f"Risk assessment report saved: {report_filename}")
    print(f"Risk assessment data exported: {csv_filename}")
