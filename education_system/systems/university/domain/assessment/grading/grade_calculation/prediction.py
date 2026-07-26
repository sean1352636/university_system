import numpy as np
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.assessment.grading.grade_calculation.conversions import percentage_to_letter
from education_system.systems.university.domain.assessment.grading.grade_calculation.utils import (
    select_student,
    select_assessment,
    calculate_trend_slope,
    export_batch_predictions,
)
from education_system.systems.university.domain.assessment.grading.grade_calculation.gpa import calculate_student_gpa


def extract_student_features(cursor, student_id):
    """Extract features for a student for prediction models"""
    try:
        # Get assessment scores
        cursor.execute('''
        SELECT g.score / a.max_points * 100 as percentage
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        WHERE g.student_id = ?
        ''', (student_id,))

        scores = [row[0] for row in cursor.fetchall()]

        if not scores:
            return None

        # Calculate basic features
        avg_score = np.mean(scores)
        assessment_count = len(scores)
        failed_count = sum(1 for score in scores if score < 60)

        # Get total possible assessments for submission rate
        cursor.execute('''
        SELECT COUNT(DISTINCT a.assessment_id)
        FROM assessments a
        JOIN student_modules sm ON a.module_code = sm.module_code
        WHERE sm.student_id = ?
        ''', (student_id,))

        total_assessments = cursor.fetchone()[0]
        submission_rate = assessment_count / total_assessments if total_assessments > 0 else 0

        return {
            'avg_score': avg_score,
            'submission_rate': submission_rate,
            'assessment_count': assessment_count,
            'failed_count': failed_count
        }

    except sqlite3.Error as e:
        print(f"Error extracting features for student {student_id}: {e}")
        return None


def batch_grade_predictions(cursor):
    """Perform batch grade predictions for multiple students"""
    print("\nBatch Grade Predictions")

    print("\nPrediction Options:")
    print("1. Predict next assessment grades for all students")
    print("2. Predict final module grades for specific module")
    print("3. Predict end-of-term GPAs")

    choice = input("Enter your choice (1-3): ").strip()

    if choice == '1':
        batch_predict_next_assessments(cursor)
    elif choice == '2':
        batch_predict_module_grades(cursor)
    elif choice == '3':
        batch_predict_end_term_gpas(cursor)
    else:
        print("Invalid choice.")


