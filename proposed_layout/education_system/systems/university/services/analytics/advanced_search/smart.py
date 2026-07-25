"""Smart features: auto-complete, smart suggestions, predictive analytics."""
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.sql_safety import (
    validate_field_for_query,
    SQLIdentifierError,
)
from education_system.systems.university.services.analytics.advanced_search import _globals
from education_system.systems.university.services.analytics.advanced_search.display import display_search_results
from education_system.systems.university.services.analytics.advanced_search.system import log_search
from education_system.systems.university.services.analytics.advanced_search.admin import audit_log


def _load_recent_search_terms(limit=10):
    """Return the most recent distinct search queries for the current user."""
    try:
        conn = get_connection()
        if conn is None:
            return []
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(search_analytics)")
        cols = {row[1] for row in cursor.fetchall()}
        if not cols:
            conn.close()
            return []
        query_col = "search_query" if "search_query" in cols else (
            "search_criteria" if "search_criteria" in cols else None
        )
        if query_col is None:
            conn.close()
            return []

        user_id = str(getattr(_globals, "current_user", None) or "cli_user")
        sql = (
            f"SELECT {query_col} FROM search_analytics "
            f"WHERE {query_col} IS NOT NULL AND {query_col} != '' "
            f"AND user_id = ? ORDER BY id DESC LIMIT ?"
        )
        cursor.execute(sql, (user_id, max(1, int(limit)) * 3))
        rows = [r[0] for r in cursor.fetchall()]

        if not rows:
            sql = (
                f"SELECT {query_col} FROM search_analytics "
                f"WHERE {query_col} IS NOT NULL AND {query_col} != '' "
                f"ORDER BY id DESC LIMIT ?"
            )
            cursor.execute(sql, (max(1, int(limit)) * 3,))
            rows = [r[0] for r in cursor.fetchall()]

        conn.close()

        seen = set()
        result = []
        for term in rows:
            t = str(term).strip()
            if not t or t in seen:
                continue
            seen.add(t)
            result.append(t[:80])
            if len(result) >= limit:
                break
        return result
    except Exception:
        return []


