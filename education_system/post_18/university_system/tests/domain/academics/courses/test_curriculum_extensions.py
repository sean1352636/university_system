"""Unit tests for the course-management *curriculum extensions* CLI.

Covers the schema bootstrap, the DB-constrained pickers, and the data flows of
all ten CLI features added in ``services/course_management/curriculum_extensions``.
The autouse ``_isolate_db`` fixture (university conftest) redirects
``get_connection()`` to a throwaway copy of the template DB, so every test runs
against its own database.

Input-driven commands are exercised by monkeypatching ``builtins.input`` with a
scripted sequence of answers, then asserting on the resulting DB state.
"""

import pytest
from unittest.mock import MagicMock, patch

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.academics.services.course_management import (
    curriculum_extensions as ce,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _suppress_activity_logger():
    """Stop the activity-logger decorators from touching the DB / threads."""
    with patch(
        "education_system.post_18.university_system.modules.shared.utils."
        "simple_activity_logger.module_api.logger"
    ) as mock_logger:
        mock_logger.log_activity = MagicMock()
        yield


@pytest.fixture
def auth():
    """A logged-in user with full course-management permission."""
    class _Auth:
        current_user = {"username": "tester"}

        def check_permission(self, _perm):
            return True
    return _Auth()


@pytest.fixture
def view_only_auth():
    class _Auth:
        current_user = {"username": "viewer"}

        def check_permission(self, perm):
            return perm == "view_courses"
    return _Auth()


@pytest.fixture
def seed():
    """Create the extension schema, course alias columns, two courses, and a
    waitlist table in the isolated DB. Returns the ``ce`` module for brevity."""
    assert ce.ensure_extension_schema()
    conn = get_connection()
    cur = conn.cursor()
    # The production DB carries legacy `code`/`name` alias columns that the
    # service SQL COALESCEs over; mirror them here.
    cur.execute("PRAGMA table_info(courses)")
    cols = {r[1] for r in cur.fetchall()}
    if "code" not in cols:
        cur.execute("ALTER TABLE courses ADD COLUMN code TEXT")
    if "name" not in cols:
        cur.execute("ALTER TABLE courses ADD COLUMN name TEXT")
    for code, cname, mx, cur_en in (("CS", "Computer Science", 30, 29),
                                    ("MA", "Mathematics", 30, 0)):
        cur.execute(
            "INSERT INTO courses (course_code, course_name, code, name, "
            "max_enrollment, current_enrollment, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            (code, cname, code, cname, mx, cur_en))
    cur.execute(
        "CREATE TABLE IF NOT EXISTS course_waitlist ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, course_id TEXT, student_id TEXT, "
        "position INTEGER, added_at TEXT, status TEXT)")
    conn.commit()
    conn.close()
    return ce


def feed(monkeypatch, answers):
    """Patch ``input`` to return each value in ``answers`` in turn."""
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(it))


def query(sql, params=()):
    """Run a query and return rows as plain tuples (get_connection uses Row)."""
    conn = get_connection()
    try:
        return [tuple(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def make_term(name="Fall 2026"):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO academic_terms (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def make_section(term_id, code="CS", section="001", enrolled=0):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO course_sections (course_code, term_id, section_number, "
            "capacity, enrolled, created_at, updated_at) "
            "VALUES (?, ?, ?, 30, ?, datetime('now'), datetime('now'))",
            (code, term_id, section, enrolled))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_creates_all_tables(self, seed):
        names = {r[0] for r in query(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        expected = {
            "academic_terms", "course_sections", "course_corequisites_ext",
            "course_restrictions", "course_materials", "course_learning_outcomes",
            "outcome_program_mappings", "course_approvals",
            "course_approval_history", "section_meetings", "course_crosslistings",
            "course_grading_schemes", "course_assessment_components", "waitlist_rules",
        }
        assert expected <= names

    def test_idempotent(self, seed):
        # Running twice more must not raise or duplicate.
        assert ce.ensure_extension_schema()
        assert ce.ensure_extension_schema()

    def test_does_not_clobber_legacy_corequisites(self):
        # A legacy table keyed by course_id must survive schema bootstrap.
        conn = get_connection()
        conn.execute("CREATE TABLE course_corequisites ("
                     "corequisite_id INTEGER PRIMARY KEY, course_id TEXT)")
        conn.commit()
        conn.close()
        assert ce.ensure_extension_schema()
        cols = {r[1] for r in query("PRAGMA table_info(course_corequisites)")}
        assert "course_id" in cols and "course_code" not in cols


# ---------------------------------------------------------------------------
# DB-constrained pickers
# ---------------------------------------------------------------------------

class TestPickers:
    def test_pick_course_rejects_unknown_then_accepts(self, seed, monkeypatch):
        feed(monkeypatch, ["ZZZ", "cs"])  # case-insensitive match
        conn = get_connection()
        try:
            assert ce._pick_course(conn.cursor()) == "CS"
        finally:
            conn.close()

    def test_pick_course_blank_cancels(self, seed, monkeypatch):
        feed(monkeypatch, [""])
        conn = get_connection()
        try:
            assert ce._pick_course(conn.cursor()) is None
        finally:
            conn.close()

    def test_pick_term_validates(self, seed, monkeypatch):
        tid = make_term()
        feed(monkeypatch, ["999", str(tid)])
        conn = get_connection()
        try:
            assert ce._pick_term(conn.cursor()) == tid
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 1. Terms & sections
# ---------------------------------------------------------------------------

class TestTermsAndSections:
    def test_add_term_persists(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["Spring 2027", "Semester", "2026-27", "", "", "Open"])
        ce._add_term(auth)
        rows = query("SELECT name, status FROM academic_terms WHERE name=?",
                     ("Spring 2027",))
        assert rows and rows[0][1] == "Open"

    def test_add_term_requires_name(self, seed, auth, monkeypatch):
        feed(monkeypatch, [""])
        ce._add_term(auth)
        assert query("SELECT COUNT(*) FROM academic_terms")[0][0] == 0

    def test_add_term_duplicate_handled(self, seed, auth, monkeypatch):
        make_term("Fall 2026")
        feed(monkeypatch, ["Fall 2026", "Semester", "", "", "", "Planned"])
        ce._add_term(auth)  # must not raise
        assert query("SELECT COUNT(*) FROM academic_terms WHERE name=?",
                     ("Fall 2026",))[0][0] == 1

    def test_delete_term_cascades_sections(self, seed, auth, monkeypatch):
        tid = make_term()
        make_section(tid)
        feed(monkeypatch, [str(tid), "y"])
        ce._delete_term(auth)
        assert query("SELECT COUNT(*) FROM academic_terms")[0][0] == 0
        assert query("SELECT COUNT(*) FROM course_sections")[0][0] == 0

    def test_add_section_persists(self, seed, auth, monkeypatch):
        tid = make_term()
        # _pick_course, _pick_term, section#, instructor, mode, location, cap, enrolled, status
        feed(monkeypatch, ["CS", str(tid), "001", "Dr Smith", "Online", "Room A",
                           "25", "0", "Open"])
        ce._add_section(auth)
        rows = query("SELECT course_code, capacity, delivery_mode FROM course_sections")
        assert rows == [("CS", 25, "Online")]

    def test_add_section_duplicate_handled(self, seed, auth, monkeypatch):
        tid = make_term()
        make_section(tid, "CS", "001")
        feed(monkeypatch, ["CS", str(tid), "001", "", "In Person", "", "30", "0", "Open"])
        ce._add_section(auth)  # UNIQUE clash -> friendly, no crash
        assert query("SELECT COUNT(*) FROM course_sections")[0][0] == 1


# ---------------------------------------------------------------------------
# 2. Co-requisites & restrictions
# ---------------------------------------------------------------------------

class TestCorequisitesAndRestrictions:
    def test_add_coreq(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["MA", "take together"])
        ce._add_coreq(auth, "CS")
        assert query("SELECT corequisite_code FROM course_corequisites_ext "
                     "WHERE course_code=?", ("CS",)) == [("MA",)]

    def test_self_coreq_rejected(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["CS"])
        ce._add_coreq(auth, "CS")
        assert query("SELECT COUNT(*) FROM course_corequisites_ext")[0][0] == 0

    def test_duplicate_coreq_ignored(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["MA", ""])
        ce._add_coreq(auth, "CS")
        feed(monkeypatch, ["MA", ""])
        ce._add_coreq(auth, "CS")  # UNIQUE -> handled
        assert query("SELECT COUNT(*) FROM course_corequisites_ext")[0][0] == 1

    def test_add_restriction(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["Major", "Computer Science", "5", "y"])
        ce._add_restriction(auth, "CS")
        rows = query("SELECT restriction_type, reserved_seats, active "
                     "FROM course_restrictions WHERE course_code=?", ("CS",))
        assert rows == [("Major", 5, 1)]


# ---------------------------------------------------------------------------
# 3. Materials
# ---------------------------------------------------------------------------

class TestMaterials:
    def test_add_material(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["Textbook", "Intro to CS", "Author X", "12345",
                           "3rd", "http://x", "49.99", "y"])
        ce._add_material(auth, "CS")
        rows = query("SELECT title, cost, required FROM course_materials "
                     "WHERE course_code=?", ("CS",))
        assert rows[0][0] == "Intro to CS"
        assert abs(rows[0][1] - 49.99) < 0.001 and rows[0][2] == 1

    def test_material_requires_title(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["Textbook", ""])
        ce._add_material(auth, "CS")
        assert query("SELECT COUNT(*) FROM course_materials")[0][0] == 0


# ---------------------------------------------------------------------------
# 4. Learning outcomes & mappings
# ---------------------------------------------------------------------------

class TestOutcomes:
    def _add_outcome(self, auth, monkeypatch, code="CS"):
        feed(monkeypatch, ["CLO1", "Understand recursion"])
        ce._add_outcome(auth, code)
        return query("SELECT id FROM course_learning_outcomes")[0][0]

    def test_add_outcome(self, seed, auth, monkeypatch):
        oid = self._add_outcome(auth, monkeypatch)
        assert oid

    def test_remove_outcome_cascades_mappings(self, seed, auth, monkeypatch):
        oid = self._add_outcome(auth, monkeypatch)
        conn = get_connection()
        conn.execute("INSERT INTO outcome_program_mappings (outcome_id, "
                     "standard_type, standard_code) VALUES (?, 'Program Outcome', 'PO1')",
                     (oid,))
        conn.commit()
        conn.close()
        # _remove_outcome lists outcomes then prompts for the ID.
        feed(monkeypatch, [str(oid)])
        ce._remove_outcome(auth, "CS")
        assert query("SELECT COUNT(*) FROM course_learning_outcomes")[0][0] == 0
        assert query("SELECT COUNT(*) FROM outcome_program_mappings")[0][0] == 0


# ---------------------------------------------------------------------------
# 5. Approvals
# ---------------------------------------------------------------------------

class TestApprovals:
    def test_transition_creates_row_and_history(self, seed, auth, monkeypatch):
        # _pick_course, target selection (1 = Submitted), comment
        feed(monkeypatch, ["CS", "1", "ready for review"])
        ce._transition_approval(auth)
        appr = query("SELECT stage, submitted_by FROM course_approvals "
                     "WHERE course_code=?", ("CS",))
        assert appr == [("Submitted", "tester")]
        hist = query("SELECT from_stage, to_stage FROM course_approval_history "
                     "WHERE course_code=?", ("CS",))
        assert hist == [("Draft", "Submitted")]

    def test_reject_requires_comment(self, seed, auth, monkeypatch):
        # Move to Under Review first.
        conn = get_connection()
        conn.execute("INSERT INTO course_approvals (course_code, stage) "
                     "VALUES ('CS', 'Under Review')")
        conn.commit()
        conn.close()
        # targets from Under Review = [Approved, Rejected]; pick 2 (Rejected), blank comment
        feed(monkeypatch, ["CS", "2", ""])
        ce._transition_approval(auth)
        # Stage must stay 'Under Review' because the reject was refused.
        assert query("SELECT stage FROM course_approvals WHERE course_code=?",
                     ("CS",)) == [("Under Review",)]


# ---------------------------------------------------------------------------
# 6. Timetable meetings
# ---------------------------------------------------------------------------

class TestTimetable:
    def test_add_meeting(self, seed, auth, monkeypatch):
        tid = make_term()
        sid = make_section(tid)
        feed(monkeypatch, [str(sid), "Monday", "09:00", "10:30", "Room B"])
        ce._add_meeting(auth, tid)
        rows = query("SELECT day_of_week, start_time, end_time FROM section_meetings "
                     "WHERE section_id=?", (sid,))
        assert rows == [("Monday", "09:00", "10:30")]

    def test_add_meeting_rejects_bad_time_order(self, seed, auth, monkeypatch):
        tid = make_term()
        sid = make_section(tid)
        feed(monkeypatch, [str(sid), "Monday", "11:00", "10:00", "Room B"])
        ce._add_meeting(auth, tid)
        assert query("SELECT COUNT(*) FROM section_meetings")[0][0] == 0


# ---------------------------------------------------------------------------
# 7. Term rollover
# ---------------------------------------------------------------------------

class TestRollover:
    def test_rollover_copies_sections_and_meetings(self, seed, auth, monkeypatch):
        src = make_term("Fall 2026")
        dst = make_term("Spring 2027")
        sid = make_section(src, "CS", "001", enrolled=12)
        conn = get_connection()
        conn.execute("INSERT INTO section_meetings (section_id, day_of_week, "
                     "start_time, end_time, location) VALUES (?, 'Monday', "
                     "'09:00', '10:00', 'R1')", (sid,))
        conn.commit()
        conn.close()
        # src, dst, reset=y, copy meetings=y, skip existing=y
        feed(monkeypatch, [str(src), str(dst), "y", "y", "y"])
        ce.term_rollover(auth)
        new = query("SELECT enrolled FROM course_sections WHERE term_id=?", (dst,))
        assert new == [(0,)]  # enrolment reset
        assert query("SELECT COUNT(*) FROM section_meetings")[0][0] == 2  # carried forward

    def test_rollover_skips_existing(self, seed, auth, monkeypatch):
        src = make_term("Fall 2026")
        dst = make_term("Spring 2027")
        make_section(src, "CS", "001")
        make_section(dst, "CS", "001")  # already present in target
        feed(monkeypatch, [str(src), str(dst), "y", "n", "y"])
        ce.term_rollover(auth)
        # Still exactly one CS-001 in the target term.
        assert query("SELECT COUNT(*) FROM course_sections WHERE term_id=? "
                     "AND section_number='001'", (dst,))[0][0] == 1


# ---------------------------------------------------------------------------
# 8. Cross-listing
# ---------------------------------------------------------------------------

class TestCrosslisting:
    def test_symmetric_link_mirrored(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["MA", "Cross-listed", "same class"])
        ce._add_crosslisting(auth, "CS")
        assert query("SELECT COUNT(*) FROM course_crosslistings "
                     "WHERE course_code='CS' AND related_code='MA'")[0][0] == 1
        assert query("SELECT COUNT(*) FROM course_crosslistings "
                     "WHERE course_code='MA' AND related_code='CS'")[0][0] == 1

    def test_transfer_equivalent_not_mirrored(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["MA", "Transfer Equivalent", ""])
        ce._add_crosslisting(auth, "CS")
        assert query("SELECT COUNT(*) FROM course_crosslistings "
                     "WHERE course_code='MA'")[0][0] == 0

    def test_remove_symmetric_removes_both(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["MA", "Cross-listed", ""])
        ce._add_crosslisting(auth, "CS")
        link_id = query("SELECT id FROM course_crosslistings "
                        "WHERE course_code='CS'")[0][0]
        feed(monkeypatch, [str(link_id)])
        ce._remove_crosslisting(auth, "CS")
        assert query("SELECT COUNT(*) FROM course_crosslistings")[0][0] == 0


# ---------------------------------------------------------------------------
# 9. Grading
# ---------------------------------------------------------------------------

class TestGrading:
    def test_set_scheme_upserts(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["Percentage", "60"])
        ce._set_scheme(auth, "CS")
        feed(monkeypatch, ["Letter", "40"])
        ce._set_scheme(auth, "CS")
        rows = query("SELECT scheme_type, pass_mark FROM course_grading_schemes "
                     "WHERE course_code=?", ("CS",))
        assert rows == [("Letter", 40.0)]  # one row, updated in place

    def test_add_component(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["Final Exam", "50", "closed book"])
        ce._add_component(auth, "CS")
        rows = query("SELECT name, weight FROM course_assessment_components "
                     "WHERE course_code=?", ("CS",))
        assert rows == [("Final Exam", 50.0)]

    def test_component_requires_name(self, seed, auth, monkeypatch):
        feed(monkeypatch, [""])
        ce._add_component(auth, "CS")
        assert query("SELECT COUNT(*) FROM course_assessment_components")[0][0] == 0


# ---------------------------------------------------------------------------
# 10. Waitlist automation
# ---------------------------------------------------------------------------

class TestWaitlist:
    def _add_waiters(self, statuses):
        conn = get_connection()
        cur = conn.cursor()
        for i, status in enumerate(statuses, start=1):
            cur.execute("INSERT INTO course_waitlist (course_id, student_id, "
                        "position, added_at, status) VALUES ('CS', ?, ?, ?, ?)",
                        (f"S{i}", i, f"2026-01-0{i}", status))
        conn.commit()
        conn.close()

    def test_rule_upserts(self, seed, auth, monkeypatch):
        feed(monkeypatch, ["y", "FIFO", "y", "2", "y"])
        ce._set_waitlist_rule(auth, "CS")
        feed(monkeypatch, ["n", "Priority", "n", "0", "y"])
        ce._set_waitlist_rule(auth, "CS")
        rows = query("SELECT auto_promote, promotion_order, max_auto "
                     "FROM waitlist_rules WHERE course_code=?", ("CS",))
        assert rows == [(0, "Priority", 0)]

    def test_candidates_exclude_done(self, seed):
        self._add_waiters(["Waiting", "Waiting", "Promoted"])
        conn = get_connection()
        try:
            cands = ce._waitlist_candidates(conn.cursor(), "CS")
        finally:
            conn.close()
        assert [c[1] for c in cands] == ["S1", "S2"]

    def test_run_promotion_respects_free_seats(self, seed, auth, monkeypatch):
        # CS has max 30 / current 29 -> exactly 1 free seat.
        self._add_waiters(["Waiting", "Waiting"])
        feed(monkeypatch, ["y"])  # confirm promotion
        ce._promotion_action("CS", commit=True, auth=auth)
        promoted = query("SELECT student_id FROM course_waitlist "
                         "WHERE status='Promoted'")
        assert promoted == [("S1",)]  # only one seat -> only first promoted
        # Enrolment incremented by exactly one.
        assert query("SELECT current_enrollment FROM courses "
                     "WHERE course_code='CS'")[0][0] == 30

    def test_preview_does_not_mutate(self, seed):
        self._add_waiters(["Waiting", "Waiting"])
        ce._promotion_action("CS", commit=False)
        assert query("SELECT COUNT(*) FROM course_waitlist "
                     "WHERE status='Promoted'")[0][0] == 0


# ---------------------------------------------------------------------------
# Permission gating
# ---------------------------------------------------------------------------

class TestPermissions:
    def test_can_edit_true_for_manage(self, auth):
        assert ce._can_edit(auth) is True

    def test_can_edit_false_for_view_only(self, view_only_auth):
        assert ce._can_edit(view_only_auth) is False

    def test_term_rollover_blocked_for_view_only(self, seed, view_only_auth, monkeypatch):
        src = make_term("Fall 2026")
        dst = make_term("Spring 2027")
        make_section(src, "CS", "001")
        # Should bail on the permission check before reading any input.
        ce.term_rollover(view_only_auth)
        assert query("SELECT COUNT(*) FROM course_sections WHERE term_id=?",
                     (dst,))[0][0] == 0
