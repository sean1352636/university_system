#!/usr/bin/env python3
"""
Script to create 10 comprehensive report templates with real database queries
"""
import json
from datetime import datetime
from university_system.infrastructure.database.db import get_connection

def create_templates():
    """Create 10 report templates with real database queries"""

    templates = [
        {
            "name": "Student Enrollment Report",
            "description": "Comprehensive overview of student enrollments by course and semester",
            "sections": ["student_overview", "student_list", "registration_trends"],
            "filters": {"status": "active"},
            "visualization_type": "standard",
            "schedule_config": {},
            "security_level": "normal",
            "custom_sql": {
                "enrollment_summary": """
                    SELECT
                        c.course_name,
                        c.course_code,
                        COUNT(DISTINCT lse.student_id) as total_enrolled,
                        lse.semester,
                        lse.academic_year
                    FROM lms_student_enrollment lse
                    JOIN courses c ON lse.course_id = c.course_id
                    WHERE lse.enrollment_date BETWEEN ? AND ?
                    GROUP BY c.course_id, lse.semester, lse.academic_year
                    ORDER BY total_enrolled DESC
                """,
                "student_demographics": """
                    SELECT
                        COUNT(*) as total_students,
                        SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END) as male_count,
                        SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) as female_count,
                        AVG(CAST((julianday('now') - julianday(date_of_birth)) / 365.25 AS INTEGER)) as avg_age
                    FROM students
                    WHERE created_at BETWEEN ? AND ?
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Financial Aid Distribution",
            "description": "Analysis of financial aid packages, scholarships, and student assistance",
            "sections": ["student_overview"],
            "filters": {},
            "visualization_type": "standard",
            "schedule_config": {},
            "security_level": "confidential",
            "custom_sql": {
                "aid_summary": """
                    SELECT
                        fa.aid_type,
                        COUNT(DISTINCT sfa.student_id) as recipients_count,
                        SUM(sfa.amount) as total_amount,
                        AVG(sfa.amount) as avg_amount,
                        sfa.academic_year
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fa ON sfa.aid_type_id = fa.aid_type_id
                    WHERE sfa.date_awarded BETWEEN ? AND ?
                    GROUP BY fa.aid_type, sfa.academic_year
                    ORDER BY total_amount DESC
                """,
                "scholarship_overview": """
                    SELECT
                        s.scholarship_name,
                        COUNT(DISTINCT sa.student_id) as awardees,
                        SUM(sa.amount) as total_awarded,
                        s.scholarship_type
                    FROM scholarship_awards sa
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    WHERE sa.award_date BETWEEN ? AND ?
                    GROUP BY s.scholarship_id
                    ORDER BY total_awarded DESC
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Course Performance Analysis",
            "description": "Detailed analysis of course grades, completion rates, and student performance",
            "sections": ["grade_distribution", "course_distribution"],
            "filters": {},
            "visualization_type": "interactive",
            "schedule_config": {},
            "security_level": "normal",
            "custom_sql": {
                "grade_statistics": """
                    SELECT
                        c.course_name,
                        c.course_code,
                        COUNT(DISTINCT g.student_id) as students_graded,
                        AVG(g.grade) as avg_grade,
                        MIN(g.grade) as min_grade,
                        MAX(g.grade) as max_grade,
                        SUM(CASE WHEN g.grade >= 70 THEN 1 ELSE 0 END) as passing_count,
                        SUM(CASE WHEN g.grade < 70 THEN 1 ELSE 0 END) as failing_count
                    FROM grades g
                    JOIN courses c ON g.course_id = c.course_id
                    WHERE g.date_recorded BETWEEN ? AND ?
                    GROUP BY c.course_id
                    ORDER BY avg_grade DESC
                """,
                "completion_rates": """
                    SELECT
                        c.course_name,
                        COUNT(DISTINCT lse.student_id) as enrolled,
                        COUNT(DISTINCT CASE WHEN lse.completion_status = 'completed' THEN lse.student_id END) as completed,
                        ROUND(100.0 * COUNT(DISTINCT CASE WHEN lse.completion_status = 'completed' THEN lse.student_id END) /
                              NULLIF(COUNT(DISTINCT lse.student_id), 0), 2) as completion_rate
                    FROM lms_student_enrollment lse
                    JOIN courses c ON lse.course_id = c.course_id
                    WHERE lse.enrollment_date BETWEEN ? AND ?
                    GROUP BY c.course_id
                    HAVING enrolled > 0
                    ORDER BY completion_rate DESC
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Student Affairs Activities",
            "description": "Overview of student union events, club participation, and campus activities",
            "sections": ["student_overview"],
            "filters": {},
            "visualization_type": "standard",
            "schedule_config": {},
            "security_level": "normal",
            "custom_sql": {
                "event_participation": """
                    SELECT
                        ue.event_name,
                        ue.event_type,
                        ue.event_date,
                        COUNT(DISTINCT uer.student_id) as registrations,
                        ue.capacity,
                        ROUND(100.0 * COUNT(DISTINCT uer.student_id) / NULLIF(ue.capacity, 0), 2) as fill_rate
                    FROM union_events ue
                    LEFT JOIN union_event_registrations uer ON ue.event_id = uer.event_id
                    WHERE ue.event_date BETWEEN ? AND ?
                    GROUP BY ue.event_id
                    ORDER BY registrations DESC
                """,
                "club_membership": """
                    SELECT
                        sc.club_name,
                        sc.category,
                        COUNT(DISTINCT cm.student_id) as member_count,
                        sc.status
                    FROM student_clubs sc
                    LEFT JOIN club_members cm ON sc.club_id = cm.club_id
                    WHERE cm.join_date BETWEEN ? AND ? OR cm.join_date IS NULL
                    GROUP BY sc.club_id
                    ORDER BY member_count DESC
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Health Services Utilization",
            "description": "Analysis of health appointments, services usage, and student wellness",
            "sections": ["student_overview"],
            "filters": {},
            "visualization_type": "standard",
            "schedule_config": {},
            "security_level": "confidential",
            "custom_sql": {
                "appointment_summary": """
                    SELECT
                        ha.appointment_type,
                        ha.status,
                        COUNT(*) as appointment_count,
                        DATE(ha.appointment_date) as date,
                        AVG(CAST((julianday(ha.end_time) - julianday(ha.start_time)) * 24 * 60 AS REAL)) as avg_duration_minutes
                    FROM health_appointments ha
                    WHERE ha.appointment_date BETWEEN ? AND ?
                    GROUP BY ha.appointment_type, ha.status, DATE(ha.appointment_date)
                    ORDER BY date DESC, appointment_count DESC
                """,
                "health_metrics": """
                    SELECT
                        COUNT(DISTINCT ha.student_id) as unique_patients,
                        COUNT(*) as total_appointments,
                        COUNT(DISTINCT ha.appointment_date) as days_active,
                        AVG(appointments_per_student) as avg_appointments_per_student
                    FROM health_appointments ha
                    LEFT JOIN (
                        SELECT student_id, COUNT(*) as appointments_per_student
                        FROM health_appointments
                        WHERE appointment_date BETWEEN ? AND ?
                        GROUP BY student_id
                    ) AS student_stats ON ha.student_id = student_stats.student_id
                    WHERE ha.appointment_date BETWEEN ? AND ?
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Housing Occupancy Report",
            "description": "Housing assignments, availability, and residence hall statistics",
            "sections": ["student_overview"],
            "filters": {},
            "visualization_type": "standard",
            "schedule_config": {},
            "security_level": "normal",
            "custom_sql": {
                "occupancy_summary": """
                    SELECT
                        hb.building_name,
                        COUNT(DISTINCT hr.room_id) as total_rooms,
                        COUNT(DISTINCT CASE WHEN ha.status = 'active' THEN ha.room_id END) as occupied_rooms,
                        COUNT(DISTINCT ha.student_id) as total_residents,
                        ROUND(100.0 * COUNT(DISTINCT CASE WHEN ha.status = 'active' THEN ha.room_id END) /
                              NULLIF(COUNT(DISTINCT hr.room_id), 0), 2) as occupancy_rate
                    FROM housing_buildings hb
                    LEFT JOIN housing_rooms hr ON hb.building_id = hr.building_id
                    LEFT JOIN housing_assignments ha ON hr.room_id = ha.room_id
                    WHERE ha.start_date <= ? AND (ha.end_date >= ? OR ha.end_date IS NULL)
                    GROUP BY hb.building_id
                    ORDER BY occupancy_rate DESC
                """,
                "maintenance_requests": """
                    SELECT
                        hmr.priority,
                        hmr.status,
                        COUNT(*) as request_count,
                        AVG(CAST((julianday(COALESCE(hmr.resolved_date, 'now')) - julianday(hmr.request_date)) AS REAL)) as avg_resolution_days
                    FROM housing_maintenance_requests hmr
                    WHERE hmr.request_date BETWEEN ? AND ?
                    GROUP BY hmr.priority, hmr.status
                    ORDER BY request_count DESC
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Library Usage Statistics",
            "description": "Book loans, reservations, popular titles, and library engagement metrics",
            "sections": ["student_overview"],
            "filters": {},
            "visualization_type": "standard",
            "schedule_config": {},
            "security_level": "normal",
            "custom_sql": {
                "loan_statistics": """
                    SELECT
                        b.title,
                        b.author,
                        b.category,
                        COUNT(DISTINCT bl.loan_id) as times_borrowed,
                        AVG(CAST((julianday(COALESCE(bl.return_date, 'now')) - julianday(bl.loan_date)) AS REAL)) as avg_loan_days,
                        COUNT(DISTINCT bl.student_id) as unique_borrowers
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.loan_date BETWEEN ? AND ?
                    GROUP BY b.book_id
                    ORDER BY times_borrowed DESC
                    LIMIT 50
                """,
                "library_engagement": """
                    SELECT
                        COUNT(DISTINCT bl.student_id) as active_users,
                        COUNT(*) as total_loans,
                        SUM(CASE WHEN bl.return_date > bl.due_date THEN 1 ELSE 0 END) as overdue_count,
                        ROUND(100.0 * SUM(CASE WHEN bl.return_date > bl.due_date THEN 1 ELSE 0 END) /
                              NULLIF(COUNT(*), 0), 2) as overdue_rate
                    FROM book_loans bl
                    WHERE bl.loan_date BETWEEN ? AND ?
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Payment and Revenue Report",
            "description": "Tuition payments, fees, outstanding balances, and revenue analysis",
            "sections": ["student_overview"],
            "filters": {},
            "visualization_type": "standard",
            "schedule_config": {},
            "security_level": "confidential",
            "custom_sql": {
                "payment_summary": """
                    SELECT
                        p.payment_method,
                        p.payment_type,
                        COUNT(*) as transaction_count,
                        SUM(p.amount) as total_revenue,
                        AVG(p.amount) as avg_payment,
                        DATE(p.payment_date) as date
                    FROM payments p
                    WHERE p.payment_date BETWEEN ? AND ?
                    AND p.status = 'completed'
                    GROUP BY p.payment_method, p.payment_type, DATE(p.payment_date)
                    ORDER BY date DESC, total_revenue DESC
                """,
                "outstanding_balances": """
                    SELECT
                        sf.fee_type,
                        COUNT(DISTINCT sf.student_id) as students_with_fees,
                        SUM(sf.amount) as total_fees,
                        SUM(sf.amount_paid) as total_paid,
                        SUM(sf.amount - sf.amount_paid) as outstanding_balance
                    FROM student_fees sf
                    WHERE sf.due_date <= ? AND sf.amount > sf.amount_paid
                    GROUP BY sf.fee_type
                    ORDER BY outstanding_balance DESC
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Academic Performance Dashboard",
            "description": "Student grades, GPA trends, academic warnings, and performance indicators",
            "sections": ["grade_distribution", "student_overview"],
            "filters": {},
            "visualization_type": "interactive",
            "schedule_config": {},
            "security_level": "normal",
            "custom_sql": {
                "gpa_analysis": """
                    SELECT
                        s.student_id,
                        s.first_name || ' ' || s.last_name as student_name,
                        s.program,
                        AVG(g.grade) as current_gpa,
                        COUNT(DISTINCT g.course_id) as courses_taken,
                        SUM(CASE WHEN g.grade >= 70 THEN 1 ELSE 0 END) as courses_passed,
                        SUM(CASE WHEN g.grade < 70 THEN 1 ELSE 0 END) as courses_failed
                    FROM students s
                    LEFT JOIN grades g ON s.student_id = g.student_id
                    WHERE g.date_recorded BETWEEN ? AND ?
                    GROUP BY s.student_id
                    HAVING AVG(g.grade) IS NOT NULL
                    ORDER BY current_gpa DESC
                """,
                "at_risk_students": """
                    SELECT
                        s.student_id,
                        s.first_name || ' ' || s.last_name as student_name,
                        AVG(g.grade) as gpa,
                        COUNT(DISTINCT CASE WHEN g.grade < 70 THEN g.course_id END) as failing_courses,
                        'Academic Warning' as risk_level
                    FROM students s
                    JOIN grades g ON s.student_id = g.student_id
                    WHERE g.date_recorded BETWEEN ? AND ?
                    GROUP BY s.student_id
                    HAVING AVG(g.grade) < 70 OR COUNT(DISTINCT CASE WHEN g.grade < 70 THEN g.course_id END) >= 2
                    ORDER BY gpa ASC
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        {
            "name": "Campus Events and Engagement",
            "description": "Campus events, attendance, student engagement, and activity trends",
            "sections": ["student_overview"],
            "filters": {},
            "visualization_type": "standard",
            "schedule_config": {},
            "security_level": "normal",
            "custom_sql": {
                "event_overview": """
                    SELECT
                        ce.event_name,
                        ce.event_type,
                        ce.event_date,
                        ce.location,
                        COUNT(DISTINCT ea.student_id) as attendees,
                        ce.max_capacity,
                        ROUND(100.0 * COUNT(DISTINCT ea.student_id) / NULLIF(ce.max_capacity, 0), 2) as attendance_rate
                    FROM campus_events ce
                    LEFT JOIN event_attendance ea ON ce.event_id = ea.event_id
                    WHERE ce.event_date BETWEEN ? AND ?
                    GROUP BY ce.event_id
                    ORDER BY attendees DESC
                """,
                "engagement_trends": """
                    SELECT
                        DATE(ce.event_date) as date,
                        ce.event_type,
                        COUNT(DISTINCT ce.event_id) as events_held,
                        COUNT(DISTINCT ea.student_id) as total_unique_attendees,
                        SUM(COUNT(DISTINCT ea.student_id)) OVER (PARTITION BY ce.event_type ORDER BY DATE(ce.event_date)) as cumulative_attendees
                    FROM campus_events ce
                    LEFT JOIN event_attendance ea ON ce.event_id = ea.event_id
                    WHERE ce.event_date BETWEEN ? AND ?
                    GROUP BY DATE(ce.event_date), ce.event_type
                    ORDER BY date DESC
                """
            },
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }
    ]

    # Insert templates into database
    conn = get_connection()
    cursor = conn.cursor()

    inserted_count = 0
    updated_count = 0

    for template_data in templates:
        # Check if template already exists
        cursor.execute("""
            SELECT template_id FROM email_templates
            WHERE template_name = ? AND template_type = 'report_template'
        """, (template_data['name'],))

        existing = cursor.fetchone()
        template_json = json.dumps(template_data)

        if existing:
            # Update existing template
            cursor.execute("""
                UPDATE email_templates
                SET template_content = ?, updated_at = ?
                WHERE template_id = ?
            """, (template_json, datetime.now().isoformat(), existing[0]))
            updated_count += 1
            print(f"Updated template: {template_data['name']}")
        else:
            # Insert new template
            cursor.execute("""
                INSERT INTO email_templates
                (template_name, template_content, template_type, created_date)
                VALUES (?, ?, 'report_template', ?)
            """, (template_data['name'], template_json, datetime.now().isoformat()))
            inserted_count += 1
            print(f"Inserted template: {template_data['name']}")

    conn.commit()
    conn.close()

    print(f"\n✅ Template creation complete!")
    print(f"   - Inserted: {inserted_count} new templates")
    print(f"   - Updated: {updated_count} existing templates")
    print(f"   - Total: {len(templates)} templates now available")

if __name__ == "__main__":
    create_templates()
