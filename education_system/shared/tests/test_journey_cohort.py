"""Tests for JourneyService.get_cohort_flow (cross-system progression funnel)."""

import sqlite3

import pytest

from education_system.shared.cross_system.journey_service import JourneyService


@pytest.fixture()
def auth_db(tmp_path):
    """A minimal student_journey registry with three journeys and transitions.

    A: primary -> school -> college -> university (full path, active)
    B: primary -> school only (dropped before college, active)
    C: primary only (withdrawn after primary)
    """
    path = tmp_path / "auth.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE student_journey (
            journey_id TEXT PRIMARY KEY,
            primary_pk INTEGER, school_pk INTEGER,
            college_pk INTEGER, university_pk INTEGER,
            primary_student_id TEXT, school_student_id TEXT,
            college_student_id TEXT, university_student_id TEXT,
            legal_first_name TEXT, legal_last_name TEXT, date_of_birth TEXT,
            current_system TEXT, status TEXT, created_at TEXT, updated_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE student_journey_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, journey_id TEXT,
            from_system TEXT, to_system TEXT, reason TEXT,
            actor_user_id INTEGER, occurred_at TEXT, notes TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO student_journey (journey_id, primary_pk, school_pk, "
        "college_pk, university_pk, current_system, status, created_at) "
        "VALUES ('A', 1, 1, 1, 1, 'university', 'active', '2020-09-01')"
    )
    conn.execute(
        "INSERT INTO student_journey (journey_id, primary_pk, school_pk, "
        "current_system, status, created_at) "
        "VALUES ('B', 2, 2, 'secondary', 'active', '2020-09-01')"
    )
    conn.execute(
        "INSERT INTO student_journey (journey_id, primary_pk, "
        "current_system, status, created_at) "
        "VALUES ('C', 3, 'primary', 'withdrawn', '2021-09-01')"
    )
    for jid, frm, to, when in [
        ("A", "primary", "secondary", "2021-09-01"),
        ("A", "secondary", "sixth_form", "2022-09-01"),
        ("A", "sixth_form", "university", "2023-09-01"),
        ("B", "primary", "secondary", "2021-09-01"),
    ]:
        conn.execute(
            "INSERT INTO student_journey_transitions "
            "(journey_id, from_system, to_system, occurred_at) VALUES (?, ?, ?, ?)",
            (jid, frm, to, when),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def svc(auth_db):
    return JourneyService(db_paths={}, auth_db=str(auth_db))


class TestCohortFlow:
    def test_total_journeys(self, svc):
        assert svc.get_cohort_flow()["total_journeys"] == 3

    def test_stage_presence(self, svc):
        flow = svc.get_cohort_flow()
        counts = {s["system"]: s["count"] for s in flow["stage_presence"]}
        assert counts == {"primary": 3, "secondary": 2, "sixth_form": 1, "university": 1}

    def test_continuation_and_dropoff(self, svc):
        cont = {(c["from"], c["to"]): c for c in svc.get_cohort_flow()["continuation"]}
        p2s = cont[("primary", "secondary")]
        assert p2s["from_count"] == 3
        assert p2s["continued"] == 2
        assert p2s["dropped"] == 1
        assert p2s["rate"] == 66.7

        s2c = cont[("secondary", "sixth_form")]
        assert s2c["continued"] == 1
        assert s2c["dropped"] == 1
        assert s2c["rate"] == 50.0

        c2u = cont[("sixth_form", "university")]
        assert c2u["rate"] == 100.0
        assert c2u["dropped"] == 0

    def test_by_status(self, svc):
        assert svc.get_cohort_flow()["by_status"] == {"active": 2, "withdrawn": 1}

    def test_current_distribution(self, svc):
        dist = {d["system"]: d["count"] for d in svc.get_cohort_flow()["current_distribution"]}
        assert dist == {"university": 1, "secondary": 1, "primary": 1}

    def test_transitions_grouped(self, svc):
        trans = {(t["from_system"], t["to_system"]): t["count"]
                 for t in svc.get_cohort_flow()["transitions"]}
        assert trans[("primary", "secondary")] == 2
        assert trans[("secondary", "sixth_form")] == 1
        assert trans[("sixth_form", "university")] == 1

    def test_available_years(self, svc):
        years = svc.get_cohort_flow()["available_years"]
        assert set(years) >= {"2020", "2021", "2022", "2023"}
        # Newest first.
        assert years == sorted(years, reverse=True)

    def test_year_filter(self, svc):
        flow = svc.get_cohort_flow(year="2021")
        # Only journey C was created in 2021.
        assert flow["total_journeys"] == 1
        counts = {s["system"]: s["count"] for s in flow["stage_presence"]}
        assert counts["primary"] == 1
        assert counts["secondary"] == 0
        # Transitions filtered by occurred_at 2021 -> two primary->school moves.
        trans = {(t["from_system"], t["to_system"]): t["count"] for t in flow["transitions"]}
        assert trans == {("primary", "secondary"): 2}


class TestTransitionStudents:
    def test_lists_all_transitions(self, svc):
        rows = svc.get_transition_students()
        assert len(rows) == 4

    def test_filter_by_edge(self, svc):
        rows = svc.get_transition_students(from_system="primary", to_system="secondary")
        assert len(rows) == 2
        assert all(r["from_system"] == "primary" and r["to_system"] == "secondary"
                   for r in rows)

    def test_filter_by_year(self, svc):
        rows = svc.get_transition_students(year="2022")
        assert len(rows) == 1
        assert rows[0]["from_system"] == "secondary"
        assert rows[0]["to_system"] == "sixth_form"

    def test_unknown_name_when_absent(self, svc):
        # The fixture journeys carry no legal name, so names resolve to a placeholder.
        rows = svc.get_transition_students(from_system="sixth_form", to_system="university")
        assert rows[0]["name"] == "(unknown)"
        assert rows[0]["journey_id"] == "A"

    def test_name_resolved_when_present(self, auth_db):
        conn = sqlite3.connect(str(auth_db))
        conn.execute(
            "UPDATE student_journey SET legal_first_name='Noah', "
            "legal_last_name='Campbell' WHERE journey_id='A'"
        )
        conn.commit()
        conn.close()
        svc = JourneyService(db_paths={}, auth_db=str(auth_db))
        rows = svc.get_transition_students(from_system="sixth_form", to_system="university")
        assert len(rows) == 1
        assert rows[0]["name"] == "Noah Campbell"

    def test_no_transitions_table(self, tmp_path):
        path = tmp_path / "auth.db"
        sqlite3.connect(str(path)).close()
        svc = JourneyService(db_paths={}, auth_db=str(path))
        assert svc.get_transition_students() == []


class TestStudentTransitions:
    def _named(self, auth_db):
        conn = sqlite3.connect(str(auth_db))
        conn.execute(
            "UPDATE student_journey SET legal_first_name='Noah', "
            "legal_last_name='Campbell' WHERE journey_id='A'"
        )
        conn.commit()
        conn.close()
        return JourneyService(db_paths={}, auth_db=str(auth_db))

    def test_filters_to_named_student(self, auth_db):
        svc = self._named(auth_db)
        # Journey A has 3 transitions; B/C have other/none and no names.
        moves = svc.get_student_transitions("Noah Campbell")
        assert len(moves) == 3
        assert all(m["name"] == "Noah Campbell" for m in moves)

    def test_case_insensitive(self, auth_db):
        svc = self._named(auth_db)
        assert len(svc.get_student_transitions("noah campbell")) == 3

    def test_blank_name_returns_empty(self, auth_db):
        assert self._named(auth_db).get_student_transitions("  ") == []

    def test_unknown_name_returns_empty(self, auth_db):
        assert self._named(auth_db).get_student_transitions("Nobody Here") == []


class TestCohortFlowDegradation:
    def test_missing_auth_db(self, tmp_path):
        svc = JourneyService(db_paths={}, auth_db=str(tmp_path / "nope.db"))
        flow = svc.get_cohort_flow()
        assert flow["total_journeys"] == 0
        assert flow["stage_presence"] == []

    def test_missing_tables(self, tmp_path):
        path = tmp_path / "auth.db"
        sqlite3.connect(str(path)).close()
        svc = JourneyService(db_paths={}, auth_db=str(path))
        assert svc.get_cohort_flow()["total_journeys"] == 0

    def test_no_transitions_table(self, tmp_path):
        path = tmp_path / "auth.db"
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE student_journey (journey_id TEXT PRIMARY KEY, "
            "primary_pk INTEGER, school_pk INTEGER, college_pk INTEGER, "
            "university_pk INTEGER, current_system TEXT, status TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO student_journey (journey_id, primary_pk, current_system, "
            "status, created_at) VALUES ('A', 1, 'primary', 'active', '2022-01-01')"
        )
        conn.commit()
        conn.close()
        svc = JourneyService(db_paths={}, auth_db=str(path))
        flow = svc.get_cohort_flow()
        assert flow["total_journeys"] == 1
        assert flow["transitions"] == []
