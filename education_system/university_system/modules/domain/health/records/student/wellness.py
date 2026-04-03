from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.services import get_user_student_id


def manage_wellness_goals(auth):
    """Manage personal wellness goals"""
    student_id = get_user_student_id(auth)

    print("\n===== Your Wellness Goals =====")

    # Mock wellness goals - would be stored in database
    goals = [
        {"goal": "Exercise 30 minutes daily", "progress": 75, "target_date": "2024-03-01"},
        {"goal": "Drink 8 glasses of water daily", "progress": 60, "target_date": "2024-02-15"},
        {"goal": "Get 8 hours of sleep nightly", "progress": 45, "target_date": "2024-04-01"}
    ]

    for i, goal in enumerate(goals):
        progress_bar = "█" * (goal["progress"] // 10) + "░" * (10 - goal["progress"] // 10)
        print(f"\n{i+1}. {goal['goal']}")
        print(f"   Progress: [{progress_bar}] {goal['progress']}%")
        print(f"   Target Date: {goal['target_date']}")

    print("\nOptions:")
    print("1. Add New Goal")
    print("2. Update Progress")
    print("3. Remove Goal")
    print("4. Return to dashboard")

    choice = input("\nSelect option (1-4): ")

    if choice == '1':
        new_goal = input("Enter new wellness goal: ")
        target_date = input("Target date (YYYY-MM-DD): ")
        print(f"Goal '{new_goal}' added with target date {target_date}")

    elif choice == '2':
        goal_num = input("Enter goal number to update: ")
        progress = input("Enter progress percentage (0-100): ")
        print(f"Goal {goal_num} progress updated to {progress}%")



def track_personal_metrics(auth):
    """Track personal health metrics"""
    student_id = get_user_student_id(auth)

    print("\n===== Personal Health Metrics Tracking =====")

    print("Available Metrics to Track:")
    print("1. Weight")
    print("2. Blood Pressure")
    print("3. Exercise Minutes")
    print("4. Sleep Hours")
    print("5. Water Intake")
    print("6. Mood Scale (1-10)")
    print("7. View Trends")

    choice = input("\nSelect metric (1-7): ")

    if choice == '1':
        weight = input("Enter current weight (lbs): ")
        print(f"Weight logged: {weight} lbs")

    elif choice == '2':
        systolic = input("Enter systolic BP: ")
        diastolic = input("Enter diastolic BP: ")
        print(f"Blood pressure logged: {systolic}/{diastolic}")

    elif choice == '3':
        minutes = input("Enter exercise minutes today: ")
        print(f"Exercise logged: {minutes} minutes")

    elif choice == '7':
        print("\nTrend data would be displayed here with charts/graphs")
        print("• Weight trend over last 30 days")
        print("• Exercise consistency")
        print("• Sleep pattern analysis")



def quick_wellness_assessment(auth):
    print("\n===== Quick Wellness Assessment =====")
    print("Rate each area on a scale of 1-5 (1=Poor, 5=Excellent)")

    wellness_areas = [
        "Physical fitness and exercise",
        "Nutrition and eating habits",
        "Sleep quality and duration",
        "Stress management",
        "Social connections and relationships",
        "Academic performance and satisfaction",
        "Financial security",
        "Overall mental health"
    ]

    scores = {}
    total_score = 0

    for area in wellness_areas:
        while True:
            try:
                score = int(input(f"{area} (1-5): "))
                if 1 <= score <= 5:
                    scores[area] = score
                    total_score += score
                    break
                else:
                    print("Please enter a number between 1 and 5.")
            except ValueError:
                print("Please enter a valid number.")

    # Calculate results
    average_score = total_score / len(wellness_areas)
    max_possible = len(wellness_areas) * 5
    percentage = (total_score / max_possible) * 100

    print(f"\n===== Wellness Assessment Results =====")
    print(f"Total Score: {total_score}/{max_possible}")
    print(f"Average: {average_score:.1f}/5.0")
    print(f"Overall Wellness: {percentage:.1f}%")

    # Provide feedback
    if percentage >= 80:
        print("🌟 Excellent! You're doing great with your overall wellness.")
    elif percentage >= 70:
        print("👍 Good wellness overall. A few areas could use attention.")
    elif percentage >= 60:
        print("⚠️  Fair wellness. Several areas need improvement.")
    else:
        print("🔴 Poor wellness scores. Consider seeking support and resources.")

    # Identify areas for improvement
    low_scoring_areas = [area for area, score in scores.items() if score <= 2]

    if low_scoring_areas:
        print(f"\nAreas needing attention:")
        for area in low_scoring_areas:
            print(f"   • {area}")

        print(f"\nRecommended resources:")

        if "Physical fitness" in str(low_scoring_areas):
            print("   • Visit the Campus Recreation Center")
            print("   • Join a fitness class or intramural sport")

        if "mental health" in str(low_scoring_areas):
            print("   • Contact Counseling Services: (555) 123-HELP")
            print("   • Try stress management workshops")

        if "Sleep" in str(low_scoring_areas):
            print("   • Attend sleep hygiene education session")
            print("   • Review study schedule and time management")

        if "Nutrition" in str(low_scoring_areas):
            print("   • Schedule nutrition counseling appointment")
            print("   • Attend healthy cooking classes")

    # Save assessment results (in a real system)
    if auth and auth.current_user:
        save_results = input("\nSave assessment results to your health record? (y/n): ").lower()
        if save_results == 'y':
            # This would save to a wellness_assessments table
            print("Assessment results saved!")
            log_audit_event(auth.current_user['id'], 'wellness_assessment', 'wellness', 0,
                           f"Score: {total_score}/{max_possible}")

