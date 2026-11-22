from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.services import get_user_student_id


def manage_wellness_goals(auth):
    """Manage personal wellness goals (stored in ``wellness_goals``; progress
    is ``current_value`` out of ``target_value`` = 100%)."""
    student_id = get_user_student_id(auth)
    if not student_id:
        print("Error: No student ID associated with your account.")
        return

    print("\n===== Your Wellness Goals =====")

    conn = get_connection()
    try:
        goals = conn.execute(
            "SELECT goal_id, goal_description, COALESCE(current_value, 0), "
            "COALESCE(NULLIF(target_value, 0), 100), end_date, status, goal_type "
            "FROM wellness_goals WHERE student_id = ? AND COALESCE(status, 'Active') <> 'Removed' "
            "ORDER BY goal_id", (student_id,)).fetchall()

        if not goals:
            print("\nYou have no wellness goals yet.")
        for i, (gid, text, current, target, end_date, status, gtype) in enumerate(goals):
            pct = max(0, min(100, int(round(100 * float(current) / float(target)))))
            progress_bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            print(f"\n{i+1}. {text}" + (f"  [{gtype}]" if gtype and gtype != 'general' else ""))
            print(f"   Progress: [{progress_bar}] {pct}%")
            print(f"   Target Date: {end_date or 'not set'}   Status: {status or 'Active'}")

        print("\nOptions:")
        print("1. Add New Goal")
        print("2. Update Progress")
        print("3. Remove Goal")
        print("4. Return to dashboard")

        choice = input("\nSelect option (1-4): ")

        def pick():
            num = input("Enter goal number: ").strip()
            if num.isdigit() and 1 <= int(num) <= len(goals):
                return goals[int(num) - 1]
            print("Invalid goal number.")
            return None

        if choice == '1':
            new_goal = input("Enter new wellness goal: ").strip()
            if not new_goal:
                print("A goal is required.")
                return
            gtype = input("Type (exercise/nutrition/sleep/mental/other) [other]: ").strip() or "other"
            target_date = input("Target date (YYYY-MM-DD, blank for none): ").strip() or None
            if target_date:
                try:
                    datetime.strptime(target_date, '%Y-%m-%d')
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
                    return
            cur = conn.execute(
                "INSERT INTO wellness_goals (student_id, goal_type, goal_description, target_value, "
                "current_value, start_date, end_date, status) VALUES (?, ?, ?, 100, 0, ?, ?, 'Active')",
                (student_id, gtype, new_goal, datetime.now().strftime('%Y-%m-%d'), target_date))
            conn.commit()
            log_audit_event(auth.current_user['id'], 'add_wellness_goal', 'wellness_goal', cur.lastrowid)
            print(f"Goal '{new_goal}' added" + (f" with target date {target_date}" if target_date else "") + ".")

        elif choice == '2':
            goal = pick()
            if not goal:
                return
            progress = input("Enter progress percentage (0-100): ").strip()
            if not progress.isdigit() or not 0 <= int(progress) <= 100:
                print("Progress must be a whole number from 0 to 100.")
                return
            status = 'Completed' if int(progress) == 100 else 'Active'
            conn.execute("UPDATE wellness_goals SET current_value = ? * COALESCE(NULLIF(target_value, 0), 100) / 100.0, "
                         "status = ? WHERE goal_id = ? AND student_id = ?",
                         (int(progress), status, goal[0], student_id))
            conn.commit()
            log_audit_event(auth.current_user['id'], 'update_wellness_goal', 'wellness_goal', goal[0])
            print(f"Goal progress updated to {progress}%" + (" — goal completed!" if status == 'Completed' else "."))

        elif choice == '3':
            goal = pick()
            if not goal:
                return
            if input(f"Remove '{goal[1]}'? (y/n): ").strip().lower() == 'y':
                conn.execute("DELETE FROM wellness_goals WHERE goal_id = ? AND student_id = ?",
                             (goal[0], student_id))
                conn.commit()
                log_audit_event(auth.current_user['id'], 'remove_wellness_goal', 'wellness_goal', goal[0])
                print("Goal removed.")
    finally:
        conn.close()



def _metrics_session(auth):
    """``(who, student number, connection)`` for a student's own metrics, or
    ``(None, None, None)`` (message printed)."""
    from dataclasses import replace
    from education_system.systems.university.domains.health.application.health import access
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    student_id = get_user_student_id(auth)
    user = getattr(auth, "current_user", None)
    who = access.from_user(user if isinstance(user, dict) else None)
    if not student_id or who is None:
        print("Error: No student ID associated with your account.")
        return None, None, None
    # The student number resolved for this login (health rows key on it).
    who = replace(who, student_id=str(student_id))
    conn = get_connection()
    health_schema.apply_to_connection(conn)
    return who, str(student_id), conn


