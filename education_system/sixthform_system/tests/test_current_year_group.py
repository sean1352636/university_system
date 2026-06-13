"""Tests for deriving a student's current year group from enrolments.

The sixth-form system never stores year group on the student record; it is
derived from the most recent enrolment. These tests cover that selection and
its display label by stubbing list_for_student (the DB-backed lookup).
"""

from education_system.sixthform_system.modules.domain.students.enrolments import (
    enrolments as data,
)


def _enrolment(academic_year, year_group, status="Enrolled"):
    return data.Enrolment(
        enrolment_id=0,
        student_id="SF1",
        academic_year=academic_year,
        year_group=year_group,
        tutor_group=None,
        start_date=None,
        status=status,
        notes=None,
        created_at="",
    )


def _patch(monkeypatch, enrolments):
    # list_for_student returns newest academic year first (as the real query does).
    ordered = sorted(enrolments, key=lambda e: e.academic_year, reverse=True)
    monkeypatch.setattr(data, "list_for_student", lambda _sid: ordered)


class TestCurrentEnrolment:
    def test_none_when_never_enrolled(self, monkeypatch):
        _patch(monkeypatch, [])
        assert data.current_enrolment("SF1") is None
        assert data.current_year_group_label("SF1") is None

    def test_picks_latest_year(self, monkeypatch):
        _patch(monkeypatch, [
            _enrolment("2024/25", 12),
            _enrolment("2025/26", 13),
        ])
        assert data.current_enrolment("SF1").year_group == 13
        assert data.current_year_group_label("SF1") == "Year 13 (2025/26)"

    def test_prefers_active_over_newer_withdrawn(self, monkeypatch):
        # A newer but withdrawn record should not mask the active enrolment.
        _patch(monkeypatch, [
            _enrolment("2025/26", 13, status="Withdrawn"),
            _enrolment("2024/25", 12, status="Enrolled"),
        ])
        current = data.current_enrolment("SF1")
        assert current.year_group == 12
        assert current.status == "Enrolled"
        assert data.current_year_group_label("SF1") == "Year 12 (2024/25)"

    def test_label_annotates_inactive_status(self, monkeypatch):
        # If there is no active enrolment, the latest is shown with its status.
        _patch(monkeypatch, [_enrolment("2025/26", 13, status="Completed")])
        assert data.current_year_group_label("SF1") == "Year 13 (2025/26) — Completed"