def batch_predict_next_assessments(cursor):
    """Predict next assessment grades for all students"""
    print("\nBatch Next Assessment Predictions")

    # Get all students with sufficient assessment history
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course
    FROM students s
    JOIN grades g ON s.student_id = g.student_id
    GROUP BY s.student_id
    HAVING COUNT(g.grade_id) >= 3
    ORDER BY s.last_name, s.first_name
    ''')

    students = cursor.fetchall()

    if not students:
        print("No students with sufficient assessment history found.")
        return

    print(f"Generating predictions for {len(students)} students...")

    predictions = []

    for student_id, first_name, last_name, course in students:
        prediction = predict_student_next_grade(cursor, student_id)
        if prediction:
            predictions.append({
                'student_id': student_id,
                'name': f"{first_name} {last_name}",
                'course': course,
                'predicted_score': prediction['score'],
                'predicted_grade': prediction['grade'],
                'confidence': prediction['confidence']
            })

    # Display results
    print("\nNext Assessment Grade Predictions:")
    print("="*90)
    print(f"{'Name':<25} {'Course':<10} {'Predicted Score':<15} {'Grade':<8} {'Confidence'}")
    print("-"*90)

    for pred in predictions:
        print(f"{pred['name']:<25} {pred['course']:<10} {pred['predicted_score']:<15.1f}% "
              f"{pred['predicted_grade']:<8} {pred['confidence']}")

    # Export option
    export = input("\nExport predictions to CSV? (y/n): ").strip().lower()
    if export == 'y':
        export_batch_predictions(predictions, "next_assessment_predictions")


def predict_student_next_grade(cursor, student_id):
    """Predict next grade for a specific student"""
    # Get recent assessment history
    cursor.execute('''
    SELECT g.score / a.max_points * 100 as percentage
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date DESC
    LIMIT 5
    ''', (student_id,))

    recent_scores = [r[0] for r in cursor.fetchall()]

    if len(recent_scores) < 3:
        return None

    # Simple prediction based on moving average and trend
    moving_avg = np.mean(recent_scores)

    # Calculate trend
    x = list(range(len(recent_scores)))
    trend_slope = np.polyfit(x, recent_scores[::-1], 1)[0]  # Reverse for chronological order

    # Predict next score
    predicted_score = moving_avg + trend_slope
    predicted_score = max(0, min(100, predicted_score))  # Bound between 0-100

    # Convert to letter grade
    predicted_grade = percentage_to_letter(predicted_score)

    # Calculate confidence based on consistency
    score_std = np.std(recent_scores)
    if score_std < 5:
        confidence = "High"
    elif score_std < 10:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        'score': predicted_score,
        'grade': predicted_grade,
        'confidence': confidence
    }


def batch_predict_module_grades(cursor):
    """Predict final module grades for a specific module"""
    print("\nBatch Module Grade Predictions")

    # Get available modules
    cursor.execute('''
    SELECT DISTINCT m.module_code, m.module_name
    FROM modules m
    JOIN student_modules sm ON m.module_code = sm.module_code
    ORDER BY m.module_name
    ''')

    modules = cursor.fetchall()

    if not modules:
        print("No modules found.")
        return

    print("\nAvailable Modules:")
    for i, (code, name) in enumerate(modules):
        print(f"{i+1}. {code} - {name}")

    choice = input("Enter module number: ").strip()

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(modules):
            module_code, module_name = modules[idx]
        else:
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    print(f"\nPredicting final grades for module: {module_code} - {module_name}")

    # Get students enrolled in this module
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name
    FROM students s
    JOIN student_modules sm ON s.student_id = sm.student_id
    WHERE sm.module_code = ?
    ORDER BY s.last_name, s.first_name
    ''', (module_code,))

    students = cursor.fetchall()

    if not students:
        print("No students found for this module.")
        return

    predictions = []

    for student_id, first_name, last_name in students:
        prediction = predict_module_final_grade(cursor, student_id, module_code)
        if prediction:
            predictions.append({
                'student_id': student_id,
                'name': f"{first_name} {last_name}",
                'predicted_score': prediction['score'],
                'predicted_grade': prediction['grade'],
                'current_progress': prediction['progress']
            })

    # Display results
    print(f"\nFinal Grade Predictions for {module_code}:")
    print("="*80)
    print(f"{'Name':<30} {'Current Progress':<15} {'Predicted Score':<15} {'Grade'}")
    print("-"*80)

    for pred in predictions:
        print(f"{pred['name']:<30} {pred['current_progress']:<15.1f}% "
              f"{pred['predicted_score']:<15.1f}% {pred['predicted_grade']}")


def predict_module_final_grade(cursor, student_id, module_code):
    """Predict final module grade for a student"""
    # Get all assessments for this module
    cursor.execute('''
    SELECT assessment_id, weight, max_points
    FROM assessments
    WHERE module_code = ?
    ''', (module_code,))

    assessments = cursor.fetchall()

    if not assessments:
        return None

    # Get current grades
    total_weighted_score = 0
    total_weight_completed = 0

    for assessment_id, weight, max_points in assessments:
        cursor.execute('''
        SELECT score
        FROM grades
        WHERE student_id = ? AND assessment_id = ?
        ''', (student_id, assessment_id))

        grade = cursor.fetchone()

        if grade:
            # Calculate percentage score for this assessment
            percentage = (grade[0] / max_points) * 100
            weighted_score = percentage * (weight / 100)

            total_weighted_score += weighted_score
            total_weight_completed += weight

    if total_weight_completed == 0:
        return None

    # Calculate current progress
    current_progress = total_weighted_score

    # Predict final score based on current performance
    if total_weight_completed < 100:
        # Assume remaining assessments will perform at current average
        avg_performance = total_weighted_score / (total_weight_completed / 100)
        remaining_weight = 100 - total_weight_completed
        predicted_remaining = avg_performance * (remaining_weight / 100)
        predicted_final = total_weighted_score + predicted_remaining
    else:
        predicted_final = total_weighted_score

    predicted_final = max(0, min(100, predicted_final))
    predicted_grade = percentage_to_letter(predicted_final)

    return {
        'score': predicted_final,
        'grade': predicted_grade,
        'progress': current_progress
    }


