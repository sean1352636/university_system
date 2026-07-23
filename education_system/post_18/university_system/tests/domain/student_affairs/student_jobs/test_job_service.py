"""Behavioral tests for the Student Job Board service (``job_service``).

Six manager classes over the shared ``student_records.db``. The fixture points
``DEFAULT_DB_PATH`` at an empty **temp** DB (never the live app DB), bootstraps
the module's own tables via ``create_tables``, seeds the external ``students`` /
``student_degree_progress`` tables the JOINs need, and stubs the two module-level
seams (``get_auth`` for the "current user" and ``log_activity``).
"""

import sqlite3

import pytest

from education_system.post_18.university_system.core.exceptions import (
    DatabaseError,
    ValidationError,
)
from education_system.post_18.university_system.modules.domain.student_affairs.student_jobs.services import (
    job_service as js,
)
from education_system.post_18.university_system.modules.domain.student_affairs.student_jobs.services.job_service import (
    EmploymentManager,
    JobApplicationManager,
    JobPostingManager,
    PerformanceManager,
    SkillMatchingManager,
    WorkHoursManager,
)

_DB_PATH_ATTR = (
    "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH"
)

# The job tables carry FKs to users(id) and students(student_id); the shared
# connection runs with PRAGMA foreign_keys=ON, so these parent tables must
# exist and the acting user (id=99) must be present.
_EXTERNAL_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT
);
INSERT INTO users (id, username) VALUES (99, 'reviewer');
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    email_address TEXT,
    course TEXT
);
CREATE TABLE student_degree_progress (
    student_id TEXT PRIMARY KEY,
    current_gpa REAL
);
"""


class _FakeAuth:
    def __init__(self, user):
        self._user = user

    def is_logged_in(self):
        return self._user is not None

    def get_current_user(self):
        return self._user


@pytest.fixture()
def board(tmp_path, monkeypatch):
    """Bootstrapped job board on a temp DB with a logged-in reviewer (id=99)."""
    db_path = str(tmp_path / "jobs.db")
    monkeypatch.setattr(_DB_PATH_ATTR, db_path)
    # Silence the activity logger and pin a current user for auth-dependent writes.
    monkeypatch.setattr(js, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(js, "get_auth", lambda: _FakeAuth({"id": 99}))

    JobPostingManager.create_tables()
    conn = sqlite3.connect(db_path)
    conn.executescript(_EXTERNAL_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


def _seed_student(db_path, student_id="S1", gpa=3.4):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO students (student_id, first_name, last_name, email_address, course)"
        " VALUES (?, 'Ann', 'Smith', 'ann@x.test', 'CS')",
        (student_id,),
    )
    conn.execute(
        "INSERT INTO student_degree_progress (student_id, current_gpa) VALUES (?, ?)",
        (student_id, gpa),
    )
    conn.commit()
    conn.close()


def _post_job(**over):
    data = dict(
        employer_name="Library", job_title="Assistant", job_category="admin",
        employment_type="part-time", hourly_rate=12.0,
        job_description="shelving", location="Library",
    )
    data.update(over)
    return JobPostingManager.post_job(**data)


def _raw(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


# ===========================================================================
# JobPostingManager
# ===========================================================================

class TestJobPosting:
    def test_create_tables_creates_all(self, board):
        names = {
            r["name"]
            for r in _raw(board, "SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "campus_job_postings", "campus_job_applications", "student_employment",
            "work_hours_log", "student_skills", "job_skill_requirements",
            "student_job_performance",
        } <= names

    def test_post_job_persists_with_posted_by(self, board):
        job_id = _post_job(hours_per_week=15, total_positions=2)
        assert isinstance(job_id, int)
        row = _raw(board, "SELECT * FROM campus_job_postings WHERE job_id=?", (job_id,))[0]
        assert row["job_title"] == "Assistant"
        assert row["posted_by"] == 99
        assert row["total_positions"] == 2

    def test_post_job_without_login_has_null_poster(self, board, monkeypatch):
        monkeypatch.setattr(js, "get_auth", lambda: _FakeAuth(None))
        job_id = _post_job()
        row = _raw(board, "SELECT posted_by FROM campus_job_postings WHERE job_id=?",
                   (job_id,))[0]
        assert row["posted_by"] is None

    def test_post_job_with_skill_requirements(self, board):
        job_id = _post_job(skill_requirements=[
            {"name": "Python", "required": 1, "proficiency": "intermediate"},
            {"name": "SQL"},  # defaults
        ])
        reqs = _raw(board, "SELECT * FROM job_skill_requirements WHERE job_id=?",
                    (job_id,))
        by_name = {r["skill_name"]: r for r in reqs}
        assert by_name["Python"]["minimum_proficiency"] == "intermediate"
        assert by_name["SQL"]["is_required"] == 1
        assert by_name["SQL"]["minimum_proficiency"] == "beginner"

    def test_get_active_jobs_excludes_inactive(self, board):
        a = _post_job(job_title="Active")
        b = _post_job(job_title="Inactive")
        JobPostingManager.deactivate_job(b)
        titles = {j["job_title"] for j in JobPostingManager.get_active_jobs()}
        assert titles == {"Active"}

    def test_get_active_jobs_filters(self, board):
        _post_job(job_title="A", job_category="admin", employment_type="part-time",
                  hourly_rate=10.0, location="Library")
        _post_job(job_title="B", job_category="tech", employment_type="internship",
                  hourly_rate=20.0, location="Lab", is_work_study=1)

        assert {j["job_title"]
                for j in JobPostingManager.get_active_jobs({"job_category": "tech"})} == {"B"}
        assert {j["job_title"]
                for j in JobPostingManager.get_active_jobs({"employment_type": "internship"})} == {"B"}
        assert {j["job_title"]
                for j in JobPostingManager.get_active_jobs({"is_work_study": 1})} == {"B"}
        assert {j["job_title"]
                for j in JobPostingManager.get_active_jobs({"min_hourly_rate": 15})} == {"B"}
        assert {j["job_title"]
                for j in JobPostingManager.get_active_jobs({"location": "Libr"})} == {"A"}

    def test_get_job_details_includes_counts_and_skills(self, board):
        job_id = _post_job(total_positions=3, skill_requirements=[{"name": "Python"}])
        _seed_student(board, "S1")
        JobApplicationManager.apply_for_job("S1", job_id)
        details = JobPostingManager.get_job_details(job_id)
        assert details["available_positions"] == 3  # filled=0
        assert details["total_applications"] == 1
        assert details["skill_requirements"][0]["skill_name"] == "Python"

    def test_get_job_details_missing_returns_none(self, board):
        assert JobPostingManager.get_job_details(999999) is None

    def test_update_job_changes_allowed_field(self, board):
        job_id = _post_job()
        assert JobPostingManager.update_job(job_id, hourly_rate=18.0) is True
        row = _raw(board, "SELECT hourly_rate FROM campus_job_postings WHERE job_id=?",
                   (job_id,))[0]
        assert row["hourly_rate"] == 18.0

    def test_update_job_ignores_unknown_fields(self, board):
        job_id = _post_job()
        assert JobPostingManager.update_job(job_id, not_a_column="x") is False

    def test_deactivate_job(self, board):
        job_id = _post_job()
        JobPostingManager.deactivate_job(job_id)
        row = _raw(board, "SELECT is_active FROM campus_job_postings WHERE job_id=?",
                   (job_id,))[0]
        assert row["is_active"] == 0

    def test_post_job_raises_database_error_on_sql_failure(self, board):
        conn = sqlite3.connect(board)
        conn.execute("ALTER TABLE campus_job_postings RENAME TO _pg_moved")
        conn.commit()
        conn.close()
        with pytest.raises(DatabaseError):
            _post_job()


# ===========================================================================
# JobApplicationManager
# ===========================================================================

class TestApplications:
    def test_apply_and_list_for_student(self, board):
        _seed_student(board, "S1")
        job_id = _post_job(job_title="Assistant")
        app_id = JobApplicationManager.apply_for_job("S1", job_id, cover_letter="hi")
        assert isinstance(app_id, int)
        apps = JobApplicationManager.get_student_applications("S1")
        assert len(apps) == 1
        assert apps[0]["job_title"] == "Assistant"
        assert apps[0]["status"] == "pending"

    def test_duplicate_application_rejected(self, board):
        _seed_student(board, "S1")
        job_id = _post_job()
        JobApplicationManager.apply_for_job("S1", job_id)
        with pytest.raises(ValidationError, match="Already applied"):
            JobApplicationManager.apply_for_job("S1", job_id)

    def test_apply_to_inactive_job_rejected(self, board):
        _seed_student(board, "S1")
        job_id = _post_job()
        JobPostingManager.deactivate_job(job_id)
        with pytest.raises(ValidationError, match="not active"):
            JobApplicationManager.apply_for_job("S1", job_id)

    def test_apply_when_no_positions_rejected(self, board):
        _seed_student(board, "S1")
        job_id = _post_job(total_positions=1)
        conn = sqlite3.connect(board)
        conn.execute("UPDATE campus_job_postings SET filled_positions=1 WHERE job_id=?",
                     (job_id,))
        conn.commit()
        conn.close()
        with pytest.raises(ValidationError, match="No positions"):
            JobApplicationManager.apply_for_job("S1", job_id)

    def test_get_student_applications_status_filter(self, board):
        _seed_student(board, "S1")
        job_id = _post_job()
        app_id = JobApplicationManager.apply_for_job("S1", job_id)
        JobApplicationManager.update_application_status(app_id, "reviewed")
        assert len(JobApplicationManager.get_student_applications("S1", "reviewed")) == 1
        assert JobApplicationManager.get_student_applications("S1", "pending") == []

    def test_get_job_applications_joins_student(self, board):
        _seed_student(board, "S1", gpa=3.9)
        job_id = _post_job()
        JobApplicationManager.apply_for_job("S1", job_id)
        rows = JobApplicationManager.get_job_applications(job_id)
        assert len(rows) == 1
        assert rows[0]["first_name"] == "Ann"
        assert rows[0]["gpa"] == 3.9
        assert rows[0]["major"] == "CS"

    def test_get_job_applications_status_filter(self, board):
        _seed_student(board, "S1")
        job_id = _post_job()
        app_id = JobApplicationManager.apply_for_job("S1", job_id)
        JobApplicationManager.update_application_status(app_id, "interview")
        assert len(JobApplicationManager.get_job_applications(job_id, "interview")) == 1
        assert JobApplicationManager.get_job_applications(job_id, "offered") == []

    def test_update_application_status_records_reviewer(self, board):
        _seed_student(board, "S1")
        job_id = _post_job()
        app_id = JobApplicationManager.apply_for_job("S1", job_id)
        assert JobApplicationManager.update_application_status(
            app_id, "offered", notes="strong") is True
        row = _raw(board, "SELECT * FROM campus_job_applications WHERE application_id=?",
                   (app_id,))[0]
        assert row["status"] == "offered"
        assert row["notes"] == "strong"
        assert row["reviewed_by"] == 99

    def test_schedule_interview(self, board):
        _seed_student(board, "S1")
        job_id = _post_job()
        app_id = JobApplicationManager.apply_for_job("S1", job_id)
        JobApplicationManager.schedule_interview(app_id, "2026-08-10")
        row = _raw(board, "SELECT status, notes FROM campus_job_applications "
                          "WHERE application_id=?", (app_id,))[0]
        assert row["status"] == "interview"
        assert "2026-08-10" in row["notes"]


# ===========================================================================
# EmploymentManager
# ===========================================================================

class TestEmployment:
    def _hire(self, board, **over):
        _seed_student(board, "S1")
        job_id = _post_job(total_positions=2)
        app_id = JobApplicationManager.apply_for_job("S1", job_id)
        kw = dict(start_date="2026-01-01", hourly_rate=14.0, max_hours_per_week=20,
                  position_title="Aide")
        kw.update(over)
        emp_id = EmploymentManager.hire_student("S1", job_id, app_id, **kw)
        return job_id, app_id, emp_id

    def test_hire_updates_application_and_positions(self, board):
        job_id, app_id, emp_id = self._hire(board)
        assert isinstance(emp_id, int)
        app = _raw(board, "SELECT status FROM campus_job_applications "
                          "WHERE application_id=?", (app_id,))[0]
        assert app["status"] == "accepted"
        job = _raw(board, "SELECT filled_positions FROM campus_job_postings "
                          "WHERE job_id=?", (job_id,))[0]
        assert job["filled_positions"] == 1

    def test_get_student_employment_active_filter(self, board):
        job_id, app_id, emp_id = self._hire(board)
        active = EmploymentManager.get_student_employment("S1")
        assert len(active) == 1
        assert active[0]["job_title"] == "Assistant"
        EmploymentManager.end_employment(emp_id, "2026-06-01")
        assert EmploymentManager.get_student_employment("S1") == []
        assert len(EmploymentManager.get_student_employment("S1", active_only=False)) == 1

    def test_end_employment_decrements_positions(self, board):
        job_id, app_id, emp_id = self._hire(board)
        EmploymentManager.end_employment(emp_id, "2026-06-01", status="terminated")
        job = _raw(board, "SELECT filled_positions FROM campus_job_postings "
                          "WHERE job_id=?", (job_id,))[0]
        assert job["filled_positions"] == 0
        emp = _raw(board, "SELECT * FROM student_employment WHERE employment_id=?",
                   (emp_id,))[0]
        assert emp["employment_status"] == "terminated"
        assert emp["end_date"] == "2026-06-01"

    def test_end_employment_missing_record_still_true(self, board):
        assert EmploymentManager.end_employment(999999, "2026-06-01") is True


# ===========================================================================
# WorkHoursManager
# ===========================================================================

class TestWorkHours:
    def _employ(self, board, *, is_work_study=False, allocation=0.0):
        _seed_student(board, "S1")
        job_id = _post_job()
        app_id = JobApplicationManager.apply_for_job("S1", job_id)
        emp_id = EmploymentManager.hire_student(
            "S1", job_id, app_id, start_date="2026-01-01", hourly_rate=12.0,
            max_hours_per_week=20, position_title="Aide",
            is_work_study=is_work_study, work_study_allocation=allocation)
        return emp_id

    def test_clock_in_requires_active_employment(self, board):
        with pytest.raises(ValidationError, match="not found or not active"):
            WorkHoursManager.clock_in(999999, "S1", "2026-02-01", "09:00")

    def test_clock_in_out_calculates_hours_and_earnings(self, board):
        emp_id = self._employ(board)
        log_id = WorkHoursManager.clock_in(emp_id, "S1", "2026-02-01", "09:00",
                                           task_description="desk")
        assert WorkHoursManager.clock_out(log_id, "12:00",
                                          break_duration_minutes=30) is True
        row = _raw(board, "SELECT * FROM work_hours_log WHERE log_id=?", (log_id,))[0]
        assert row["total_hours"] == 2.5  # 3h - 30min
        assert row["earnings"] == 30.0    # 2.5 * 12
        assert row["work_study_deduction"] == 0.0

    def test_clock_out_missing_record(self, board):
        with pytest.raises(ValidationError, match="record not found"):
            WorkHoursManager.clock_out(999999, "12:00")

    def test_work_study_deduction_capped_by_allocation(self, board):
        emp_id = self._employ(board, is_work_study=True, allocation=20.0)
        log_id = WorkHoursManager.clock_in(emp_id, "S1", "2026-02-01", "09:00")
        WorkHoursManager.clock_out(log_id, "12:00")  # 3h * 12 = 36 earnings
        row = _raw(board, "SELECT work_study_deduction FROM work_hours_log "
                          "WHERE log_id=?", (log_id,))[0]
        assert row["work_study_deduction"] == 20.0  # min(36, allocation 20)

    def test_approve_hours_updates_work_study_used(self, board):
        emp_id = self._employ(board, is_work_study=True, allocation=100.0)
        log_id = WorkHoursManager.clock_in(emp_id, "S1", "2026-02-01", "09:00")
        WorkHoursManager.clock_out(log_id, "12:00")  # deduction 36
        assert WorkHoursManager.approve_hours(log_id) is True
        emp = _raw(board, "SELECT work_study_used FROM student_employment "
                          "WHERE employment_id=?", (emp_id,))[0]
        assert emp["work_study_used"] == 36.0
        log = _raw(board, "SELECT status, approved_by FROM work_hours_log "
                          "WHERE log_id=?", (log_id,))[0]
        assert log["status"] == "approved"
        assert log["approved_by"] == 99

    def test_approve_hours_missing_record(self, board):
        with pytest.raises(ValidationError, match="record not found"):
            WorkHoursManager.approve_hours(999999)

    def test_get_student_hours_with_date_filters(self, board):
        emp_id = self._employ(board)
        for d in ("2026-02-01", "2026-02-05", "2026-02-10"):
            lid = WorkHoursManager.clock_in(emp_id, "S1", d, "09:00")
            WorkHoursManager.clock_out(lid, "10:00")
        all_hours = WorkHoursManager.get_student_hours("S1")
        assert len(all_hours) == 3
        windowed = WorkHoursManager.get_student_hours(
            "S1", start_date="2026-02-02", end_date="2026-02-06")
        assert {h["work_date"] for h in windowed} == {"2026-02-05"}

    def test_weekly_summary_aggregates(self, board):
        emp_id = self._employ(board)
        lid1 = WorkHoursManager.clock_in(emp_id, "S1", "2026-02-02", "09:00")
        WorkHoursManager.clock_out(lid1, "11:00")  # 2h, 24
        lid2 = WorkHoursManager.clock_in(emp_id, "S1", "2026-02-03", "09:00")
        WorkHoursManager.clock_out(lid2, "10:00")  # 1h, 12
        summary = WorkHoursManager.get_weekly_summary("S1", "2026-02-02")
        assert summary["total_shifts"] == 2
        assert summary["total_hours"] == 3.0
        assert summary["total_earnings"] == 36.0
        assert summary["pending_hours"] == 3.0
        assert summary["week_end"] == "2026-02-08"


# ===========================================================================
# SkillMatchingManager
# ===========================================================================

class TestSkillMatching:
    def test_add_and_get_skills(self, board):
        _seed_student(board, "S1")
        sid = SkillMatchingManager.add_student_skill(
            "S1", "Python", skill_category="technical",
            proficiency_level="advanced", years_experience=3)
        assert isinstance(sid, int)
        skills = SkillMatchingManager.get_student_skills("S1")
        assert len(skills) == 1
        assert skills[0]["skill_name"] == "Python"
        assert skills[0]["proficiency_level"] == "advanced"

    def test_add_skill_replaces_duplicate(self, board):
        _seed_student(board, "S1")
        SkillMatchingManager.add_student_skill("S1", "Python",
                                               proficiency_level="beginner")
        SkillMatchingManager.add_student_skill("S1", "Python",
                                               proficiency_level="expert")
        skills = SkillMatchingManager.get_student_skills("S1")
        assert len(skills) == 1
        assert skills[0]["proficiency_level"] == "expert"

    def test_find_matching_jobs_no_skills_returns_empty(self, board):
        _post_job(skill_requirements=[{"name": "Python"}])
        assert SkillMatchingManager.find_matching_jobs("S1") == []

    def test_find_matching_jobs_required_and_preferred(self, board):
        _seed_student(board, "S1")
        job_id = _post_job(skill_requirements=[
            {"name": "Python", "required": 1, "proficiency": "intermediate"},
            {"name": "SQL", "required": 0, "proficiency": "beginner"},
        ])
        SkillMatchingManager.add_student_skill("S1", "Python",
                                               proficiency_level="advanced")
        SkillMatchingManager.add_student_skill("S1", "SQL",
                                               proficiency_level="beginner")
        matches = SkillMatchingManager.find_matching_jobs("S1")
        assert len(matches) == 1
        m = matches[0]
        assert m["job_id"] == job_id
        assert m["match_percentage"] == 100.0
        assert m["required_skills_matched"] == 1
        assert m["preferred_skills_matched"] == 1

    def test_find_matching_jobs_below_threshold_excluded(self, board):
        _seed_student(board, "S1")
        _post_job(skill_requirements=[
            {"name": "Python", "required": 1, "proficiency": "advanced"},
        ])
        # Student has a skill (so not the empty short-circuit) but not the
        # required one, so the required match % is 0 -> excluded.
        SkillMatchingManager.add_student_skill("S1", "Cooking",
                                               proficiency_level="expert")
        assert SkillMatchingManager.find_matching_jobs("S1") == []

    def test_find_matching_jobs_only_preferred_requirements(self, board):
        _seed_student(board, "S1")
        # No required skills -> required_match_pct defaults to 100.
        _post_job(skill_requirements=[
            {"name": "Design", "required": 0, "proficiency": "beginner"},
        ])
        SkillMatchingManager.add_student_skill("S1", "Design",
                                               proficiency_level="advanced")
        matches = SkillMatchingManager.find_matching_jobs("S1")
        assert len(matches) == 1
        assert matches[0]["match_percentage"] == 100.0

    def test_find_matching_jobs_sorted_by_match(self, board):
        _seed_student(board, "S1")
        # Job1: full match. Job2: partial (required met, preferred missing).
        SkillMatchingManager.add_student_skill("S1", "Python",
                                               proficiency_level="expert")
        j_full = _post_job(job_title="Full", skill_requirements=[
            {"name": "Python", "required": 1, "proficiency": "beginner"},
        ])
        j_partial = _post_job(job_title="Partial", skill_requirements=[
            {"name": "Python", "required": 1, "proficiency": "beginner"},
            {"name": "Rust", "required": 0, "proficiency": "beginner"},
        ])
        matches = SkillMatchingManager.find_matching_jobs("S1")
        ids = [m["job_id"] for m in matches]
        assert ids[0] == j_full  # 100% first
        assert set(ids) == {j_full, j_partial}
        assert matches[0]["match_percentage"] >= matches[1]["match_percentage"]

    def test_verify_skill(self, board):
        _seed_student(board, "S1")
        sid = SkillMatchingManager.add_student_skill("S1", "Python")
        assert SkillMatchingManager.verify_skill(sid) is True
        row = _raw(board, "SELECT verified, verified_by FROM student_skills "
                          "WHERE skill_id=?", (sid,))[0]
        assert row["verified"] == 1
        assert row["verified_by"] == 99


# ===========================================================================
# PerformanceManager
# ===========================================================================

class TestPerformance:
    def _employ(self, board):
        _seed_student(board, "S1")
        job_id = _post_job()
        app_id = JobApplicationManager.apply_for_job("S1", job_id)
        return EmploymentManager.hire_student(
            "S1", job_id, app_id, start_date="2026-01-01", hourly_rate=12.0,
            max_hours_per_week=20, position_title="Aide")

    def test_create_review_computes_overall_and_updates_employment(self, board):
        emp_id = self._employ(board)
        review_id = PerformanceManager.create_performance_review(
            emp_id, "S1", "2026-03-01", "2026-01-01", "2026-02-28",
            attendance_rating=4, quality_rating=5, initiative_rating=3,
            teamwork_rating=4, strengths="reliable")
        assert isinstance(review_id, int)
        row = _raw(board, "SELECT * FROM student_job_performance WHERE review_id=?",
                   (review_id,))[0]
        assert row["overall_rating"] == 4.0  # (4+5+3+4)/4
        assert row["reviewer_id"] == 99
        emp = _raw(board, "SELECT performance_rating FROM student_employment "
                          "WHERE employment_id=?", (emp_id,))[0]
        assert emp["performance_rating"] == 4.0

    def test_get_student_reviews(self, board):
        emp_id = self._employ(board)
        PerformanceManager.create_performance_review(
            emp_id, "S1", "2026-03-01", "2026-01-01", "2026-02-28", 4, 4, 4, 4)
        reviews = PerformanceManager.get_student_reviews("S1")
        assert len(reviews) == 1
        assert reviews[0]["employer_name"] == "Library"
        assert reviews[0]["position_title"] == "Aide"

    def test_average_performance(self, board):
        emp_id = self._employ(board)
        PerformanceManager.create_performance_review(
            emp_id, "S1", "2026-03-01", "2026-01-01", "2026-02-28", 4, 4, 4, 4)
        PerformanceManager.create_performance_review(
            emp_id, "S1", "2026-04-01", "2026-03-01", "2026-03-31", 2, 2, 2, 2)
        avg = PerformanceManager.get_average_performance("S1")
        assert avg["total_reviews"] == 2
        assert avg["avg_overall"] == 3.0  # (4.0 + 2.0) / 2
        assert avg["avg_attendance"] == 3.0


# ===========================================================================
# Extra branch coverage
# ===========================================================================

class TestExtraBranches:
    def test_approve_hours_without_work_study_deduction(self, board):
        # Non-work-study employment => deduction stays 0 => the work_study_used
        # UPDATE branch is skipped.
        _seed_student(board, "S1")
        job_id = _post_job()
        app_id = JobApplicationManager.apply_for_job("S1", job_id)
        emp_id = EmploymentManager.hire_student(
            "S1", job_id, app_id, start_date="2026-01-01", hourly_rate=12.0,
            max_hours_per_week=20, position_title="Aide")
        log_id = WorkHoursManager.clock_in(emp_id, "S1", "2026-02-01", "09:00")
        WorkHoursManager.clock_out(log_id, "10:00")
        assert WorkHoursManager.approve_hours(log_id) is True
        emp = _raw(board, "SELECT work_study_used FROM student_employment "
                          "WHERE employment_id=?", (emp_id,))[0]
        assert emp["work_study_used"] == 0.0

    def test_find_matching_jobs_insufficient_proficiency_excluded(self, board):
        # Student has the required skill but below the required proficiency, so
        # it is not counted as matched and the job falls under threshold.
        _seed_student(board, "S1")
        _post_job(skill_requirements=[
            {"name": "Python", "required": 1, "proficiency": "advanced"},
        ])
        SkillMatchingManager.add_student_skill("S1", "Python",
                                               proficiency_level="beginner")
        assert SkillMatchingManager.find_matching_jobs("S1") == []


# ===========================================================================
# DatabaseError wrappers — each mutating method re-raises sqlite errors
# ===========================================================================

def _break_table(db_path, table):
    conn = sqlite3.connect(db_path)
    conn.execute(f"ALTER TABLE {table} RENAME TO _{table}_broken")
    conn.commit()
    conn.close()


class TestDatabaseErrorWrappers:
    @pytest.mark.parametrize("table, action", [
        ("campus_job_postings",
         lambda: JobPostingManager.update_job(1, hourly_rate=9.0)),
        ("campus_job_applications",
         lambda: JobApplicationManager.apply_for_job("S1", 1)),
        ("campus_job_applications",
         lambda: JobApplicationManager.update_application_status(1, "reviewed")),
        ("student_employment",
         lambda: EmploymentManager.hire_student(
             "S1", 1, 1, "2026-01-01", 12.0, 20, "Aide")),
        ("student_employment",
         lambda: EmploymentManager.end_employment(1, "2026-06-01")),
        ("student_employment",
         lambda: WorkHoursManager.clock_in(1, "S1", "2026-02-01", "09:00")),
        ("work_hours_log",
         lambda: WorkHoursManager.clock_out(1, "10:00")),
        ("work_hours_log",
         lambda: WorkHoursManager.approve_hours(1)),
        ("student_skills",
         lambda: SkillMatchingManager.add_student_skill("S1", "Python")),
        ("student_skills",
         lambda: SkillMatchingManager.verify_skill(1)),
        ("student_job_performance",
         lambda: PerformanceManager.create_performance_review(
             1, "S1", "2026-03-01", "2026-01-01", "2026-02-28", 4, 4, 4, 4)),
    ])
    def test_method_wraps_sqlite_error(self, board, table, action):
        _break_table(board, table)
        with pytest.raises(DatabaseError):
            action()

    def test_create_tables_wraps_sqlite_error(self, board, monkeypatch):
        # Force the first CREATE to raise a sqlite error inside create_tables.
        import education_system.post_18.university_system.infrastructure.database.db as dbmod

        real_transaction = dbmod.transaction

        class _Boom:
            def __enter__(self):
                raise sqlite3.OperationalError("disk gone")

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(js, "transaction", lambda *a, **k: _Boom())
        with pytest.raises(DatabaseError):
            JobPostingManager.create_tables()
        # restore not required (monkeypatch), keep real ref alive
        assert real_transaction is dbmod.transaction
