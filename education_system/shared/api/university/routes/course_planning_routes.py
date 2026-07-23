"""Course planning routes: prerequisites, semester plans, planned courses, and sequences."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

course_planning_bp = Blueprint("course_planning", __name__, url_prefix="/api/course-planning")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- prerequisites ----

@course_planning_bp.route("/prerequisites", methods=["GET"])
@token_required
def list_prerequisites():
    course_id = request.args.get("course_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM course_prerequisites" + where + " ORDER BY prerequisite_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM course_prerequisites" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "course_prerequisites", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@course_planning_bp.route("/prerequisites/<int:prerequisite_id>", methods=["GET"])
@token_required
def get_prerequisite(prerequisite_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM course_prerequisites WHERE prerequisite_id = ?", (prerequisite_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"prerequisites {prerequisite_id} not found")
    log_activity("view", "course_prerequisites", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@course_planning_bp.route("/prerequisites", methods=["POST"])
@token_required
def create_prerequisite():
    data = request.get_json(silent=True) or {}
    for field in ["course_id", "prerequisite_course_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO course_prerequisites
               (course_id, prerequisite_course_id, prerequisite_type, minimum_grade, can_be_concurrent, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["course_id"], data["prerequisite_course_id"], data.get("prerequisite_type", ""), data.get("minimum_grade", ""), data.get("can_be_concurrent", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM course_prerequisites WHERE prerequisite_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "course_prerequisites", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- semester-plans ----

@course_planning_bp.route("/semester-plans", methods=["GET"])
@token_required
def list_semester_plans():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM semester_plans WHERE plan_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM semester_plans" + where + " ORDER BY plan_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM semester_plans" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "semester_plans", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@course_planning_bp.route("/semester-plans/<int:plan_id>", methods=["GET"])
@token_required
def get_semester_plan(plan_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM semester_plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"semester-plans {plan_id} not found")
    log_activity("view", "semester_plans", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@course_planning_bp.route("/semester-plans", methods=["POST"])
@token_required
def create_semester_plan():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "plan_name", "program_code"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO semester_plans
               (student_id, plan_name, program_code, start_semester, total_semesters, credits_per_semester, include_summer, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["plan_name"], data["program_code"], data.get("start_semester", ""), data.get("total_semesters", ""), data.get("credits_per_semester", ""), data.get("include_summer", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM semester_plans WHERE plan_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "semester_plans", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- planned-courses ----

@course_planning_bp.route("/planned-courses", methods=["GET"])
@token_required
def list_planned_courses():
    plan_id = request.args.get("plan_id")
    semester_number = request.args.get("semester_number")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if plan_id:
            conditions.append("plan_id = ?")
            params.append(plan_id)
        if semester_number:
            conditions.append("semester_number = ?")
            params.append(semester_number)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM planned_courses" + where + " ORDER BY planned_course_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM planned_courses" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "planned_courses", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@course_planning_bp.route("/planned-courses/<int:planned_course_id>", methods=["GET"])
@token_required
def get_planned_course(planned_course_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM planned_courses WHERE planned_course_id = ?", (planned_course_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"planned-courses {planned_course_id} not found")
    log_activity("view", "planned_courses", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@course_planning_bp.route("/planned-courses", methods=["POST"])
@token_required
def create_planned_course():
    data = request.get_json(silent=True) or {}
    for field in ["plan_id", "course_id", "semester_number"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO planned_courses
               (plan_id, course_id, semester_number, semester_name, is_locked, priority, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["plan_id"], data["course_id"], data["semester_number"], data.get("semester_name", ""), data.get("is_locked", ""), data.get("priority", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM planned_courses WHERE planned_course_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "planned_courses", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- auto-plan generation ----

@course_planning_bp.route("/auto-plan", methods=["POST"])
@token_required
def generate_auto_plan():
    """Automatically generate a semester plan based on degree requirements."""
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "program_code"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    student_id = data["student_id"]
    program_code = data["program_code"]
    start_semester = data.get("start_semester", "Fall 2026")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        # Create the plan
        conn.execute(
            """INSERT INTO semester_plans
               (student_id, plan_name, program_code, start_semester, total_semesters, credits_per_semester, include_summer, status, created_at)
               VALUES (?, ?, ?, ?, 8, 15, 0, 'Draft', ?)""",
            (student_id, f"Auto-Generated Plan - {program_code}", program_code, start_semester, now),
        )
        plan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        # Get student's completed courses
        completed = conn.execute(
            """SELECT module_code as course_id FROM module_grades
               WHERE student_id = ? AND final_grade IS NOT NULL
               AND final_grade NOT IN ('F', 'W', 'I')
               UNION
               SELECT module_code as course_id FROM student_grades
               WHERE student_id = ? AND grade IS NOT NULL
               AND grade NOT IN ('F', 'W', 'I')
               AND assessment_name LIKE '%Final%'""",
            (student_id, student_id),
        ).fetchall()
        completed_ids = {row["course_id"] for row in completed if row["course_id"]}

        # Get required courses for the program
        required_courses = conn.execute(
            "SELECT code as course_id, credits FROM courses WHERE department LIKE ? || '%' ORDER BY code",
            (program_code[:3],),
        ).fetchall()

        # Filter out completed courses and distribute across semesters
        semester_number = 1
        credits_this_semester = 0
        max_credits = 15

        for course in required_courses:
            if course["course_id"] in completed_ids:
                continue

            credits = course["credits"] or 3
            if credits_this_semester + credits > max_credits:
                semester_number += 1
                credits_this_semester = 0

            with transaction() as conn2:
                conn2.execute(
                    """INSERT OR IGNORE INTO planned_courses
                       (plan_id, course_id, semester_number, semester_name, is_locked, priority, notes, added_at)
                       VALUES (?, ?, ?, ?, 0, 0, NULL, ?)""",
                    (plan_id, course["course_id"], semester_number, f"Semester {semester_number}", now),
                )

            credits_this_semester += credits

    with get_connection() as conn:
        plan_row = conn.execute("SELECT * FROM semester_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        courses_rows = conn.execute(
            "SELECT * FROM planned_courses WHERE plan_id = ? ORDER BY semester_number, planned_course_id", (plan_id,)
        ).fetchall()

    log_activity("create", "auto_plan", user=g.current_user.get("sub"))
    return jsonify({
        "plan": _row_to_dict(plan_row),
        "courses": [_row_to_dict(r) for r in courses_rows],
    }), 201


# ---- prerequisite tree ----

@course_planning_bp.route("/prerequisites/tree/<course_id>", methods=["GET"])
@token_required
def get_prerequisite_tree(course_id: str):
    """Build a prerequisite tree for a given course."""
    depth = int(request.args.get("depth", 10))

    with get_connection() as conn:
        # Build prerequisite graph
        all_prereqs = conn.execute("SELECT * FROM course_prerequisites").fetchall()
        graph = {}
        for row in all_prereqs:
            d = _row_to_dict(row)
            graph.setdefault(d["course_id"], []).append(d)

    visited = set()

    def build_tree(cid, current_depth):
        if current_depth > depth or cid in visited:
            return {"course_id": cid, "prerequisites": []}
        visited.add(cid)
        prereqs = graph.get(cid, [])
        children = [build_tree(p["prerequisite_course_id"], current_depth + 1) for p in prereqs]
        return {
            "course_id": cid,
            "prerequisites": children,
            "prerequisite_count": len(children),
            "total_depth": current_depth,
        }

    tree = build_tree(course_id, 0)
    log_activity("view", "prerequisite_tree", user=g.current_user.get("sub"))
    return jsonify(tree)


# ---- prerequisite chain ----

@course_planning_bp.route("/prerequisites/chain/<course_id>", methods=["GET"])
@token_required
def get_prerequisite_chain(course_id: str):
    """Get a level-based prerequisite chain (foundation to advanced)."""
    with get_connection() as conn:
        all_prereqs = conn.execute("SELECT * FROM course_prerequisites").fetchall()
        graph = {}
        for row in all_prereqs:
            d = _row_to_dict(row)
            graph.setdefault(d["course_id"], []).append(d)

    levels = []
    current_level = [course_id]
    visited = set()

    while current_level:
        levels.append(current_level)
        next_level = []
        for cid in current_level:
            if cid in visited:
                continue
            visited.add(cid)
            for prereq in graph.get(cid, []):
                prereq_id = prereq["prerequisite_course_id"]
                if prereq_id not in visited:
                    next_level.append(prereq_id)
        current_level = list(set(next_level))

    # Reverse to show from foundation to advanced
    chain = list(reversed(levels))
    log_activity("view", "prerequisite_chain", user=g.current_user.get("sub"))
    return jsonify({"course_id": course_id, "chain": chain, "total_levels": len(chain)})


# ---- eligibility checking ----

@course_planning_bp.route("/eligibility/<student_id>/<course_id>", methods=["GET"])
@token_required
def check_eligibility(student_id: str, course_id: str):
    """Check if a student is eligible for a course based on prerequisites."""
    with get_connection() as conn:
        # Get student's completed courses
        completed = conn.execute(
            """SELECT module_code as course_id, final_grade as grade FROM module_grades
               WHERE student_id = ? AND final_grade NOT IN ('F', 'W', 'I')
               UNION
               SELECT module_code as course_id, grade FROM student_grades
               WHERE student_id = ? AND grade NOT IN ('F', 'W', 'I')
               AND assessment_name LIKE '%Final%'""",
            (student_id, student_id),
        ).fetchall()
        completed_dict = {row["course_id"]: row["grade"] for row in completed}

        # Get course prerequisites
        prerequisites = conn.execute(
            "SELECT * FROM course_prerequisites WHERE course_id = ?", (course_id,)
        ).fetchall()

    grade_order = {
        "A+": 13, "A": 12, "A-": 11, "B+": 10, "B": 9, "B-": 8,
        "C+": 7, "C": 6, "C-": 5, "D+": 4, "D": 3, "F": 0,
    }

    missing = []
    met = []
    for prereq in prerequisites:
        p = _row_to_dict(prereq)
        prereq_id = p["prerequisite_course_id"]
        min_grade = p.get("minimum_grade") or "D"

        if prereq_id in completed_dict:
            student_grade = completed_dict[prereq_id]
            if grade_order.get(student_grade, 0) >= grade_order.get(min_grade, 0):
                met.append({"course_id": prereq_id, "grade": student_grade, "required_grade": min_grade})
            else:
                missing.append({"course_id": prereq_id, "reason": f"Grade too low ({student_grade} < {min_grade})", "status": "Grade Insufficient"})
        else:
            missing.append({"course_id": prereq_id, "reason": "Not completed", "status": "Not Taken"})

    eligible = len(missing) == 0
    log_activity("view", "eligibility_check", user=g.current_user.get("sub"))
    return jsonify({
        "course_id": course_id,
        "student_id": student_id,
        "eligible": eligible,
        "met_prerequisites": met,
        "missing_prerequisites": missing,
        "total_prerequisites": len(prerequisites),
    })


# ---- schedule conflict detection ----

@course_planning_bp.route("/conflicts/<int:plan_id>", methods=["GET"])
@token_required
def detect_schedule_conflicts(plan_id: int):
    """Detect scheduling conflicts in a semester plan."""
    with get_connection() as conn:
        plan = conn.execute("SELECT * FROM semester_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if not plan:
            raise ValidationError(f"Plan {plan_id} not found")

        planned = conn.execute(
            """SELECT pc.*, c.credits, c.course_name
               FROM planned_courses pc
               LEFT JOIN courses c ON pc.course_id = c.code
               WHERE pc.plan_id = ?
               ORDER BY pc.semester_number""",
            (plan_id,),
        ).fetchall()

        # Build prerequisite graph
        all_prereqs = conn.execute("SELECT * FROM course_prerequisites").fetchall()
        prereq_graph = {}
        for row in all_prereqs:
            d = _row_to_dict(row)
            prereq_graph.setdefault(d["course_id"], []).append(d)

        # Organize courses by semester
        semesters = {}
        for c in planned:
            cd = _row_to_dict(c)
            semesters.setdefault(cd["semester_number"], []).append(cd)

        plan_dict = _row_to_dict(plan)
        max_credits = (plan_dict.get("credits_per_semester") or 15) + 3
        conflicts = []

        for sem_num, courses in semesters.items():
            # Courses in earlier semesters
            previous_course_ids = set()
            for s, cs in semesters.items():
                if s < sem_num:
                    previous_course_ids.update(c2["course_id"] for c2 in cs)

            current_course_ids = {c2["course_id"] for c2 in courses}

            # Prerequisite conflicts
            for course in courses:
                cid = course["course_id"]
                for prereq in prereq_graph.get(cid, []):
                    prereq_id = prereq["prerequisite_course_id"]
                    if prereq_id not in previous_course_ids and prereq_id not in current_course_ids:
                        conflicts.append({
                            "type": "Prerequisite Not Met",
                            "severity": "High",
                            "semester": sem_num,
                            "description": f"{cid} requires {prereq_id} which is not scheduled earlier",
                            "affected_courses": [cid, prereq_id],
                        })

            # Credit overload
            total_credits = sum(c2.get("credits") or 3 for c2 in courses)
            if total_credits > max_credits:
                conflicts.append({
                    "type": "Credit Overload",
                    "severity": "High",
                    "semester": sem_num,
                    "description": f"Semester {sem_num} has {total_credits} credits (max: {max_credits})",
                    "affected_courses": [c2["course_id"] for c2 in courses],
                })

    # Save unresolved conflicts
    for conflict in conflicts:
        with transaction() as conn2:
            existing = conn2.execute(
                """SELECT conflict_id FROM plan_schedule_conflicts
                   WHERE plan_id = ? AND conflict_type = ? AND affected_semester = ? AND is_resolved = 0
                   AND detected_at >= date('now', '-1 day')""",
                (plan_id, conflict["type"], conflict.get("semester", 0)),
            ).fetchone()
            if not existing:
                conn2.execute(
                    """INSERT INTO plan_schedule_conflicts
                       (plan_id, conflict_type, severity, description, affected_courses_json, affected_semester)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (plan_id, conflict["type"], conflict["severity"], conflict["description"],
                     str(conflict.get("affected_courses", [])), conflict.get("semester", 0)),
                )

    log_activity("view", "schedule_conflicts", user=g.current_user.get("sub"))
    return jsonify({"plan_id": plan_id, "conflicts": conflicts, "total": len(conflicts)})


