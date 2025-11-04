from datetime import datetime, timedelta
from typing import List, Dict, Any
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH


def screening_guidelines() -> Dict[str, Any]:
    """Provide health screening guidelines based on age and risk factors."""
    guidelines = {
        "general": {
            "annual_checkup": "Recommended yearly for all students",
            "blood_pressure": "Check every 2 years if normal, annually if elevated",
            "cholesterol": "Every 5 years starting at age 20",
            "diabetes": "Every 3 years starting at age 45, or earlier if risk factors"
        },
        "age_specific": {
            "18-25": ["Annual physical", "Mental health screening", "STI screening"],
            "26-35": ["Cancer screening as appropriate", "Cardiovascular risk assessment"],
            "35+": ["Diabetes screening", "Colonoscopy at 45", "Mammography for women"]
        }
    }
    return guidelines


def screening_reminders() -> List[Dict[str, Any]]:
    """Send screening reminders to students based on due dates."""
    reminders = []

    # Connect to database and get students due for screenings
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT student_id, email, last_checkup, screening_type
            FROM health_records
            WHERE next_screening_due <= date('now', '+30 days')
        """)

        for row in cursor.fetchall():
            student_id, email, last_checkup, screening_type = row
            reminders.append({
                "student_id": student_id,
                "email": email,
                "screening_type": screening_type,
                "last_checkup": last_checkup,
                "reminder_sent": datetime.now().isoformat()
            })
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return reminders


def record_screening_results(student_id: int, screening_type: str, results: Dict[str, Any], date_performed: str = None) -> bool:
    """Record health screening results in the database."""
    if date_performed is None:
        date_performed = datetime.now().date().isoformat()

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO screening_results
            (student_id, screening_type, results, date_performed, next_due_date)
            VALUES (?, ?, ?, ?, ?)
        """, (
            student_id,
            screening_type,
            str(results),
            date_performed,
            calculate_screening_due_date(screening_type, date_performed)
        ))

        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def calculate_screening_due_date(screening_type: str, last_screening_date: str) -> str:
    """Calculate when the next screening is due based on type and last screening."""
    last_date = datetime.fromisoformat(last_screening_date)

    screening_intervals = {
        "annual_physical": 365,
        "blood_pressure": 730,  # 2 years if normal
        "cholesterol": 1825,    # 5 years
        "diabetes": 1095,       # 3 years
        "mental_health": 365,
        "dental": 180,          # 6 months
        "vision": 730,          # 2 years
        "hearing": 1095         # 3 years
    }

    interval_days = screening_intervals.get(screening_type, 365)
    next_due = last_date + timedelta(days=interval_days)

    return next_due.date().isoformat()


def view_due_screenings() -> List[Dict[str, Any]]:
    """Display all screenings that are currently due."""
    due_screenings = []

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.student_id, s.first_name, s.last_name, s.email,
                   hr.screening_type, hr.next_screening_due
            FROM students s
            JOIN health_records hr ON s.student_id = hr.student_id
            WHERE hr.next_screening_due <= date('now')
            ORDER BY hr.next_screening_due ASC
        """)

        for row in cursor.fetchall():
            student_id, first_name, last_name, email, screening_type, due_date = row
            due_screenings.append({
                "student_id": student_id,
                "student_name": f"{first_name} {last_name}",
                "email": email,
                "screening_type": screening_type,
                "due_date": due_date,
                "days_overdue": (datetime.now().date() - datetime.fromisoformat(due_date).date()).days
            })
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return due_screenings


def overdue_screenings() -> List[Dict[str, Any]]:
    """Show overdue health screenings with escalation levels."""
    overdue = []

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.student_id, s.first_name, s.last_name, s.email,
                   hr.screening_type, hr.next_screening_due
            FROM students s
            JOIN health_records hr ON s.student_id = hr.student_id
            WHERE hr.next_screening_due < date('now')
            ORDER BY hr.next_screening_due ASC
        """)

        for row in cursor.fetchall():
            student_id, first_name, last_name, email, screening_type, due_date = row
            days_overdue = (datetime.now().date() - datetime.fromisoformat(due_date).date()).days

            escalation_level = "low"
            if days_overdue > 90:
                escalation_level = "high"
            elif days_overdue > 30:
                escalation_level = "medium"

            overdue.append({
                "student_id": student_id,
                "student_name": f"{first_name} {last_name}",
                "email": email,
                "screening_type": screening_type,
                "due_date": due_date,
                "days_overdue": days_overdue,
                "escalation_level": escalation_level
            })
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return overdue