@audit_log
def auto_complete_search():
    """Auto-complete search functionality"""
    print("\n💡 AUTO-COMPLETE SEARCH")
    print("="*40)

    # Whitelist of allowed search fields
    ALLOWED_SEARCH_FIELDS = {'first_name', 'last_name', 'course'}

    search_field = input("Search field (first_name/last_name/course): ").strip()

    if search_field not in ALLOWED_SEARCH_FIELDS:
        print("Invalid search field.")
        return

    # Validate field name using SQL safety utility (defense-in-depth)
    try:
        validated_field = validate_field_for_query(search_field, ALLOWED_SEARCH_FIELDS, "search field")
    except SQLIdentifierError as e:
        print(f"Invalid search field: {e}")
        return

    partial_input = input(f"Enter partial {validated_field}: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Use bracket-quoted validated field name
        query = f"SELECT DISTINCT [{validated_field}] FROM students WHERE [{validated_field}] LIKE ? ORDER BY [{validated_field}]"
        cursor.execute(query, (f"{partial_input}%",))

        suggestions = cursor.fetchall()

        if not suggestions:
            print("No suggestions found.")
            return

        print(f"\n💡 Suggestions for '{partial_input}':")
        print("-" * 40)

        for i, (suggestion,) in enumerate(suggestions[:10], 1):  # Limit to 10
            print(f"{i}. {suggestion}")

        choice = input("\nSelect suggestion number (or press Enter to skip): ").strip()

        if choice:
            try:
                index = int(choice) - 1
                if 0 <= index < len(suggestions):
                    selected = suggestions[index][0]
                    print(f"\nSearching for {validated_field} = '{selected}'...")

                    # Execute search with selected suggestion (using validated field name)
                    cursor.execute("SELECT * FROM students WHERE [" + validated_field + "] = ?", (selected,))
                    results = cursor.fetchall()

                    log_search("auto_complete", {validated_field: selected}, len(results))
                    display_search_results(results)
            except ValueError:
                print("Invalid selection.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def smart_suggestions():
    """Provide smart search suggestions based on patterns"""
    print("\n🧠 SMART SEARCH SUGGESTIONS")
    print("="*50)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Analyze search patterns and suggest useful searches
        suggestions = [
            ("Students without email addresses",
             "SELECT * FROM students WHERE email IS NULL OR email = ''"),
            ("Students enrolled in multiple modules",
             """SELECT s.*, COUNT(sm.module_code) as module_count
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                GROUP BY s.student_id
                HAVING module_count > 3"""),
            ("Recent registrations (last 30 days)",
             "SELECT * FROM students WHERE registration_datetime >= date('now', '-30 days')"),
            ("Students by age groups",
             "SELECT * FROM students ORDER BY age"),
            ("Course distribution analysis",
             "SELECT course, COUNT(*) FROM students GROUP BY course")
        ]

        print("🔍 Suggested searches:")
        print("-" * 50)

        for i, (description, query) in enumerate(suggestions, 1):
            print(f"{i}. {description}")

        # Append user's own recent searches from the search_analytics table.
        recent_terms = _load_recent_search_terms(limit=5)
        if recent_terms:
            print("\n🕘 Your recent searches:")
            print("-" * 50)
            for j, term in enumerate(recent_terms, len(suggestions) + 1):
                print(f"{j}. {term}  (re-run as text search)")
        else:
            print("\n🕘 Your recent searches: (none recorded yet)")

        max_choice = len(suggestions) + len(recent_terms)
        choice = input(f"\nSelect option (1-{max_choice}) or press Enter to skip: ").strip()

        if choice:
            try:
                index = int(choice) - 1
                if 0 <= index < len(suggestions):
                    description, query = suggestions[index]
                    print(f"\nExecuting: {description}")

                    cursor.execute(query)
                    results = cursor.fetchall()

                    log_search("smart_suggestion", {"description": description}, len(results))

                    if "GROUP BY" in query or "COUNT" in query:
                        # Display aggregate results
                        print(f"\n📊 Results for: {description}")
                        print("-" * 50)
                        for result in results:
                            print(result)
                    else:
                        display_search_results(results)
                elif len(suggestions) <= index < len(suggestions) + len(recent_terms):
                    term = recent_terms[index - len(suggestions)]
                    print(f"\nRe-running recent search: {term}")
                    like = f"%{term}%"
                    cursor.execute(
                        "SELECT * FROM students WHERE "
                        "LOWER(first_name || ' ' || last_name) LIKE LOWER(?) "
                        "OR LOWER(email_address) LIKE LOWER(?) "
                        "OR LOWER(student_id) LIKE LOWER(?)",
                        (like, like, like),
                    )
                    results = cursor.fetchall()
                    log_search("recent_search_rerun", {"term": term}, len(results))
                    display_search_results(results)
                else:
                    print("Invalid selection.")

            except ValueError:
                print("Invalid selection.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def predictive_analytics():
    """Basic predictive analytics for student data"""
    print("\n🔮 PREDICTIVE ANALYTICS")
    print("="*40)

    print("Available analytics:")
    print("1. At-risk Student Identification")
    print("2. Enrollment Prediction")
    print("3. Module Success Probability")
    print("4. Graduation Timeline Forecast")

    choice = input("Select analysis (1-4): ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if choice == '1':
            identify_at_risk_students(cursor)
        elif choice == '2':
            enrollment_prediction(cursor)
        elif choice == '3':
            module_success_probability(cursor)
        elif choice == '4':
            graduation_timeline_forecast(cursor)

        conn.close()

    except sqlite3.Error as e:
        print(f"Error in predictive analytics: {e}")

def identify_at_risk_students(cursor):
    """Identify students who might be at risk"""
    print("\n⚠️  AT-RISK STUDENT IDENTIFICATION")
    print("-" * 50)

    # Simple risk factors: incomplete modules, delayed registration, etc.
    cursor.execute('''
    SELECT s.student_id, s.first_name, s.last_name, s.course,
           COUNT(sm.module_code) as total_modules,
           SUM(CASE WHEN sm.grade IS NULL THEN 1 ELSE 0 END) as incomplete_modules,
           julianday('now') - julianday(s.registration_datetime) as days_since_registration
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
    GROUP BY s.student_id, s.first_name, s.last_name, s.course, s.registration_datetime
    ''')

    students = cursor.fetchall()
    at_risk_students = []

    for student in students:
        risk_score = 0
        risk_factors = []

        student_id, first_name, last_name, course, total_modules, incomplete_modules, days_since_reg = student

        # Risk factor 1: High ratio of incomplete modules
        if total_modules > 0:
            incomplete_ratio = incomplete_modules / total_modules
            if incomplete_ratio > 0.5:
                risk_score += 3
                risk_factors.append(f"High incomplete ratio ({incomplete_ratio:.1%})")

        # Risk factor 2: No modules enrolled after significant time
        if total_modules == 0 and days_since_reg > 30:
            risk_score += 4
            risk_factors.append("No module enrollment after 30+ days")

        # Risk factor 3: Too many incomplete modules
        if incomplete_modules > 3:
            risk_score += 2
            risk_factors.append(f"{incomplete_modules} incomplete modules")

        if risk_score >= 3:  # Threshold for at-risk classification
            at_risk_students.append((student, risk_score, risk_factors))

    # Sort by risk score (highest first)
    at_risk_students.sort(key=lambda x: x[1], reverse=True)

    if not at_risk_students:
        print("✅ No at-risk students identified.")
        return

    print(f"🚨 Identified {len(at_risk_students)} at-risk students:")
    print("-" * 80)

    for student_data, risk_score, risk_factors in at_risk_students[:10]:  # Top 10
        student_id, first_name, last_name, course = student_data[:4]
        print(f"\n{student_id}: {first_name} {last_name} ({course}) - Risk Score: {risk_score}")
        for factor in risk_factors:
            print(f"  → {factor}")

def enrollment_prediction(cursor):
    """Predict future enrollment trends"""
    print("\n📈 ENROLLMENT PREDICTION")
    print("-" * 40)

    # Analyze historical enrollment patterns
    cursor.execute('''
    SELECT
        strftime('%Y-%m', registration_datetime) as month,
        COUNT(*) as enrollments
    FROM students
    WHERE registration_datetime >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', registration_datetime)
    ORDER BY month
    ''')

    historical_data = cursor.fetchall()

    if len(historical_data) < 3:
        print("Insufficient historical data for prediction.")
        return

    # Simple trend analysis
    enrollments = [count for _, count in historical_data]

    # Calculate moving average
    if len(enrollments) >= 3:
        recent_avg = sum(enrollments[-3:]) / 3
        overall_avg = sum(enrollments) / len(enrollments)

        trend = "increasing" if recent_avg > overall_avg else "decreasing"
        change_percent = ((recent_avg - overall_avg) / overall_avg) * 100

        print("📊 Historical Enrollment Analysis:")
        print(f"Overall average: {overall_avg:.1f} students/month")
        print(f"Recent average (last 3 months): {recent_avg:.1f} students/month")
        print(f"Trend: {trend} ({change_percent:+.1f}%)")

        # Simple prediction for next month
        predicted_next_month = int(recent_avg * (1 + change_percent/100))

        print(f"\n🔮 Prediction for next month: ~{predicted_next_month} new enrollments")

        # Course-specific predictions
        cursor.execute('''
        SELECT course, COUNT(*)
        FROM students
        WHERE registration_datetime >= date('now', '-3 months')
        GROUP BY course
        ''')

        course_data = cursor.fetchall()
        print("\n📚 Course-specific recent trends:")
        for course, count in course_data:
            monthly_avg = count / 3
            print(f"  {course}: {monthly_avg:.1f} students/month")

def module_success_probability(cursor):
    """Calculate module success probability"""
    print("\n🎯 MODULE SUCCESS PROBABILITY")
    print("-" * 50)

    # Get module statistics
    cursor.execute('''
    SELECT sm.module_code, sm.module_name,
           COUNT(*) as total_enrolled,
           COALESCE(SUM(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1 ELSE 0 END), 0) as passed,
           COALESCE(AVG(CASE WHEN sm.grade IS NOT NULL THEN 1.0 ELSE 0.0 END), 0.0) as completion_rate
    FROM student_modules sm
    GROUP BY sm.module_code, sm.module_name
    HAVING total_enrolled >= 5
    ORDER BY completion_rate DESC
    ''')

    module_stats = cursor.fetchall()

    if not module_stats:
        print("Insufficient data for probability calculation.")
        return

    print("📊 MODULE SUCCESS PROBABILITIES:")
    print("-" * 80)
    print(f"{'Module Code':<12} {'Module Name':<30} {'Success Rate':<12} {'Prediction':<15}")
    print("-" * 80)

    for module_code, module_name, total, passed, completion_rate in module_stats:
        passed_safe = passed if passed is not None else 0
        success_rate = (passed_safe / total) * 100 if total > 0 else 0

        # Simple prediction based on historical data
        if success_rate >= 80:
            prediction = "High Success"
        elif success_rate >= 60:
            prediction = "Moderate Success"
        else:
            prediction = "Low Success"

        print(f"{module_code:<12} {module_name:<30} {success_rate:>8.1f}%    {prediction:<15}")

def graduation_timeline_forecast(cursor):
    """Forecast graduation timelines"""
    print("\n🎓 GRADUATION TIMELINE FORECAST")
    print("-" * 50)

    # Get student progress data
    cursor.execute('''
    SELECT s.student_id, s.first_name, s.last_name, s.course,
           COUNT(sm.module_code) as completed_modules,
           s.registration_datetime,
           julianday('now') - julianday(s.registration_datetime) as days_enrolled
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
                                  AND sm.grade IS NOT NULL
                                  AND sm.grade != 'F'
    GROUP BY s.student_id, s.first_name, s.last_name, s.course, s.registration_datetime
    HAVING days_enrolled > 30
    ORDER BY completed_modules DESC
    ''')

    student_progress = cursor.fetchall()

    if not student_progress:
        print("Insufficient data for graduation forecast.")
        return

    # Assume typical program requires 8 modules for CS, 6 for DS
    required_modules = {'CS': 8, 'DS': 6}

    print("🔮 GRADUATION FORECASTS:")
    print("-" * 90)
    print(f"{'Student ID':<12} {'Name':<25} {'Course':<8} {'Progress':<10} {'Est. Graduation':<15}")
    print("-" * 90)

    for student_id, first_name, last_name, course, completed, reg_date, days_enrolled in student_progress[:15]:
        required = required_modules.get(course, 8)
        progress_pct = (completed / required) * 100

        if completed >= required:
            forecast = "Graduated"
        elif completed == 0:
            forecast = "No progress"
        else:
            # Simple linear projection
            modules_per_day = completed / days_enrolled if days_enrolled > 0 else 0
            remaining_modules = required - completed

            if modules_per_day > 0:
                days_to_graduate = remaining_modules / modules_per_day
                months_to_graduate = days_to_graduate / 30

                if months_to_graduate < 12:
                    forecast = f"{months_to_graduate:.1f} months"
                else:
                    forecast = f"{months_to_graduate/12:.1f} years"
            else:
                forecast = "Stalled"

        name = f"{first_name} {last_name}"
        progress_text = f"{completed}/{required}"

        print(f"{student_id:<12} {name:<25} {course:<8} {progress_text:<10} {forecast:<15}")