# ---- course recommendations ----

@course_planning_bp.route("/recommendations/<student_id>", methods=["GET"])
@token_required
def get_course_recommendations(student_id: str):
    """Get course recommendations for a student."""
    semester = request.args.get("semester", "")
    limit = int(request.args.get("limit", 10))

    with get_connection() as conn:
        # Get student's completed courses
        completed = conn.execute(
            """SELECT module_code as course_id FROM module_grades
               WHERE student_id = ? AND final_grade NOT IN ('F', 'W', 'I')
               UNION
               SELECT module_code as course_id FROM student_grades
               WHERE student_id = ? AND grade NOT IN ('F', 'W', 'I')
               AND assessment_name LIKE '%Final%'""",
            (student_id, student_id),
        ).fetchall()
        completed_ids = {row["course_id"] for row in completed if row["course_id"]}

        # Get student's program
        student = conn.execute("SELECT course FROM students WHERE student_id = ?", (student_id,)).fetchone()
        program_code = (_row_to_dict(student).get("course") or "")[:3] if student else ""

        # Get eligible courses
        all_courses = conn.execute(
            "SELECT code as course_id, course_name, credits, department FROM courses WHERE department LIKE ? || '%'",
            (program_code,),
        ).fetchall()

        # Get prerequisites
        all_prereqs = conn.execute("SELECT * FROM course_prerequisites").fetchall()
        prereq_graph = {}
        for row in all_prereqs:
            d = _row_to_dict(row)
            prereq_graph.setdefault(d["course_id"], []).append(d)

        recommendations = []
        for course in all_courses:
            cd = _row_to_dict(course)
            cid = cd["course_id"]
            if cid in completed_ids:
                continue

            # Check prerequisites
            prereqs = prereq_graph.get(cid, [])
            all_met = all(p["prerequisite_course_id"] in completed_ids for p in prereqs)
            if not all_met:
                continue

            score = 1.0
            if cd.get("department", "").startswith(program_code):
                score += 0.5
            score += len(prereqs) * 0.1

            recommendations.append({
                "course_id": cid,
                "course_name": cd.get("course_name"),
                "credits": cd.get("credits"),
                "relevance_score": round(score, 2),
                "prerequisites_met": True,
            })

        recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)
        recommendations = recommendations[:limit]

    # Save recommendations
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for rec in recommendations:
        with transaction() as conn2:
            conn2.execute(
                """INSERT INTO course_recommendations
                   (student_id, course_id, recommendation_reason, relevance_score, semester_recommended, prerequisites_met, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (student_id, rec["course_id"], "Eligible based on completed prerequisites", rec["relevance_score"], semester, now),
            )

    log_activity("view", "course_recommendations", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "recommendations": recommendations, "total": len(recommendations)})


# ---- planning analytics ----

@course_planning_bp.route("/analytics/<student_id>", methods=["GET"])
@token_required
def get_planning_analytics(student_id: str):
    """Get comprehensive planning analytics for a student."""
    with get_connection() as conn:
        plan_stats = conn.execute(
            """SELECT COUNT(*) as total_plans,
                      SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_plans
               FROM semester_plans WHERE student_id = ?""",
            (student_id,),
        ).fetchone()

        conflict_stats = conn.execute(
            """SELECT COUNT(*) as total_conflicts,
                      SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) as resolved_conflicts,
                      SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) as high_severity_conflicts
               FROM plan_schedule_conflicts sc
               JOIN semester_plans sp ON sc.plan_id = sp.plan_id
               WHERE sp.student_id = ?""",
            (student_id,),
        ).fetchone()

        rec_stats = conn.execute(
            """SELECT COUNT(*) as total_recommendations,
                      AVG(relevance_score) as avg_relevance_score
               FROM course_recommendations WHERE student_id = ?""",
            (student_id,),
        ).fetchone()

    log_activity("view", "planning_analytics", user=g.current_user.get("sub"))
    return jsonify({
        "student_id": student_id,
        "plans": _row_to_dict(plan_stats),
        "conflicts": _row_to_dict(conflict_stats),
        "recommendations": _row_to_dict(rec_stats),
    })
