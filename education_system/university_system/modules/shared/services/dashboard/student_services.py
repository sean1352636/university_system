"""Student dashboard data services (Features 31-43)."""

import logging
from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class StudentDashboardService:
    """Provides shared data methods for student dashboard widgets and feature GUIs."""

    @staticmethod
    def get_grades_by_module(student_id):
        """Get assignment grades grouped by module.

        Returns list of dicts with module_code, module_name, assignments (list),
        and average_score.
        """
        results = []
        try:
            with get_connection() as conn:
                modules = conn.execute(
                    "SELECT m.module_code, m.module_name "
                    "FROM modules m "
                    "INNER JOIN student_modules sm ON m.module_code = sm.module_code "
                    "WHERE sm.student_id = ? AND sm.status = 'Enrolled' "
                    "ORDER BY m.module_code",
                    (student_id,),
                ).fetchall()

                for mod in modules or []:
                    mc = mod["module_code"]
                    assignments = conn.execute(
                        "SELECT a.title, a.max_marks, a.due_date, "
                        "s.grade, s.submission_date "
                        "FROM assignments a "
                        "LEFT JOIN assignment_submissions s "
                        "  ON a.id = s.assignment_id AND s.student_id = ? "
                        "WHERE a.module_code = ? "
                        "ORDER BY a.due_date",
                        (student_id, mc),
                    ).fetchall()

                    assign_list = [dict(a) for a in assignments] if assignments else []
                    graded = [a["grade"] for a in assign_list if a.get("grade") is not None]
                    avg = round(sum(graded) / len(graded), 1) if graded else None

                    results.append({
                        "module_code": mc,
                        "module_name": mod["module_name"],
                        "assignments": assign_list,
                        "average_score": avg,
                    })
        except Exception as e:
            logger.error(f"Error fetching grades by module: {e}")
        return results

    @staticmethod
    def get_degree_progress_summary(student_id):
        """Get degree progress summary for a student.

        Returns dict with credits_earned, credits_required, gpa,
        progress_pct, and requirements list.
        """
        data = {
            "credits_earned": 0,
            "credits_required": 120,
            "gpa": None,
            "progress_pct": 0.0,
            "estimated_graduation": None,
            "requirements": [],
        }
        try:
            with get_connection() as conn:
                # Credits from enrolled/completed modules
                row = conn.execute(
                    "SELECT COALESCE(SUM(m.credits), 0) as earned "
                    "FROM modules m "
                    "INNER JOIN student_modules sm ON m.module_code = sm.module_code "
                    "WHERE sm.student_id = ? AND sm.status IN ('Enrolled', 'Completed')",
                    (student_id,),
                ).fetchone()
                data["credits_earned"] = row["earned"] if row else 0

                # Degree progress record
                # Note: student_degree_progress may store numeric student IDs
                # (e.g. '5') rather than formatted IDs (e.g. 'S12345').
                # Try the original ID first, then strip the prefix and try numeric.
                try:
                    prog = conn.execute(
                        "SELECT sdp.total_credits_earned, sdp.current_gpa, "
                        "sdp.completion_percentage, sdp.expected_graduation_date, "
                        "sdp.program_id "
                        "FROM student_degree_progress sdp "
                        "WHERE sdp.student_id = ?",
                        (student_id,),
                    ).fetchone()

                    if not prog:
                        # Try numeric ID (strip leading letters)
                        numeric_id = ''.join(c for c in student_id if c.isdigit())
                        if numeric_id:
                            prog = conn.execute(
                                "SELECT sdp.total_credits_earned, sdp.current_gpa, "
                                "sdp.completion_percentage, sdp.expected_graduation_date, "
                                "sdp.program_id "
                                "FROM student_degree_progress sdp "
                                "WHERE sdp.student_id = ?",
                                (numeric_id,),
                            ).fetchone()

                    if prog:
                        data["credits_earned"] = prog["total_credits_earned"] or data["credits_earned"]
                        data["gpa"] = prog["current_gpa"]
                        data["estimated_graduation"] = prog["expected_graduation_date"]

                        # Get total_credits_required from degree_programs
                        if prog["program_id"]:
                            dp_row = conn.execute(
                                "SELECT total_credits_required FROM degree_programs "
                                "WHERE program_id = ?",
                                (prog["program_id"],),
                            ).fetchone()
                            if dp_row and dp_row["total_credits_required"]:
                                data["credits_required"] = dp_row["total_credits_required"]
                except Exception:
                    pass

                if data["credits_required"] > 0:
                    data["progress_pct"] = round(
                        (data["credits_earned"] / data["credits_required"]) * 100, 1
                    )

                # GPA fallback
                if data["gpa"] is None:
                    try:
                        gpa_row = conn.execute(
                            "SELECT AVG(CASE "
                            "  WHEN s.grade >= 90 THEN 4.0 "
                            "  WHEN s.grade >= 80 THEN 3.0 "
                            "  WHEN s.grade >= 70 THEN 2.0 "
                            "  WHEN s.grade >= 60 THEN 1.0 "
                            "  ELSE 0.0 END) as gpa "
                            "FROM assignment_submissions s "
                            "WHERE s.student_id = ? AND s.grade IS NOT NULL",
                            (student_id,),
                        ).fetchone()
                        if gpa_row and gpa_row["gpa"] is not None:
                            data["gpa"] = round(gpa_row["gpa"], 2)
                    except Exception:
                        pass

                # Requirement completion
                # Join with degree_requirements to get readable names
                try:
                    numeric_sid = student_id
                    # Try numeric ID for requirement_completion as well
                    numeric_only = ''.join(c for c in student_id if c.isdigit())

                    reqs = conn.execute(
                        "SELECT dr.requirement_name, dr.requirement_type, "
                        "rc.is_completed, dr.credits_required AS credits_needed, "
                        "rc.credits_earned AS credits_completed "
                        "FROM requirement_completion rc "
                        "JOIN degree_requirements dr ON rc.requirement_id = dr.requirement_id "
                        "WHERE rc.student_id = ? OR rc.student_id = ? "
                        "ORDER BY dr.requirement_type, dr.requirement_name",
                        (student_id, numeric_only),
                    ).fetchall()

                    if reqs:
                        req_list = []
                        for r in reqs:
                            req_dict = dict(r)
                            # Map is_completed to a status string
                            req_dict['status'] = (
                                'completed' if req_dict.get('is_completed')
                                else 'in_progress'
                            )
                            req_list.append(req_dict)
                        data["requirements"] = req_list
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error fetching degree progress: {e}")
        return data

    @staticmethod
    def get_financial_summary(student_id):
        """Get financial summary for a student.

        Returns dict with balance, total_charges, total_aid,
        total_scholarships, upcoming_payments, and overdue_payments.
        """
        data = {
            "balance": 0.0,
            "total_charges": 0.0,
            "total_aid": 0.0,
            "total_scholarships": 0.0,
            "upcoming_payments": [],
            "overdue_payments": [],
        }
        try:
            with get_connection() as conn:
                # Finance account
                try:
                    acct = conn.execute(
                        "SELECT balance, total_charges, total_payments "
                        "FROM student_finance_accounts WHERE student_id = ?",
                        (student_id,),
                    ).fetchone()
                    if acct:
                        data["balance"] = acct["balance"] or 0.0
                        data["total_charges"] = acct["total_charges"] or 0.0
                except Exception:
                    pass

                # Financial aid
                try:
                    aid = conn.execute(
                        "SELECT COALESCE(SUM(awarded_amount), 0) as total "
                        "FROM student_financial_aid "
                        "WHERE student_id = ? AND status IN ('approved', 'disbursed')",
                        (student_id,),
                    ).fetchone()
                    data["total_aid"] = aid["total"] if aid else 0.0
                except Exception:
                    pass

                # Scholarships
                try:
                    sch = conn.execute(
                        "SELECT COALESCE(SUM(amount), 0) as total "
                        "FROM student_scholarships "
                        "WHERE student_id = ? AND status = 'active'",
                        (student_id,),
                    ).fetchone()
                    data["total_scholarships"] = sch["total"] if sch else 0.0
                except Exception:
                    pass

                # Upcoming payments (from payment_plans or transactions)
                try:
                    from datetime import datetime

                    today = datetime.now().strftime("%Y-%m-%d")
                    upcoming = conn.execute(
                        "SELECT description, amount, due_date "
                        "FROM payment_schedule "
                        "WHERE student_id = ? AND status = 'pending' "
                        "AND due_date >= ? ORDER BY due_date LIMIT 5",
                        (student_id, today),
                    ).fetchall()
                    data["upcoming_payments"] = [dict(r) for r in upcoming] if upcoming else []
                except Exception:
                    pass

                # Overdue payments
                try:
                    from datetime import datetime

                    today = datetime.now().strftime("%Y-%m-%d")
                    overdue = conn.execute(
                        "SELECT description, amount, due_date "
                        "FROM payment_schedule "
                        "WHERE student_id = ? AND status = 'pending' "
                        "AND due_date < ? ORDER BY due_date",
                        (student_id, today),
                    ).fetchall()
                    data["overdue_payments"] = [dict(r) for r in overdue] if overdue else []
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error fetching financial summary: {e}")
        return data

    @staticmethod
    def simulate_gpa(student_id, hypothetical_grades):
        """Compute projected GPA from current grades + hypothetical grades.

        Args:
            student_id: The student identifier.
            hypothetical_grades: dict mapping module_code -> hypothetical letter grade.

        Returns dict with current_gpa, projected_gpa, and delta.
        """
        grade_points = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
        result = {"current_gpa": None, "projected_gpa": None, "delta": 0.0}

        try:
            with get_connection() as conn:
                # Current grades
                rows = conn.execute(
                    "SELECT a.module_code, AVG(s.grade) as avg_grade "
                    "FROM assignment_submissions s "
                    "JOIN assignments a ON s.assignment_id = a.id "
                    "WHERE s.student_id = ? AND s.grade IS NOT NULL "
                    "GROUP BY a.module_code",
                    (student_id,),
                ).fetchall()

                def score_to_gp(score):
                    if score >= 90:
                        return 4.0
                    elif score >= 80:
                        return 3.0
                    elif score >= 70:
                        return 2.0
                    elif score >= 60:
                        return 1.0
                    return 0.0

                current_gps = []
                projected_gps = []

                for r in rows or []:
                    mc = r["module_code"]
                    gp = score_to_gp(r["avg_grade"])
                    current_gps.append(gp)

                    if mc in hypothetical_grades:
                        hyp = hypothetical_grades[mc]
                        projected_gps.append(grade_points.get(hyp, gp))
                    else:
                        projected_gps.append(gp)

                # Add hypothetical for modules without current grades
                for mc, letter in hypothetical_grades.items():
                    if not any(r["module_code"] == mc for r in (rows or [])):
                        projected_gps.append(grade_points.get(letter, 0.0))

                if current_gps:
                    result["current_gpa"] = round(sum(current_gps) / len(current_gps), 2)

                if projected_gps:
                    result["projected_gpa"] = round(
                        sum(projected_gps) / len(projected_gps), 2
                    )

                if result["current_gpa"] is not None and result["projected_gpa"] is not None:
                    result["delta"] = round(
                        result["projected_gpa"] - result["current_gpa"], 2
                    )

        except Exception as e:
            logger.error(f"Error simulating GPA: {e}")
        return result
