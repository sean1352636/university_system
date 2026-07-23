"""CLI handler for predictive analytics."""

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.academics.services.attendance.records import get_modules


def handle_predictive_analytics(analytics):
    """Handle predictive analytics"""
    print("\n🔮 PREDICTIVE ANALYTICS")
    print("1. Train Prediction Model")
    print("2. Predict Student Risk")
    print("3. Batch Risk Assessment")
    print("4. View Prediction History")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        print("Training predictive model...")
        success = analytics.train_model()

        if success:
            print("✅ Model trained successfully!")
        else:
            print("❌ Model training failed or insufficient data.")

    elif choice == '2':
        student_id = input("Enter student ID: ")

        modules = get_modules()
        if not modules:
            print("No modules found.")
            return

        print("\nAvailable Modules:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")

        try:
            module_idx = int(input("Select module number: ")) - 1
            if 0 <= module_idx < len(modules):
                module_code = modules[module_idx][0]

                prediction = analytics.predict_student_risk(student_id, module_code)

                if prediction:
                    print(f"\n🔮 PREDICTION FOR STUDENT {student_id} IN {module_code}")
                    print("=" * 50)
                    print(f"Risk Level: {prediction['risk_level']}")
                    print(f"Confidence: {prediction['confidence']:.3f}")
                    print(f"Current Attendance Rate: {prediction['current_attendance_rate']:.1f}%")
                    print(f"Consecutive Absences: {prediction['factors']['consecutive_absences']}")
                    print(f"Days Since Last Attendance: {prediction['factors']['days_since_last_attendance']}")

                    if prediction['risk_level'] in ['Medium Risk', 'High Risk']:
                        print("\n⚠️  RECOMMENDED ACTIONS:")
                        if prediction['factors']['consecutive_absences'] >= 3:
                            print("• Contact student immediately about consecutive absences")
                        if prediction['factors']['days_since_last_attendance'] > 7:
                            print("• Schedule academic advisor meeting")
                        print("• Send attendance warning notification")
                        print("• Consider academic support referral")
                else:
                    print("Unable to generate prediction. Insufficient data or model not trained.")
        except (ValueError, IndexError):
            print("Invalid selection.")

    elif choice == '3':
        print("Performing batch risk assessment...")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get all active student-module combinations
            cursor.execute('''
            SELECT DISTINCT ar.student_id, ar.module_code, s.first_name, s.last_name
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.date >= date('now', '-60 days')
            ''')

            combinations = cursor.fetchall()
            conn.close()

            high_risk_students = []
            medium_risk_students = []

            for student_id, module_code, first_name, last_name in combinations:
                prediction = analytics.predict_student_risk(student_id, module_code)

                if prediction:
                    if prediction['risk_level'] == 'High Risk':
                        high_risk_students.append((student_id, module_code, first_name, last_name, prediction))
                    elif prediction['risk_level'] == 'Medium Risk':
                        medium_risk_students.append((student_id, module_code, first_name, last_name, prediction))

            print("\n🚨 BATCH RISK ASSESSMENT RESULTS")
            print("=" * 60)

            if high_risk_students:
                print(f"\n⚠️  HIGH RISK STUDENTS ({len(high_risk_students)}):")
                print(f"{'Student ID':<12} {'Name':<25} {'Module':<12} {'Confidence'}")
                print("-" * 60)
                for student_id, module_code, first_name, last_name, pred in high_risk_students:
                    name = f"{first_name} {last_name}"
                    print(f"{student_id:<12} {name:<25} {module_code:<12} {pred['confidence']:.3f}")

            if medium_risk_students:
                print(f"\n⚠️  MEDIUM RISK STUDENTS ({len(medium_risk_students)}):")
                print(f"{'Student ID':<12} {'Name':<25} {'Module':<12} {'Confidence'}")
                print("-" * 60)
                for student_id, module_code, first_name, last_name, pred in medium_risk_students:
                    name = f"{first_name} {last_name}"
                    print(f"{student_id:<12} {name:<25} {module_code:<12} {pred['confidence']:.3f}")

            if not high_risk_students and not medium_risk_students:
                print("No at-risk students identified.")

        except Exception as e:
            print(f"Error performing batch assessment: {e}")