def batch_predict_end_term_gpas(cursor):
    """Predict end-of-term GPAs for all students"""
    print("\nBatch End-of-Term GPA Predictions")

    # Get all students with current grades
    cursor.execute('''
    SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course
    FROM students s
    JOIN module_grades mg ON s.student_id = mg.student_id
    ORDER BY s.last_name, s.first_name
    ''')

    students = cursor.fetchall()

    if not students:
        print("No students with grades found.")
        return

    print(f"Predicting end-of-term GPAs for {len(students)} students...")

    predictions = []

    for student_id, first_name, last_name, course in students:
        prediction = predict_end_term_gpa(cursor, student_id)
        if prediction:
            predictions.append({
                'student_id': student_id,
                'name': f"{first_name} {last_name}",
                'course': course,
                'current_gpa': prediction['current_gpa'],
                'predicted_gpa': prediction['predicted_gpa'],
                'trend': prediction['trend']
            })

    # Sort by predicted GPA (lowest first for attention)
    predictions.sort(key=lambda x: x['predicted_gpa'])

    # Display results
    print("\nEnd-of-Term GPA Predictions:")
    print("="*80)
    print(f"{'Name':<25} {'Course':<10} {'Current GPA':<12} {'Predicted GPA':<15} {'Trend'}")
    print("-"*80)

    for pred in predictions:
        trend_symbol = "up" if pred['trend'] > 0.1 else "down" if pred['trend'] < -0.1 else "stable"
        print(f"{pred['name']:<25} {pred['course']:<10} {pred['current_gpa']:<12.2f} "
              f"{pred['predicted_gpa']:<15.2f} {trend_symbol}")

    # Identify students needing attention
    at_risk_predictions = [p for p in predictions if p['predicted_gpa'] < 2.0]

    if at_risk_predictions:
        print(f"\nStudents predicted to have GPA < 2.0 ({len(at_risk_predictions)}):")
        for pred in at_risk_predictions:
            print(f"   - {pred['name']} ({pred['course']}): {pred['predicted_gpa']:.2f}")


def predict_end_term_gpa(cursor, student_id):
    """Predict end-of-term GPA for a student"""
    # Get current GPA
    current_gpa, credits, _ = calculate_student_gpa(cursor, student_id)

    if not current_gpa:
        return None

    # Get recent performance trend
    cursor.execute('''
    SELECT g.score / a.max_points * 100, g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date DESC
    LIMIT 10
    ''', (student_id,))

    recent_scores = cursor.fetchall()

    if len(recent_scores) < 5:
        # Not enough data for trend analysis
        return {
            'current_gpa': current_gpa,
            'predicted_gpa': current_gpa,
            'trend': 0
        }

    # Calculate performance trend
    scores = [score for score, _ in recent_scores]
    x = list(range(len(scores)))
    trend_slope = np.polyfit(x, scores[::-1], 1)[0]  # Reverse for chronological order

    # Convert trend to GPA change (simplified)
    gpa_trend = trend_slope / 25  # Rough conversion from percentage to GPA points

    # Predict future GPA
    predicted_gpa = current_gpa + gpa_trend
    predicted_gpa = max(0, min(4.3, predicted_gpa))  # Bound within GPA range

    return {
        'current_gpa': current_gpa,
        'predicted_gpa': predicted_gpa,
        'trend': gpa_trend
    }


def forecast_assessment_performance(cursor):
    """Forecast assessment performance trends"""
    print("\nAssessment Performance Forecasting")

    # Get assessment types with historical data
    cursor.execute('''
    SELECT a.assessment_type,
           COUNT(DISTINCT strftime('%Y-%m', g.submission_date)) as months_with_data
    FROM assessments a
    JOIN grades g ON a.assessment_id = g.assessment_id
    WHERE g.submission_date IS NOT NULL
    GROUP BY a.assessment_type
    HAVING months_with_data >= 6
    ORDER BY a.assessment_type
    ''')

    assessment_types = cursor.fetchall()

    if not assessment_types:
        print("No assessment types with sufficient historical data found.")
        return

    print(f"\nForecasting performance trends for {len(assessment_types)} assessment types...")

    for assess_type, months_count in assessment_types:
        forecast_assessment_type_performance(cursor, assess_type)