def track_personal_metrics(auth):
    """Track personal health metrics (``personal_health_metrics``,
    application/health/personal_metrics): log a reading, view trends."""
    from education_system.systems.university.domains.health.application.health import (
        personal_metrics as pm,
    )
    who, student_id, conn = _metrics_session(auth)
    if conn is None:
        return

    print("\n===== Personal Health Metrics Tracking =====")

    print("Available Metrics to Track:")
    print("1. Weight")
    print("2. Blood Pressure")
    print("3. Exercise Minutes")
    print("4. Sleep Hours")
    print("5. Water Intake")
    print("6. Mood Scale (1-10)")
    print("7. View Trends")

    choice = input("\nSelect metric (1-7): ").strip()
    keys = {"1": "weight", "2": "blood_pressure", "3": "exercise", "4": "sleep",
            "5": "water", "6": "mood"}
    prompts = {"weight": "Enter current weight (kg): ",
               "exercise": "Enter exercise minutes today: ",
               "sleep": "Enter hours slept last night: ",
               "water": "Enter water intake today (litres): ",
               "mood": "Rate your mood today (1-10): "}
    try:
        if choice in keys:
            metric = keys[choice]
            label, unit, *_ = pm.METRICS[metric]
            if metric == "blood_pressure":
                value = input("Enter systolic BP: ")
                value2 = input("Enter diastolic BP: ")
            else:
                value, value2 = input(prompts[metric]), None
            day = input("Date (YYYY-MM-DD, blank for today): ").strip() or None
            pm.log(conn, who, student_id, metric, value, value2, recorded_on=day)
            conn.commit()
            shown = f"{value.strip()}/{value2.strip()}" if value2 else value.strip()
            print(f"{label} logged: {shown}{' ' + unit if unit else ''}")
            log_audit_event(auth.current_user['id'], 'log_personal_metric', 'personal_metric',
                            0, metric)
        elif choice == '7':
            rows = pm.trends(conn, who, student_id, days=30)
            if not rows:
                print("\nNothing logged in the last 30 days yet.")
                return
            print("\nYour last 30 days:")
            print(f"{'Metric':<26}{'Readings':>9}{'Latest':>12}{'Average':>10}"
                  f"{'Low':>8}{'High':>8}{'Change':>9}")
            print("-" * 82)
            for r in rows:
                latest = (f"{r['latest']:g}/{r['latest2']:g}" if r['latest2'] is not None
                          else f"{r['latest']:g}")
                print(f"{r['label']:<26}{r['count']:>9}{latest:>12}{r['average']:>10g}"
                      f"{r['lowest']:>8g}{r['highest']:>8g}{r['change']:>+9g}"
                      f"  {r['unit']}")
            exercise = next((r for r in rows if r["metric"] == "exercise"), None)
            if exercise:
                print(f"\nExercise logged on {exercise['days_logged']} of the last 30 days.")
            sleep = next((r for r in rows if r["metric"] == "sleep"), None)
            if sleep:
                print(f"Average sleep: {sleep['average']:g} hours a night.")
        else:
            print("Invalid choice.")
    except (ValueError, PermissionError) as e:
        conn.rollback()
        print(f"Not logged: {e}")
    finally:
        conn.close()



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

    print("\n===== Wellness Assessment Results =====")
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
        print("\nAreas needing attention:")
        for area in low_scoring_areas:
            print(f"   • {area}")

        print("\nRecommended resources:")

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

    # Save the result with the student's own metrics (personal_health_metrics,
    # metric 'wellness_assessment'; the scores per area go in the notes).
    if auth and auth.current_user:
        save_results = input("\nSave assessment results to your health record? (y/n): ").lower()
        if save_results == 'y':
            from education_system.systems.university.domains.health.application.health import (
                personal_metrics as pm,
            )
            who, student_id, conn = _metrics_session(auth)
            if conn is None:
                return
            try:
                pm.log(conn, who, student_id, "wellness_assessment", round(percentage, 1),
                       notes="; ".join(f"{a}: {s}" for a, s in scores.items()))
                conn.commit()
                print("Assessment results saved!")
                log_audit_event(auth.current_user['id'], 'wellness_assessment', 'wellness', 0,
                               f"Score: {total_score}/{max_possible}")
            except (ValueError, PermissionError) as e:
                conn.rollback()
                print(f"Not saved: {e}")
            finally:
                conn.close()