def population_screening_reports() -> Dict[str, Any]:
    """Generate population health reports for administration."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    report = {
        "total_students": 0,
        "screening_compliance": {},
        "overdue_by_type": {},
        "completion_rates": {},
        "trends": {}
    }

    try:
        # Total students
        cursor.execute("SELECT COUNT(*) FROM students")
        report["total_students"] = cursor.fetchone()[0]

        # Compliance by screening type
        cursor.execute("""
            SELECT screening_type,
                   COUNT(*) as total,
                   SUM(CASE WHEN next_screening_due >= date('now') THEN 1 ELSE 0 END) as compliant
            FROM health_records
            GROUP BY screening_type
        """)

        for row in cursor.fetchall():
            screening_type, total, compliant = row
            compliance_rate = (compliant / total * 100) if total > 0 else 0
            report["screening_compliance"][screening_type] = {
                "total": total,
                "compliant": compliant,
                "rate": round(compliance_rate, 2)
            }

        # Overdue by type
        cursor.execute("""
            SELECT screening_type, COUNT(*) as overdue_count
            FROM health_records
            WHERE next_screening_due < date('now')
            GROUP BY screening_type
        """)

        for row in cursor.fetchall():
            screening_type, overdue_count = row
            report["overdue_by_type"][screening_type] = overdue_count

    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return report


def recent_lab_results_dashboard() -> Dict[str, Any]:
    """Dashboard showing recent lab results and alerts."""
    dashboard = {
        "recent_results": [],
        "abnormal_results": [],
        "pending_reviews": [],
        "summary_stats": {}
    }

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Recent results (last 30 days)
        cursor.execute("""
            SELECT s.student_id, s.first_name, s.last_name,
                   lr.test_type, lr.result_value, lr.normal_range, lr.date_performed
            FROM students s
            JOIN lab_results lr ON s.student_id = lr.student_id
            WHERE lr.date_performed >= date('now', '-30 days')
            ORDER BY lr.date_performed DESC
            LIMIT 50
        """)

        for row in cursor.fetchall():
            student_id, first_name, last_name, test_type, result, normal_range, date_performed = row
            dashboard["recent_results"].append({
                "student_id": student_id,
                "student_name": f"{first_name} {last_name}",
                "test_type": test_type,
                "result": result,
                "normal_range": normal_range,
                "date": date_performed
            })

        # Abnormal results requiring attention
        cursor.execute("""
            SELECT s.student_id, s.first_name, s.last_name,
                   lr.test_type, lr.result_value, lr.normal_range, lr.date_performed
            FROM students s
            JOIN lab_results lr ON s.student_id = lr.student_id
            WHERE lr.abnormal_flag = 1 AND lr.reviewed = 0
            ORDER BY lr.date_performed DESC
        """)

        for row in cursor.fetchall():
            student_id, first_name, last_name, test_type, result, normal_range, date_performed = row
            dashboard["abnormal_results"].append({
                "student_id": student_id,
                "student_name": f"{first_name} {last_name}",
                "test_type": test_type,
                "result": result,
                "normal_range": normal_range,
                "date": date_performed,
                "priority": "high" if "critical" in str(result).lower() else "medium"
            })

    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return dashboard


def vaccination_due_list() -> List[Dict[str, Any]]:
    """List students due for vaccinations based on university requirements."""
    due_vaccinations = []

    required_vaccines = {
        "meningitis": {"interval_months": 60, "required": True},
        "tdap": {"interval_months": 120, "required": True},
        "mmr": {"interval_months": 0, "required": True},  # Usually one-time
        "hepatitis_b": {"interval_months": 0, "required": True},
        "flu": {"interval_months": 12, "required": False},
        "covid19": {"interval_months": 6, "required": True}
    }

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        for vaccine, details in required_vaccines.items():
            interval_days = details["interval_months"] * 30 if details["interval_months"] > 0 else 0

            if interval_days == 0:  # One-time vaccines
                cursor.execute("""
                    SELECT s.student_id, s.first_name, s.last_name, s.email
                    FROM students s
                    LEFT JOIN vaccination_records vr ON s.student_id = vr.student_id
                        AND vr.vaccine_type = ?
                    WHERE vr.student_id IS NULL
                """, (vaccine,))
            else:  # Recurring vaccines
                cursor.execute("""
                    SELECT s.student_id, s.first_name, s.last_name, s.email,
                           vr.last_vaccination_date
                    FROM students s
                    LEFT JOIN vaccination_records vr ON s.student_id = vr.student_id
                        AND vr.vaccine_type = ?
                    WHERE vr.student_id IS NULL
                       OR date(vr.last_vaccination_date, '+{} days') <= date('now')
                """.format(interval_days), (vaccine,))

            for row in cursor.fetchall():
                if len(row) == 4:
                    student_id, first_name, last_name, email = row
                    last_vaccination = None
                else:
                    student_id, first_name, last_name, email, last_vaccination = row

                due_vaccinations.append({
                    "student_id": student_id,
                    "student_name": f"{first_name} {last_name}",
                    "email": email,
                    "vaccine_type": vaccine,
                    "last_vaccination": last_vaccination,
                    "required": details["required"],
                    "priority": "high" if details["required"] else "medium"
                })

    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return due_vaccinations