def forecast_assessment_type_performance(cursor, assess_type):
    """Forecast performance for a specific assessment type"""
    print(f"\n--- {assess_type} Assessment Forecast ---")

    # Get monthly performance data
    cursor.execute('''
    SELECT strftime('%Y-%m', g.submission_date) as month,
           AVG(g.score / a.max_points * 100) as avg_percentage,
           COUNT(*) as grade_count
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE a.assessment_type = ? AND g.submission_date IS NOT NULL
    GROUP BY strftime('%Y-%m', g.submission_date)
    HAVING grade_count >= 5
    ORDER BY month
    ''', (assess_type,))

    monthly_data = cursor.fetchall()

    if len(monthly_data) < 6:
        print("Insufficient data for forecasting")
        return

    # Analyze and forecast
    months = [data[0] for data in monthly_data]
    averages = [data[1] for data in monthly_data]

    # Calculate trend
    x = np.arange(len(averages))
    trend_slope = np.polyfit(x, averages, 1)[0]

    # Project forward
    future_performance = averages[-1] + (trend_slope * 3)
    future_performance = max(0, min(100, future_performance))

    print(f"Current Average: {np.mean(averages[-3:]):.1f}%")
    print(f"Trend: {trend_slope:+.2f}% per month")
    print(f"3-Month Projection: {future_performance:.1f}%")

    if trend_slope > 1:
        print("Status: Improving performance expected")
    elif trend_slope < -1:
        print("Status: Declining performance expected")
    else:
        print("Status: Stable performance expected")


def build_assessment_prediction_model(cursor):
    """Build a model to predict assessment performance"""
    print("\nBuilding Assessment Performance Prediction Model...")

    # This would predict likely assessment scores based on historical performance
    print("Assessment prediction model building - would use historical performance patterns")
    print("Features would include: recent scores, assessment type, time since last assessment, etc.")


def build_gpa_prediction_model(cursor):
    """Build a simple GPA prediction model"""
    print("\nBuilding GPA Prediction Model...")

    # Collect training data
    training_data = []

    cursor.execute('SELECT DISTINCT student_id FROM module_grades')
    students = cursor.fetchall()

    for (student_id,) in students:
        # Get student features
        features = extract_student_features(cursor, student_id)
        if features:
            gpa, _, _ = calculate_student_gpa(cursor, student_id)
            if gpa is not None:
                features['target_gpa'] = gpa
                training_data.append(features)

    if len(training_data) < 10:
        print("Insufficient data for model training (need at least 10 students).")
        return

    print(f"Training model with {len(training_data)} student records...")

    # Prepare data for modeling
    X = []
    y = []

    feature_names = ['avg_score', 'submission_rate', 'assessment_count', 'failed_count']

    for record in training_data:
        features_vector = [
            record.get('avg_score', 0),
            record.get('submission_rate', 0),
            record.get('assessment_count', 0),
            record.get('failed_count', 0)
        ]
        X.append(features_vector)
        y.append(record['target_gpa'])

    X = np.array(X)
    y = np.array(y)

    # Simple linear regression model
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_squared_error, r2_score

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train model
    model = LinearRegression()
    model.fit(X_train, y_train)

    # Make predictions
    y_pred = model.predict(X_test)

    # Evaluate model
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print("\nModel Performance:")
    print(f"Mean Squared Error: {mse:.3f}")
    print(f"R2 Score: {r2:.3f}")
    print(f"Model Accuracy: {r2*100:.1f}%")

    # Feature importance
    print("\nFeature Importance:")
    for i, feature in enumerate(feature_names):
        importance = abs(model.coef_[i])
        print(f"  {feature}: {importance:.3f}")

    # Make prediction for a new student
    predict_new = input("\nPredict GPA for a specific student? (y/n): ").strip().lower()
    if predict_new == 'y':
        student_id = select_student(cursor)
        if student_id:
            predict_student_gpa(cursor, model, student_id, feature_names)


def predict_student_gpa(cursor, model, student_id, feature_names):
    """Predict GPA for a specific student"""
    # Get student info
    cursor.execute('''
    SELECT first_name, last_name
    FROM students
    WHERE student_id = ?
    ''', (student_id,))

    student = cursor.fetchone()
    if not student:
        print("Student not found.")
        return

    first_name, last_name = student

    # Extract features
    features = extract_student_features(cursor, student_id)
    if not features:
        print("No data available for this student.")
        return

    # Prepare feature vector
    X = np.array([[
        features.get('avg_score', 0),
        features.get('submission_rate', 0),
        features.get('assessment_count', 0),
        features.get('failed_count', 0)
    ]])

    # Make prediction
    predicted_gpa = model.predict(X)[0]

    # Get actual GPA if available
    actual_gpa, _, _ = calculate_student_gpa(cursor, student_id)

    print(f"\nGPA Prediction for {first_name} {last_name}:")
    print(f"Predicted GPA: {predicted_gpa:.2f}")
    if actual_gpa:
        print(f"Actual GPA: {actual_gpa:.2f}")
        print(f"Prediction Error: {abs(predicted_gpa - actual_gpa):.2f}")

    print("\nStudent Features:")
    print(f"  Average Score: {features['avg_score']:.1f}%")
    print(f"  Submission Rate: {features['submission_rate']*100:.1f}%")
    print(f"  Assessments Taken: {features['assessment_count']}")
    print(f"  Failed Assessments: {features['failed_count']}")


