"""Tests for the course-planning PlanningService.

Focuses on the self-contained logic: plan CRUD, prerequisite-graph traversal
(tree / chain / transitive closure), topological sort, semester arithmetic,
grade comparison, course sequences and conflict records. Paths that depend on
the full course catalog / grade tables (auto-plan, eligibility, recommend) are
out of scope here.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)


def _add_prereq(course_id, prereq_id, ptype="Required", min_grade="D"):
    """Insert a row directly into course_prerequisites (temp DB via patched path)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO course_prerequisites "
            "(course_id, prerequisite_course_id, prerequisite_type, minimum_grade) "
            "VALUES (?, ?, ?, ?)",
            (course_id, prereq_id, ptype, min_grade),
        )
        conn.commit()


# ── Plan CRUD ────────────────────────────────────────────────────────

class TestPlanCrud:
    def test_create_plan_returns_id(self, planning_service):
        pid = planning_service.create_semester_plan("S12345", "My Plan")
        assert isinstance(pid, int) and pid > 0

    def test_get_plan_shape(self, planning_service):
        pid = planning_service.create_semester_plan(
            "S12345", "Plan A", program_code="CS", start_semester="Fall 2026"
        )
        data = planning_service.get_semester_plan(pid)
        assert data["plan"]["plan_name"] == "Plan A"
        assert data["total_courses"] == 0
        assert data["semesters"] == {}

    def test_get_missing_plan_returns_none(self, planning_service):
        assert planning_service.get_semester_plan(99999) is None

    def test_add_course_and_group_by_semester(self, planning_service):
        pid = planning_service.create_semester_plan("S12345", "Plan B")
        planning_service.add_course_to_plan(pid, "CIS0001", 1, "Fall 2026")
        planning_service.add_course_to_plan(pid, "CIS0002", 2, "Spring 2027")
        data = planning_service.get_semester_plan(pid)
        assert data["total_courses"] == 2
        assert set(data["semesters"].keys()) == {1, 2}

    def test_add_course_to_missing_plan_raises(self, planning_service):
        with pytest.raises(ValueError):
            planning_service.add_course_to_plan(99999, "CIS0001", 1, "Fall 2026")

    def test_get_student_plans_orders_and_filters(self, planning_service):
        planning_service.create_semester_plan("S12345", "P1")
        planning_service.create_semester_plan("S12345", "P2")
        planning_service.create_semester_plan("OTHER", "P3")
        plans = planning_service.get_student_plans("S12345")
        assert len(plans) == 2
        assert {p["plan_name"] for p in plans} == {"P1", "P2"}


# ── Prerequisite graph ───────────────────────────────────────────────

class TestPrerequisiteGraph:
    def test_build_graph_indexes_by_course(self, planning_service):
        _add_prereq("CS201", "CS101")
        graph = planning_service._build_prerequisite_graph()
        assert "CS201" in graph
        assert graph["CS201"][0]["prerequisite_course_id"] == "CS101"

    def test_tree_captures_nested_prerequisites(self, planning_service):
        _add_prereq("CS301", "CS201")
        _add_prereq("CS201", "CS101")
        tree = planning_service.build_prerequisite_tree("CS301")
        assert tree["course_id"] == "CS301"
        child = tree["prerequisites"][0]
        assert child["course_id"] == "CS201"
        assert child["prerequisites"][0]["course_id"] == "CS101"

    def test_get_all_prerequisites_is_transitive(self, planning_service):
        _add_prereq("CS301", "CS201")
        _add_prereq("CS201", "CS101")
        allp = set(planning_service.get_all_prerequisites("CS301"))
        assert allp == {"CS201", "CS101"}

    def test_no_prerequisites_returns_empty(self, planning_service):
        assert planning_service.get_all_prerequisites("STANDALONE") == []

    def test_visualize_chain_orders_foundation_first(self, planning_service):
        _add_prereq("CS301", "CS201")
        _add_prereq("CS201", "CS101")
        levels = planning_service.visualize_prerequisite_chain("CS301")
        # Deepest foundation appears first, the target course last.
        assert levels[0] == ["CS101"]
        assert levels[-1] == ["CS301"]


# ── Topological sort ─────────────────────────────────────────────────