def predict_next_assessment_grade(cursor):
    """Predict a student's next assessment grade"""
    print("\nNext Assessment Grade Prediction")

    student_id = select_student(cursor)
    if not student_id:
        return

    # Get student info
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

    # Get student's assessment history
    cursor.execute('''
    SELECT g.score / a.max_points * 100 as percentage,
           a.assessment_type,
           g.submission_date
    FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.student_id = ?
    ORDER BY g.submission_date DESC
    ''', (student_id,))

    assessment_history = cursor.fetchall()

    if len(assessment_history) < 3:
        print("Insufficient assessment history for prediction (need at least 3 assessments).")
        return

    # Calculate prediction based on trend analysis
    recent_scores = [score for score, _, _ in assessment_history[:5]]  # Last 5 assessments

    # Simple trend-based prediction
    if len(recent_scores) >= 3:
        # Calculate moving average
        moving_avg = np.mean(recent_scores)

        # Calculate trend
        x = list(range(len(recent_scores)))
        trend_slope = np.polyfit(x, recent_scores[::-1], 1)[0]  # Reverse for chronological order

        # Predict next grade
        predicted_score = moving_avg + trend_slope
        predicted_score = max(0, min(100, predicted_score))  # Bound between 0-100

        # Convert to letter grade
        predicted_letter = percentage_to_letter(predicted_score)

        print(f"\nGrade Prediction for {first_name} {last_name}:")
        print(f"Recent Performance Average: {moving_avg:.1f}%")
        print(f"Performance Trend: {trend_slope:+.1f}% per assessment")
        print(f"Predicted Next Score: {predicted_score:.1f}%")
        print(f"Predicted Letter Grade: {predicted_letter}")

        # Confidence assessment
        score_std = np.std(recent_scores)
        if score_std < 5:
            confidence = "High"
        elif score_std < 10:
            confidence = "Medium"
        else:
            confidence = "Low"

        print(f"Prediction Confidence: {confidence} (sigma = {score_std:.1f}%)")

        # Performance by assessment type
        type_performance = {}
        for score, assess_type, _ in assessment_history:
            if assess_type not in type_performance:
                type_performance[assess_type] = []
            type_performance[assess_type].append(score)

        print("\nPerformance by Assessment Type:")
        for assess_type, scores in type_performance.items():
            avg_score = np.mean(scores)
            print(f"  {assess_type}: {avg_score:.1f}% (n={len(scores)})")


def predict_final_module_grade(cursor):
    """Interactive wrapper to predict a student's final module grade"""
    print("\nPredict Final Module Grade")

    # 1) pick student
    student_id = select_student(cursor)
    if not student_id:
        print("No student selected.")
        return

    # 2) list only this student's modules
    cursor.execute("""
    SELECT DISTINCT m.module_code, m.module_name
      FROM modules m
      JOIN student_modules sm ON m.module_code = sm.module_code
     WHERE sm.student_id = ?
     ORDER BY m.module_name
    """, (student_id,))
    modules = cursor.fetchall() or []
    if not modules:
        print("No enrolled modules found for this student.")
        return

    print("\nStudent's Modules:")
    for i, (code, name) in enumerate(modules, start=1):
        print(f"{i}. {code} - {name}")

    choice = input("Enter module number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(modules):
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    module_code, module_name = modules[idx]

    # 3) compute prediction using existing core function
    result = predict_module_final_grade(cursor, student_id, module_code)
    if not result:
        print("Not enough data to predict final grade for this module.")
        return

    print(f"\nPrediction for {module_code} - {module_name}")
    print(f"Current Progress: {result['progress']:.1f}%")
    print(f"Predicted Final Score: {result['score']:.1f}%")
    print(f"Predicted Final Grade: {result['grade']}")