class TestTopologicalSort:
    def test_orders_prereqs_before_dependents(self, planning_service):
        graph = {
            "B": [{"prerequisite_course_id": "A"}],
            "C": [{"prerequisite_course_id": "B"}],
        }
        order = planning_service._topological_sort(["C", "B", "A"], graph)
        assert order.index("A") < order.index("B") < order.index("C")

    def test_cycle_still_returns_all_courses(self, planning_service):
        graph = {
            "X": [{"prerequisite_course_id": "Y"}],
            "Y": [{"prerequisite_course_id": "X"}],
        }
        order = planning_service._topological_sort(["X", "Y"], graph)
        assert set(order) == {"X", "Y"}

    def test_external_prereqs_ignored(self, planning_service):
        # A prereq not in the input list must not create an in-degree.
        graph = {"B": [{"prerequisite_course_id": "NOT_IN_LIST"}]}
        order = planning_service._topological_sort(["B"], graph)
        assert order == ["B"]


# ── Semester arithmetic ──────────────────────────────────────────────

class TestSemesterMath:
    @pytest.mark.parametrize(
        "current,expected",
        [
            ("Fall 2026", "Spring 2027"),
            ("Spring 2027", "Fall 2027"),
            ("Summer 2027", "Fall 2027"),
        ],
    )
    def test_next_semester(self, planning_service, current, expected):
        assert planning_service._get_next_semester(current) == expected

    def test_calculate_semester_info_advances_years(self, planning_service):
        # Characterisation: this method floors the year offset over a 2-season
        # cycle, so from a Fall start the paired Spring lands in the SAME
        # calendar year (Spring 2026), then the next Fall rolls over. NB this
        # disagrees with _get_next_semester, which maps Fall 2026 -> Spring
        # 2027; the two semester models in this class are not consistent.
        assert planning_service._calculate_semester_info("Fall 2026", 1)["full_name"] == "Fall 2026"
        assert planning_service._calculate_semester_info("Fall 2026", 2)["full_name"] == "Spring 2026"
        assert planning_service._calculate_semester_info("Fall 2026", 3)["full_name"] == "Fall 2027"


# ── Grade comparison ─────────────────────────────────────────────────

class TestCompareGrades:
    def test_higher_grade_wins(self, planning_service):
        assert planning_service._compare_grades("A", "B") == 1
        assert planning_service._compare_grades("C", "B") == -1

    def test_equal_grades(self, planning_service):
        assert planning_service._compare_grades("B+", "B+") == 0

    def test_unknown_grade_treated_as_zero(self, planning_service):
        # Unknown grades map to 0, same as F.
        assert planning_service._compare_grades("???", "F") == 0
        assert planning_service._compare_grades("A", "???") == 1


# ── Course sequences ─────────────────────────────────────────────────

class TestCourseSequences:
    def test_create_and_fetch_by_program(self, planning_service):
        planning_service.create_course_sequence("Core Track", "CS", ["CS101", "CS201"])
        seqs = planning_service.get_recommended_sequences("CS")
        assert len(seqs) == 1
        assert seqs[0]["sequence_name"] == "Core Track"

    def test_fetch_unknown_program_is_empty(self, planning_service):
        assert planning_service.get_recommended_sequences("NOPE") == []


# ── Conflict records ─────────────────────────────────────────────────

class TestConflicts:
    def _seed_conflict(self, planning_service, plan_id):
        planning_service._save_conflict_record(
            plan_id,
            {
                "type": "Credit Overload",
                "severity": "High",
                "description": "too many credits",
                "affected_courses": ["CS101"],
                "semester": 1,
                "suggestions": ["drop one"],
            },
        )

    def test_save_and_get_conflicts(self, planning_service):
        pid = planning_service.create_semester_plan("S12345", "Plan")
        self._seed_conflict(planning_service, pid)
        conflicts = planning_service.get_plan_conflicts(pid)
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "Credit Overload"

    def test_save_is_deduplicated(self, planning_service):
        pid = planning_service.create_semester_plan("S12345", "Plan")
        self._seed_conflict(planning_service, pid)
        self._seed_conflict(planning_service, pid)  # same type/semester/day
        assert len(planning_service.get_plan_conflicts(pid)) == 1

    def test_resolve_hides_conflict(self, planning_service):
        pid = planning_service.create_semester_plan("S12345", "Plan")
        self._seed_conflict(planning_service, pid)
        cid = planning_service.get_plan_conflicts(pid)[0]["conflict_id"]
        assert planning_service.resolve_conflict(cid) is True
        assert planning_service.get_plan_conflicts(pid) == []
